#!/usr/bin/env python3
import os
import logging
import yaml
import utils
from pathlib import Path
from ops.charm import CharmBase
from ops.main import main
from ops.framework import StoredState
from ops.model import ActiveStatus, MaintenanceStatus
from oci_image import OCIImageResource, OCIImageResourceError

from charmhelpers.core.hookenv import (
    log,
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


class OPAManagerCharm(CharmBase):
    """
    A Juju Charm for OPA
    """

    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.stop, self._on_stop)
        self.framework.observe(self.on.install, self._on_install)
        # self.framework.observe(self.on.start, self._on_start)
        self._stored.set_default(things=[])
        self.image = OCIImageResource(self, "gatekeeper-image")

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

    def _load_yaml_objects(self, files_list):
        yaml_objects = []
        try:
            yaml_objects = [yaml.load(Path(f).read_text(), yaml.Loader) for f in files_list]
        except yaml.YAMLError as exc:
            print("Error in configuration file:", exc)

        return yaml_objects

    def _on_install(self, event):
        logger.info("Congratulations, the charm was properly installed!")

    def _build_pod_spec(self):
        """
        Construct a Juju pod specification for OPA
        """
        logger.debug("Building Pod Spec")

        # Load Custom Resource Definitions
        crd_objects = [
            CustomResourceDefintion(crd["metadata"]["name"], yaml.dump(crd["spec"]))
            for crd in self._load_yaml_objects(
                [
                    "files/configs.config.gatekeeper.sh.yaml",
                    "files/constrainttemplates.templates.gatekeeper.sh.yaml",
                    "files/constraintpodstatuses.status.gatekeeper.sh.yaml",
                    "files/constrainttemplatepodstatuses.status.gatekeeper.sh.yaml",
                ]
            )
        ]

        config = self.model.config

        try:
            image_details = self.image.fetch()
        except OCIImageResourceError as e:
            self.model.unit.status = e.status
            return
        template_args = {
            "crds": crd_objects,
            "image_details": image_details,
            "imagePullPolicy": config["imagePullPolicy"],
            "app_name": self.app.name,
            "cli_args": self._cli_args(),
            "namespace": os.environ["JUJU_MODEL_NAME"],
        }

        template = self._render_jinja_template(
            "files/pod-spec.yaml.jinja2", template_args
        )

        spec = yaml.load(template, yaml.Loader)
        return spec

    def _cli_args(self):
        """
        Construct command line arguments for OPA
        """

        args = [
            "--logtostderr",
            "--port=8443",
            f"--exempt-namespace={os.environ['JUJU_MODEL_NAME']}",
            "--operation=webhook",
        ]
        return args

    def _render_jinja_template(self, template, ctx):
        spec_template = {}
        with open(template) as fh:
            spec_template = Template(fh.read())

        return spec_template.render(**ctx)

    def _on_start(self, event):
        k8s_objects = self._load_yaml_objects(["files/psp.yaml"])
        k8s_objects.append(
            yaml.load(
                self._render_jinja_template(
                    "files/sync.yaml.jinja2",
                    {"namespace": os.environ["JUJU_MODEL_NAME"]},
                ),
                yaml.Loader
            )
        )
        log(f"K8s objects: {k8s_objects}")
        for k8s_object in k8s_objects:
            utils.create_k8s_object(os.environ["JUJU_MODEL_NAME"], k8s_object)

    def _configure_pod(self):
        """
        Setup a new OPA pod specification
        """
        logger.debug("Configuring Pod")

        if not self.unit.is_leader():
            self.unit.status = ActiveStatus()
            return

        self.unit.status = MaintenanceStatus("Setting pod spec.")
        pod_spec = self._build_pod_spec()

        self.model.pod.set_spec(pod_spec)
        self.unit.status = ActiveStatus()


if __name__ == "__main__":
    main(OPAManagerCharm)
