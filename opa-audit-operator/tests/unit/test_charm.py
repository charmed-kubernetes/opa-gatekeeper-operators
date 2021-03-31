# Copyright {{ year }} {{ author }}
# See LICENSE file for licensing details.

import unittest
from ops.testing import Harness
from charm import OPAAuditCharm


class TestCharm(unittest.TestCase):
    def test_cli_args(self):
        harness = Harness(OPAAuditCharm)
        self.addCleanup(harness.cleanup)
        harness.begin()
        args = [
            "--operation=audit",
            "--operation=status",
            "--logtostderr",
        ]
        assert args == harness.charm._audit_cli_args()

    def test_on_config_changed(self):
        harness = Harness(OPAAuditCharm)
        self.addCleanup(harness.cleanup)
        harness.begin()

        assert harness.charm._on_config_changed({}) is None

    def test_on_stop(self):
        harness = Harness(OPAAuditCharm)
        self.addCleanup(harness.cleanup)
        harness.begin()

        assert harness.charm._on_stop({}) is None

    def test_on_install(self):
        harness = Harness(OPAAuditCharm)
        self.addCleanup(harness.cleanup)
        harness.begin()

        assert harness.charm._on_install({}) is None

    def test_on_update_status(self):
        harness = Harness(OPAAuditCharm)
        self.addCleanup(harness.cleanup)
        harness.begin()

        assert harness.charm._on_update_status({}) is None

    def test_configure_pod(self):
        harness = Harness(OPAAuditCharm)
        self.addCleanup(harness.cleanup)
        harness.begin()

        assert harness.charm._configure_pod() is None
