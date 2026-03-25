import asyncio
import sqlite3
from arq import create_pool
from arq.connections import RedisSettings
from app.core.config import settings

async def main():
    redis_pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    
    conn = sqlite3.connect("denim_leads.db")
    cursor = conn.cursor()
    
    # Find all leads currently marked as QUEUED
    cursor.execute("SELECT id, user_id, campaign_brief_id, company_name FROM lead WHERE UPPER(status) = 'QUEUED'")
    rows = cursor.fetchall()
    
    if not rows:
        print("No QUEUED leads found.")
        
    for row in rows:
        lead_id, user_id, campaign_brief_id, company_name = row
        print(f"Re-enqueuing Lead {lead_id} ({company_name}) to ARQ")
        
        if campaign_brief_id:
            await redis_pool.enqueue_job('run_full_pipeline', lead_id, user_id, campaign_brief_id)
            
    conn.commit()
    conn.close()
            
if __name__ == "__main__":
    asyncio.run(main())
