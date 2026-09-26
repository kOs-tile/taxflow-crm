"""
TaxFlow CRM — Deadline Tests
Tests: auto-generation logic, upcoming deadline query, status transitions.
"""
import pytest
from datetime import date, timedelta


@pytest.mark.asyncio
class TestDeadlineAutoGeneration:

    async def test_individual_deadlines_generated(self, client, auth_headers):
        """Individual clients get standard deadlines including April 15 and Q estimates."""
        r = await client.post(
            "/api/clients?auto_deadlines=true",
            json={
                "full_name": "Deadline Auto Test Individual",
                "email": "deadline.individual@example.com",
                "entity_type": "individual",
                "tax_year": 2024,
            },
            headers=auth_headers,
        )
        assert r.status_code == 201
        cid = r.json()["id"]

        res = await client.get(f"/api/deadlines/client/{cid}", headers=auth_headers)
        assert res.status_code == 200
        deadlines = res.json()

        # Should have federal return, extension, and 4 quarterly estimates
        assert len(deadlines) >= 4
        types = [d["deadline_type"] for d in deadlines]
        assert any("Federal Return" in t for t in types)
        assert any("Estimated" in t for t in types)

    async def test_scorp_deadlines_generated(self, client, auth_headers):
        """S-Corp clients get March 15 return deadline (not April 15)."""
        r = await client.post(
            "/api/clients?auto_deadlines=true",
            json={
                "full_name": "Deadline Auto Test SCorp",
                "email": "deadline.scorp@example.com",
                "entity_type": "s_corp",
                "tax_year": 2024,
            },
            headers=auth_headers,
        )
        cid = r.json()["id"]

        res = await client.get(f"/api/deadlines/client/{cid}", headers=auth_headers)
        deadlines = res.json()

        return_deadline = next(
            (d for d in deadlines if "Federal Return" in d["deadline_type"]), None
        )
        assert return_deadline is not None
        # March 15, 2025 is Saturday, so the demo generator advances to Monday.
        assert return_deadline["due_date"] == "2025-03-17"

    async def test_ccorp_uses_april_return_deadline(self, client, auth_headers):
        """Calendar-year C-Corp demo deadline must not reuse the S-Corp March date."""
        r = await client.post(
            "/api/clients?auto_deadlines=true",
            json={
                "full_name": "Deadline Auto Test CCorp",
                "email": "deadline.ccorp@example.com",
                "entity_type": "c_corp",
                "tax_year": 2024,
            },
            headers=auth_headers,
        )
        cid = r.json()["id"]
        res = await client.get(f"/api/deadlines/client/{cid}", headers=auth_headers)
        deadlines = res.json()
        return_deadline = next(
            (d for d in deadlines if "Federal Return" in d["deadline_type"]), None
        )
        assert return_deadline is not None
        assert return_deadline["due_date"] == "2025-04-15"

    async def test_llc_deadlines_fail_closed_without_tax_classification(self, client, auth_headers):
        """LLC legal form alone is insufficient to infer a federal filing calendar."""
        r = await client.post(
            "/api/clients?auto_deadlines=true",
            json={
                "full_name": "Ambiguous LLC",
                "email": "ambiguous.llc@example.com",
                "entity_type": "llc",
                "tax_year": 2024,
            },
            headers=auth_headers,
        )
        cid = r.json()["id"]
        res = await client.get(f"/api/deadlines/client/{cid}", headers=auth_headers)
        assert res.json() == []

    async def test_partnership_deadlines_generated(self, client, auth_headers):
        """Partnership clients get March 15 deadline."""
        r = await client.post(
            "/api/clients?auto_deadlines=true",
            json={
                "full_name": "Deadline Auto Test Partnership",
                "email": "deadline.partnership@example.com",
                "entity_type": "partnership",
                "tax_year": 2024,
            },
            headers=auth_headers,
        )
        cid = r.json()["id"]

        res = await client.get(f"/api/deadlines/client/{cid}", headers=auth_headers)
        deadlines = res.json()

        return_deadline = next(
            (d for d in deadlines if "Federal Return" in d["deadline_type"]), None
        )
        assert return_deadline is not None
        assert return_deadline["due_date"] == "2025-03-15"

    async def test_individual_return_due_april_15(self, client, auth_headers):
        """Individual 1040 is due April 15."""
        r = await client.post(
            "/api/clients?auto_deadlines=true",
            json={
                "full_name": "April 15 Test",
                "email": "april15.test@example.com",
                "entity_type": "individual",
                "tax_year": 2024,
            },
            headers=auth_headers,
        )
        cid = r.json()["id"]

        res = await client.get(f"/api/deadlines/client/{cid}", headers=auth_headers)
        deadlines = res.json()

        return_deadline = next(
            (d for d in deadlines if "Federal Return" in d["deadline_type"]), None
        )
        assert return_deadline is not None
        assert return_deadline["due_date"] == "2025-04-15"

    async def test_auto_generate_no_duplicates(self, client, auth_headers):
        """Auto-generate does not create duplicate deadlines."""
        r = await client.post(
            "/api/clients?auto_deadlines=false",
            json={
                "full_name": "No Duplicate Deadlines Test",
                "email": "no.dup.deadlines@example.com",
                "entity_type": "individual",
                "tax_year": 2024,
            },
            headers=auth_headers,
        )
        cid = r.json()["id"]

        # Auto-generate twice
        r1 = await client.post(f"/api/deadlines/client/{cid}/auto-generate", headers=auth_headers)
        assert r1.status_code == 201
        created_first = r1.json()["created"]
        assert created_first > 0

        r2 = await client.post(f"/api/deadlines/client/{cid}/auto-generate", headers=auth_headers)
        assert r2.status_code == 201
        created_second = r2.json()["created"]
        assert created_second == 0  # No duplicates

    async def test_upcoming_deadlines_query(self, client, auth_headers):
        """Upcoming deadline query returns deadlines within N days."""
        res = await client.get(
            "/api/deadlines/upcoming?days=365",
            headers=auth_headers,
        )
        assert res.status_code == 200
        deadlines = res.json()
        assert isinstance(deadlines, list)

        # All returned deadlines should be upcoming or in_progress
        for d in deadlines:
            assert d["status"] in ("upcoming", "in_progress")

    async def test_deadline_status_update(self, client, auth_headers):
        """Update deadline status from upcoming to completed."""
        r = await client.post(
            "/api/clients?auto_deadlines=false",
            json={
                "full_name": "Status Update Test",
                "email": "status.update.test@example.com",
                "entity_type": "individual",
                "tax_year": 2024,
            },
            headers=auth_headers,
        )
        cid = r.json()["id"]

        # Create a deadline
        future_date = (date.today() + timedelta(days=30)).isoformat()
        dr = await client.post(
            "/api/deadlines",
            json={
                "client_id": cid,
                "deadline_type": "Federal Return (1040/1120/1065)",
                "due_date": future_date,
                "status": "upcoming",
            },
            headers=auth_headers,
        )
        assert dr.status_code == 201
        deadline_id = dr.json()["id"]

        # Mark completed
        ur = await client.patch(
            f"/api/deadlines/{deadline_id}",
            json={"status": "completed"},
            headers=auth_headers,
        )
        assert ur.status_code == 200
        assert ur.json()["status"] == "completed"

    async def test_days_until_computed(self, client, auth_headers):
        """days_until is correctly computed in deadline responses."""
        r = await client.post(
            "/api/clients?auto_deadlines=false",
            json={
                "full_name": "Days Until Test",
                "email": "days.until@example.com",
                "entity_type": "individual",
                "tax_year": 2024,
            },
            headers=auth_headers,
        )
        cid = r.json()["id"]

        future_date = (date.today() + timedelta(days=14)).isoformat()
        dr = await client.post(
            "/api/deadlines",
            json={
                "client_id": cid,
                "deadline_type": "Custom Deadline",
                "due_date": future_date,
            },
            headers=auth_headers,
        )
        deadline_id = dr.json()["id"]

        res = await client.get(f"/api/deadlines/client/{cid}", headers=auth_headers)
        deadlines = res.json()
        our_dl = next((d for d in deadlines if d["id"] == deadline_id), None)
        assert our_dl is not None
        assert our_dl["days_until"] == 14

    async def test_deadline_calendar_reference(self, client, auth_headers):
        """Calendar endpoint returns standard US tax dates."""
        res = await client.get("/api/deadlines/calendar?year=2025", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["year"] == 2025
        assert "federal_deadlines" in data
        assert len(data["federal_deadlines"]) > 5
