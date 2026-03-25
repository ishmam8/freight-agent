from sqlmodel import create_engine
from sqlalchemy import text

engine = create_engine("sqlite:///./denim_leads.db")

queries = [
    "ALTER TABLE user ADD COLUMN tier TEXT DEFAULT 'free';",
]

with engine.connect() as conn:
    for q in queries:
        try:
            conn.execute(text(q))
        except Exception as e:
            print(f"Error executing {q}: {e}")
            pass
    conn.commit()

print("User tier migration complete.")
