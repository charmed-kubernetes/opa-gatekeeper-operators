import unittest

# from unittest.mock import Mock

from ops.testing import Harness
from charm import OPAManagerCharm


class TestCharm(unittest.TestCase):
    def test_config_changed(self):
        harness = Harness(OPAManagerCharm)
        self.addCleanup(harness.cleanup)
        harness.begin()
        self.assertEqual(list(harness.charm._stored.things), [])
        print("Tests are TODO!")