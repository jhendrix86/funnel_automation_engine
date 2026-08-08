"""
Tests for social_media.py - the fleet's only service with real (working)
external platform posting logic (Twitter API v2, LinkedIn UGC API).
"""
from datetime import datetime

import aiohttp
import pytest
from bson import ObjectId


class _FakeResponse:
    """Minimal async-context-manager stand-in for aiohttp's response object."""

    def __init__(self, status):
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False


def _mock_session_post(monkeypatch, status):
    """Patch aiohttp.ClientSession.post to return a fixed-status fake response."""

    def fake_post(self, url, **kwargs):
        return _FakeResponse(status)

    monkeypatch.setattr(aiohttp.ClientSession, "post", fake_post)


class TestSerializeDoc:
    def test_none_returns_none(self, social_media_module):
        assert social_media_module._serialize_doc(None) is None

    def test_object_id_becomes_string(self, social_media_module):
        oid = ObjectId()
        result = social_media_module._serialize_doc({"_id": oid})
        assert result["_id"] == str(oid)
        assert isinstance(result["_id"], str)

    def test_datetime_becomes_isoformat(self, social_media_module):
        now = datetime(2026, 1, 1, 12, 0, 0)
        result = social_media_module._serialize_doc({"created_at": now})
        assert result["created_at"] == now.isoformat()

    def test_nested_dict_is_recursively_serialized(self, social_media_module):
        oid = ObjectId()
        result = social_media_module._serialize_doc({"analytics": {"owner": oid}})
        assert result["analytics"]["owner"] == str(oid)

    def test_list_of_mixed_types_is_serialized(self, social_media_module):
        oid = ObjectId()
        now = datetime(2026, 1, 1)
        result = social_media_module._serialize_doc(
            {"items": [{"id": oid}, oid, now, "plain"]}
        )
        assert result["items"][0]["id"] == str(oid)
        assert result["items"][1] == str(oid)
        assert result["items"][2] == now.isoformat()
        assert result["items"][3] == "plain"


class TestPostToTwitter:
    @pytest.mark.asyncio
    async def test_returns_false_without_credentials(self, social_media_module, monkeypatch):
        monkeypatch.setattr(social_media_module, "TWITTER_API_KEY", None)
        monkeypatch.setattr(social_media_module, "TWITTER_API_SECRET", None)
        monkeypatch.setattr(social_media_module, "TWITTER_ACCESS_TOKEN", None)
        monkeypatch.setattr(social_media_module, "TWITTER_ACCESS_SECRET", None)

        result = await social_media_module.post_to_twitter("hello world")

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_on_201(self, social_media_module, monkeypatch):
        monkeypatch.setattr(social_media_module, "TWITTER_API_KEY", "key")
        monkeypatch.setattr(social_media_module, "TWITTER_API_SECRET", "secret")
        monkeypatch.setattr(social_media_module, "TWITTER_ACCESS_TOKEN", "token")
        monkeypatch.setattr(social_media_module, "TWITTER_ACCESS_SECRET", "access-secret")
        _mock_session_post(monkeypatch, status=201)

        result = await social_media_module.post_to_twitter("hello world")

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_on_non_201(self, social_media_module, monkeypatch):
        monkeypatch.setattr(social_media_module, "TWITTER_API_KEY", "key")
        monkeypatch.setattr(social_media_module, "TWITTER_API_SECRET", "secret")
        monkeypatch.setattr(social_media_module, "TWITTER_ACCESS_TOKEN", "token")
        monkeypatch.setattr(social_media_module, "TWITTER_ACCESS_SECRET", "access-secret")
        _mock_session_post(monkeypatch, status=403)

        result = await social_media_module.post_to_twitter("hello world")

        assert result is False


class TestPostToLinkedin:
    @pytest.mark.asyncio
    async def test_returns_false_without_credentials(self, social_media_module, monkeypatch):
        monkeypatch.setattr(social_media_module, "LINKEDIN_ACCESS_TOKEN", None)

        result = await social_media_module.post_to_linkedin("hello world")

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_on_201(self, social_media_module, monkeypatch):
        monkeypatch.setattr(social_media_module, "LINKEDIN_ACCESS_TOKEN", "token")
        _mock_session_post(monkeypatch, status=201)

        result = await social_media_module.post_to_linkedin("hello world")

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_on_non_201(self, social_media_module, monkeypatch):
        monkeypatch.setattr(social_media_module, "LINKEDIN_ACCESS_TOKEN", "token")
        _mock_session_post(monkeypatch, status=401)

        result = await social_media_module.post_to_linkedin("hello world")

        assert result is False


class TestPostToPlatform:
    @pytest.mark.asyncio
    async def test_successful_post_marks_status_posted(self, social_media_module, monkeypatch):
        post_id = social_media_module.social_posts_collection.insert_one({
            "platform": "twitter",
            "content": "hello",
            "hashtags": [],
            "status": "pending",
        }).inserted_id

        async def fake_post_to_twitter(content):
            return True

        monkeypatch.setattr(social_media_module, "post_to_twitter", fake_post_to_twitter)

        await social_media_module.post_to_platform(str(post_id))

        updated = social_media_module.social_posts_collection.find_one({"_id": post_id})
        assert updated["status"] == "posted"
        assert updated["posted_at"] is not None

    @pytest.mark.asyncio
    async def test_failed_post_marks_status_failed(self, social_media_module, monkeypatch):
        post_id = social_media_module.social_posts_collection.insert_one({
            "platform": "twitter",
            "content": "hello",
            "hashtags": [],
            "status": "pending",
        }).inserted_id

        async def fake_post_to_twitter(content):
            return False

        monkeypatch.setattr(social_media_module, "post_to_twitter", fake_post_to_twitter)

        await social_media_module.post_to_platform(str(post_id))

        updated = social_media_module.social_posts_collection.find_one({"_id": post_id})
        assert updated["status"] == "failed"

    @pytest.mark.asyncio
    async def test_unknown_platform_marks_status_failed(self, social_media_module):
        post_id = social_media_module.social_posts_collection.insert_one({
            "platform": "myspace",
            "content": "hello",
            "hashtags": [],
            "status": "pending",
        }).inserted_id

        await social_media_module.post_to_platform(str(post_id))

        updated = social_media_module.social_posts_collection.find_one({"_id": post_id})
        assert updated["status"] == "failed"


class TestEndpoints:
    def test_health_check(self, social_media_client):
        response = social_media_client.get("/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert body["service"] == "social-media"

    def test_create_post_without_schedule_runs_immediately(self, social_media_client, social_media_module, monkeypatch):
        monkeypatch.setattr(social_media_module, "TWITTER_API_KEY", None)

        response = social_media_client.post("/post/create", json={
            "platform": "twitter",
            "content": "Check out our launch!",
            "hashtags": ["launch"],
        })

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "success"
        assert "post_id" in body

        stored = social_media_module.social_posts_collection.find_one(
            {"_id": ObjectId(body["post_id"])}
        )
        # No Twitter credentials configured -> background post attempt fails honestly
        assert stored["status"] == "failed"

    def test_get_posts_filters_by_platform(self, social_media_client, social_media_module):
        social_media_module.social_posts_collection.insert_many([
            {"platform": "twitter", "content": "a", "created_at": datetime.now()},
            {"platform": "linkedin", "content": "b", "created_at": datetime.now()},
        ])

        response = social_media_client.get("/posts", params={"platform": "twitter"})

        assert response.status_code == 200
        posts = response.json()["posts"]
        assert len(posts) == 1
        assert posts[0]["platform"] == "twitter"

    def test_create_campaign_inserts_and_starts_background_run(
        self, social_media_client, social_media_module, monkeypatch
    ):
        started = {}

        async def fake_run_campaign(campaign_id):
            started["campaign_id"] = campaign_id

        monkeypatch.setattr(social_media_module, "run_campaign", fake_run_campaign)

        response = social_media_client.post("/campaign/create", json={
            "name": "Launch Week",
            "funnel_id": "funnel-1",
            "platforms": ["twitter"],
            "start_date": "2026-01-01T00:00:00",
            "end_date": "2026-01-08T00:00:00",
            "posts_per_day": 2,
        })

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "success"
        assert started["campaign_id"] == body["campaign_id"]

        stored = social_media_module.social_campaigns_collection.find_one(
            {"_id": ObjectId(body["campaign_id"])}
        )
        assert stored["name"] == "Launch Week"
        assert stored["status"] == "active"

    def test_get_campaigns_filters_by_funnel(self, social_media_client, social_media_module):
        social_media_module.social_campaigns_collection.insert_many([
            {"name": "A", "funnel_id": "f1"},
            {"name": "B", "funnel_id": "f2"},
        ])

        response = social_media_client.get("/campaigns", params={"funnel_id": "f1"})

        assert response.status_code == 200
        campaigns = response.json()["campaigns"]
        assert len(campaigns) == 1
        assert campaigns[0]["name"] == "A"
