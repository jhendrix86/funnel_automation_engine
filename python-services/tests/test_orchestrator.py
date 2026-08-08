"""
Tests for orchestrator.py - the central coordinator wiring together content,
email, lead, conversion, gumroad, traffic, and social services.

The multi-service funnel-creation/launch flows (create_autonomous_funnel,
_execute_funnel_launch, etc.) call out to six other HTTP services and are not
covered here - they need a broader integration harness. This suite covers the
pure helpers and the self-contained CRUD endpoints.
"""
from datetime import datetime

from bson import ObjectId


class TestToObjectId:
    def test_valid_hex_string_becomes_object_id(self, orchestrator_module):
        oid = ObjectId()
        result = orchestrator_module._to_object_id(str(oid))
        assert result == oid

    def test_invalid_string_is_returned_unchanged(self, orchestrator_module):
        result = orchestrator_module._to_object_id("not-a-valid-id")
        assert result == "not-a-valid-id"

    def test_non_string_is_returned_unchanged(self, orchestrator_module):
        # bson.ObjectId(None) generates a fresh id rather than raising - only
        # genuinely incompatible types (e.g. int) hit the TypeError branch.
        result = orchestrator_module._to_object_id(123)
        assert result == 123


class TestSerializeDoc:
    def test_none_returns_none(self, orchestrator_module):
        assert orchestrator_module._serialize_doc(None) is None

    def test_object_id_becomes_string(self, orchestrator_module):
        oid = ObjectId()
        result = orchestrator_module._serialize_doc({"_id": oid})
        assert result["_id"] == str(oid)

    def test_datetime_becomes_isoformat(self, orchestrator_module):
        now = datetime(2026, 1, 1, 12, 0, 0)
        result = orchestrator_module._serialize_doc({"created_at": now})
        assert result["created_at"] == now.isoformat()


class TestNormalizeGumroadProduct:
    def test_prefers_product_id_over_id(self, orchestrator_module):
        result = orchestrator_module._normalize_gumroad_product(
            {"product_id": "p1", "id": "p2"}
        )
        assert result["product_id"] == "p1"

    def test_falls_back_to_id(self, orchestrator_module):
        result = orchestrator_module._normalize_gumroad_product({"id": "p2"})
        assert result["product_id"] == "p2"

    def test_string_tag_is_wrapped_in_list(self, orchestrator_module):
        result = orchestrator_module._normalize_gumroad_product(
            {"id": "p1", "tags": "single-tag"}
        )
        assert result["tags"] == ["single-tag"]

    def test_price_is_coerced_to_float(self, orchestrator_module):
        result = orchestrator_module._normalize_gumroad_product({"id": "p1", "price": "19.99"})
        assert result["price"] == 19.99

    def test_missing_price_defaults_to_zero(self, orchestrator_module):
        result = orchestrator_module._normalize_gumroad_product({"id": "p1"})
        assert result["price"] == 0.0

    def test_missing_optional_fields_get_safe_defaults(self, orchestrator_module):
        result = orchestrator_module._normalize_gumroad_product({"id": "p1"})
        assert result["name"] == ""
        assert result["description"] == ""
        assert result["url"] == ""
        assert result["published"] is False
        assert result["tags"] == []


class TestEndpoints:
    def test_health_check(self, orchestrator_client):
        response = orchestrator_client.get("/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert body["service"] == "orchestrator"

    def test_get_funnels_empty(self, orchestrator_client):
        response = orchestrator_client.get("/funnels")

        assert response.status_code == 200
        assert response.json()["funnels"] == []

    def test_get_funnels_filters_by_status(self, orchestrator_client, orchestrator_module):
        orchestrator_module.funnels_collection.insert_many([
            {"name": "Active Funnel", "status": "active"},
            {"name": "Paused Funnel", "status": "paused"},
        ])

        response = orchestrator_client.get("/funnels", params={"status": "active"})

        assert response.status_code == 200
        funnels = response.json()["funnels"]
        assert len(funnels) == 1
        assert funnels[0]["name"] == "Active Funnel"

    def test_get_funnel_not_found_returns_404(self, orchestrator_client):
        response = orchestrator_client.get(f"/funnel/{ObjectId()}")

        assert response.status_code == 404

    def test_get_funnel_includes_related_workflows(self, orchestrator_client, orchestrator_module):
        funnel_id = orchestrator_module.funnels_collection.insert_one(
            {"name": "My Funnel", "status": "active"}
        ).inserted_id
        orchestrator_module.automation_workflows_collection.insert_one(
            {"funnel_id": str(funnel_id), "workflow_name": "nurture"}
        )

        response = orchestrator_client.get(f"/funnel/{funnel_id}")

        assert response.status_code == 200
        body = response.json()
        assert body["funnel"]["name"] == "My Funnel"
        assert len(body["workflows"]) == 1

    def test_delete_funnel_cascades_related_collections(self, orchestrator_client, orchestrator_module):
        funnel_id = orchestrator_module.funnels_collection.insert_one(
            {"name": "Doomed Funnel", "status": "active"}
        ).inserted_id
        orchestrator_module.automation_workflows_collection.insert_one(
            {"funnel_id": str(funnel_id)}
        )
        orchestrator_module.db.leads.insert_one({"funnel_id": str(funnel_id)})

        response = orchestrator_client.delete(f"/funnel/{funnel_id}")

        assert response.status_code == 200
        assert orchestrator_module.funnels_collection.find_one({"_id": funnel_id}) is None
        assert orchestrator_module.automation_workflows_collection.count_documents(
            {"funnel_id": str(funnel_id)}
        ) == 0
        assert orchestrator_module.db.leads.count_documents({"funnel_id": str(funnel_id)}) == 0

    def test_pause_funnel_updates_status(self, orchestrator_client, orchestrator_module):
        funnel_id = orchestrator_module.funnels_collection.insert_one(
            {"name": "Running Funnel", "status": "active"}
        ).inserted_id
        orchestrator_module.automation_workflows_collection.insert_one(
            {"funnel_id": str(funnel_id), "status": "active"}
        )

        response = orchestrator_client.post(f"/funnel/{funnel_id}/pause")

        assert response.status_code == 200
        assert response.json()["status"] == "paused"
        updated = orchestrator_module.funnels_collection.find_one({"_id": funnel_id})
        assert updated["status"] == "paused"
        workflow = orchestrator_module.automation_workflows_collection.find_one(
            {"funnel_id": str(funnel_id)}
        )
        assert workflow["status"] == "paused"

    def test_resume_funnel_updates_status_and_schedules_optimization(
        self, orchestrator_client, orchestrator_module, monkeypatch
    ):
        started = {}

        async def fake_run_continuous_optimization(funnel_id):
            started["funnel_id"] = funnel_id

        monkeypatch.setattr(
            orchestrator_module, "run_continuous_optimization", fake_run_continuous_optimization
        )

        funnel_id = orchestrator_module.funnels_collection.insert_one(
            {"name": "Paused Funnel", "status": "paused"}
        ).inserted_id

        response = orchestrator_client.post(f"/funnel/{funnel_id}/resume")

        assert response.status_code == 200
        assert response.json()["status"] == "active"
        updated = orchestrator_module.funnels_collection.find_one({"_id": funnel_id})
        assert updated["status"] == "active"
        assert started["funnel_id"] == str(funnel_id)
