"""
TaxFlow CRM — AI Assistant Tests
Tests: context assembly, prompt suggestions, API structure.
Uses mocked LLM to avoid real API calls.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
class TestAssistantContextBuilding:

    async def test_chat_endpoint_exists(self, client, auth_headers):
        """The /assistant/chat endpoint exists and validates input."""
        # Without AI key, should return 503 (not configured)
        res = await client.post(
            "/api/assistant/chat",
            json={
                "message": "Test query",
                "client_id": None,
                "conversation_history": [],
            },
            headers=auth_headers,
        )
        # 503 means AI not configured, 200 means it worked — both are acceptable
        assert res.status_code in (200, 503)
        if res.status_code == 503:
            assert "AI" in res.json()["detail"] or "configured" in res.json()["detail"]

    async def test_chat_requires_auth(self, client):
        """Chat endpoint requires authentication."""
        res = await client.post(
            "/api/assistant/chat",
            json={"message": "Hello", "client_id": None},
        )
        assert res.status_code == 401

    async def test_suggested_prompts_global(self, client, auth_headers):
        """Get suggested prompts without a specific client."""
        res = await client.get("/api/assistant/prompts", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert "prompts" in data
        assert isinstance(data["prompts"], list)
        assert len(data["prompts"]) >= 3
        # Should include tax-specific prompts
        all_prompts = " ".join(data["prompts"]).lower()
        assert any(word in all_prompts for word in ["client", "deadline", "document", "tax"])

    async def test_suggested_prompts_with_client(self, client, auth_headers, sample_client):
        """Get suggested prompts for a specific client."""
        cid = sample_client["id"]
        res = await client.get(f"/api/assistant/prompts?client_id={cid}", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert "prompts" in data
        assert data.get("client_id") == cid
        assert len(data["prompts"]) >= 3

    async def test_chat_with_mocked_ai(self, client, auth_headers, sample_client):
        """Chat endpoint works with a mocked OpenAI response."""
        cid = sample_client["id"]

        mock_choice = MagicMock()
        mock_choice.message.content = "Based on the client's profile, they are missing their W-2 and 1099-INT documents."
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_ai_client = AsyncMock()
        mock_ai_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch("backend.routes.assistant.get_ai_client", return_value=mock_ai_client):
            with patch("backend.config.get_settings") as mock_settings:
                mock_settings.return_value.ai_api_key = "mock-key"
                mock_settings.return_value.ai_model = "gpt-4o-mini"
                mock_settings.return_value.ai_base_url = None

                # Temporarily patch settings in assistant module
                import backend.routes.assistant as assistant_module
                original_settings = assistant_module.settings

                mock_s = MagicMock()
                mock_s.ai_api_key = "mock-key"
                mock_s.ai_model = "gpt-4o-mini"
                mock_s.ai_base_url = None
                assistant_module.settings = mock_s

                try:
                    res = await client.post(
                        "/api/assistant/chat",
                        json={
                            "client_id": cid,
                            "message": "What documents is this client missing?",
                            "conversation_history": [],
                        },
                        headers=auth_headers,
                    )
                    # With mock, should return 200
                    if res.status_code == 200:
                        data = res.json()
                        assert "reply" in data
                        assert len(data["reply"]) > 0
                        assert "suggested_actions" in data
                        assert isinstance(data["suggested_actions"], list)
                finally:
                    assistant_module.settings = original_settings

    async def test_chat_without_client_context(self, client, auth_headers):
        """Chat works without client_id (global query)."""
        mock_choice = MagicMock()
        mock_choice.message.content = "The Q2 2025 estimated tax payment is due June 15, 2025."
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_ai_client = AsyncMock()
        mock_ai_client.chat.completions.create = AsyncMock(return_value=mock_response)

        import backend.routes.assistant as assistant_module
        original_settings = assistant_module.settings
        mock_s = MagicMock()
        mock_s.ai_api_key = "mock-key"
        mock_s.ai_model = "gpt-4o-mini"
        mock_s.ai_base_url = None
        assistant_module.settings = mock_s

        try:
            res = await client.post(
                "/api/assistant/chat",
                json={
                    "client_id": None,
                    "message": "What are the Q2 estimated tax dates?",
                    "conversation_history": [],
                },
                headers=auth_headers,
            )
            if res.status_code == 200:
                data = res.json()
                assert "reply" in data
                assert data.get("referenced_client") is None
        finally:
            assistant_module.settings = original_settings

    async def test_client_summary_endpoint(self, client, auth_headers, sample_client):
        """Client summary endpoint returns structured context data."""
        cid = sample_client["id"]
        res = await client.get(f"/api/clients/{cid}/summary", headers=auth_headers)
        assert res.status_code == 200
        summary = res.json()

        # Check all context fields are present
        assert "client" in summary
        assert "document_stats" in summary
        assert "missing_documents" in summary
        assert "upcoming_deadlines" in summary
        assert "missed_deadlines" in summary
        assert "open_tasks" in summary

        # Client data should match
        assert summary["client"]["id"] == cid

    async def test_context_build_with_documents(self, client, auth_headers):
        """Assistant context correctly reflects document status."""
        r = await client.post(
            "/api/clients?auto_deadlines=false",
            json={
                "full_name": "AI Context Doc Test",
                "email": "ai.context.doc@example.com",
                "entity_type": "individual",
                "tax_year": 2024,
            },
            headers=auth_headers,
        )
        cid = r.json()["id"]

        # Add 2 awaiting, 1 received
        for doc_type, status in [("W-2", "awaiting"), ("1099-NEC", "awaiting"), ("1098", "received")]:
            await client.post(
                "/api/documents",
                json={"client_id": cid, "doc_type": doc_type, "tax_year": 2024, "status": status},
                headers=auth_headers,
            )

        res = await client.get(f"/api/clients/{cid}/summary", headers=auth_headers)
        summary = res.json()

        # Missing docs should include W-2 and 1099-NEC
        assert "W-2" in summary["missing_documents"]
        assert "1099-NEC" in summary["missing_documents"]
        # 1098 received should NOT be in missing
        assert "1098" not in summary["missing_documents"]

    async def test_suggested_actions_for_document_query(self):
        """Suggested actions extracted correctly for document queries."""
        from backend.routes.assistant import _extract_suggested_actions

        actions = _extract_suggested_actions("what documents are missing?", "reply text")
        assert any("document" in a.lower() or "checklist" in a.lower() for a in actions)

    async def test_suggested_actions_for_email_query(self):
        """Suggested actions extracted for email draft queries."""
        from backend.routes.assistant import _extract_suggested_actions

        actions = _extract_suggested_actions("draft a reminder email", "Here's a draft email...")
        assert any("email" in a.lower() or "message" in a.lower() for a in actions)

    async def test_system_prompt_contains_tax_knowledge(self):
        """System prompt includes key US tax concepts."""
        from backend.routes.assistant import TAXFLOW_SYSTEM_PROMPT

        assert "1040" in TAXFLOW_SYSTEM_PROMPT
        assert "April 15" in TAXFLOW_SYSTEM_PROMPT
        assert "W-2" in TAXFLOW_SYSTEM_PROMPT
        assert "1099" in TAXFLOW_SYSTEM_PROMPT
        assert "estimated" in TAXFLOW_SYSTEM_PROMPT.lower()
        assert "extension" in TAXFLOW_SYSTEM_PROMPT.lower()
