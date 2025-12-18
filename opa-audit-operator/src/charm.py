#!/usr/bin/env python3
import json
import logging

from charms.observability_libs.v1.kubernetes_service_patch import KubernetesServicePatch
from charms.prometheus_k8s.v0.prometheus_scrape import MetricsEndpointProvider
from lightkube import Client
from lightkube.generic_resource import (
    get_generic_resource,
    load_in_cluster_generic_resources,
)
from lightkube.models.core_v1 import ServicePort
from lightkube.resources.apps_v1 import StatefulSet
from ops.charm import CharmBase
from ops.main import main
from ops.manifests import Collector, ManifestClientError
from ops.model import ActiveStatus, BlockedStatus, ModelError, WaitingStatus
from ops.pebble import Error as PebbleError
from ops.pebble import ServiceStatus

from manifests import ControllerManagerManifests

logger = logging.getLogger(__name__)

scrape_config = [{"static_configs": [{"targets": ["*:8888"]}]}]


class OPAAuditCharm(CharmBase):
    """
    A Juju Charm for OPA
    """

    _GATEKEEPER_CONTAINER_NAME = "gatekeeper"

    def __init__(self, *args):
        super().__init__(*args)

        self.metrics_endpoint = MetricsEndpointProvider(
            self, "metrics-endpoint", jobs=scrape_config
        )
        metrics = ServicePort(8888, protocol="TCP", name="metrics")
        self.service_patcher = KubernetesServicePatch(self, [metrics])

        self.manifests = ControllerManagerManifests(self, self.config)
        self.collector = Collector(self.manifests)

        self.client = Client(field_manager=self.app.name, namespace=self.model.name)

        self.framework.observe(self.on.install, self._install_or_upgrade)
        self.framework.observe(self.on.upgrade_charm, self._install_or_upgrade)
        self.framework.observe(
            self.on.gatekeeper_pebble_ready, self._on_gatekeeper_pebble_ready
        )
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.update_status, self._on_update_status)

        # Template-related actions
        self.framework.observe(self.on.list_constraints_action, self._list_constraints)
        self.framework.observe(self.on.list_violations_action, self._list_violations)
        self.framework.observe(self.on.get_violation_action, self._get_violation)

        # Manifest-related actions
        self.framework.observe(self.on.list_resources_action, self._list_resources)
        self.framework.observe(self.on.list_versions_action, self._list_versions)
        self.framework.observe(
            self.on.reconcile_resources_action, self._reconcile_resources
        )

        self.framework.observe(self.on.remove, self._cleanup)

    @property
    def is_running(self):
        """Determine if a given service is running in a given container"""
        try:
            container = self.unit.get_container(self._GATEKEEPER_CONTAINER_NAME)
            service = container.get_service(self._GATEKEEPER_CONTAINER_NAME)
        except (ModelError, PebbleError):
            return False
        return service.current == ServiceStatus.ACTIVE

    @property
    def pod_name(self):
        return "-".join(self.unit.name.rsplit("/"))

    def _gatekeeper_layer(self):
        return {
            "summary": "Gatekeeper layer",
            "description": "pebble config layer for Gatekeeper",
            "services": {
                self._GATEKEEPER_CONTAINER_NAME: {
                    "override": "replace",
                    "summary": "Gatekeeper",
                    "command": "/manager "
                    "--operation=audit "
                    "--operation=status "
                    "--operation=mutation-status "
                    "--logtostderr "
                    "--disable-opa-builtin={http.send} "
                    "--disable-cert-rotation "
                    f"--constraint-violations-limit={self.config['constraint-violations-limit']} "
                    f"--audit-chunk-size={self.config['audit-chunk-size']} "
                    f"--audit-interval={self.config['audit-interval']} "
                    f"--log-level {self.config['log-level']}",
                    "startup": "enabled",
                    "environment": {
                        "POD_NAMESPACE": self.model.name,
                        "POD_NAME": self.pod_name,
                        "NAMESPACE": self.model.name,
                        "CONTAINER_NAME": self._GATEKEEPER_CONTAINER_NAME,
                    },
                },
            },
            "checks": {
                "up": {
                    "override": "replace",
                    "level": "alive",
                    "http": {
                        "url": "http://localhost:9090/healthz",
                    },
                },
                "ready": {
                    "override": "replace",
                    "level": "ready",
                    "http": {
                        "url": "http://localhost:9090/readyz",
                    },
                },
            },
        }

    def _install_or_upgrade(self, event):
        if not self.unit.is_leader():
            return
        logger.info("Installing manifest resources ...")
        try:
            self.manifests.apply_manifests()
        except ManifestClientError():
            self.unit.status = WaitingStatus("Waiting kube-apiserver")
            event.defer()
            return

    def _on_gatekeeper_pebble_ready(self, event):
        if self.is_running:
            logger.info("Gatekeeper already started")
            return

        container = event.workload
        self._patch_statefulset()
        layer = self._gatekeeper_layer()
        container.add_layer(self._GATEKEEPER_CONTAINER_NAME, layer, combine=True)
        container.autostart()
        self._on_update_status(event)

    def _on_config_changed(self, event):
        if not self.is_running:
            logger.info("Gatekeeper is not running")
            return

        container = self.unit.get_container(self._GATEKEEPER_CONTAINER_NAME)
        layer = self._gatekeeper_layer()
        container.add_layer(self._GATEKEEPER_CONTAINER_NAME, layer, combine=True)
        container.restart(self._GATEKEEPER_CONTAINER_NAME)
        self._on_update_status(event)

    def _on_update_status(self, event):
        """Update Juju status"""
        logger.info("Update status")
        if not self.is_running:
            self.unit.status = WaitingStatus("Gatekeeper is not running")
        elif self.manifests.resources != self.manifests.installed_resources():
            self.unit.status = BlockedStatus(
                "Missing resources, to reconcile run: "
                f"`juju run {self.unit.name} reconcile-resources`"
            )
        elif unready := self.collector.unready:
            # Wait for all installed resource to be ready
            self.unit.status = WaitingStatus(", ".join(unready))
        else:
            self.unit.status = ActiveStatus()

    def _cleanup(self, event):
        logger.info("Cleaning up manifest resources ...")
        try:
            self.manifests.delete_manifests(
                ignore_unauthorized=True, ignore_not_found=True
            )
        except ManifestClientError:
            self.unit.status = WaitingStatus("Waiting kube-apiserver")
            event.defer()
            return

    def _list_resources(self, event):
        return self.collector.list_resources(event, None, None)

    def _list_versions(self, event):
        self.collector.list_versions(event)

    def _reconcile_resources(self, event):
        try:
            event.log("Reconciling resources")
            self.collector.apply_missing_resources(event, None, None)
            event.log("Updating status")
            self._on_update_status(event)
        except ManifestClientError:
            event.set_results(
                {"result": "Failed to reconcile. API server unavailable."}
            )

    def _list_constraints(self, event):
        event.log("Fetching templates")
        load_in_cluster_generic_resources(self.client)
        ConstraintTemplate = get_generic_resource(
            "templates.gatekeeper.sh/v1", "ConstraintTemplate"
        )
        templates = self.client.list(ConstraintTemplate)
        names = [t.spec["crd"]["spec"]["names"]["kind"] for t in templates]
        constraint_resources = {
            name: get_generic_resource("constraints.gatekeeper.sh/v1beta1", name)
            for name in names
        }

        def get_resource_name(_resource):
            return _resource.metadata.name

        constraints = {
            name.lower(): "\n".join(map(get_resource_name, self.client.list(resource)))
            for name, resource in constraint_resources.items()
        }
        event.set_results(constraints)

    def _list_violations(self, event):
        event.log("Fetching templates")
        load_in_cluster_generic_resources(self.client)
        ConstraintTemplate = get_generic_resource(
            "templates.gatekeeper.sh/v1", "ConstraintTemplate"
        )
        templates = self.client.list(ConstraintTemplate)
        names = [t.spec["crd"]["spec"]["names"]["kind"] for t in templates]
        constraint_resources = {
            name: get_generic_resource("constraints.gatekeeper.sh/v1beta1", name)
            for name in names
        }

        ret = []
        for name, constraint_resource in constraint_resources.items():
            for constraint in self.client.list(constraint_resource):
                if (violations := constraint.status) is not None:
                    violations = violations.get("totalViolations")
                ret.append(
                    {
                        "constraint_resource": name,
                        "constraint": constraint.metadata.name,
                        "total-violations": violations,
                    }
                )
        event.set_results({"constraint-violations": json.dumps(ret, indent=2)})

    def _get_violation(self, event):
        load_in_cluster_generic_resources(self.client)
        constraint_template = event.params["constraint-template"]
        constraint = event.params["constraint"]

        ConstraintTemplate = get_generic_resource(
            "constraints.gatekeeper.sh/v1beta1", constraint_template
        )
        if ConstraintTemplate is None:
            event.log(f"Unknown constraint template: {constraint_template}")
            raise ValueError(f"Unknown constraint template: {constraint_template}")
        constraint = self.client.get(ConstraintTemplate, name=constraint)
        event.set_results(
            {"violations": json.dumps(constraint.status["violations"], indent=2)}
        )

    def _patch_statefulset(self):
        """
        Patch the statefulset to make it reflect the vanilla gatekeeper deployment spec
        """
        if not self.unit.is_leader():
            return
        logger.info("Patching the statefulset")

        pod_spec_patch = {
            "containers": [
                {
                    "name": "gatekeeper",
                    "volumeMounts": [
                        {
                            "mountPath": "/certs",
                            "name": "cert",
                            "readOnly": True,
                        },
                    ],
                },
            ],
            "priorityClassName": "system-cluster-critical",
            "volumes": [
                {
                    "name": "cert",
                    "secret": {
                        "defaultMode": 420,
                        "secretName": "gatekeeper-webhook-server-cert",
                    },
                },
            ],
        }

        patch = {"spec": {"template": {"spec": pod_spec_patch}}}
        self.client.patch(
            StatefulSet, name=self.meta.name, namespace=self.model.name, obj=patch
        )


if __name__ == "__main__":
    main(OPAAuditCharm)
