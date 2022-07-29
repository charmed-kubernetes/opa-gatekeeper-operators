#!/usr/bin/env python3
import logging
from pathlib import Path

# Shouldn't this work without `lib.`?
from charms.observability_libs.v1.kubernetes_service_patch import KubernetesServicePatch
from ops.charm import CharmBase
from ops.pebble import ServiceStatus
from ops.pebble import Error as PebbleError
from ops.main import main
from ops.framework import StoredState
from ops.model import ActiveStatus, MaintenanceStatus, WaitingStatus, ModelError
from lightkube.models.core_v1 import ServicePort
from lightkube.resources.apps_v1 import StatefulSet
from lightkube import Client, codecs


logger = logging.getLogger(__name__)


class OPAManagerCharm(CharmBase):
    """
    A Juju Charm for OPA
    """

    _GATEKEEPER_CONTAINER_NAME = "gatekeeper"

    def __init__(self, *args):
        super().__init__(*args)
        sp = ServicePort(443, name="https-webhook-server", targetPort="webhook-server")
        self.service_patcher = KubernetesServicePatch(
            self,
            [sp],
            service_name="gatekeeper-webhook-service",
        )

        self.client = Client(field_manager=self.app.name, namespace=self.model.name)

        self.framework.observe(self.on.gatekeeper_pebble_ready, self._on_gatekeeper_pebble_ready)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.update_status, self._on_update_status)

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
            # "checks":{
            #     "up": {
            #         "override": "replace",
            #         "level": "alive",
            #         "http": {
            #             "url": "http://localhost:9090/healthz",
            #         }
            #     },
            #     "ready": {
            #         "override": "replace",
            #         "level": "ready",
            #         "http": {
            #             "url": "http://localhost:9090/readyz",
            #         }
            #     },
            # }
        }

    def _on_gatekeeper_pebble_ready(self, event):
        if self.is_running:
            logger.info("Gatekeeper already started")
            return

        container = event.workload
        layer = self._gatekeeper_layer()
        if container.can_connect():
            services = container.get_plan().to_dict().get("services", {})
            if services != layer["services"]:
                container.add_layer(self._GATEKEEPER_CONTAINER_NAME, layer)
                container.autostart()
        self._apply_spec()
        self._patch_statefulset()

        self._on_update_status(event)

    def _on_update_status(self, event):
        """Update Juju status"""
        logger.info("Update status")
        if not self.is_running:
            self.unit.status = WaitingStatus("Gatekeeper is not running")
        else:
            self.unit.status = ActiveStatus()

    def _apply_spec(self):
        if not self.unit.is_leader():
            return
        logger.info("Applying gatekeeper.yaml")

        with Path("files", "gatekeeper.yaml").open() as f:
            for policy in codecs.load_all_yaml(
                f, context={"namespace": self.model.name}, create_resources_for_crds=True
            ):
                # TODO: This may throw, should we catch it and change the status?
                self.client.apply(policy, force=True)

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
                                            "key": "gatekeeper.sh/operation",
                                            "operator": "In",
                                            "values": ["webhook"],
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
                    "ports":[
                        {
                            "containerPort": 8443,
                            "name": "webhook-server",
                            "protocol": "TCP",
                        },
                        {
                            "containerPort": 8888,
                            "name": "metrics",
                            "protocol": "TCP",
                        },
                        {
                            "containerPort": 9090,
                            "name": "healthz",
                            "protocol": "TCP",
                        },
                    ],
                },
            ],
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

        patch = {
            "spec": {
                "template": {
                    "spec": pod_spec_patch
                }
            }
        }
        self.client.patch(
            StatefulSet, name=self.meta.name, namespace=self.model.name, obj=patch
        )

    def _on_config_changed(self, event):
        """
        Set a new Juju pod specification
        """
        logger.info("Config changed")


if __name__ == "__main__":
    main(OPAManagerCharm)
