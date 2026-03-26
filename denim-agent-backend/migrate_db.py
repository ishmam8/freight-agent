from sqlmodel import create_engine
from sqlalchemy import text

engine = create_engine("sqlite:///./denim_leads.db")

queries = [
    "ALTER TABLE lead ADD COLUMN company_email TEXT",
    "ALTER TABLE lead ADD COLUMN company_phone TEXT",
    "ALTER TABLE lead ADD COLUMN company_location TEXT",
    "ALTER TABLE lead ADD COLUMN contact_priority TEXT",
    "ALTER TABLE lead ADD COLUMN enrichment_notes TEXT",
    "ALTER TABLE lead ADD COLUMN campaign_brief_id INTEGER REFERENCES campaignbrief(id)",
    "ALTER TABLE campaignbrief ADD COLUMN sender_name VARCHAR DEFAULT 'Team'",
    "ALTER TABLE campaignbrief ADD COLUMN sender_company VARCHAR DEFAULT 'Our Company'",
    "ALTER TABLE outreachdraft ADD COLUMN draft_mode VARCHAR",
    "ALTER TABLE outreachdraft ADD COLUMN personalization_json TEXT",
    "ALTER TABLE outreachdraft ADD COLUMN hook_type VARCHAR",
    "ALTER TABLE outreachdraft ADD COLUMN word_count INTEGER",
    "ALTER TABLE outreachdraft ADD COLUMN draft_notes TEXT",
]

with engine.connect() as conn:
    for q in queries:
        try:
            conn.execute(text(q))
        except Exception:
            pass
    conn.commit()

print("Phase 3 migration complete.")