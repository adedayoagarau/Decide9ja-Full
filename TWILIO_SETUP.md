# Twilio WhatsApp Setup for Tade

## ✅ Prerequisites

1. **Twilio Account** - You already have one! ✅
2. **WhatsApp Business API** - Approved (or use Twilio Sandbox)
3. **FastAPI App** - Decide9ja backend

## 🔧 Setup Steps

### 1. Install Dependencies

```bash
cd /Volumes/Admin/Decide9ja/decide9ja_backend
source venv/bin/activate  # or your env
pip install twilio
```

### 2. Set Environment Variables

```bash
# Add to .env file or export directly
export TWILIO_ACCOUNT_SID="your_twilio_account_sid_here"
export TWILIO_AUTH_TOKEN="your_twilio_auth_token_here"
export TWILIO_PHONE_NUMBER="your_twilio_phone_number_here"
```

**⚠️ Security Note:** Never commit these to git! Add `.env` to `.gitignore`.

### 3. Update FastAPI Main App

Add to your `main.py` or app entry point:

```python
from fastapi import FastAPI
from app.channels.twilio_whatsapp import router as twilio_router, get_twilio_handler
from app.services.tade_unified import UnifiedTadeHandler

app = FastAPI()

# Initialize Tade
@app.on_event("startup")
async def startup():
    tade = UnifiedTadeHandler()
    # Pass Tade handler to Twilio
    get_twilio_handler(tade_handler=tade)

# Include Twilio webhook routes
app.include_router(twilio_router)
```

### 4. Configure Twilio Webhook

1. Go to [Twilio Console](https://console.twilio.com)
2. Navigate to **Messaging → Try it out → Send a WhatsApp message**
3. Or for production: **Messaging → Settings → WhatsApp Sandbox Settings**
4. Set **Webhook URL**:
   ```
   https://your-domain.com/api/v1/webhook/twilio
   ```
   For local testing, use ngrok:
   ```bash
   ngrok http 8000
   # Use the https URL + /api/v1/webhook/twilio
   ```

### 5. Test the Integration

```bash
# Start your FastAPI app
uvicorn app.main:app --reload

# Test config
curl http://localhost:8000/api/v1/webhook/twilio/test
```

Expected response:
```json
{
  "configured": true,
  "phone_number": "+1XXXXXXXXXX",
  "account_sid_prefix": "ACXXXXXXX..."
}
```

### 6. Send a Test Message

Send WhatsApp to your Twilio number with message:
```
Hello Tade!
```

You should receive a reply from Tade! 🎉

---

## 🧪 Sandbox Mode (Quick Test)

If your WhatsApp Business API isn't fully approved yet:

1. Go to **Messaging → Try it out → Send a WhatsApp message**
2. Send the join code to your sandbox number
3. Twilio will reply with confirmation
4. Now you can test!

---

## 📊 Features

| Feature | Status |
|---------|--------|
| Incoming messages | ✅ Works |
| Outgoing messages | ✅ Works |
| Tade integration | ✅ Integrated |
| Error handling | ✅ Built-in |
| Progress updates | ✅ Example included |

---

## 🔗 Integration with Tade

The `TwilioWhatsAppHandler` class automatically:
1. Receives WhatsApp messages via webhook
2. Extracts phone number and message text
3. Calls `UnifiedTadeHandler.handle_message()`
4. Returns Tade's response via Twilio

All Tade features work immediately:
- Location identification
- Representative lookup
- Budget queries
- Archive searches
- Working memory

---

## 🚀 Production Checklist

- [ ] Environment variables set in production
- [ ] Webhook URL is HTTPS (required by Twilio)
- [ ] Domain whitelisted in Twilio
- [ ] Error monitoring (Sentry recommended)
- [ ] Rate limiting configured
- [ ] Message logging for analytics

---

## 📞 Your Twilio Details

| Setting | Value |
|---------|-------|
| Account SID | Set in environment variables |
| Phone Number | Set in environment variables |
| Region | US |

---

*Need help? Check Twilio docs: https://www.twilio.com/docs/whatsapp/quickstart/python*
