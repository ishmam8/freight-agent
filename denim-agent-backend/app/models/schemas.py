from pydantic import BaseModel, HttpUrl, field_validator, Field
from typing import Optional
from urllib.parse import urlparse
from app.models.domain import LeadCategory # Absolute import

class LeadCreate(BaseModel):
    company_name: str
    website_url: HttpUrl
    category: LeadCategory
    description: Optional[str] = None
    source: str

    @field_validator('website_url', mode='after')
    def normalize_url(cls, v: HttpUrl) -> str:
        parsed = urlparse(str(v))
        domain = parsed.netloc.replace("www.", "").lower()
        return domain

class ResearchRequest(BaseModel):
    category: LeadCategory
    location: str = Field(default="Canada")
    target_url: Optional[HttpUrl] = None
    num_results: int = Field(default=10, le=100)

class ResearchResponse(BaseModel):
    status: str
    total_found: int
    new_leads_inserted: int

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenPayload(BaseModel):
    sub: Optional[str] = None

class PromptRequest(BaseModel):
    prompt: str
    conversation_id: Optional[int] = None

class UserCreate(BaseModel):
    email: str
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None

class UserProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None

class UserProfileResponse(BaseModel):
    id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: str
    subscription_tier: str
    credits: int
    stripe_customer_id: Optional[str] = None

class LaunchRequest(BaseModel):
    conversation_id: Optional[int] = None
    original_prompt: str
    target_audience: str
    banned_terms: list[str]
    buyer_titles: list[str]
    value_proposition: str
    exa_search_queries: list[str]
    sender_name: str = "Team"
    sender_company: str = "Our Company"

class DraftUpdateRequest(BaseModel):
    subject: str
    body: str

class CheckoutRequest(BaseModel):
    action: str
