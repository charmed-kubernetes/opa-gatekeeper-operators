from lightkube.codecs import from_dict
from ops.manifests import Collector, Manifests, ManifestLabel, ConfigRegistry, SubtractEq
from typing import Dict

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
                metadata=dict(name="gatekeeper-controller-manager", namespace="gatekeeper-system"),
            )
        )


class ControllerManagerManifests(Manifests):
    def __init__(self, app_name, charm_config):

        manipulations = [
            ManifestLabel(self),
            SubtractEq(self, audit_controller),
            SubtractEq(self, controller_manager),
        ]
        super().__init__("controller-manager", app_name, "upstream/controller-manager", manipulations)
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
