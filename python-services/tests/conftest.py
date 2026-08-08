"""
Shared pytest fixtures for the funnel_automation_engine python-services.

Each service module is a standalone script (no shared package), and each
opens a real pymongo MongoClient at import time. Tests never talk to a real
Mongo instance: fixtures below swap each module's module-level `db` and
collection globals for a fresh mongomock in-memory database per test.
"""
import sys
from pathlib import Path

import mongomock
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def social_media_module():
    import social_media as module

    fake_client = mongomock.MongoClient()
    module.mongo_client = fake_client
    module.db = fake_client.traffic_funnel
    module.social_posts_collection = module.db.social_posts
    module.social_campaigns_collection = module.db.social_campaigns
    module.social_analytics_collection = module.db.social_analytics
    return module


@pytest.fixture
def social_media_client(social_media_module):
    return TestClient(social_media_module.app)


@pytest.fixture
def orchestrator_module():
    import orchestrator as module

    fake_client = mongomock.MongoClient()
    module.mongo_client = fake_client
    module.db = fake_client.traffic_funnel
    module.funnels_collection = module.db.funnels
    module.orchestrator_logs_collection = module.db.orchestrator_logs
    module.automation_workflows_collection = module.db.automation_workflows
    return module


@pytest.fixture
def orchestrator_client(orchestrator_module):
    return TestClient(orchestrator_module.app)
