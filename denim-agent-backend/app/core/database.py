from sqlmodel import create_engine, Session, select
from app.models.domain import SQLModel, Lead
from app.models.schemas import LeadCreate
from datetime import datetime

sqlite_url = "sqlite:///./denim_leads.db"
engine = create_engine(sqlite_url, echo=False)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def upsert_lead(session: Session, lead_data: LeadCreate) -> bool:
    normalized_url = lead_data.website_url 
    statement = select(Lead).where(Lead.website_url == normalized_url)
    existing_lead = session.exec(statement).first()
    
    if existing_lead:
        existing_lead.last_seen_at = datetime.utcnow()
        session.add(existing_lead)
        session.commit()
        return False
    else:
        new_lead = Lead(
            company_name=lead_data.company_name,
            website_url=normalized_url,
            category=lead_data.category,
            description=lead_data.description,
            source=lead_data.source
        )
        session.add(new_lead)
        session.commit()
        return True