from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session
from app.models.schemas import ResearchRequest, ResearchResponse
from app.core.database import engine, upsert_lead
from app.services.research.researcher import run_hybrid_research

router = APIRouter()

def get_session():
    with Session(engine) as session:
        yield session

@router.post("/start", response_model=ResearchResponse)
async def start_research(request: ResearchRequest, session: Session = Depends(get_session)):
    try:
        found_leads = await run_hybrid_research(request)
        
        new_inserts = 0
        for lead in found_leads:
            if upsert_lead(session, lead):
                new_inserts += 1
                
        return ResearchResponse(
            status="success",
            total_found=len(found_leads),
            new_leads_inserted=new_inserts
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))