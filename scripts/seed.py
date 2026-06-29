"""
TaxFlow CRM — Database Seeder
Populates with 10 realistic US tax clients across entity types,
with documents at various stages, realistic deadlines, and message threads.

Run: python -m scripts.seed
"""
import asyncio
import sys
import os
from datetime import date, datetime, timedelta

# Allow running from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.db import init_db, get_db
from backend.auth import hash_password
from loguru import logger

# ─── Sample Data ──────────────────────────────────────────────────────────────

PREPARERS = [
    {"email": "sarah.chen@taxflow.app", "full_name": "Sarah Chen", "role": "preparer", "password": "preparer123"},
    {"email": "marcus.johnson@taxflow.app", "full_name": "Marcus Johnson", "role": "preparer", "password": "preparer123"},
    {"email": "admin@taxflow.app", "full_name": "Admin User", "role": "admin", "password": "TaxFlow2025!"},
]

CLIENTS = [
    {
        "full_name": "Jennifer & Robert Walsh",
        "email": "jwalshhousehold@gmail.com",
        "phone": "(617) 555-0142",
        "tax_year": 2024,
        "filing_status": "married_filing_jointly",
        "entity_type": "individual",
        "ssn_last4": "4821",
        "state": "MA",
        "notes": "Two W-2 earners. Robert has some RSU vesting from his tech job. They sold their rental property in 2024.",
        "portal_password": "client1234",
        "preparer_index": 0,
        "doc_statuses": {
            "W-2": "received",
            "1099-B": "awaiting",
            "1099-INT": "received",
            "1099-DIV": "received",
            "1098": "received",
            "Prior Year Return": "reviewed",
            "Charitable Donation Records": "awaiting",
        },
        "messages": [
            ("client", "Hi, I just uploaded my W-2. Should I also send the RSU vesting schedule?"),
            ("staff", "Yes, please send the RSU vesting schedule and your Form 3921. Also, do you have the closing documents from the rental property sale?"),
            ("client", "I'll dig those up. The closing happened in October — I should have the HUD-1 somewhere."),
            ("staff", "Perfect. Also reminding you that we still need your 1099-B from Fidelity for the stock sales. You should receive it by mid-February."),
        ],
    },
    {
        "full_name": "Apex Digital Solutions LLC",
        "email": "accounting@apexdigital.io",
        "phone": "(312) 555-0238",
        "tax_year": 2024,
        "filing_status": None,
        "entity_type": "llc",
        "ein": "82-4831920",
        "state": "IL",
        "notes": "Digital marketing agency. Single-member LLC filing Schedule C. About $380K gross revenue in 2024.",
        "portal_password": "apex2024",
        "preparer_index": 1,
        "doc_statuses": {
            "1099-NEC": "received",
            "Schedule C": "awaiting",
            "Business Expenses": "awaiting",
            "Prior Year Return": "reviewed",
            "Vehicle Log": "awaiting",
            "Home Office Info": "not_applicable",
        },
        "messages": [
            ("client", "I have all my 1099-NECs together now. Can I just email them to you?"),
            ("staff", "Please upload them through your client portal — it's more secure than email. Once I have those and your expense spreadsheet, I can start on Schedule C."),
            ("client", "Sure, will do tomorrow. Quick question — I bought a new MacBook Pro for the business in November. Is that deductible?"),
            ("staff", "Yes, under Section 179 you can expense the full cost in 2024. Please include it in your business expense summary with the purchase date and amount."),
        ],
    },
    {
        "full_name": "Westlake Family Dentistry S-Corp",
        "email": "dr.westlake@westlakedental.com",
        "phone": "(602) 555-0371",
        "tax_year": 2024,
        "filing_status": None,
        "entity_type": "s_corp",
        "ein": "91-3847265",
        "state": "AZ",
        "notes": "S-Corp election active since 2019. Dr. Westlake is sole shareholder. Files 1120-S and personal 1040. Reasonable salary: $180K.",
        "portal_password": "dental2024",
        "preparer_index": 0,
        "doc_statuses": {
            "1099-NEC": "received",
            "Business Expenses": "received",
            "Prior Year Return": "reviewed",
            "Vehicle Log": "received",
            "K-1": "awaiting",
        },
        "messages": [
            ("staff", "Dr. Westlake, your 1120-S is due March 15. We still need your K-1 from the DSO partnership. Have you received it yet?"),
            ("client", "Not yet — they said they're running behind. Is there an option to extend?"),
            ("staff", "Yes, we can file Form 7004 for an automatic 6-month extension. That would push the deadline to September 15. Would you like me to prepare that?"),
            ("client", "Yes please. I'd rather wait and get it right than rush."),
        ],
    },
    {
        "full_name": "Carlos Mendez",
        "email": "carlos.mendez.tx@gmail.com",
        "phone": "(210) 555-0499",
        "tax_year": 2024,
        "filing_status": "single",
        "entity_type": "individual",
        "ssn_last4": "7302",
        "state": "TX",
        "notes": "Freelance web developer. 1099 income from multiple clients. High quarterly estimated payments — tends to underpay Q3.",
        "portal_password": "carlos1234",
        "preparer_index": 1,
        "doc_statuses": {
            "1099-NEC": "received",
            "Business Expenses": "received",
            "Prior Year Return": "reviewed",
            "Vehicle Log": "not_applicable",
        },
        "messages": [
            ("client", "Did I pay enough estimated taxes this year? I'm worried about a big bill."),
            ("staff", "I'll run the numbers once we have all your income together. Based on last year, Q3 looked underpaid. Did you make the September 15 payment?"),
            ("client", "I paid $3,200 in September. Is that enough?"),
        ],
    },
    {
        "full_name": "Blue Ridge Partners LP",
        "email": "partners@blueridgepartners.com",
        "phone": "(404) 555-0567",
        "tax_year": 2024,
        "filing_status": None,
        "entity_type": "partnership",
        "ein": "46-7391820",
        "state": "GA",
        "notes": "Real estate limited partnership. 4 partners. Complex K-1 allocation. Files 1065. Two properties in GA, one in FL.",
        "portal_password": "blueridge24",
        "preparer_index": 0,
        "doc_statuses": {
            "K-1": "awaiting",
            "Business Expenses": "received",
            "Prior Year Return": "reviewed",
            "Rental Income/Expenses": "received",
            "1099-NEC": "not_applicable",
        },
        "messages": [
            ("staff", "Good morning. We need the Florida property income/expense breakdown and the Florida depreciation schedule before we can finalize the 1065."),
            ("client", "I'll get those from our property manager. They're usually slow — is March 15 the hard deadline?"),
            ("staff", "March 15 is the original deadline for 1065. We can extend to September 15 if needed, which gives partners more time to file their personal returns."),
        ],
    },
    {
        "full_name": "Nina Patel",
        "email": "nina.patel.boston@outlook.com",
        "phone": "(617) 555-0682",
        "tax_year": 2024,
        "filing_status": "single",
        "entity_type": "individual",
        "ssn_last4": "5590",
        "state": "MA",
        "notes": "Teacher with side tutoring business. Has a student loan interest deduction. First year as a client.",
        "portal_password": "nina2024",
        "preparer_index": 1,
        "doc_statuses": {
            "W-2": "received",
            "1099-NEC": "received",
            "1098-E": "awaiting",
            "1098-T": "not_applicable",
            "Prior Year Return": "awaiting",
            "Business Expenses": "awaiting",
        },
        "messages": [
            ("staff", "Welcome to TaxFlow! I'm Marcus, your tax preparer. To get started, I'll need your W-2, any 1099s, your student loan interest statement (1098-E), and your prior year return if you have it."),
            ("client", "Hi Marcus! I got my W-2 and 1099-NEC. I'm waiting on the 1098-E from Navient. When do you need everything by?"),
            ("staff", "Your 1098-E should arrive by end of January. Aim to have everything to me by February 28 so we have plenty of time before April 15."),
        ],
    },
    {
        "full_name": "Rooftop Roofing & Construction Inc.",
        "email": "bookkeeper@rooftopconstruction.net",
        "phone": "(303) 555-0741",
        "tax_year": 2024,
        "filing_status": None,
        "entity_type": "c_corp",
        "ein": "33-9201847",
        "state": "CO",
        "notes": "C-Corp formed 2021. Calendar year. Significant subcontractor payments — over 40 1099-NECs to file. Revenue ~$2.1M.",
        "portal_password": "rooftop24",
        "preparer_index": 0,
        "doc_statuses": {
            "1099-NEC": "received",
            "Business Expenses": "received",
            "Prior Year Return": "reviewed",
            "W-2": "received",
            "Vehicle Log": "received",
        },
        "messages": [
            ("client", "We need to file over 40 1099-NECs this year. Can TaxFlow help with that?"),
            ("staff", "Yes. Please send a spreadsheet with each contractor name, EIN/SSN, address, and 2024 payment amount. The W-2/1099 deadline is January 31."),
            ("client", "Sending that over now. Also — what's the deadline for our corporate return?"),
            ("staff", "C-Corp 1120 is due April 15 (same as individual 1040). You can extend to October 15 with Form 7004. We'll get your 1099s filed first."),
        ],
    },
    {
        "full_name": "David & Priya Okonkwo",
        "email": "david.okonkwo@gmail.com",
        "phone": "(713) 555-0834",
        "tax_year": 2024,
        "filing_status": "married_filing_jointly",
        "entity_type": "individual",
        "ssn_last4": "1177",
        "state": "TX",
        "notes": "David is a petroleum engineer (W-2). Priya has a small Etsy shop. Foreign bank account — FBAR may be required.",
        "portal_password": "david1234",
        "preparer_index": 1,
        "doc_statuses": {
            "W-2": "received",
            "1099-NEC": "received",
            "1099-B": "awaiting",
            "Foreign Account Info (FBAR)": "awaiting",
            "Prior Year Return": "reviewed",
            "Business Expenses": "received",
        },
        "messages": [
            ("staff", "Hello! I wanted to flag that you mentioned a foreign bank account last year. Do you still have it? If the balance exceeded $10,000 at any point in 2024, we need to file an FBAR by April 15 (extendable to October 15)."),
            ("client", "Yes, Priya still has her UK account. The balance was around £15,000 at its highest. What info do you need?"),
            ("staff", "I'll need the bank name, account number, highest balance in 2024 (in USD), and whether there was any income. Also, if you have foreign account statements, please upload those."),
        ],
    },
    {
        "full_name": "Green Leaf Yoga Studio LLC",
        "email": "owner@greenleafyoga.com",
        "phone": "(503) 555-0923",
        "tax_year": 2024,
        "filing_status": None,
        "entity_type": "llc",
        "ein": "84-2930187",
        "state": "OR",
        "notes": "Multi-member LLC (2 members). Studio + online classes. ~$195K revenue. Has an SBA loan from 2021.",
        "portal_password": "yoga2024",
        "preparer_index": 0,
        "doc_statuses": {
            "1099-NEC": "received",
            "Schedule C": "awaiting",
            "Business Expenses": "awaiting",
            "Prior Year Return": "reviewed",
            "1098": "received",
        },
        "messages": [
            ("client", "We're switching to a multi-member LLC structure starting 2024. Does that change our filing requirements?"),
            ("staff", "Yes, as a multi-member LLC you'll now file Form 1065 (Partnership return) and issue K-1s to each member. This is different from last year's Schedule C. I'll need the ownership percentages and any operating agreement changes."),
        ],
    },
    {
        "full_name": "Thomas Harrington",
        "email": "tharrington.cpa@protonmail.com",
        "phone": "(212) 555-0016",
        "tax_year": 2024,
        "filing_status": "married_filing_separately",
        "entity_type": "individual",
        "ssn_last4": "9943",
        "state": "NY",
        "notes": "CPA himself — reviews everything carefully. Has rental income from 2 NYC apartments. High-income taxpayer. NIIT applies.",
        "portal_password": "thomas24",
        "preparer_index": 1,
        "doc_statuses": {
            "W-2": "reviewed",
            "1099-INT": "reviewed",
            "1099-DIV": "reviewed",
            "Schedule E": "awaiting",
            "1098": "reviewed",
            "Prior Year Return": "reviewed",
            "Rental Income/Expenses": "awaiting",
            "Charitable Donation Records": "received",
        },
        "messages": [
            ("staff", "Thomas, we still need your 2024 rental income/expense summaries for both properties. We have everything else in reviewed status."),
            ("client", "I'll have those to you by Friday. Quick question — is the net investment income tax still 3.8% for 2024? I want to make sure we've estimated correctly."),
            ("staff", "Yes, still 3.8% on the lesser of net investment income or the excess of MAGI over the threshold ($250K for MFS). Given your income level, plan on the full NIIT applying to all rental and investment income."),
        ],
    },
]

# ─── Seeder ───────────────────────────────────────────────────────────────────

async def seed():
    await init_db()

    async with await get_db() as db:
        # Create preparers (skip admin, already exists)
        preparer_ids = []
        for p in PREPARERS:
            async with db.execute("SELECT id FROM users WHERE email = ?", (p["email"],)) as c:
                existing = await c.fetchone()
            if existing:
                preparer_ids.append(existing["id"])
                logger.info(f"User exists: {p['email']}")
            else:
                cur = await db.execute(
                    "INSERT INTO users (email, full_name, role, password_hash) VALUES (?, ?, ?, ?)",
                    (p["email"], p["full_name"], p["role"], hash_password(p["password"]))
                )
                preparer_ids.append(cur.lastrowid)
                logger.info(f"Created user: {p['email']}")
        await db.commit()

        # Seed clients
        for i, client_data in enumerate(CLIENTS):
            # Check if already exists
            async with db.execute("SELECT id FROM clients WHERE email = ?", (client_data["email"],)) as c:
                existing = await c.fetchone()
            if existing:
                logger.info(f"Client exists: {client_data['full_name']}")
                continue

            preparer_id = preparer_ids[client_data.pop("preparer_index")]
            doc_statuses = client_data.pop("doc_statuses")
            messages = client_data.pop("messages")
            portal_password = client_data.pop("portal_password")

            # Insert client
            cur = await db.execute(
                """INSERT INTO clients
                   (full_name, email, phone, tax_year, filing_status, entity_type,
                    ssn_last4, ein, state, notes, is_active, assigned_preparer_id, portal_password_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
                (
                    client_data["full_name"],
                    client_data["email"],
                    client_data.get("phone"),
                    client_data["tax_year"],
                    client_data.get("filing_status"),
                    client_data["entity_type"],
                    client_data.get("ssn_last4"),
                    client_data.get("ein"),
                    client_data.get("state"),
                    client_data.get("notes"),
                    preparer_id,
                    hash_password(portal_password),
                )
            )
            client_id = cur.lastrowid
            logger.info(f"Created client: {client_data['full_name']} (ID: {client_id})")

            # Insert documents
            for doc_type, status in doc_statuses.items():
                received_at = None
                reviewed_at = None
                if status in ("received", "reviewed"):
                    received_at = (datetime.utcnow() - timedelta(days=i*2+3)).isoformat()
                if status == "reviewed":
                    reviewed_at = (datetime.utcnow() - timedelta(days=i+1)).isoformat()

                await db.execute(
                    """INSERT OR IGNORE INTO documents
                       (client_id, doc_type, tax_year, status, received_at, reviewed_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (client_id, doc_type, 2024, status, received_at, reviewed_at)
                )

            # Generate standard deadlines based on entity type
            from backend.db import auto_generate_deadlines
            deadlines = auto_generate_deadlines(client_id, client_data["entity_type"], 2024)
            for dl in deadlines:
                await db.execute(
                    "INSERT INTO deadlines (client_id, deadline_type, due_date, status) VALUES (?, ?, ?, ?)",
                    (dl["client_id"], dl["deadline_type"], str(dl["due_date"]), dl["status"])
                )

            # Insert some past-due deadlines for at-risk clients (clients 4, 7)
            if i in (3, 6):
                await db.execute(
                    """INSERT INTO deadlines (client_id, deadline_type, due_date, status)
                       VALUES (?, 'W-2/1099 Filing (Jan 31)', '2025-01-31', 'missed')""",
                    (client_id,)
                )

            # Insert message thread
            base_time = datetime.utcnow() - timedelta(days=14-i)
            for j, (role, content) in enumerate(messages):
                msg_time = (base_time + timedelta(hours=j*4)).isoformat()
                await db.execute(
                    "INSERT INTO messages (client_id, sender_role, content, read, created_at) VALUES (?, ?, ?, ?, ?)",
                    (client_id, role, content, 1 if role == "staff" else 0, msg_time)
                )

            # Add a couple of tasks
            await db.execute(
                """INSERT INTO tasks (client_id, title, priority, due_date)
                   VALUES (?, ?, ?, ?)""",
                (client_id, "Follow up on missing documents", "high",
                 (date.today() + timedelta(days=7)).isoformat())
            )
            if i % 3 == 0:
                await db.execute(
                    """INSERT INTO tasks (client_id, title, priority, completed)
                       VALUES (?, ?, ?, 1)""",
                    (client_id, "Initial intake call completed", "medium")
                )

        await db.commit()
        logger.success("✓ Database seeded successfully!")
        logger.info(f"Created {len(CLIENTS)} clients with documents, deadlines, messages, and tasks.")
        logger.info("Staff logins:")
        for p in PREPARERS:
            logger.info(f"  {p['email']} / {p['password']}")


if __name__ == "__main__":
    asyncio.run(seed())
