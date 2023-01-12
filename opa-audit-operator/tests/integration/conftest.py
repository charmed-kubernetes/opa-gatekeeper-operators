import logging
import os
from pathlib import Path

import pytest
import pytest_asyncio
from lightkube import Client, KubeConfig

log = logging.getLogger(__name__)
KUBECONFIG = os.environ.get("TESTING_KUBECONFIG", "~/.kube/config")


@pytest.fixture(scope="module")
def client():
    return Client(config=KubeConfig.from_file(KUBECONFIG), field_manager="integration")


@pytest_asyncio.fixture(scope="module")
async def charm(ops_test):
    _charm = next(Path(".").glob("gatekeeper-audit*.charm"), None)
    if not _charm:
        log.info("Building Charm...")
        _charm = await ops_test.build_charm(".")
    return _charm
