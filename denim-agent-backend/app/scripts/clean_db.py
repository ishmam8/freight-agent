import sys
from typing import Type, Optional
from sqlmodel import Session, select, create_engine, SQLModel

from app.models.domain import EnrichedLead, Lead, SelectedContact, OutreachDraft

DATABASE_URL = "sqlite:///denim_leads.db"
engine = create_engine(DATABASE_URL, echo=False)

MODEL_MAP: dict[str, Type[SQLModel]] = {
    "enrichedlead": EnrichedLead,
    "lead": Lead,
    "selectedcontact": SelectedContact,
    "outreachdraft": OutreachDraft,
}


def count_rows(session: Session, model: Type[SQLModel]) -> int:
    rows = session.exec(select(model)).all()
    return len(rows)


def delete_all(session: Session, model: Type[SQLModel]) -> int:
    rows = session.exec(select(model)).all()
    count = len(rows)
    for row in rows:
        session.delete(row)
    session.commit()
    return count


def delete_by_lead_ids_from_enriched_leads(session: Session, lead_ids: list[int]) -> int:
    rows = session.exec(
        select(EnrichedLead).where(EnrichedLead.lead_id.in_(lead_ids))
    ).all()
    count = len(rows)
    for row in rows:
        session.delete(row)
    session.commit()
    return count


def clear_columns_from_outreachdraft(
    session: Session,
    col_name: str,
    limit: Optional[int] = None,
) -> int:
    if col_name not in OutreachDraft.__table__.columns:
        raise ValueError(f"Unknown OutreachDraft column: {col_name}")

    column = OutreachDraft.__table__.columns[col_name]
    statement = select(OutreachDraft).where(column.is_not(None))

    if limit is not None:
        statement = statement.limit(limit)

    rows = session.exec(statement).all()
    count = len(rows)

    for row in rows:
        setattr(row, col_name, None)
        session.add(row)

    session.commit()
    return count


from sqlmodel import Session, select
from sqlalchemy import delete
from app.core.database import engine # Adjust this import if your engine is elsewhere

from app.models.domain import (
    OutreachDraft,
    SelectedContact,
    EnrichedLead,
    Lead
)

def delete_last_10_leads():
    with Session(engine) as session:
        print("🔍 Searching for the last 10 leads...")
        
        # 1. Grab the last 10 leads (ordered by ID descending)
        recent_leads = session.exec(
            select(Lead).order_by(Lead.id.desc()).limit(5)
        ).all()
        
        if not recent_leads:
            print("No leads found in the database.")
            return

        # Extract their exact IDs into a list
        lead_ids = [lead.id for lead in recent_leads]
        print(f"🎯 Target Acquired. Deleting cascade for Lead IDs: {lead_ids}")

        # 2. Find the associated EnrichedLead IDs so we can delete their drafts
        enriched_leads = session.exec(
            select(EnrichedLead).where(EnrichedLead.lead_id.in_(lead_ids))
        ).all()
        enriched_lead_ids = [e.id for e in enriched_leads]

        # 3. Delete OutreachDrafts linked to these enriched leads
        if enriched_lead_ids:
            session.exec(
                delete(OutreachDraft).where(OutreachDraft.enriched_lead_id.in_(enriched_lead_ids))
            )
            print("[-] Deleted corresponding OutreachDrafts")

        # 4. Delete SelectedContacts linked to these leads
        session.exec(
            delete(SelectedContact).where(SelectedContact.lead_id.in_(lead_ids))
        )
        print("[-] Deleted corresponding SelectedContacts")

        # 5. Delete EnrichedLeads linked to these leads
        session.exec(
            delete(EnrichedLead).where(EnrichedLead.lead_id.in_(lead_ids))
        )
        print("[-] Deleted corresponding EnrichedLeads")

        # 6. Delete the Leads themselves
        session.exec(
            delete(Lead).where(Lead.id.in_(lead_ids))
        )
        print("[-] Deleted the Leads")

        # Commit the transaction to finalize the surgical strike
        session.commit()
        print("✅ Successfully cleared the last 10 leads! Ready for your next test.")



def main():
    if len(sys.argv) < 3:
        print("Usage:")
        print("  python -m app.scripts.clean_db delete_all <model>")
        print("  python -m app.scripts.clean_db delete_enriched_by_lead_ids 1 2 3")
        print("  python -m app.scripts.clean_db clear_outreachdraft_column <column_name> [limit]")
        print("Models: enrichedlead, lead, selectedcontact, outreachdraft")
        return

    mode = sys.argv[1].strip().lower()

    with Session(engine) as session:
        if mode == "delete_all":
            model_name = sys.argv[2].strip().lower()
            model = MODEL_MAP.get(model_name)

            if not model:
                print(f"Unknown model: {model_name}")
                print("Models: enrichedlead, lead, selectedcontact, outreachdraft")
                return

            before = count_rows(session, model)
            print(f"{model.__name__} rows before: {before}")

            deleted = delete_all(session, model)
            print(f"Deleted {deleted} rows from {model.__name__}.")

            after = count_rows(session, model)
            print(f"{model.__name__} rows after: {after}")
            return

        if mode == "delete_enriched_by_lead_ids":
            try:
                lead_ids = [int(x) for x in sys.argv[2:]]
            except ValueError:
                print("All lead IDs must be integers.")
                return

            before = count_rows(session, EnrichedLead)
            print(f"EnrichedLead rows before: {before}")

            deleted = delete_by_lead_ids_from_enriched_leads(session, lead_ids)
            print(f"Deleted {deleted} EnrichedLead rows for lead_ids={lead_ids}.")

            after = count_rows(session, EnrichedLead)
            print(f"EnrichedLead rows after: {after}")
            return

        if mode == "clear_outreachdraft_column":
            col_name = sys.argv[2].strip()
            limit = None

            if len(sys.argv) > 3:
                try:
                    limit = int(sys.argv[3])
                except ValueError:
                    print("Limit must be an integer.")
                    return

            try:
                before = count_rows(session, OutreachDraft)
                print(f"OutreachDraft rows total: {before}")

                cleared = clear_columns_from_outreachdraft(session, col_name, limit)
                print(f"Cleared column '{col_name}' for {cleared} OutreachDraft rows.")
            except ValueError as e:
                print(str(e))
            return

        print("Unknown mode.")
        print("Use one of:")
        print("  python -m app.scripts.clean_db delete_all <model>")
        print("  python -m app.scripts.clean_db delete_enriched_by_lead_ids 1 2 3")
        print("  python -m app.scripts.clean_db clear_outreachdraft_column <column_name> [limit]")


if __name__ == "__main__":
    # main()
    delete_last_10_leads()