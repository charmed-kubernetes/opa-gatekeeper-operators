import asyncio
import contextlib
import json
import logging
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
        if int(time.time() - start) > timeout:
            raise ModelTimeout


async def wait_for_workload_status(model, app_name, status="active", timeout=60):
    start = time.time()
    while True:
        apps = await model.get_status()
        app = apps.applications[app_name]
        if all(unit.workload_status.status == status for unit in app.units.values()):
            return
        await asyncio.sleep(2)
        if int(time.time() - start) > timeout:
            raise ModelTimeout


@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test, charm):
    model = ops_test.model
    image = metadata["resources"]["gatekeeper-image"]["upstream-source"]

    await model.deploy(
        entity_url=charm.resolve(),
        trust=True,
        resources={"gatekeeper-image": image},
    )
    await model.block_until(
        lambda: "gatekeeper-audit" in model.applications, timeout=60
    )

    # We don't use wait for idle because we want to wait for the application to be
    # active and not the units
    await wait_for_application(model, "gatekeeper-audit", status="active", timeout=120)


@pytest.mark.abort_on_fail
async def test_apply_policy(client):
    # Create a template and a constraint
    load_in_cluster_generic_resources(client)
    policy = codecs.load_all_yaml(
        (files / "policy-example.yaml").read_text(), create_resources_for_crds=True
    )[0]
    ConstraintTemplate = get_generic_resource(
        "templates.gatekeeper.sh/v1", "ConstraintTemplate"
    )
    client.create(policy)
    # Wait for the template crd to be created from gatekeeper
    client.wait(
        CustomResourceDefinition,
        "k8srequiredlabels.constraints.gatekeeper.sh",
        for_conditions=("Established",),
    )
    load_in_cluster_generic_resources(client)
    assert client.get(ConstraintTemplate, policy.metadata.name)

    constraint = codecs.load_all_yaml(
        (files / "policy-spec-example.yaml").read_text(),
        create_resources_for_crds=True,
    )[0]
    client.create(constraint)

    load_in_cluster_generic_resources(client)
    Constraint = get_generic_resource(
        "constraints.gatekeeper.sh/v1beta1", policy.spec["crd"]["spec"]["names"]["kind"]
    )
    # Verify that the constraint was created
    assert client.get(Constraint, constraint.metadata.name)


def test_audit(client):
    # We test whether policy violations are being logged
    K8sRequiredLabels = get_generic_resource(
        "constraints.gatekeeper.sh/v1beta1", "K8sRequiredLabels"
    )
    for _ in range(60):
        constraint = client.get(K8sRequiredLabels, name="ns-must-have-gk")
        if constraint.status and "violations" in constraint.status:
            break
        time.sleep(1)

    assert constraint.status is not None
    assert "violations" in constraint.status


async def test_list_violations(ops_test):
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
    violations = json.loads(res["results"]["constraint-violations"])[0]
    assert res["status"] == "completed"
    assert violations["constraint"] == "ns-must-have-gk"
    assert violations["constraint_resource"] == "K8sRequiredLabels"
    assert violations["total-violations"] > 0


async def test_get_violations(ops_test):
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


async def test_reconciliation_required(ops_test, client):
    model = ops_test.model
    client.delete(CustomResourceDefinition, "assign.mutations.gatekeeper.sh")

    async with fast_forward(ops_test, interval="5s"):
        await wait_for_workload_status(model, "gatekeeper-audit", status="blocked")

    apps = await model.get_status()
    app = apps.applications["gatekeeper-audit"]
    unit = list(app.units.values())[0]
    assert unit.workload_status.status == "blocked"

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
    apps = await model.get_status()
    app = apps.applications["gatekeeper-audit"]
    unit = list(app.units.values())[0]
    assert unit.workload_status.status == "active"


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
    await model.wait_for_idle(status="active")
