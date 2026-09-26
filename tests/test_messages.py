"""
TaxFlow CRM — Message Tests
Tests: message thread, read status, portal auth, SSE endpoint.
"""
import pytest


@pytest.mark.asyncio
class TestMessageThread:

    async def test_send_staff_message(self, client, auth_headers, sample_client):
        """Staff can send a message to a client."""
        cid = sample_client["id"]
        res = await client.post(
            f"/api/messages/client/{cid}/send",
            json={"client_id": cid, "content": "Hello from staff!"},
            headers=auth_headers,
        )
        assert res.status_code == 201
        msg = res.json()
        assert msg["sender_role"] == "staff"
        assert msg["content"] == "Hello from staff!"
        assert msg["client_id"] == cid
        assert "id" in msg
        assert "created_at" in msg

    async def test_get_client_messages(self, client, auth_headers, sample_client):
        """Staff can retrieve message thread for a client."""
        cid = sample_client["id"]
        # Send a message first
        await client.post(
            f"/api/messages/client/{cid}/send",
            json={"client_id": cid, "content": "Thread test message"},
            headers=auth_headers,
        )

        res = await client.get(f"/api/messages/client/{cid}", headers=auth_headers)
        assert res.status_code == 200
        messages = res.json()
        assert isinstance(messages, list)
        assert any(m["content"] == "Thread test message" for m in messages)

    async def test_messages_ordered_chronologically(self, client, auth_headers, sample_client):
        """Messages are returned in chronological order (oldest first)."""
        cid = sample_client["id"]
        for i in range(3):
            await client.post(
                f"/api/messages/client/{cid}/send",
                json={"client_id": cid, "content": f"Message {i}"},
                headers=auth_headers,
            )

        res = await client.get(f"/api/messages/client/{cid}", headers=auth_headers)
        messages = res.json()
        # Timestamps should be ascending
        timestamps = [m["created_at"] for m in messages if m["created_at"]]
        assert timestamps == sorted(timestamps)

    async def test_mark_messages_read(self, client, auth_headers, sample_client):
        """Staff can mark messages as read."""
        cid = sample_client["id"]
        res = await client.post(f"/api/messages/client/{cid}/read", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert "marked_read" in data

    async def test_get_all_threads(self, client, auth_headers):
        """Get all message threads for inbox view."""
        res = await client.get("/api/messages/threads", headers=auth_headers)
        assert res.status_code == 200
        threads = res.json()
        assert isinstance(threads, list)

    async def test_message_for_nonexistent_client(self, client, auth_headers):
        """Cannot send message to non-existent client."""
        res = await client.post(
            "/api/messages/client/999999/send",
            json={"client_id": 999999, "content": "Ghost message"},
            headers=auth_headers,
        )
        assert res.status_code == 404

    async def test_requires_auth_for_messages(self, client, sample_client):
        """Unauthenticated requests rejected."""
        cid = sample_client["id"]
        res = await client.get(f"/api/messages/client/{cid}")
        assert res.status_code == 401


@pytest.mark.asyncio
class TestClientPortal:

    async def test_portal_login_with_valid_credentials(self, client, auth_headers):
        """Client can log in to portal with correct credentials."""
        # Create client with portal password
        r = await client.post(
            "/api/clients?auto_deadlines=false",
            json={
                "full_name": "Portal Test Client",
                "email": "portal.test@example.com",
                "entity_type": "individual",
                "tax_year": 2024,
                "portal_password": "PortalPass123",
            },
            headers=auth_headers,
        )
        assert r.status_code == 201

        # Log in to portal
        res = await client.post(
            "/api/auth/portal/login",
            json={"email": "portal.test@example.com", "password": "PortalPass123"},
        )
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert data["client_name"] == "Portal Test Client"

    async def test_portal_login_wrong_password(self, client, auth_headers):
        """Portal login fails with wrong password."""
        await client.post(
            "/api/clients?auto_deadlines=false",
            json={
                "full_name": "Wrong Pass Test",
                "email": "wrong.pass@example.com",
                "entity_type": "individual",
                "tax_year": 2024,
                "portal_password": "RightPass456",
            },
            headers=auth_headers,
        )

        res = await client.post(
            "/api/auth/portal/login",
            json={"email": "wrong.pass@example.com", "password": "WrongPass999"},
        )
        assert res.status_code == 401

    async def test_portal_login_no_password_set(self, client, auth_headers):
        """Portal login fails if no portal password has been set."""
        await client.post(
            "/api/clients?auto_deadlines=false",
            json={
                "full_name": "No Portal Pass",
                "email": "no.portal.pass@example.com",
                "entity_type": "individual",
                "tax_year": 2024,
            },
            headers=auth_headers,
        )

        res = await client.post(
            "/api/auth/portal/login",
            json={"email": "no.portal.pass@example.com", "password": "anything"},
        )
        assert res.status_code == 401

    async def test_portal_can_read_own_messages(self, client, auth_headers):
        """Client portal can read their own message thread."""
        r = await client.post(
            "/api/clients?auto_deadlines=false",
            json={
                "full_name": "Portal Reader Test",
                "email": "portal.reader@example.com",
                "entity_type": "individual",
                "tax_year": 2024,
                "portal_password": "ReadMyMsgs",
            },
            headers=auth_headers,
        )
        cid = r.json()["id"]

        # Staff sends a message
        await client.post(
            f"/api/messages/client/{cid}/send",
            json={"client_id": cid, "content": "Hello from your accountant"},
            headers=auth_headers,
        )

        # Client logs in
        portal_res = await client.post(
            "/api/auth/portal/login",
            json={"email": "portal.reader@example.com", "password": "ReadMyMsgs"},
        )
        portal_token = portal_res.json()["access_token"]
        portal_headers = {"Authorization": f"Bearer {portal_token}"}

        # Read messages via portal endpoint
        msgs_res = await client.get("/api/portal/messages", headers=portal_headers)
        assert msgs_res.status_code == 200
        messages = msgs_res.json()
        assert any(m["content"] == "Hello from your accountant" for m in messages)

    async def test_portal_can_send_message(self, client, auth_headers):
        """Client portal can send a message to staff."""
        r = await client.post(
            "/api/clients?auto_deadlines=false",
            json={
                "full_name": "Portal Sender Test",
                "email": "portal.sender@example.com",
                "entity_type": "individual",
                "tax_year": 2024,
                "portal_password": "SendMsg456",
            },
            headers=auth_headers,
        )
        cid = r.json()["id"]

        portal_res = await client.post(
            "/api/auth/portal/login",
            json={"email": "portal.sender@example.com", "password": "SendMsg456"},
        )
        portal_token = portal_res.json()["access_token"]
        portal_headers = {"Authorization": f"Bearer {portal_token}"}

        # Send message as client
        send_res = await client.post(
            "/api/portal/messages/send",
            json={"client_id": cid, "content": "Hi, I have a question about my W-2"},
            headers=portal_headers,
        )
        assert send_res.status_code == 201
        msg = send_res.json()
        assert msg["sender_role"] == "client"
        assert msg["content"] == "Hi, I have a question about my W-2"

    async def test_staff_token_rejected_on_portal_endpoint(self, client, auth_headers):
        """Staff JWT cannot access client portal endpoint."""
        res = await client.get("/api/portal/messages", headers=auth_headers)
        assert res.status_code == 403
