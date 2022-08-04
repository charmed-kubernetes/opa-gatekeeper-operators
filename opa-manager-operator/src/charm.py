#!/usr/bin/env python3
import logging
from pathlib import Path

from lightkube import Client, codecs
from lightkube.resources.apps_v1 import StatefulSet
from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus, MaintenanceStatus, ModelError, WaitingStatus
from ops.pebble import Error as PebbleError
from ops.pebble import ServiceStatus
from ops.manifests import Collector
from manifests import ControllerManagerManifests

logger = logging.getLogger(__name__)


class OPAManagerCharm(CharmBase):
    """
    A Juju Charm for OPA
    """

    _GATEKEEPER_CONTAINER_NAME = "gatekeeper"

    def __init__(self, *args):
        super().__init__(*args)

        self.manifests = ControllerManagerManifests(self.model.name, self.app.name, self.config)
        self.collector = Collector(self.manifests)

        self.client = Client(field_manager=self.app.name, namespace=self.model.name)

        self.framework.observe(self.on.install, self._install_or_upgrade)
        self.framework.observe(self.on.upgrade_charm, self._install_or_upgrade)
        self.framework.observe(
            self.on.gatekeeper_pebble_ready, self._on_gatekeeper_pebble_ready
        )
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.update_status, self._on_update_status)

        # Manifest-related actions
        self.framework.observe(self.on.list_resources_action, self._list_resources)
        self.framework.observe(self.on.list_versions_action, self._list_versions)

        self.framework.observe(self.on.stop, self._cleanup)
        self.framework.observe(self.on.stop, self._cleanup)

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
        # XXX: Temporary hack, we need to somehow get the pod's name
        return "-".join(self.unit.name.rsplit("/"))

    def _gatekeeper_layer(self):
        return {
            "summary": "Gatekeeper layer",
            "description": "pebble config layer for Gatekeeper",
            "services": {
                self._GATEKEEPER_CONTAINER_NAME: {
                    "override": "replace",
                    "summary": "Gatekeeper",
                    "command": "/manager --port=8443 --logtostderr "
                    "--exempt-namespace=gatekeeper-system --operation=webhook "
                    "--operation=mutation-webhook --disable-opa-builtin={http.send}",
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

    def _install_or_upgrade(self, _event):
        if not self.unit.is_leader():
            return
        self.manifests.apply_manifests()

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

        container = event.workload
        container.stop()
        container.start()
        self._on_update_status(event)

    def _on_update_status(self, event):
        """Update Juju status"""
        logger.info("Update status")
        if not self.is_running:
            self.unit.status = WaitingStatus("Gatekeeper is not running")
        else:
            self.unit.status = ActiveStatus()

    def _cleanup(self, _event):
        self.manifests.delete_manifests(ignore_unauthorized=True, ignore_not_found=True)

    def _list_resources(self, event):
        return self.collector.list_resources(event, None, None)

    def _list_versions(self, event):
        self.collector.list_versions(event)

    def _patch_statefulset(self):
        """
        Patch the statefulset to make it reflect the vanilla gatekeeper deployment spec
        """
        if not self.unit.is_leader():
            return
        logger.info("Patching the statefulset")

        pod_spec_patch = {
            "affinity": {
                "podAntiAffinity": {
                    "preferredDuringSchedulingIgnoredDuringExecution": [
                        {
                            "podAffinityTerm": {
                                "labelSelector": {
                                    "matchExpressions": [
                                        {
                                            "key": "app.kubernetes.io/name",
                                            "operator": "In",
                                            "values": ["gatekeeper-controller-manager"],
                                        }
                                    ],
                                },
                                "topologyKey": "kubernetes.io/hostname",
                            },
                            "weight": 100,
                        },
                    ],
                },
            },
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
    main(OPAManagerCharm)
