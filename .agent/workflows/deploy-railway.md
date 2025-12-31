---
description: Deploy Decide9ja Backend to Railway
---

# Deploy Decide9ja Backend to Railway

This workflow deploys the `decide9ja_backend` scheduler to Railway for 24/7 news crawling operation.

## Prerequisites
- Railway account (sign up at https://railway.app)
- Railway CLI installed

## Step 1: Install Railway CLI
```bash
brew install railway
```

## Step 2: Login to Railway
```bash
railway login
```
This will open a browser for authentication.

## Step 3: Initialize the Project
```bash
cd /Users/Admin/Decide9ja/decide9ja_backend
railway init
```
Select "Create new project" when prompted.

## Step 4: Configure Environment Variables
In the Railway dashboard (https://railway.app/dashboard), go to your project and add these variables:

Required:
- `ANTHROPIC_API_KEY` - Your Claude API key

Optional (for full functionality):
- `WHATSAPP_PHONE_NUMBER_ID` - WhatsApp Business phone number ID
- `WHATSAPP_ACCESS_TOKEN` - WhatsApp Business access token
- `WHATSAPP_VERIFY_TOKEN` - Webhook verification token
- `OPENAI_API_KEY` - For Whisper transcription
- `SERPER_API_KEY` - For web search
- `GOOGLE_MAPS_API_KEY` - For geocoding
- `ELEVENLABS_API_KEY` - For voice synthesis

## Step 5: Deploy
```bash
railway up
```
Railway will build and deploy automatically.

## Step 6: Check Logs
```bash
railway logs
```

## Important Notes

### Database
The deployed version uses SQLite which is ephemeral on Railway. For persistent data:
1. Add a PostgreSQL plugin in Railway dashboard
2. Update `DATABASE_URL` environment variable to the PostgreSQL connection string

### Monitoring
Check the scheduler is running:
```bash
railway logs -f
```

### Redeploying After Changes
```bash
cd /Users/Admin/Decide9ja/decide9ja_backend
railway up
```
