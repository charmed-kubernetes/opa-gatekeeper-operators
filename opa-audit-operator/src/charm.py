#!/usr/bin/env python3

import logging
import yaml
from pathlib import Path
from ops.charm import CharmBase
from ops.main import main
from ops.framework import StoredState
from ops.model import ActiveStatus, MaintenanceStatus, BlockedStatus
from charmhelpers.core.hookenv import (
    log,
    # metadata,
    # status_set,
    # config,
    # network_get,
    # relation_id,
)
from jinja2 import Template


logger = logging.getLogger(__name__)


class CustomResourceDefintion(object):

    def __init__(self, name, spec):

        self._name = name
        self._spec = spec

    @property
    def spec(self):
        return self._spec
    @property
    def name(self):
        return self._name


class OPAAuditCharm(CharmBase):
    """
    A Juju Charm for OPA
    """

    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.update_status, self._on_update_status)
        self.framework.observe(self.on.stop, self._on_stop)
        self.framework.observe(self.on.install, self._on_install)
        self._stored.set_default(things=[])

    def _on_config_changed(self, _):
        """
        Set a new Juju pod specification
        """
        self._configure_pod()

    def _on_stop(self, _):
        """
        Mark unit is inactive
        """
        self.unit.status = MaintenanceStatus("Pod is terminating.")
        logger.info("Pod is terminating.")

    def _on_install(self, event):
        logger.info("Congratulations, the charm was properly installed!")

    def _on_update_status(self, event):
        logger.info("Status updated")

    def _build_pod_spec(self):
        """
        Construct a Juju pod specification for OPA
        """
        logger.debug("Building Pod Spec")
        crds = []
        try:
            crds = [
                yaml.load(Path(f).read_text())
                for f in [
                    "files/configs.config.gatekeeper.sh.yaml",
                    "files/constrainttemplates.templates.gatekeeper.sh.yaml",
                    "files/constraintpodstatuses.status.gatekeeper.sh.yaml",
                    "files/constrainttemplatepodstatuses.status.gatekeeper.sh.yaml",
                    # "files/sync.yaml",
                ]
            ]
        except yaml.YAMLError as exc:
            print("Error in configuration file:", exc)

        crd_objects = [
            CustomResourceDefintion(crd['metadata']['name'], crd['spec'])
            for crd in crds
        ]

        config = self.model.config
        spec_template = {}
        with open("files/pod-spec.yaml.jinja2") as fh:
            spec_template = Template(fh.read())

        template_args = {
            'crds': crd_objects,
            'image_path': config["imagePath"],
            'imagePullPolicy': config["imagePullPolicy"],
            'app_name': self.app.name,
            'audit_cli_args': self._audit_cli_args(),
            'namespace': os.environ['JUJU_MODEL_NAME']
        }

        spec = yaml.load(spec_template.render(**template_args))

        print(f"Pod spec: {spec}")
        return spec


    def _audit_cli_args(self):
        """
        Construct command line arguments for OPA Audit
        """
        config = self.model.config

        args = [
            "--operation=audit",
            "--operation=status",
            "--logtostderr",
        ]

        return args

    def _opa_config(self):
        """
        Construct opa configuration
        """
        config = self.model.config

        logger.debug("opa config : {}".format(config))

        return yaml.dump(config)

    def _check_config(self):
        """
        Identify missing but required items in configuation
        :returns: list of missing configuration items (configuration keys)
        """
        logger.debug("Checking Config")
        config = self.model.config
        missing = []

        if not config.get("imagePath"):
            missing.append("imagePath")

        return missing

    def _configure_pod(self):
        """
        Setup a new opa pod specification
        """
        logger.debug("Configuring Pod")
        missing_config = self._check_config()
        if missing_config:
            logger.error(
                "Incomplete Configuration : {}. "
                "Application will be blocked.".format(missing_config)
            )
            self.unit.status = BlockedStatus(
                "Missing configuration: {}".format(missing_config)
            )
            return

        if not self.unit.is_leader():
            self.unit.status = ActiveStatus()
            return

        self.unit.status = MaintenanceStatus("Setting pod spec.")
        pod_spec = self._build_pod_spec()

        self.model.pod.set_spec(pod_spec)
        self.app.status = ActiveStatus()
        self.unit.status = ActiveStatus()


if __name__ == "__main__":
    main(OPAAuditCharm)
