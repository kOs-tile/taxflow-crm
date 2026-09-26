"""
TaxFlow CRM — Demo Mode Walkthrough
Prints a guided tour of the system's capabilities and API endpoints.

Run: python -m scripts.demo
"""
import asyncio
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def demo():
    print("""
╔═══════════════════════════════════════════════════════════════════╗
║                TaxFlow CRM — Demo Walkthrough                     ║
║         AI-Powered CRM for US Tax Professionals                   ║
╚═══════════════════════════════════════════════════════════════════╝

This demo walks through TaxFlow's core features.
Make sure the server is running: uvicorn backend.main:app --reload

""")

    import httpx
    from backend.config import get_settings

    BASE = "http://localhost:8000/api"
    settings = get_settings()

    async with httpx.AsyncClient() as client:

        # ── Step 1: Login ─────────────────────────────────────────────
        print("━━━ Step 1: Staff Login ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        res = await client.post(f"{BASE}/auth/login", json={
            "email": settings.admin_email,
            "password": settings.admin_password
        })
        if res.status_code != 200:
            print("❌ Login failed. Have you run: python -m scripts.seed ?")
            return

        token = res.json()["access_token"]
        user = res.json()["user"]
        headers = {"Authorization": f"Bearer {token}"}
        print(f"✅ Logged in as {user['full_name']} ({user['role']})")

        # ── Step 2: Dashboard ─────────────────────────────────────────
        print("\n━━━ Step 2: Dashboard Stats ━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        res = await client.get(f"{BASE}/dashboard/stats", headers=headers)
        stats = res.json()
        print(f"  Total Clients:      {stats['total_clients']}")
        print(f"  Active Clients:     {stats['active_clients']}")
        print(f"  Docs This Week:     {stats['docs_received_this_week']}")
        print(f"  Deadlines in 7d:    {stats['deadlines_in_7_days']}")
        print(f"  At-Risk Clients:    {stats['at_risk_clients']}")
        print(f"  Unread Messages:    {stats['unread_messages']}")

        # ── Step 3: Client List ───────────────────────────────────────
        print("\n━━━ Step 3: Client List ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        res = await client.get(f"{BASE}/clients?enrich=true", headers=headers)
        clients = res.json()
        print(f"  {len(clients)} clients loaded:")
        for c in clients[:5]:
            pct = c.get('document_completion_pct') or 0
            print(f"  • {c['full_name']:<35} {c['entity_type']:<15} {pct:.0f}% docs")

        if not clients:
            print("  No clients found. Run: python -m scripts.seed")
            return

        first_client = clients[0]
        cid = first_client["id"]

        # ── Step 4: Document Checklist ────────────────────────────────
        print(f"\n━━━ Step 4: Documents for '{first_client['full_name']}' ━━━━━━━━━━━━")
        res = await client.get(f"{BASE}/documents/client/{cid}", headers=headers)
        docs = res.json()
        for d in docs[:6]:
            icon = {"awaiting": "⏳", "received": "📄", "reviewed": "✅", "not_applicable": "—"}.get(d["status"], "?")
            print(f"  {icon} {d['doc_type']:<35} {d['status']}")

        # ── Step 5: Deadlines ─────────────────────────────────────────
        print(f"\n━━━ Step 5: Upcoming Deadlines (next 90 days) ━━━━━━━━━━")
        res = await client.get(f"{BASE}/deadlines/upcoming?days=90", headers=headers)
        deadlines = res.json()
        for d in deadlines[:5]:
            days = d.get("days_until", "?")
            flag = "🔴" if isinstance(days, int) and days <= 14 else "🟡" if isinstance(days, int) and days <= 30 else "🟢"
            print(f"  {flag} {d['deadline_type']:<40} {d['due_date']} ({days}d) — {d.get('client_name', '')}")

        # ── Step 6: Messages ──────────────────────────────────────────
        print(f"\n━━━ Step 6: Message Thread ━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        res = await client.get(f"{BASE}/messages/client/{cid}", headers=headers)
        messages = res.json()
        for m in messages[-3:]:
            role_label = "Staff  →" if m["sender_role"] == "staff" else "Client →"
            print(f"  {role_label} {m['content'][:70]}...")

        # ── Step 7: AI Assistant ──────────────────────────────────────
        print(f"\n━━━ Step 7: AI Assistant (context-aware) ━━━━━━━━━━━━━━")
        print(f"  Query: 'What documents is {first_client['full_name']} still missing?'")
        try:
            res = await client.post(
                f"{BASE}/assistant/chat",
                headers=headers,
                json={
                    "client_id": cid,
                    "message": f"What documents is this client still missing and what should I follow up on?",
                    "conversation_history": [],
                },
                timeout=30.0
            )
            if res.status_code == 200:
                reply = res.json()["reply"]
                print(f"\n  AI Response:\n  {reply[:400]}...")
            elif res.status_code == 503:
                print("  ⚠️  AI not configured (add OPENAI_API_KEY to .env). Response would include:")
                print("     - Client profile summary")
                print("     - List of missing documents")
                print("     - Upcoming deadlines")
                print("     - Suggested follow-up email draft")
        except Exception as e:
            print(f"  ⚠️  AI assistant: {e}")

        # ── Summary ───────────────────────────────────────────────────
        print("""
━━━ Demo Complete ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TaxFlow CRM is running with:
  ✅ JWT Authentication (staff + client portal)
  ✅ Client management with document tracking
  ✅ Auto-generated tax deadlines by entity type
  ✅ Real-time messaging (SSE)
  ✅ AI Assistant with tax-aware context
  ✅ Dashboard with at-risk client detection
  ✅ Client portal (separate login)

URLs:
  Main CRM:     http://localhost:8000/
  API Docs:     http://localhost:8000/api/docs
  Client Portal: http://localhost:8000/portal

Default login: admin@taxflow.app / TaxFlow2025!
""")


if __name__ == "__main__":
    asyncio.run(demo())
