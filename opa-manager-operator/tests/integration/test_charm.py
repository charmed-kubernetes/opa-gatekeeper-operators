import logging
import random
from pathlib import Path
from time import sleep

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
        lambda: "gatekeeper-controller-manager" in model.applications, timeout=60
    )
    await model.wait_for_idle(status="active")


@pytest.mark.abort_on_fail
async def test_apply_policy(client):
    # Create a template and a constraint
    load_in_cluster_generic_resources(client)
    policy = codecs.load_all_yaml(
        Path("docs/policy-example.yaml").read_text(), create_resources_for_crds=True
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
        Path("docs/policy-spec-example.yaml").read_text(),
        create_resources_for_crds=True,
    )[0]
    client.create(constraint)

    load_in_cluster_generic_resources(client)
    Constraint = get_generic_resource(
        "constraints.gatekeeper.sh/v1beta1", policy.spec["crd"]["spec"]["names"]["kind"]
    )
    # Verify that the constraint was created
    assert client.get(Constraint, constraint.metadata.name)

    ns_name = f"test-ns-{random.randint(1, 99999)}"
    # Verify that the policy is enforced
    for _ in range(10):
        with pytest.raises(ApiError) as e:
            client.create(Namespace(metadata=ObjectMeta(name=ns_name)))
            log.info("Namespace was created, the policy was not enforced")
            # The policy was not enforce, clean the workspace
            client.delete(Namespace, ns_name)

        err_msg = e.value.response.json()["message"]
        if e.value.response.status_code == 500:
            # the constraint has not been created yet, retry
            assert err_msg.startswith(
                "Internal error occurred: failed calling webhook "
                '"check-ignore-label.gatekeeper.sh"'
            )
            # We sleep in order to wait for opa to register the constraint
            # TODO: Is there a better way to do this?
            log.info("The constraint is not synced yet, going to sleep")
            sleep(3)
            log.info("Retrying...")
            continue
        assert e.value.response.status_code == 403
        assert err_msg.startswith(
            'admission webhook "validation.gatekeeper.sh" denied the request:'
        )
        break

    # Test that the namespace with the appropriate label is created
    client.create(
        Namespace(
            metadata=ObjectMeta(
                name=ns_name,
                labels=dict(gatekeeper="True"),
            )
        )
    )
    # Clean the workspace
    client.delete(Namespace, ns_name)


async def test_list_constraints(ops_test):
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
    await model.wait_for_idle(status="active")
