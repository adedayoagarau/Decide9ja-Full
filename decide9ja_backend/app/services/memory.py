"""
Conversation Memory Service
Manages user profiles and chat history in PostgreSQL.
"""
import json
import logging
from typing import List, Dict, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from app.database import get_db, User, ChatHistory

logger = logging.getLogger(__name__)

def get_user_profile(db: Session, phone_number: str) -> Optional[Dict]:
    """Get user profile data."""
    try:
        user = db.query(User).filter(User.phone_number == phone_number).first()
        if not user:
            return None
            
        return {
            "phone_number": user.phone_number,
            "name": user.name,
            "state": user.state,
            "lga": user.lga,
            "flow_state": json.loads(user.flow_state) if user.flow_state else {},
            "preferences": json.loads(user.preferences_json) if user.preferences_json else {}
        }
    except Exception as e:
        logger.error(f"Error fetching profile for {phone_number}: {e}")
        return None

def update_user_profile(db: Session, phone_number: str, data: Dict) -> bool:
    """Update or create user profile."""
    try:
        user = db.query(User).filter(User.phone_number == phone_number).first()
        
        if not user:
            user = User(phone_number=phone_number)
            db.add(user)
        
        # Update fields
        if "name" in data:
            user.name = data["name"]
        if "state" in data:
            user.state = data["state"]
        if "lga" in data:
            user.lga = data["lga"]
        if "flow_state" in data:
            user.flow_state = json.dumps(data["flow_state"])
        if "preferences" in data:
            user.preferences_json = json.dumps(data["preferences"])
            
        db.commit()
        return True
    except Exception as e:
        logger.error(f"Error updating profile for {phone_number}: {e}")
        db.rollback()
        return False

def add_message(db: Session, phone_number: str, role: str, content: str, intent: str = None):
    """Save a message to chat history."""
    try:
        msg = ChatHistory(
            user_phone=phone_number,
            role=role,
            content=content,
            intent=intent
        )
        db.add(msg)
        db.commit()
    except Exception as e:
        logger.error(f"Error saving message: {e}")
        db.rollback()

def get_chat_history(db: Session, phone_number: str, limit: int = 6) -> List[Dict]:
    """Get recent chat history for context."""
    try:
        messages = db.query(ChatHistory)\
            .filter(ChatHistory.user_phone == phone_number)\
            .order_by(ChatHistory.timestamp.desc())\
            .limit(limit)\
            .all()
            
        # Reverse to get chronological order
        history = []
        for msg in reversed(messages):
            history.append({
                "role": msg.role,
                "content": msg.content
            })
            
        return history
    except Exception as e:
        logger.error(f"Error fetching history: {e}")
        return []
