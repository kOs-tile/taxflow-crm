"""
TaxFlow CRM — Pydantic Models (Request/Response schemas)
These are the API-layer models. Database schemas live in db.py.
"""
from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator


# ─── Enums ────────────────────────────────────────────────────────────────────

class FilingStatus(str, Enum):
    single = "single"
    married_filing_jointly = "married_filing_jointly"
    married_filing_separately = "married_filing_separately"
    head_of_household = "head_of_household"
    qualifying_widow = "qualifying_widow"


class EntityType(str, Enum):
    individual = "individual"
    llc = "llc"
    s_corp = "s_corp"
    c_corp = "c_corp"
    partnership = "partnership"
    sole_proprietor = "sole_proprietor"
    nonprofit = "nonprofit"


class DocumentType(str, Enum):
    w2 = "W-2"
    form_1099_nec = "1099-NEC"
    form_1099_misc = "1099-MISC"
    form_1099_b = "1099-B"
    form_1099_int = "1099-INT"
    form_1099_div = "1099-DIV"
    form_1099_r = "1099-R"
    form_1099_g = "1099-G"
    k1 = "K-1"
    form_1098 = "1098"
    form_1098_e = "1098-E"
    form_1098_t = "1098-T"
    schedule_c = "Schedule C"
    schedule_e = "Schedule E"
    prior_return = "Prior Year Return"
    business_expenses = "Business Expenses"
    vehicle_log = "Vehicle Log"
    home_office = "Home Office Info"
    rental_income = "Rental Income/Expenses"
    crypto_transactions = "Crypto Transactions"
    foreign_accounts = "Foreign Account Info (FBAR)"
    charitable_donations = "Charitable Donation Records"
    medical_expenses = "Medical Expenses"
    other = "Other"


class DocumentStatus(str, Enum):
    awaiting = "awaiting"
    received = "received"
    reviewed = "reviewed"
    not_applicable = "not_applicable"


class DeadlineType(str, Enum):
    # Federal
    federal_return = "Federal Return (1040/1120/1065)"
    federal_extension = "Federal Extension"
    q1_estimated = "Q1 Estimated Tax (Apr 15)"
    q2_estimated = "Q2 Estimated Tax (Jun 15)"
    q3_estimated = "Q3 Estimated Tax (Sep 15)"
    q4_estimated = "Q4 Estimated Tax (Jan 15)"
    w2_1099_filing = "W-2/1099 Filing (Jan 31)"
    fica_deposit = "FICA/Payroll Deposit"
    fbar = "FBAR (FinCEN 114)"
    # State
    state_return = "State Return"
    state_extension = "State Extension"
    # Business
    s_corp_election = "S-Corp Election (Form 2553)"
    estimated_corp = "Corporate Estimated Tax"
    custom = "Custom Deadline"


class DeadlineStatus(str, Enum):
    upcoming = "upcoming"
    completed = "completed"
    missed = "missed"
    extended = "extended"
    in_progress = "in_progress"


class UserRole(str, Enum):
    admin = "admin"
    preparer = "preparer"
    reviewer = "reviewer"


class SenderRole(str, Enum):
    staff = "staff"
    client = "client"


class TaskPriority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"


# ─── User Models ──────────────────────────────────────────────────────────────

class UserBase(BaseModel):
    email: str
    full_name: str
    role: UserRole = UserRole.preparer


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    password: Optional[str] = None


class UserOut(UserBase):
    id: int
    created_at: datetime
    is_active: bool

    model_config = {"from_attributes": True}


# ─── Client Models ────────────────────────────────────────────────────────────

class ClientBase(BaseModel):
    full_name: str
    email: str
    phone: Optional[str] = None
    address: Optional[str] = None
    tax_year: int = 2024
    filing_status: Optional[FilingStatus] = None
    entity_type: EntityType = EntityType.individual
    ssn_last4: Optional[str] = None  # last 4 digits only
    ein: Optional[str] = None        # for business entities
    state: Optional[str] = None      # primary state of filing
    assigned_preparer_id: Optional[int] = None
    notes: Optional[str] = None
    is_active: bool = True

    @field_validator("ssn_last4")
    @classmethod
    def validate_ssn_last4(cls, v):
        if v and (not v.isdigit() or len(v) != 4):
            raise ValueError("ssn_last4 must be exactly 4 digits")
        return v


class ClientCreate(ClientBase):
    # Accepted in the JSON body so credentials never need to appear in the URL.
    portal_password: Optional[str] = None


class ClientUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    tax_year: Optional[int] = None
    filing_status: Optional[FilingStatus] = None
    entity_type: Optional[EntityType] = None
    ssn_last4: Optional[str] = None
    ein: Optional[str] = None
    state: Optional[str] = None
    assigned_preparer_id: Optional[int] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class ClientOut(ClientBase):
    id: int
    created_at: datetime
    document_completion_pct: Optional[float] = None
    upcoming_deadline_count: Optional[int] = None
    unread_message_count: Optional[int] = None

    model_config = {"from_attributes": True}


class ClientSummary(BaseModel):
    """Lightweight client summary for lists/dropdowns."""
    id: int
    full_name: str
    email: str
    entity_type: EntityType
    tax_year: int
    assigned_preparer_id: Optional[int]
    document_completion_pct: Optional[float] = None
    is_active: bool

    model_config = {"from_attributes": True}


# ─── Document Models ──────────────────────────────────────────────────────────

class DocumentBase(BaseModel):
    client_id: int
    doc_type: DocumentType
    tax_year: int = 2024
    status: DocumentStatus = DocumentStatus.awaiting
    notes: Optional[str] = None


class DocumentCreate(DocumentBase):
    pass


class DocumentUpdate(BaseModel):
    status: Optional[DocumentStatus] = None
    notes: Optional[str] = None
    received_at: Optional[datetime] = None


class DocumentOut(DocumentBase):
    id: int
    received_at: Optional[datetime]
    reviewed_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentCompletionStats(BaseModel):
    client_id: int
    total: int
    awaiting: int
    received: int
    reviewed: int
    not_applicable: int
    completion_pct: float  # (received + reviewed) / applicable * 100


# ─── Deadline Models ──────────────────────────────────────────────────────────

class DeadlineBase(BaseModel):
    client_id: int
    deadline_type: DeadlineType
    due_date: date
    status: DeadlineStatus = DeadlineStatus.upcoming
    notes: Optional[str] = None
    state_code: Optional[str] = None  # for state deadlines


class DeadlineCreate(DeadlineBase):
    pass


class DeadlineUpdate(BaseModel):
    due_date: Optional[date] = None
    status: Optional[DeadlineStatus] = None
    notes: Optional[str] = None


class DeadlineOut(DeadlineBase):
    id: int
    client_name: Optional[str] = None
    created_at: datetime
    days_until: Optional[int] = None  # computed field

    model_config = {"from_attributes": True}


# ─── Message Models ───────────────────────────────────────────────────────────

class MessageBase(BaseModel):
    client_id: int
    content: str
    sender_role: SenderRole


class MessageCreate(BaseModel):
    client_id: int
    content: str


class MessageOut(MessageBase):
    id: int
    created_at: datetime
    read: bool
    sender_name: Optional[str] = None

    model_config = {"from_attributes": True}


class MessageThread(BaseModel):
    client_id: int
    client_name: str
    messages: list[MessageOut]
    unread_count: int


# ─── Task Models ──────────────────────────────────────────────────────────────

class TaskBase(BaseModel):
    client_id: int
    title: str
    description: Optional[str] = None
    due_date: Optional[date] = None
    priority: TaskPriority = TaskPriority.medium
    assigned_to_id: Optional[int] = None


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[date] = None
    priority: Optional[TaskPriority] = None
    completed: Optional[bool] = None
    assigned_to_id: Optional[int] = None


class TaskOut(TaskBase):
    id: int
    completed: bool
    completed_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Auth Models ──────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class LoginRequest(BaseModel):
    email: str
    password: str


class ClientPortalLoginRequest(BaseModel):
    email: str
    password: str


class ClientPortalToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    client_id: int
    client_name: str


# ─── AI Assistant Models ──────────────────────────────────────────────────────

class AssistantMessage(BaseModel):
    role: str  # "user" | "assistant" | "system"
    content: str


class AssistantChatRequest(BaseModel):
    client_id: Optional[int] = None  # None = global query
    message: str
    conversation_history: Optional[list[AssistantMessage]] = []


class AssistantChatResponse(BaseModel):
    reply: str
    suggested_actions: Optional[list[str]] = []
    referenced_client: Optional[str] = None


# ─── Dashboard Models ─────────────────────────────────────────────────────────

class DashboardStats(BaseModel):
    total_clients: int
    active_clients: int
    docs_received_this_week: int
    deadlines_in_7_days: int
    deadlines_in_30_days: int
    at_risk_clients: int  # clients with missed deadlines or <50% docs
    unread_messages: int
    completed_returns_ytd: int


class ActivityItem(BaseModel):
    type: str  # "document", "message", "deadline", "task"
    description: str
    client_id: Optional[int]
    client_name: Optional[str]
    timestamp: datetime
    icon: str


class DashboardResponse(BaseModel):
    stats: DashboardStats
    upcoming_deadlines: list[DeadlineOut]
    recent_activity: list[ActivityItem]
    at_risk_clients: list[ClientSummary]
