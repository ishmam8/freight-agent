from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.database import create_db_and_tables
from app.api.routes import research, investigate, auth, campaigns, billing

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield

app = FastAPI(title="Denim Sourcing Agent Phase 1", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"], # Allows your Next.js frontend
    allow_credentials=True,
    allow_methods=["*"], # The "*" allows POST, GET, and the crucial OPTIONS method
    allow_headers=["*"], # The "*" allows the Authorization header to pass through
)

# Include the router we built in the api/routes folder
app.include_router(research.router, prefix="/api/research", tags=["Research"])
app.include_router(investigate.router, prefix="/api/investigate", tags=["Investigate"])
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(campaigns.router, prefix="/api/campaigns", tags=["Campaigns"])
app.include_router(billing.router, prefix="/api/billing", tags=["Billing"])

@app.get("/")
async def health_check():
    return {"status": "Agent Backend is Running"}