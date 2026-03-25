from sqlmodel import SQLModel, Field
from sqlalchemy import Column, JSON
from typing import TypedDict, Optional, Dict, Any, List
from enum import Enum
from datetime import datetime

class LeadCategory(str, Enum):
    INDEPENDENT_BRAND = "INDEPENDENT_BRAND"       # Target 1: Brands that design their own clothes
    PRIVATE_LABEL_RETAILER = "PRIVATE_LABEL_RETAILER"      # Target 2: Stores that manufacture their own house brands
    EXPO_EXHIBITOR = "EXPO_EXHIBITOR"

class LeadStatus(str, Enum):
    QUEUED = "QUEUED"                     # waiting to enter the pipeline
    INVESTIGATING = "INVESTIGATING"       # Phase 2 processing
    REJECTED = "REJECTED"                 # lead rejected by investigator
    FETCH_FAILED = "FETCH_FAILED"         # website could not be inspected
    ENRICHING = "ENRICHING"               # Phase 3 processing
    DRAFTING = "DRAFTING"                 # Phase 4 processing
    COMPLETED = "COMPLETED"               # Phase 4 finished

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    tier: str = Field(default="free")
    created_at: datetime = Field(default_factory=datetime.utcnow)

class CampaignBrief(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    original_prompt: str
    target_audience: str
    banned_terms: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    buyer_titles: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    value_proposition: str
    exa_search_queries: List[str] = Field(default_factory=list, sa_column=Column(JSON))

class Lead(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    campaign_brief_id: Optional[int] = Field(default=None, foreign_key="campaignbrief.id")
    company_name: str
    website_url: str = Field(unique=True, index=True)
    category: LeadCategory
    description: Optional[str] = None
    source: str
    last_seen_at: datetime = Field(default_factory=datetime.utcnow)
    
    status: LeadStatus = Field(default=LeadStatus.QUEUED)

    canonical_domain: Optional[str] = None
    scraped_context: Optional[str] = None
    investigation_notes: Optional[str] = None
    rejection_reason: Optional[str] = None
    investigation_confidence: Optional[float] = None

    employee_count: Optional[int] = None
    buyer_name: Optional[str] = None
    buyer_email: Optional[str] = None
    buyer_title: Optional[str] = None

    company_email: Optional[str] = None
    company_phone: Optional[str] = None
    company_location: Optional[str] = None
    contact_priority: Optional[str] = None
    enrichment_notes: Optional[str] = None


class EnrichedLead(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    lead_id: int = Field(index=True, unique=True)

    company_name: str
    website_url: str
    canonical_domain: Optional[str] = Field(default=None, index=True)

    employee_count: Optional[int] = None
    address: Optional[str] = None

    hunter_people_json: Optional[str] = None
    hunter_emails_json: Optional[str] = None

    regex_emails_json: Optional[str] = None

    web_founders_json: Optional[str] = None
    web_emails_json: Optional[str] = None
    web_sources_json: Optional[str] = None

    enrichment_notes: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SelectedContact(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    lead_id: int = Field(index=True, unique=True)
    enriched_lead_id: int = Field(index=True, unique=True)

    company_name: str
    website_url: str
    canonical_domain: Optional[str] = Field(default=None, index=True)

    selected_contact_name: Optional[str] = None
    selected_contact_title: Optional[str] = None
    selected_email: Optional[str] = None
    selected_contact_type: Optional[str] = None
    selected_source: Optional[str] = None
    selected_source_url: Optional[str] = None

    selection_score: Optional[int] = None
    selection_confidence: Optional[float] = None
    selection_reason: Optional[str] = None

    all_candidate_contacts_json: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class OutreachDraft(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    enriched_lead_id: Optional[int] = Field(default=None, index=True, foreign_key="enrichedlead.id")
    selected_contact_id: int = Field(index=True, unique=True)

    company_name: str
    contact_name: Optional[str] = None
    contact_title: Optional[str] = None
    contact_email: Optional[str] = None

    subject: str
    body: str

    draft_status: str = Field(default="generated", index=True)
    draft_version: int = Field(default=1)

    draft_mode: Optional[str] = None
    personalization_json: Optional[str] = None
    draft_notes: Optional[str] = None

    gmail_draft_id: Optional[str] = Field(default=None, index=True)
    gmail_thread_id: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Conversation(SQLModel, table=True):
    """Represents a single chat thread/session in the sidebar."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    
    # We will auto-generate this title from the user's first prompt (e.g., "Find UK SaaS...")
    title: str = Field(default="New Campaign") 
    
    # Optional: Link this conversation directly to the blueprint it generated
    campaign_brief_id: Optional[int] = Field(default=None, foreign_key="campaignbrief.id")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships (Optional but helpful for SQLAlchemy queries)
    # messages: List["ChatMessage"] = Relationship(back_populates="conversation")


class ChatMessage(SQLModel, table=True):
    """Represents a single message bubble inside a conversation."""
    id: Optional[int] = Field(default=None, primary_key=True)
    conversation_id: int = Field(foreign_key="conversation.id", index=True)
    
    role: str = Field(description="Either 'user' or 'ai'")
    content: str
    
    created_at: datetime = Field(default_factory=datetime.utcnow)