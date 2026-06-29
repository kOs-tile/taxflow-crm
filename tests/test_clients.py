"""
TaxFlow CRM — Client Tests
Tests: CRUD operations, search/filter, document completion calculation.
"""
import pytest
import pytest_asyncio


@pytest.mark.asyncio
class TestClientCRUD:

    async def test_create_individual_client(self, client, auth_headers):
        """Create a basic individual client."""
        res = await client.post(
            "/api/clients?auto_deadlines=false",
            json={
                "full_name": "Alice Johnson",
                "email": "alice.johnson.test@example.com",
                "entity_type": "individual",
                "tax_year": 2024,
                "filing_status": "single",
                "state": "CA",
            },
            headers=auth_headers,
        )
        assert res.status_code == 201
        data = res.json()
        assert data["full_name"] == "Alice Johnson"
        assert data["entity_type"] == "individual"
        assert data["tax_year"] == 2024
        assert data["id"] > 0
        return data

    async def test_create_llc_client(self, client, auth_headers):
        """Create an LLC client."""
        res = await client.post(
            "/api/clients?auto_deadlines=false",
            json={
                "full_name": "Test Consulting LLC",
                "email": "test.llc@example.com",
                "entity_type": "llc",
                "tax_year": 2024,
                "ein": "12-3456789",
            },
            headers=auth_headers,
        )
        assert res.status_code == 201
        data = res.json()
        assert data["entity_type"] == "llc"
        assert data["ein"] == "12-3456789"

    async def test_create_scorp_client(self, client, auth_headers):
        """Create an S-Corp client."""
        res = await client.post(
            "/api/clients?auto_deadlines=false",
            json={
                "full_name": "My S-Corp Inc",
                "email": "my.scorp.test@example.com",
                "entity_type": "s_corp",
                "tax_year": 2024,
            },
            headers=auth_headers,
        )
        assert res.status_code == 201
        assert res.json()["entity_type"] == "s_corp"

    async def test_duplicate_email_rejected(self, client, auth_headers):
        """Cannot create two clients with the same email."""
        payload = {
            "full_name": "Duplicate Test",
            "email": "unique.test@example.com",
            "entity_type": "individual",
            "tax_year": 2024,
        }
        r1 = await client.post("/api/clients?auto_deadlines=false", json=payload, headers=auth_headers)
        assert r1.status_code == 201

        r2 = await client.post("/api/clients?auto_deadlines=false", json=payload, headers=auth_headers)
        # Should fail with 409 or 500 (unique constraint)
        assert r2.status_code in (409, 400, 500)

    async def test_get_client(self, client, auth_headers, sample_client):
        """Get a specific client by ID."""
        client_id = sample_client["id"]
        res = await client.get(f"/api/clients/{client_id}", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["id"] == client_id
        assert data["full_name"] == sample_client["full_name"]

    async def test_get_nonexistent_client(self, client, auth_headers):
        """404 for non-existent client."""
        res = await client.get("/api/clients/999999", headers=auth_headers)
        assert res.status_code == 404

    async def test_update_client(self, client, auth_headers, sample_client):
        """Partially update a client."""
        client_id = sample_client["id"]
        res = await client.patch(
            f"/api/clients/{client_id}",
            json={"notes": "Updated notes for testing"},
            headers=auth_headers,
        )
        assert res.status_code == 200
        assert res.json()["notes"] == "Updated notes for testing"

    async def test_list_clients(self, client, auth_headers):
        """List all clients."""
        res = await client.get("/api/clients?enrich=false", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    async def test_search_clients(self, client, auth_headers):
        """Search clients by name."""
        # Create a uniquely named client
        unique_name = "UniqueSearchableClient XYZ"
        await client.post(
            "/api/clients?auto_deadlines=false",
            json={
                "full_name": unique_name,
                "email": "unique.searchable@example.com",
                "entity_type": "individual",
                "tax_year": 2024,
            },
            headers=auth_headers,
        )
        res = await client.get(
            "/api/clients?search=UniqueSearchableClient&enrich=false",
            headers=auth_headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert any(c["full_name"] == unique_name for c in data)

    async def test_filter_by_entity_type(self, client, auth_headers):
        """Filter clients by entity type."""
        res = await client.get(
            "/api/clients?entity_type=individual&enrich=false",
            headers=auth_headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert all(c["entity_type"] == "individual" for c in data)

    async def test_requires_auth(self, client):
        """Unauthenticated requests are rejected."""
        res = await client.get("/api/clients")
        assert res.status_code == 401


@pytest.mark.asyncio
class TestDocumentCompletion:

    async def test_empty_checklist_is_zero(self, client, auth_headers, sample_client):
        """Client with no documents has 0% completion."""
        cid = sample_client["id"]
        res = await client.get(f"/api/documents/client/{cid}/stats", headers=auth_headers)
        assert res.status_code == 200
        stats = res.json()
        assert stats["completion_pct"] == 0.0
        assert stats["total"] == 0

    async def test_initialize_document_checklist(self, client, auth_headers):
        """Initialize creates standard docs for entity type."""
        # Create individual client
        r = await client.post(
            "/api/clients?auto_deadlines=false",
            json={
                "full_name": "Doc Init Test",
                "email": "doc.init.test@example.com",
                "entity_type": "individual",
                "tax_year": 2024,
            },
            headers=auth_headers,
        )
        cid = r.json()["id"]

        res = await client.post(f"/api/documents/client/{cid}/initialize", headers=auth_headers)
        assert res.status_code == 201
        data = res.json()
        assert data["created"] > 0

        # Verify documents exist
        docs_res = await client.get(f"/api/documents/client/{cid}", headers=auth_headers)
        docs = docs_res.json()
        assert len(docs) > 0
        assert all(d["status"] == "awaiting" for d in docs)

    async def test_document_status_flow(self, client, auth_headers):
        """Document progresses awaiting → received → reviewed."""
        # Create client and add document
        r = await client.post(
            "/api/clients?auto_deadlines=false",
            json={
                "full_name": "Status Flow Test",
                "email": "status.flow.test@example.com",
                "entity_type": "individual",
                "tax_year": 2024,
            },
            headers=auth_headers,
        )
        cid = r.json()["id"]

        doc_r = await client.post(
            "/api/documents",
            json={"client_id": cid, "doc_type": "W-2", "tax_year": 2024, "status": "awaiting"},
            headers=auth_headers,
        )
        assert doc_r.status_code == 201
        doc_id = doc_r.json()["id"]

        # Mark received
        r2 = await client.patch(
            f"/api/documents/{doc_id}",
            json={"status": "received"},
            headers=auth_headers,
        )
        assert r2.status_code == 200
        assert r2.json()["status"] == "received"
        assert r2.json()["received_at"] is not None

        # Mark reviewed
        r3 = await client.patch(
            f"/api/documents/{doc_id}",
            json={"status": "reviewed"},
            headers=auth_headers,
        )
        assert r3.status_code == 200
        assert r3.json()["status"] == "reviewed"

    async def test_completion_percentage_calculation(self, client, auth_headers):
        """Document completion % = (received + reviewed) / applicable * 100."""
        r = await client.post(
            "/api/clients?auto_deadlines=false",
            json={
                "full_name": "Completion Pct Test",
                "email": "completion.pct.test@example.com",
                "entity_type": "individual",
                "tax_year": 2024,
            },
            headers=auth_headers,
        )
        cid = r.json()["id"]

        # Add 4 documents
        doc_ids = []
        for doc_type in ["W-2", "1099-NEC", "1099-INT", "Prior Year Return"]:
            dr = await client.post(
                "/api/documents",
                json={"client_id": cid, "doc_type": doc_type, "tax_year": 2024, "status": "awaiting"},
                headers=auth_headers,
            )
            doc_ids.append(dr.json()["id"])

        # Mark 2 as received
        for did in doc_ids[:2]:
            await client.patch(f"/api/documents/{did}", json={"status": "received"}, headers=auth_headers)

        stats = (await client.get(f"/api/documents/client/{cid}/stats", headers=auth_headers)).json()
        assert stats["total"] == 4
        assert stats["received"] == 2
        assert stats["awaiting"] == 2
        assert stats["completion_pct"] == 50.0

    async def test_not_applicable_excluded_from_completion(self, client, auth_headers):
        """N/A documents don't count toward completion denominator."""
        r = await client.post(
            "/api/clients?auto_deadlines=false",
            json={
                "full_name": "NA Exclusion Test",
                "email": "na.exclusion.test@example.com",
                "entity_type": "individual",
                "tax_year": 2024,
            },
            headers=auth_headers,
        )
        cid = r.json()["id"]

        # 2 applicable, 1 N/A
        for doc_type, status in [("W-2", "received"), ("1099-NEC", "awaiting"), ("K-1", "not_applicable")]:
            await client.post(
                "/api/documents",
                json={"client_id": cid, "doc_type": doc_type, "tax_year": 2024, "status": status},
                headers=auth_headers,
            )

        stats = (await client.get(f"/api/documents/client/{cid}/stats", headers=auth_headers)).json()
        # 1 received / 2 applicable = 50%
        assert stats["completion_pct"] == 50.0
        assert stats["not_applicable"] == 1
