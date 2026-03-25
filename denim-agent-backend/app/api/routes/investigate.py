from fastapi import APIRouter
from sqlmodel import Session

from app.core.database import engine
from app.services.investigator import run_phase_2_investigation

router = APIRouter()


@router.post("/run")
async def run_investigator(batch_size: int = 10):
    with Session(engine) as session:
        result = await run_phase_2_investigation(session, batch_size=batch_size)
        return result