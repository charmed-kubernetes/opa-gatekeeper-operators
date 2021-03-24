# Copyright {{ year }} {{ author }}
# See LICENSE file for licensing details.

import unittest
from unittest.mock import Mock, patch

from ops.testing import Harness
from pathlib import Path
from charm import OPAManagerCharm




class TestCharm(unittest.TestCase):
    # def test_config_changed(self):
    #     harness = Harness(OPAManagerCharm)
    #     self.addCleanup(harness.cleanup)
    #     harness.begin()
    #     self.assertEqual(list(harness.charm._stored.things), [])
    #     harness.update_config({"thing": "foo"})
    #     self.assertEqual(list(harness.charm._stored.things), ["foo"])

    @patch('yaml.load')
    # @patch('pathlib.Path')
    def test_load_yaml_objects(self, yaml):
        harness = Harness(OPAManagerCharm)
        self.addCleanup(harness.cleanup)
        harness.begin()
        yaml.return_value = {"some.key": "some.value"}
        Path("/tmp/test.file").write_text("This is a test file")
        # pathlib.read_text.return_value = ""
        yaml_objects = harness.charm._load_yaml_objects(["/tmp/test.file"])

        assert yaml_objects == [{"some.key": "some.value"}]


    def test_cli_args(self):
        harness = Harness(OPAManagerCharm)
        self.addCleanup(harness.cleanup)
        harness.begin()
        args = [
            "--operation=audit",
            "--operation=status",
            "--logtostderr",
            "--port=8443",
            "--logtostderr",
            f"--exempt-namespace={harness.model}",
            "--operation=webhook",
        ]
        assert args == harness.charm._cli_args()


    def test_cli_args(self):
        harness = Harness(OPAManagerCharm)
        self.addCleanup(harness.cleanup)
        harness.begin()
        args = [
            "--operation=audit",
            "--operation=status",
            "--logtostderr",
        ]
        assert args == harness.charm._audit_cli_args()

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



    # def test_action(self):
    #     harness = Harness(OPAManagerCharm)
    #     harness.begin()
    #     # the harness doesn't (yet!) help much with actions themselves
    #     action_event = Mock(params={"fail": ""})
    #     harness.charm._on_fortune_action(action_event)

    #     self.assertTrue(action_event.set_results.called)

    # def test_action_fail(self):
    #     harness = Harness(OPAManagerCharm)
    #     harness.begin()
    #     action_event = Mock(params={"fail": "fail this"})
    #     harness.charm._on_fortune_action(action_event)

    #     self.assertEqual(action_event.fail.call_args, [("fail this",)])
