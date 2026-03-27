import os
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session
from app.core.database import get_session
from app.models.schemas import CheckoutRequest
from app.models.domain import User

# 1. IMPORT YOUR SECURITY DEPENDENCY
from app.api.deps import get_current_user 

router = APIRouter()

stripe.api_key = os.getenv("STRIPE_API_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

@router.post("/checkout")
async def create_checkout_session(
    req: CheckoutRequest, 
    # 2. INJECT THE SECURE USER TOKEN IN THE FUNCTION SIGNATURE
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_session)
):
    # We completely removed the db.get(User, req.user_id) block!
    # If the token is invalid or missing, get_current_user will automatically 
    # block the request and return a 401 Unauthorized before this code even runs.

    if req.action == "priority_air":
        unit_amount = 2500  # $25.00 CAD
        product_name = "Priority Air Subscription"
    elif req.action == "buy_credits":
        unit_amount = 1000  # $10.00 CAD
        product_name = "50 Extra Credits"
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "cad",
                        "unit_amount": unit_amount,
                        "product_data": {
                            "name": product_name,
                        },
                    },
                    "quantity": 1,
                }
            ],
            mode="payment",
            success_url=f"{FRONTEND_URL}/dashboard?checkout=success",
            cancel_url=f"{FRONTEND_URL}/dashboard?checkout=canceled",
            metadata={
                # 3. USE THE SECURE ID DIRECTLY FROM THE DATABASE OBJECT
                "user_id": str(current_user.id), 
                "action": req.action,
            },
        )
        return {"checkout_url": session.url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_session)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        # Invalid payload
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        # 1. Grab the Stripe session object
        session_obj = event["data"]["object"]
        
        # 2. Safely access metadata using dot notation or dictionary access
        metadata = session_obj.metadata if getattr(session_obj, "metadata", None) else {}
        
        # 3. Extract our custom variables
        if isinstance(metadata, dict):
            user_id_str = metadata.get("user_id")
            action = metadata.get("action")
        else:
            user_id_str = getattr(metadata, "user_id", None)
            action = getattr(metadata, "action", None)

        # 4. Update the database
        if user_id_str and action:
            user_id = int(user_id_str)
            user = db.get(User, user_id)
            if user:
                if action == "priority_air":
                    user.subscription_tier = "priority_air"
                    user.credits += 500  
                elif action == "buy_credits":
                    user.credits += 50
                
                db.add(user)
                db.commit()
                
    return {"status": "success"}