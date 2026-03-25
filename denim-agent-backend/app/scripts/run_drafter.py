import asyncio
import sys

from sqlmodel import Session, create_engine, select

from app.services.drafting.drafter_graph import build_drafter_graph, create_db_and_tables
from app.models.domain import SelectedContact, OutreachDraft

DATABASE_URL = "sqlite:///denim_leads.db"
engine = create_engine(DATABASE_URL, echo=False)


async def main():
    create_db_and_tables()
    graph = build_drafter_graph()

    batch_size = 5
    if len(sys.argv) > 1:
        try:
            batch_size = int(sys.argv[1])
        except ValueError:
            print("Invalid batch size, using 5")

    with Session(engine) as session:
        selected_rows = session.exec(
            select(SelectedContact)
            .where(
                SelectedContact.id.not_in(
                    select(OutreachDraft.selected_contact_id)
                )
            )
            .limit(batch_size)
        ).all()

    if not selected_rows:
        print("No undrafted SelectedContact rows found.")
        return

    for selected in selected_rows:
        result = await graph.ainvoke({"selected_contact_id": selected.id})
        print(
            f"[{result.get('status')}] "
            f"selected_contact_id={selected.id} "
            f"gmail_draft_id={result.get('gmail_draft_id')} "
            f"error={result.get('error')}"
        )


if __name__ == "__main__":
    asyncio.run(main())