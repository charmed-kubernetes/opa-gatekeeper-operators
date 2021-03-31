import unittest
import os
from unittest.mock import patch
from ops.testing import Harness
from pathlib import Path
from charm import OPAManagerCharm


class TestCharm(unittest.TestCase):
    @patch("yaml.load")
    def test_load_yaml_objects(self, yaml):
        harness = Harness(OPAManagerCharm)
        self.addCleanup(harness.cleanup)
        harness.begin()
        yaml.return_value = {"some.key": "some.value"}
        Path("/tmp/test.file").write_text("This is a test file")
        yaml_objects = harness.charm._load_yaml_objects(["/tmp/test.file"])

        assert yaml_objects == [{"some.key": "some.value"}]

    def test_cli_args(self):
        harness = Harness(OPAManagerCharm)
        self.addCleanup(harness.cleanup)
        harness.begin()
        model_name = "test-cli-args"
        os.environ["JUJU_MODEL_NAME"] = model_name
        args = [
            "--operation=audit",
            "--operation=status",
            "--logtostderr",
            "--port=8443",
            "--logtostderr",
            f"--exempt-namespace={model_name}",
            "--operation=webhook",
        ]
        assert args == harness.charm._cli_args()

    def test_on_config_changed(self):
        harness = Harness(OPAManagerCharm)
        self.addCleanup(harness.cleanup)
        harness.begin()

        assert harness.charm._on_config_changed({}) is None

    def test_on_stop(self):
        harness = Harness(OPAManagerCharm)
        self.addCleanup(harness.cleanup)
        harness.begin()

        assert harness.charm._on_stop({}) is None

    def test_on_install(self):
        harness = Harness(OPAManagerCharm)
        self.addCleanup(harness.cleanup)
        harness.begin()

        assert harness.charm._on_install({}) is None

    def test_on_update_status(self):
        harness = Harness(OPAManagerCharm)
        self.addCleanup(harness.cleanup)
        harness.begin()

        assert harness.charm._on_update_status({}) is None

    def test_configure_pod(self):
        harness = Harness(OPAManagerCharm)
        self.addCleanup(harness.cleanup)
        harness.begin()

        assert harness.charm._configure_pod() is None
