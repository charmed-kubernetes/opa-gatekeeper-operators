import asyncio
import contextlib
import json
import logging
import shlex
import time
from pathlib import Path

import pytest
import yaml
from lightkube import codecs
from lightkube.generic_resource import (
    get_generic_resource,
    load_in_cluster_generic_resources,
)
from lightkube.resources.apiextensions_v1 import CustomResourceDefinition

log = logging.getLogger(__name__)

metadata = yaml.safe_load(Path("metadata.yaml").read_text())
files = Path(__file__).parent.parent.parent.parent / "docs"


class ModelTimeout(Exception):
    """Model timeout exception."""

    pass


@contextlib.asynccontextmanager
async def fast_forward(ops_test, interval: str = "5s"):
    # temporarily speed up update-status firing rate
    await ops_test.model.set_config({"update-status-hook-interval": interval})
    yield
    await ops_test.model.set_config({"update-status-hook-interval": "60m"})


async def wait_for_application(model, app_name, status="active", timeout=60):
    start = time.time()
    while True:
        apps = await model.get_status()
        app = apps.applications[app_name]
        if app.status.status == status:
            return
        await asyncio.sleep(2)
        log.info(
            f"Waiting for {app_name} to be {status}, currently={app.status.status}"
        )
        if int(time.time() - start) > timeout:
            raise ModelTimeout


@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test, charm):
    model = ops_test.model
    image = metadata["resources"]["gatekeeper-image"]["upstream-source"]

    cmd = (
        f"juju deploy -m {ops_test.model_full_name} "
        f"{charm.resolve()} "
        f"--resource gatekeeper-image={image} "
        "--trust"
    )
    await ops_test.run(*shlex.split(cmd), check=True)
    await model.block_until(
        lambda: "gatekeeper-audit" in model.applications, timeout=60
    )

    # We don't use wait for idle because we want to wait for the application to be
    # active and not the units
    await wait_for_application(model, "gatekeeper-audit", status="active", timeout=120)


@pytest.fixture(scope="class")
def policies(client):
    applied = []
    try:
        # Create a template and a constraint
        load_in_cluster_generic_resources(client)
        policy = codecs.load_all_yaml(
            (files / "policy-example.yaml").read_text(), create_resources_for_crds=True
        )[0]
        ConstraintTemplate = get_generic_resource(
            "templates.gatekeeper.sh/v1", "ConstraintTemplate"
        )
        client.apply(policy)
        applied.append(policy)
        # Wait for the template crd to be created from gatekeeper
        client.wait(
            CustomResourceDefinition,
            "k8srequiredlabels.constraints.gatekeeper.sh",
            for_conditions=("Established",),
        )
        # Confirm ConstraintTemplate
        load_in_cluster_generic_resources(client)
        assert client.get(ConstraintTemplate, policy.metadata.name)

        constraint = codecs.load_all_yaml(
            (files / "policy-spec-example.yaml").read_text(),
            create_resources_for_crds=True,
        )[0]
        client.apply(constraint)
        applied.append(constraint)

        load_in_cluster_generic_resources(client)
        Constraint = get_generic_resource(
            "constraints.gatekeeper.sh/v1beta1",
            policy.spec["crd"]["spec"]["names"]["kind"],
        )
        # Verify that the constraint was created
        assert client.get(Constraint, constraint.metadata.name)
        constraint = codecs.load_all_yaml(
            (files / "policy-spec-null-example.yaml").read_text(),
            create_resources_for_crds=True,
        )[0]
        client.apply(constraint)
        applied.append(constraint)
        load_in_cluster_generic_resources(client)
        Constraint = get_generic_resource(
            "constraints.gatekeeper.sh/v1beta1",
            policy.spec["crd"]["spec"]["names"]["kind"],
        )
        # Verify that the constraint was created
        assert client.get(Constraint, constraint.metadata.name)

        yield applied
    finally:
        for resource in reversed(applied):
            log.info(f"Removing {type(resource)} {resource.metadata.name}")
            client.delete(type(resource), resource.metadata.name)


@pytest.mark.usefixtures("policies")
class TestPolicies:
    async def test_list_no_violations(self, ops_test):
        """This will run before the resources have been audited"""
        unit = list(ops_test.model.units.values())[0]
        unit_name = unit.name
        res = await ops_test.juju(
            "run-action",
            unit_name,
            "list-violations",
            "--wait",
            "-m",
            ops_test.model.info.name,
        )
        res = yaml.full_load(res[1])[unit.tag]
        violations = json.loads(res["results"]["constraint-violations"])
        assert len(violations) == 2, json.dumps(violations, indent=2)
        assert any(
            v
            == {
                "constraint_resource": "K8sRequiredLabels",
                "constraint": "ns-must-have-any",
                "total-violations": None,
            }
            for v in violations
        )
        assert any(
            v
            == {
                "constraint_resource": "K8sRequiredLabels",
                "constraint": "ns-must-have-gk",
                "total-violations": None,
            }
            for v in violations
        )

    async def test_audit(self, ops_test, client):
        # Set the audit interval to 1
        await ops_test.juju(
            "config",
            "gatekeeper-audit",
            "audit-interval=1",
        )
        await wait_for_application(
            ops_test.model, "gatekeeper-audit", status="active", timeout=120
        )
        # We test whether policy violations are being logged
        K8sRequiredLabels = get_generic_resource(
            "constraints.gatekeeper.sh/v1beta1", "K8sRequiredLabels"
        )
        for _ in range(30):
            constraint = client.get(K8sRequiredLabels, name="ns-must-have-gk")
            if constraint.status and "violations" in constraint.status:
                break
            time.sleep(1)

        assert constraint.status is not None
        assert "violations" in constraint.status

    async def test_list_violations(self, ops_test):
        unit = list(ops_test.model.units.values())[0]
        unit_name = unit.name
        res = await ops_test.juju(
            "run-action",
            unit_name,
            "list-violations",
            "--wait",
            "-m",
            ops_test.model.info.name,
        )
        res = yaml.full_load(res[1])[unit.tag]
        violations = json.loads(res["results"]["constraint-violations"])
        assert res["status"] == "completed"
        assert len(violations) == 2
        assert any(
            violation["constraint"] == "ns-must-have-gk"
            and violation["constraint_resource"] == "K8sRequiredLabels"
            and violation["total-violations"] > 0
            for violation in violations
        )
        assert any(
            violation["constraint"] == "ns-must-have-any"
            and violation["constraint_resource"] == "K8sRequiredLabels"
            and violation["total-violations"] == 0
            for violation in violations
        )

    async def test_get_violations(self, ops_test):
        expected_model_violation = {
            "enforcementAction": "deny",
            "group": "",
            "kind": "Namespace",
            "message": 'you must provide labels: {"gatekeeper"}',
            "name": ops_test.model_name,
            "version": "v1",
        }

        unit = list(ops_test.model.units.values())[0]
        unit_name = unit.name
        res = await ops_test.juju(
            "run-action",
            unit_name,
            "get-violation",
            "constraint-template=K8sRequiredLabels",
            "constraint=ns-must-have-gk",
            "--wait",
            "-m",
            ops_test.model.info.name,
        )
        res = yaml.full_load(res[1])[unit.tag]
        violations = json.loads(res["results"]["violations"])
        assert res["status"] == "completed"
        assert any(v == expected_model_violation for v in violations)

    async def test_reconciliation_required(self, ops_test, client):
        model = ops_test.model
        client.delete(CustomResourceDefinition, "assign.mutations.gatekeeper.sh")

        async with fast_forward(ops_test, interval="5s"):
            await model.wait_for_idle(
                apps=["gatekeeper-audit"], status="blocked", timeout=60
            )

        unit = list(ops_test.model.units.values())[0]
        unit_name = unit.name
        res = await ops_test.juju(
            "run-action",
            unit_name,
            "reconcile-resources",
            "--wait",
            "-m",
            ops_test.model.info.name,
        )

        res = yaml.full_load(res[1])[unit.tag]
        assert res["status"] == "completed"
        await model.wait_for_idle(
            apps=["gatekeeper-audit"], status="active", timeout=60
        )


async def test_upgrade(ops_test, charm):
    model = ops_test.model
    image = metadata["resources"]["gatekeeper-image"]["upstream-source"]

    app = model.applications["gatekeeper-audit"]
    log.debug("Refreshing the charm")
    await app.upgrade_charm(
        path=charm.resolve(),
        resources={"gatekeeper-image": image},
    )

    log.debug("Waiting for the charm to come up")
    await model.block_until(
        lambda: "gatekeeper-audit" in model.applications, timeout=60
    )
    async with fast_forward(ops_test, interval="5s"):
        await model.wait_for_idle(status="active")
