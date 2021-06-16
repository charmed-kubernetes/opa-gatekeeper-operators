"""Kubernetes utils library."""

import logging
import os
import random
import string
from kubernetes import client, config
from kubernetes.client.rest import ApiException


logger = logging.getLogger(__name__)


def crud_pod_security_policy_with_api(namespace, psp, action):
    """Create pod security policy."""
    # Using the API because of LP:1886694
    logging.info("Creating pod security policy with K8s API")
    _load_kube_config()

    body = client.ExtensionsV1beta1PodSecurityPolicy(**psp)

    with client.ApiClient() as api_client:
        api_instance = client.PolicyV1beta1Api(api_client)
        try:
            if action.lower() == "create":
                api_instance.create_pod_security_policy(body, pretty=True)
            elif action.lower() == "delete":
                api_instance.delete_pod_security_policy(
                    name=psp["metadata"]["name"], pretty=True
                )
        except ApiException as err:
            if err.status == 409:
                # ignore "already exists" errors so that we can recover from
                # partially failed setups
                return
            else:
                raise


def crud_custom_object(namespace, obj, action):
    """Create custom object using the k8s generic API"""
    # Using the API because of LP:1886694
    logging.info("Creating CRD object with K8s API")
    _load_kube_config()

    with client.ApiClient() as api_client:
        api_instance = client.CustomObjectsApi(api_client)
        try:
            if action.lower() == "create":
                api_instance.create_namespaced_custom_object(**obj)
        except ApiException as err:
            if err.status == 409:
                # ignore "already exists" errors so that we can recover from
                # partially failed setups
                return
            else:
                raise


def crud_crd_object(namespace, obj, action):
    """Create Custom Resource Definitino object"""
    # Using the API because of LP:1886694
    logging.info("Creating CRD object with K8s API")
    _load_kube_config()

    body = client.V1beta1CustomResourceDefinition(**obj)

    with client.ApiClient() as api_client:
        api_instance = client.ApiextensionsV1beta1Api(api_client)
        try:
            if action.lower() == "create":
                api_instance.create_custom_resource_definition(body, pretty=True)
            elif action.lower() == "delete":
                api_instance.delete_custom_resource_definition(
                    name=obj["metadata"]["name"], pretty=True
                )
        except ApiException as err:
            if err.status == 409:
                # ignore "already exists" errors so that we can recover from
                # partially failed setups
                return
            else:
                raise


def _load_kube_config():
    # TODO: Remove this workaround when bug LP:1892255 is fixed
    from pathlib import Path

    os.environ.update(
        dict(
            e.split("=")
            for e in Path("/proc/1/environ").read_text().split("\x00")
            if "KUBERNETES_SERVICE" in e
        )
    )
    # end workaround
    config.load_incluster_config()


ACTION_MAP = {"PodSecurityPolicy": crud_pod_security_policy_with_api}


def try_crd(ns, obj, action):
    try:
        crud_crd_object(ns, obj, action)
    except TypeError:
        crud_custom_object(ns, obj, action)


def create_k8s_object(namespace, k8s_object):
    """Create all supplementary K8s objects."""
    ACTION_MAP.get(k8s_object.get("kind"), try_crd)(namespace, k8s_object, "create")


def remove_k8s_object(namespace, k8s_object):
    """Remove all supplementary K8s objects."""
    ACTION_MAP.get(k8s_object.get("kind"), try_crd)(namespace, k8s_object, "delete")
