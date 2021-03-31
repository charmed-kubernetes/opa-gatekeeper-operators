import logging
from pathlib import Path
import os
import pytest
import yaml
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from jinja2 import Template

log = logging.getLogger(__name__)

meta = yaml.safe_load(Path("metadata.yaml").read_text())

KUBECONFIG = os.environ.get("TESTING_KUBECONFIG", "~/.kube/config")

config.load_kube_config(KUBECONFIG)  # TODO: check how to use this with designated file


def todo():
    raise NotImplementedError


def setup_cluster():
    pass


@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test):
    charm = await ops_test.build_charm(".")

    role_binding_file = Path("/tmp/k8s-rolebinding.yaml")

    model_name = ops_test._default_model_name

    with open("docs/gatekeeper-rb.yaml.template", "r") as fh:
        template = Template(fh.read())
        role_binding_file.write_text(
            template.render(
                service_account_user=f"system:serviceaccount:{model_name}:kubernetes-operator"
            )
        )
    role_binding = yaml.load_all(role_binding_file.read_text(), Loader=yaml.FullLoader)
    with client.ApiClient() as api_client:
        api_instance = client.RbacAuthorizationV1Api(api_client)
        try:
            for k8s_obj in role_binding:
                if k8s_obj["kind"] == "ClusterRoleBinding":
                    api_instance.create_cluster_role_binding(body=k8s_obj)
                if k8s_obj["kind"] == "ClusterRole":
                    api_instance.create_cluster_role(body=k8s_obj)
        except ApiException as err:
            if err.status == 409:
                # ignore "already exists" errors so that we can recover from
                # partially failed setups
                return
            else:
                raise
    for series in meta["series"]:
        await ops_test.model.deploy(charm, application_name=series, series=series)
    await ops_test.model.wait_for_idle(wait_for_active=True, timeout=60 * 60)

    with open("docs/gatekeeper-rb.yaml.template", "r") as fh:
        template = Template(fh.read())
        role_binding_file.write_text(
            template.render(
                service_account_user=f"system:serviceaccount:{model_name}:kubernetes-operator"
            )
        )
    role_binding = yaml.load_all(role_binding_file.read_text(), Loader=yaml.FullLoader)
    # yield role_binding
    # import pdb; pdb.set_trace()
    with client.ApiClient() as api_client:
        api_instance = client.RbacAuthorizationV1Api(api_client)
        try:
            for k8s_obj in role_binding:
                if k8s_obj["kind"] == "ClusterRoleBinding":
                    api_instance.create_cluster_role_binding(body=k8s_obj)
                if k8s_obj["kind"] == "ClusterRole":
                    api_instance.create_cluster_role(body=k8s_obj)
        except ApiException as err:
            if err.status == 409:
                # ignore "already exists" errors so that we can recover from
                # partially failed setups
                return
            else:
                raise
    ca_cert = ""
    with client.ApiClient() as api_client:
        # Create an instance of the API class
        api_instance = client.CoreV1Api(api_client)
        name = f"{model_name}-gatekeeper-validating-webhook-configuration"

        ca_cert = api_instance.read_namespaced_secret(name, model_name)

    with client.ApiClient() as api_client:
        # Create an instance of the API class
        api_instance = client.AdmissionregistrationV1Api(api_client)
        name = f"{model_name}-gatekeeper-validating-webhook-configuration"
        for i in range(1):
            body = [
                {
                    "op": "replace",
                    "path": f"/webhooks/{i}/clientConfig/caBundle",
                    "value": f"{ca_cert}",
                }
            ]

            api_instance.patch_validating_webhook_configuration(name, body)


async def test_status_messages(ops_test):
    """ Validate that the status messages are correct. """
    expected_messages = {}

    for app, message in expected_messages.items():
        for unit in ops_test.model.applications[app].units:
            assert unit.workload_status_message == message
