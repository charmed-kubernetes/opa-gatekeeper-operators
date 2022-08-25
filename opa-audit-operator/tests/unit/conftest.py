import unittest.mock as mock

import pytest
from ops.pebble import ServiceStatus
from ops.testing import Harness

from charm import OPAAuditCharm


@pytest.fixture(autouse=True)
def lk_client():
    with mock.patch("ops.manifests.manifest.Client", autospec=True) as mock_lightkube:
        with mock.patch("charm.Client", mock_lightkube):
            yield mock_lightkube.return_value


@pytest.fixture(autouse=True)
def mocked_service_patch(mocker):
    mocked_service_patch = mocker.patch("charm.KubernetesServicePatch")
    yield mocked_service_patch


@pytest.fixture(autouse=True)
def mock_installed_resources(monkeypatch):
    mocked_resources = mock.MagicMock(
        return_value=frozenset({"2": None, "3": None}.keys())
    )
    monkeypatch.setattr(
        "manifests.ControllerManagerManifests.resources", mocked_resources
    )
    monkeypatch.setattr(
        "manifests.ControllerManagerManifests.installed_resources",
        lambda _: mocked_resources,
    )
    return mocked_resources


@pytest.fixture
def harness(mocker):
    harness = Harness(OPAAuditCharm)
    harness.set_model_name("gatekeeper-model")
    harness.set_leader(True)
    harness.begin_with_initial_hooks()
    harness.container_pebble_ready("gatekeeper")
    harness.model.get_binding = mocker.MagicMock()
    return harness


@pytest.fixture()
def container(harness, mocker):
    container = harness.model.unit.get_container("gatekeeper")
    container.restart = mocker.MagicMock()
    return container


@pytest.fixture()
def active_service(mocker):
    mocked_service = mocker.MagicMock()
    mocked_service.current = ServiceStatus.ACTIVE
    return mocked_service


@pytest.fixture()
def active_container(mocker, container, active_service):
    container.get_service = mocker.MagicMock(return_value=active_service)
    return container
