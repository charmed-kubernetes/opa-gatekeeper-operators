import logging
from unittest.mock import MagicMock

import ops.testing
from lightkube.resources.apps_v1 import StatefulSet

ops.testing.SIMULATE_CAN_CONNECT = True


def test_on_install(harness, lk_client, monkeypatch):
    mock = MagicMock(side_effect=harness.charm.manifests.apply_manifests)
    monkeypatch.setattr("manifests.ControllerManagerManifests.apply_manifests", mock)
    assert harness.charm.on.install.emit() is None
    mock.assert_called_once()
    assert all(
        i[0][0].kind not in ["Deployment", "Namespace"]
        for i in lk_client.apply.call_args_list
    )


def test_on_config_changed(harness, active_container):
    assert harness.charm._on_config_changed({}) is None
    active_container.stop.assert_called_once()
    active_container.start.assert_called_once()


def test_on_remove(harness, monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("manifests.ControllerManagerManifests.delete_manifests", mock)
    assert harness.charm._cleanup({}) is None
    mock.assert_called_once()


def test_gatekeeper_pebble_ready(harness, lk_client):
    expected_plan = {
        "checks": {
            "ready": {
                "http": {"url": "http://localhost:9090/readyz"},
                "level": "ready",
                "override": "replace",
            },
            "up": {
                "http": {"url": "http://localhost:9090/healthz"},
                "level": "alive",
                "override": "replace",
            },
        },
        "description": "pebble config layer for Gatekeeper",
        "services": {
            "gatekeeper": {
                "command": "/manager --port=8443 --logtostderr "
                "--exempt-namespace=gatekeeper-model "
                "--operation=webhook "
                "--operation=mutation-webhook "
                "--disable-opa-builtin={http.send}",
                "environment": {
                    "CONTAINER_NAME": "gatekeeper",
                    "NAMESPACE": "gatekeeper-model",
                    "POD_NAME": "gatekeeper-controller-manager-0",
                    "POD_NAMESPACE": "gatekeeper-model",
                },
                "override": "replace",
                "startup": "enabled",
                "summary": "Gatekeeper",
            }
        },
        "summary": "Gatekeeper layer",
    }
    actual_plan = harness.charm._gatekeeper_layer()
    assert expected_plan == actual_plan
    harness.set_can_connect("gatekeeper", True)
    harness.container_pebble_ready("gatekeeper")
    service = harness.model.unit.get_container("gatekeeper").get_service("gatekeeper")
    assert service.is_running()
    assert harness.model.unit.status.name == "active"

    # testing that the statefulset is patched via lightkube
    patch = lk_client.patch
    patch.assert_called_once()
    assert patch.call_args[0][0] == StatefulSet
    assert patch.call_args[1]["name"] == "gatekeeper-controller-manager"
    assert patch.call_args[1]["namespace"] == "gatekeeper-model"


def test_gatekeeper_pebble_ready_already_started(harness, active_container, caplog):
    with caplog.at_level(logging.INFO):
        harness.charm.on.gatekeeper_pebble_ready.emit(active_container)
    assert "Gatekeeper already started" in caplog.text
