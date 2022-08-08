import logging
from typing import Dict

from lightkube.codecs import from_dict
from ops.manifests import ManifestLabel, Manifests, Patch, SubtractEq

log = logging.getLogger(__file__)

audit_controller = from_dict(
    dict(
        apiVersion="apps/v1",
        kind="Deployment",
        metadata=dict(name="gatekeeper-audit", namespace="gatekeeper-system"),
    )
)

controller_manager = from_dict(
    dict(
        apiVersion="apps/v1",
        kind="Deployment",
        metadata=dict(
            name="gatekeeper-controller-manager", namespace="gatekeeper-system"
        ),
    )
)

gatekeeper_system_ns = from_dict(
    dict(
        apiVersion="v1",
        kind="Namespace",
        metadata=dict(name="gatekeeper-system"),
    )
)


class ModelNamespace(Patch):
    """Update the namespace of any namespaced resources to the model name."""

    def __call__(self, obj):
        if not obj.metadata.namespace:
            return

        log.info(f"Patching namespace for {obj.kind} {obj.metadata.name}")
        obj.metadata.namespace = self.manifests.model.name


class WebhookConfiguration(Patch):
    """Update the namespace of any webhook clientConfig services to the model name."""

    def __call__(self, obj):
        if (
            obj.kind == "ValidatingWebhookConfiguration"
            or obj.kind == "MutatingWebhookConfiguration"
        ):
            for webhook in obj.webhooks:
                log.info(
                    f"Patching clientConfig service namespace for {obj.kind} {obj.metadata.name}"
                )
                webhook.clientConfig.service.namespace = self.manifests.model.name


class RoleBinding(Patch):
    """Update the namespace of any RoleBinding or ClusteRoleBinding subjects to the model name."""

    def __call__(self, obj):
        if obj.kind == "RoleBinding" or obj.kind == "ClusterRoleBinding":
            for subject in obj.subjects:
                log.info(
                    f"Patching subject namespace for {obj.kind} {obj.metadata.name}"
                )
                subject.namespace = self.manifests.model.name


class ServicePorts(Patch):
    """Patch target ports to use port numbers instead of named ports.
    This is an alternative to patching the container ports in the juju-deployed statefulset for the charm
    """

    def __call__(self, obj):
        if obj.metadata.name == "gatekeeper-webhook-service":
            for port in obj.spec.ports:
                if port.name == "https-webhook-server":
                    log.info(f"Patching target port for {obj.metadata.name}")
                    port.targetPort = 8443


class ServiceSelector(Patch):
    """Patch the service selector to match the pod's labels"""

    def __call__(self, obj):
        if obj.metadata.name == "gatekeeper-webhook-service":
            obj.spec.selector = {
                "app.kubernetes.io/name": "gatekeeper-controller-manager"
            }


class ControllerManagerManifests(Manifests):
    def __init__(self, charm, charm_config):

        manipulations = [
            SubtractEq(self, gatekeeper_system_ns),
            SubtractEq(self, audit_controller),
            SubtractEq(self, controller_manager),
            ManifestLabel(self),
            ModelNamespace(self),
            ServicePorts(self),
            ServiceSelector(self),
            WebhookConfiguration(self),
            RoleBinding(self),
        ]
        super().__init__(
            "controller-manager",
            charm.model,
            "upstream/controller-manager",
            manipulations,
        )
        self.charm_config = charm_config

    @property
    def config(self) -> Dict:
        """Returns config mapped from charm config and joined relations."""
        config = dict(**self.charm_config)

        for key, value in dict(**config).items():
            if value == "" or value is None:
                del config[key]  # blank out keys not currently set to something

        config["release"] = config.pop("release", None)
        return config
