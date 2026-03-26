from sqlmodel import create_engine
from sqlalchemy import text

engine = create_engine("sqlite:///./denim_leads.db")

queries = [
    "ALTER TABLE user ADD COLUMN first_name VARCHAR",
    "ALTER TABLE user ADD COLUMN last_name VARCHAR",
]

with engine.connect() as conn:
    for q in queries:
        try:
            conn.execute(text(q))
        except Exception:
            pass
    conn.commit()

print("Migration for user names complete.")
