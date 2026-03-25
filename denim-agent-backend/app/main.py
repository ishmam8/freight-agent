from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.core.database import create_db_and_tables
from app.api.routes import research, investigate, auth, campaigns

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield

app = FastAPI(title="Denim Sourcing Agent Phase 1", lifespan=lifespan)

# Include the router we built in the api/routes folder
app.include_router(research.router, prefix="/api/research", tags=["Research"])
app.include_router(investigate.router, prefix="/api/investigate", tags=["Investigate"])
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(campaigns.router, prefix="/api/campaigns", tags=["Campaigns"])

@app.get("/")
async def health_check():
    return {"status": "Agent Backend is Running"}