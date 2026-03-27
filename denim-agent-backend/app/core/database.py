from sqlmodel import create_engine, Session, select
from app.models.domain import SQLModel, Lead
from app.models.schemas import LeadCreate
from datetime import datetime
import os

# Get the Railway URL
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not found! Postgres is required.")

# Fix: SQLAlchemy requires 'postgresql://', but Railway often provides 'postgres://'
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
engine = create_engine(DATABASE_URL, echo=False)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session

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