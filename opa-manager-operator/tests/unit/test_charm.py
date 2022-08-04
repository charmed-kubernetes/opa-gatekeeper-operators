import unittest
import os
from unittest.mock import patch
from ops.testing import Harness
from pathlib import Path
from charm import OPAManagerCharm


class TestCharm(unittest.TestCase):
    def test_on_config_changed(self):
        harness = Harness(OPAManagerCharm)
        self.addCleanup(harness.cleanup)
        harness.begin()

        assert harness.charm._on_config_changed({}) is None

    def test_on_stop(self):
        harness = Harness(OPAManagerCharm)
        self.addCleanup(harness.cleanup)
        harness.begin()

        assert harness.charm._cleanup({}) is None

