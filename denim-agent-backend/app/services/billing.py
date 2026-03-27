from sqlmodel import Session
from app.models.domain import User

def get_user_credits(user_id: int, db: Session) -> int:
    """
    Returns the exact number of successful AI deliveries they have left.
    """
    user = db.get(User, user_id)
    if not user:
        return 0
    return user.credits

def decrement_user_credits(user_id: int, db: Session, amount: int = 1) -> bool:
    """
    Decrements the user's credits by the specified amount.
    Returns True if successful, False if insufficient credits or user not found.
    """
    user = db.get(User, user_id)
    if not user:
        return False
    
    if user.credits < amount:
        return False
        
    user.credits -= amount
    db.add(user)
    db.commit()
    return True
