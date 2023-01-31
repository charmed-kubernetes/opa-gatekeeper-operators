import asyncio
import contextlib
import logging
import random
import shlex
import time
from pathlib import Path

import pytest
import yaml
from lightkube import codecs
from lightkube.core.exceptions import ApiError
from lightkube.generic_resource import (
    get_generic_resource,
    load_in_cluster_generic_resources,
)
from lightkube.models.meta_v1 import ObjectMeta
from lightkube.resources.apiextensions_v1 import CustomResourceDefinition
from lightkube.resources.core_v1 import Namespace

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
        f"{charm.resolve()} -n 2 "
        f"--resource gatekeeper-image={image} "
        "--trust"
    )
    await ops_test.run(*shlex.split(cmd), check=True)
    await model.block_until(
        lambda: "gatekeeper-controller-manager" in model.applications, timeout=60
    )

    # We don't use wait for idle because we want to wait for the application to be
    # active and not the units
    async with fast_forward(ops_test, interval="10s"):
        await wait_for_application(
            model, "gatekeeper-controller-manager", status="active", timeout=60 * 10
        )


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
        yield applied
    finally:
        for resource in reversed(applied):
            log.info(f"Removing {type(resource)} {resource.metadata.name}")
            client.delete(type(resource), resource.metadata.name)


@pytest.mark.usefixtures("policies")
class TestPolicies:
    async def test_list_constraints(self, ops_test):
        unit = list(ops_test.model.units.values())[0]
        unit_name = unit.name
        res = await ops_test.juju(
            "run-action",
            unit_name,
            "list-constraints",
            "--wait",
            "-m",
            ops_test.model.info.name,
        )
        res = yaml.full_load(res[1])[unit.tag]
        assert res["status"] == "completed"
        assert res["results"] == {"k8srequiredlabels": "ns-must-have-gk"}

    def test_policy_is_enforced(self, client):
        # We test whether the policy is being enforced after we test the list
        # action, in order to give gatekeeper enough time to register the constraint
        ns_name = f"test-ns-{random.randint(1, 99999)}"
        # Verify that the policy is enforced
        with pytest.raises(ApiError) as e:
            client.apply(Namespace(metadata=ObjectMeta(name=ns_name)))
            log.info("Namespace was created, the policy was not enforced")
            # The policy was not enforce, clean the workspace
            client.delete(Namespace, ns_name)

        err_msg = e.value.response.json()["message"]
        assert e.value.response.status_code == 403
        assert err_msg.startswith(
            'admission webhook "validation.gatekeeper.sh" denied the request:'
        )

        # Test that the namespace with the appropriate label is created
        client.apply(
            Namespace(
                metadata=ObjectMeta(
                    name=ns_name,
                    labels=dict(gatekeeper="True"),
                )
            )
        )
        # Clean the workspace
        client.delete(Namespace, ns_name)

    async def test_reconciliation_required(self, ops_test, client):
        model = ops_test.model
        client.delete(CustomResourceDefinition, "assign.mutations.gatekeeper.sh")

        async with fast_forward(ops_test, interval="5s"):
            await model.wait_for_idle(
                apps=["gatekeeper-controller-manager"], status="blocked", timeout=60
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
        async with fast_forward(ops_test, interval="5s"):
            await model.wait_for_idle(
                apps=["gatekeeper-controller-manager"], status="active", timeout=60
            )


async def test_upgrade(ops_test, charm):
    model = ops_test.model
    image = metadata["resources"]["gatekeeper-image"]["upstream-source"]

    app = model.applications["gatekeeper-controller-manager"]
    log.debug("Refreshing the charm")
    await app.upgrade_charm(
        path=charm.resolve(),
        resources={"gatekeeper-image": image},
    )

    log.debug("Waiting for the charm to come up")
    await model.block_until(
        lambda: "gatekeeper-controller-manager" in model.applications, timeout=60
    )
    async with fast_forward(ops_test, interval="30s"):
        await model.wait_for_idle(status="active")
