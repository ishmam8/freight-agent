from sqlmodel import Session, select
from app.core.database import engine
from app.models.domain import Lead
from app.services.investigator import investigate_lead
import asyncio


async def test_one():
    with Session(engine) as session:
        lead = session.exec(select(Lead)).first()

        result = await investigate_lead(lead)

        print(result)

asyncio.run(test_one())