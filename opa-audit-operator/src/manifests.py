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

service = from_dict(
    dict(
        apiVersion="v1",
        kind="Service",
        metadata=dict(name="gatekeeper-webhook-service", namespace="gatekeeper-system"),
    )
)

validating_webhook = from_dict(
    dict(
        apiVersion="admissionregistration.k8s.io/v1",
        kind="ValidatingWebhookConfiguration",
        metadata=dict(name="gatekeeper-validating-webhook-configuration"),
    )
)

mutating_webhook = from_dict(
    dict(
        apiVersion="admissionregistration.k8s.io/v1",
        kind="MutatingWebhookConfiguration",
        metadata=dict(name="gatekeeper-mutating-webhook-configuration"),
    )
)

pod_disruption_budget = from_dict(
    dict(
        apiVersion="policy/v1beta1",
        kind="PodDisruptionBudget",
        metadata=dict(
            name="gatekeeper-controller-manager", namespace="PodDisruptionBudget"
        ),
    )
)


class ModelNamespace(Patch):
    """Update the namespace of any namespaced resources to the model name."""

    def __call__(self, obj):
        if not obj.metadata.namespace:
            return

        log.info(f"Patching namespace for {obj.kind} {obj.metadata.name}")
        obj.metadata.namespace = self.manifests.model.name


class RoleBinding(Patch):
    """Update the namespace of any RoleBinding or ClusteRoleBinding subjects to the model name."""

    def __call__(self, obj):
        if obj.kind == "RoleBinding" or obj.kind == "ClusterRoleBinding":
            for subject in obj.subjects:
                log.info(
                    f"Patching subject namespace for {obj.kind} {obj.metadata.name}"
                )
                subject.namespace = self.manifests.model.name


class ControllerManagerManifests(Manifests):
    def __init__(self, charm, charm_config):

        manipulations = [
            SubtractEq(self, gatekeeper_system_ns),
            SubtractEq(self, audit_controller),
            SubtractEq(self, controller_manager),
            SubtractEq(self, service),
            SubtractEq(self, validating_webhook),
            SubtractEq(self, mutating_webhook),
            SubtractEq(self, pod_disruption_budget),
            ManifestLabel(self),
            ModelNamespace(self),
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
