import logging
from pathlib import Path

import pytest
import yaml
from pytest_operator import OperatorTest


log = logging.getLogger(__name__)


class IntegrationTests(OperatorTest):
    meta = yaml.safe_load(Path("metadata.yaml").read_text())

    @pytest.mark.order("first")
    @pytest.mark.abort_on_fail
    async def test_build_and_deploy(self):
        charm = await self.build_charm(".")
        for series in self.meta["series"]:
            await self.model.deploy(charm, application_name=series, series=series)
        await self.model.wait_for_idle(wait_for_active=True, timeout=60 * 60)

    async def test_status_messages(self):
        """ Validate that the status messages are correct. """
        expected_messages = {}
        for series in self.meta["series"]:
            expected_messages[series] = "Active and running"
        for app, message in expected_messages.items():
            for unit in self.model.applications[app].units:
                assert unit.workload_status_message == message
