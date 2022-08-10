import logging

import ops.testing

ops.testing.SIMULATE_CAN_CONNECT = True


def test_on_config_changed(harness):
    assert harness.charm._on_config_changed({}) is None


def test_on_stop(harness):
    assert harness.charm._cleanup({}) is None


def test_gatekeeper_pebble_ready(harness, lk_client, container):
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
                "--exempt-namespace=gatekeeper-system "
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


def test_coredns_pebble_ready_already_started(harness, active_container, caplog):
    with caplog.at_level(logging.INFO):
        harness.charm.on.gatekeeper_pebble_ready.emit(active_container)
    assert "Gatekeeper already started" in caplog.text
