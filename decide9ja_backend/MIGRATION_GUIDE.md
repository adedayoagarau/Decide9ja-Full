"""
MIGRATION: Connect UnifiedTadeHandler to Webhook

This file shows exactly what to change in app/routers/webhook.py
to complete the OLD Tade + NEW Tade merger.
"""

# ============================================================================
# STEP 1: Add imports at the top of webhook.py
# ============================================================================

# AFTER existing imports, ADD these:
from app.services.tade_unified import UnifiedTadeHandler

# Initialize the unified handler (singleton pattern)
_unified_handler = None

def get_unified_handler():
    global _unified_handler
    if _unified_handler is None:
        _unified_handler = UnifiedTadeHandler()
    return _unified_handler


# ============================================================================
# STEP 2: Replace Meta webhook handler (around line 130)
# ============================================================================

# REPLACE this line:
background_tasks.add_task(handle_whatsapp_message, payload)

# WITH this:
background_tasks.add_task(process_with_unified_handler, payload)


# ADD this new function (before the routes):
async def process_with_unified_handler(payload: dict):
    """
    Process WhatsApp message using UnifiedTadeHandler (NEW Tade).
    This merges OLD Tade features with NEW Tade enhancements.
    """
    try:
        handler = get_unified_handler()
        
        # Extract message from payload
        entries = payload.get("entry", [])
        for entry in entries:
            changes = entry.get("changes", [])
            for change in changes:
                value = change.get("value", {})
                messages = value.get("messages", [])
                
                for msg in messages:
                    user_id = msg.get("from")
                    text = ""
                    
                    if msg.get("type") == "text":
                        text = msg.get("text", {}).get("body", "")
                    
                    if user_id and text:
                        # Use UnifiedTadeHandler (merges old + new)
                        response = await handler.handle_message(
                            phone=user_id,
                            message=text
                        )
                        
                        # Send response back via Meta API
                        from app.services import whatsapp
                        whatsapp.send_message(user_id, response)
                        
    except Exception as e:
        logger.error(f"Unified handler error: {e}")


# ============================================================================
# STEP 3: Replace Twilio webhook handler (around line 195)
# ============================================================================

# REPLACE this block:
response = await process_multimodal_message(message, user_hash)

# WITH this:
handler = get_unified_handler()
response = await handler.handle_message(
    phone=message["from"],
    message=message.get("text", "")
)


# ============================================================================
# STEP 4: Add Archive Integration to tade_unified.py
# ============================================================================

# In app/services/tade_unified.py, add to UnifiedTadeHandler.handle_message():

# After intent detection, ADD:
if intent == "archive_search" or any(word in message_lower for word in ["news", "archive", "history", "past"]):
    from app.services.archive_integration import query_archive
    archive_results = query_archive(message)
    if archive_results:
        response = f"📰 *Archive Results:*\n\n{archive_results}\n\n{response}"


# ============================================================================
# STEP 5: Create archive_integration.py
# ============================================================================

# Create app/services/archive_integration.py:
"""
"""
Archive Integration for Tade
Queries the archivi.ng database for historical news.
"""

import json
import sqlite3
from pathlib import Path
from typing import List, Dict, Optional

def query_archive(query: str, politician: str = None, year: int = None, limit: int = 5) -> str:
    \"\"\"
    Query historical news archives.
    
    Args:
        query: Search query (e.g., "Obasanjo corruption 2007")
        politician: Filter by politician name
        year: Filter by year
        limit: Max results
        
    Returns:
        Formatted results or None if no database
    \"\"\"
    # Check if database exists
    db_path = Path("/Users/adedayoagarau/.openclaw/workspace/beast-crawler/data/decide9ja.db")
    if not db_path.exists():
        return None
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Search in OCR text
        sql = """
            SELECT date, ocr_text, source 
            FROM articles 
            WHERE ocr_text LIKE ? 
        """
        params = [f"%{query}%"]
        
        if politician:
            sql += " AND ocr_text LIKE ?"
            params.append(f"%{politician}%")
        
        if year:
            sql += " AND year = ?"
            params.append(year)
        
        sql += " ORDER BY date DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(sql, params)
        results = cursor.fetchall()
        
        if not results:
            return None
        
        # Format results
        formatted = []
        for date, text, source in results:
            preview = text[:200].replace("\n", " ")
            formatted.append(f"📅 {date} ({source}): {preview}...")
        
        return "\n\n".join(formatted)
        
    except Exception as e:
        print(f"Archive query error: {e}")
        return None
    finally:
        if conn:
            conn.close()


# ============================================================================
# STEP 6: Test the merger
# ============================================================================

# After making changes, test with:
curl -X POST http://localhost:8000/webhook/twilio \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "From=whatsapp:+2348160179151" \
  -d "Body=Hello Tade" \
  -d "MessageSid=test123"

# Check logs for:
# - "📩 WhatsApp from..." (Twilio receiving)
# - "UnifiedTadeHandler initialized" (handler active)
# - "📤 Replying to..." (response sent)

# ============================================================================
# VERIFICATION CHECKLIST
# ============================================================================

# [ ] UnifiedTadeHandler imported in webhook.py
# [ ] get_unified_handler() function added
# [ ] Meta webhook uses process_with_unified_handler()
# [ ] Twilio webhook uses handler.handle_message()
# [ ] archive_integration.py created
# [ ] Archive query added to intent handling
# [ ] Test message returns Tade response
# [ ] Logs show "UnifiedTadeHandler" activity
# [ ] Working memory persists between messages
# [ ] Supermemory stores conversation history

# ============================================================================
# ROLLBACK PLAN (if something breaks)
# ============================================================================

# Just comment out the new lines and uncomment the old ones:
# - Switch back to handle_whatsapp_message for Meta
# - Switch back to process_multimodal_message for Twilio
# - App will use OLD Tade (v4) again
