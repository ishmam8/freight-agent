import asyncio
from sqlmodel import Session, select
from arq import create_pool
from arq.connections import RedisSettings

from app.core.database import engine, create_db_and_tables
from app.models.domain import User, Lead, LeadStatus, LeadCategory
from app.core.config import settings

import uuid

async def main():
    create_db_and_tables()
    
    with Session(engine) as session:
        user = session.exec(select(User)).first()
        if not user:
            user = User(email="test_worker_verification@example.com", hashed_password="hashed")
            session.add(user)
            session.commit()
            session.refresh(user)
            
        new_lead = Lead(
            user_id=user.id,
            company_name=f"Vogue {uuid.uuid4().hex[:6]}",
            website_url=f"https://www.vogue-{uuid.uuid4().hex[:6]}.com",
            category=LeadCategory.INDEPENDENT_BRAND,
            source="manual",
            status=LeadStatus.QUEUED
        )
        session.add(new_lead)
        session.commit()
        session.refresh(new_lead)
        lead_id = new_lead.id
        user_id = user.id
        print(f"Created Lead {lead_id} with status QUEUED")
        
    redis_pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    await redis_pool.enqueue_job('run_full_pipeline', lead_id, user_id)
    await redis_pool.close()
    print(f"Enqueued job run_full_pipeline for lead {lead_id}.")
    
    for i in range(30):
        with Session(engine) as session:
            lead = session.get(Lead, lead_id)
            print(f"[{i*2}s] Current Status: {lead.status}")
            if lead.status in [LeadStatus.COMPLETED, LeadStatus.REJECTED, LeadStatus.FETCH_FAILED]:
                print("Pipeline finished or rejected.")
                break
        await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())
