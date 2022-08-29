import logging
from unittest.mock import MagicMock

import ops.testing
from lightkube.resources.apps_v1 import StatefulSet
from ops.model import BlockedStatus

ops.testing.SIMULATE_CAN_CONNECT = True


def test_on_install(harness, lk_client, monkeypatch):
    excluded = [
        "Deployment",
        "Namespace",
        "Service",
        "ValidatingWebhookConfiguration",
        "MutatingWebhookConfiguration",
        "PodDisruptionBudget",
    ]
    mock = MagicMock(side_effect=harness.charm.manifests.apply_manifests)
    monkeypatch.setattr("manifests.ControllerManagerManifests.apply_manifests", mock)
    assert harness.charm.on.install.emit() is None
    mock.assert_called_once()
    assert all(
        i[0][0].kind not in excluded
        for i in lk_client.apply.call_args_list
    )


def test_on_config_changed(harness, active_container):
    assert harness.charm._on_config_changed({}) is None
    active_container.restart.assert_called_once()


def test_on_remove(harness, monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("manifests.ControllerManagerManifests.delete_manifests", mock)
    assert harness.charm._cleanup({}) is None
    mock.assert_called_once()


def test_reconciliation_required(harness, monkeypatch):
    mocked_resources = MagicMock(return_value={"1": None, "2": None, "3": None}.keys())
    mocked_installed_resources = MagicMock(
        return_value=frozenset({"2": None, "3": None}.keys())
    )
    monkeypatch.setattr(
        "manifests.ControllerManagerManifests.resources", mocked_resources
    )
    monkeypatch.setattr(
        "manifests.ControllerManagerManifests.installed_resources",
        mocked_installed_resources,
    )

    harness.charm.on.update_status.emit()

    assert isinstance(harness.charm.unit.status, BlockedStatus)


def test_gatekeeper_pebble_ready(harness, lk_client, mock_installed_resources):
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
                "command": "/manager "
                "--operation=audit "
                "--operation=status "
                "--operation=mutation-status "
                "--logtostderr "
                "--disable-opa-builtin={http.send} "
                "--disable-cert-rotation "
                "--constraint-violations-limit=20 "
                "--audit-chunk-size=500 "
                "--audit-interval=60 "
                "--log-level INFO",
                "environment": {
                    "CONTAINER_NAME": "gatekeeper",
                    "NAMESPACE": "gatekeeper-model",
                    "POD_NAME": "gatekeeper-audit-0",
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
    assert patch.call_args[1]["name"] == "gatekeeper-audit"
    assert patch.call_args[1]["namespace"] == "gatekeeper-model"


def test_gatekeeper_pebble_ready_already_started(harness, active_container, caplog):
    with caplog.at_level(logging.INFO):
        harness.charm.on.gatekeeper_pebble_ready.emit(active_container)
    assert "Gatekeeper already started" in caplog.text


def test_config_changed(harness, active_container, caplog):
    harness.update_config({"log-level": "DEBUG"})
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
                "command": "/manager "
                "--operation=audit "
                "--operation=status "
                "--operation=mutation-status "
                "--logtostderr "
                "--disable-opa-builtin={http.send} "
                "--disable-cert-rotation "
                "--constraint-violations-limit=20 "
                "--audit-chunk-size=500 "
                "--audit-interval=60 "
                "--log-level DEBUG",
                "environment": {
                    "CONTAINER_NAME": "gatekeeper",
                    "NAMESPACE": "gatekeeper-model",
                    "POD_NAME": "gatekeeper-audit-0",
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
    active_container.restart.assert_called_once()
