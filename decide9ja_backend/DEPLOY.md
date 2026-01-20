# Decide9ja V5 Multi-Agent Deployment Guide

## Overview

This document covers deployment of the V5 multi-agent architecture.

**Architecture:** Database First, LLM Last
**Cost Target:** 80% of queries at $0 (database + cache + rules)

---

## Pre-Deployment Checklist

### 1. Environment Variables

Add these to your deployment environment (Railway, Heroku, etc.):

```bash
# REQUIRED: Core Feature Flags
USE_V5=false                    # Start with false, enable gradually
V5_ROLLOUT_PERCENTAGE=0         # Gradual rollout (0-100%)

# RECOMMENDED: Safety
AUTO_FALLBACK_ON_ERROR=true     # Auto-fallback to v4 on errors
MAX_CONSECUTIVE_ERRORS=10       # Disable v5 after N consecutive errors
ENABLE_QUALITY_CHECKS=true      # Response quality validation

# RECOMMENDED: Analytics & Logging
ENABLE_ANALYTICS=true           # B2B analytics collection
ENABLE_AGENT_METRICS=true       # Agent performance tracking
LOG_HANDOFFS=true               # Log agent handoffs
LOG_RESPONSE_TIMES=true         # Log response times

# OPTIONAL: Performance
ENABLE_CACHING=true             # Response caching
CACHE_TTL_SECONDS=3600          # Cache TTL (1 hour default)
ENABLE_FAST_PATH=true           # Skip agent chain for greetings/help

# OPTIONAL: Debug (staging only)
DEBUG_AGENTS=false              # Detailed agent logging

# OPTIONAL: Cost Control
MAX_LLM_CALLS_PER_REQUEST=3     # Limit LLM calls per request
DAILY_LLM_BUDGET_USD=0          # Daily budget (0 = unlimited)
```

### 2. Database Migrations

**No database migrations required for V5.**

The multi-agent system uses the existing database schema. All agents query the same `Politician`, `Document`, and `Interaction` tables.

### 3. Dependencies

Ensure all dependencies are installed:

```bash
pip install -r requirements.txt
```

No new dependencies added for V5.

---

## Deployment Steps

### Stage 1: Deploy with V5 Disabled (Safe)

1. Deploy code with `USE_V5=false`
2. Verify v4 still works correctly
3. Monitor logs for any import errors

```bash
# Verify deployment
curl https://your-app.railway.app/health
```

### Stage 2: Enable V5 for Testing (10% Rollout)

1. Set `V5_ROLLOUT_PERCENTAGE=10`
2. Monitor logs for:
   - Agent handoffs
   - Response times
   - Any fallback triggers

```bash
# Railway
railway variables set V5_ROLLOUT_PERCENTAGE=10
```

### Stage 3: Gradual Rollout (25% → 50% → 100%)

1. Increase rollout percentage gradually:
   ```bash
   V5_ROLLOUT_PERCENTAGE=25  # Wait 1 hour
   V5_ROLLOUT_PERCENTAGE=50  # Wait 1 hour
   V5_ROLLOUT_PERCENTAGE=100 # Full rollout
   ```

2. Monitor at each stage:
   - Error rates
   - Response times
   - User feedback

### Stage 4: Full V5 Activation

Once confident, switch to direct V5:

```bash
USE_V5=true
V5_ROLLOUT_PERCENTAGE=0  # Not needed when USE_V5=true
```

---

## Rollback Procedure

### Immediate Rollback (< 30 seconds)

Set `USE_V5=false` in environment:

```bash
# Railway
railway variables set USE_V5=false

# Heroku
heroku config:set USE_V5=false

# Manual restart if needed
railway restart
```

### Automatic Rollback

V5 auto-disables after `MAX_CONSECUTIVE_ERRORS` (default: 10) consecutive errors.

Check logs for:
```
V5 auto-disabled after 10 consecutive errors
```

### Code Rollback

If code changes are needed, revert to previous commit:

```bash
git revert HEAD
git push origin main
```

---

## Monitoring

### Key Metrics to Watch

1. **Response Time**
   ```
   [abc123] Completed in 45ms | agents=gatekeeper→classifier→router→rep_lookup | intent=rep_lookup | cost=FREE
   ```

2. **Agent Chain**
   - Normal: `gatekeeper→classifier→router→specialist`
   - Problem: More than 5 handoffs

3. **Fallback Triggers**
   ```
   [abc123] Falling back to V4
   ```

4. **Cost Levels**
   - Target: 80% FREE
   - Warning: >30% EXPENSIVE

### Log Queries

```bash
# Find all fallbacks
grep "Falling back to V4" app.log

# Find slow requests (>500ms)
grep "Completed in [5-9][0-9][0-9]ms" app.log

# Find errors
grep "V5 error" app.log

# Agent distribution
grep "intent=" app.log | cut -d'|' -f3 | sort | uniq -c | sort -rn
```

### Health Check Endpoints

```bash
# Basic health
GET /health

# Agent stats (if implemented)
GET /admin/agent-stats

# Feature flags (if implemented)
GET /admin/feature-flags
```

---

## Architecture Reference

### Agent Flow

```
User Message
    ↓
┌─────────────┐
│ Gatekeeper  │ ← User recognition (FREE)
└─────┬───────┘
      ↓
┌─────────────┐
│ Classifier  │ ← Intent detection (70% FREE)
└─────┬───────┘
      ↓
┌─────────────┐
│   Router    │ ← Agent dispatch (FREE)
└─────┬───────┘
      ↓
┌─────────────────────────────────────┐
│           Specialists               │
│  ┌──────────┐  ┌──────────────┐    │
│  │RepLookup │  │PoliticianProf│    │
│  └──────────┘  └──────────────┘    │
│  ┌──────────┐  ┌──────────────┐    │
│  │Election  │  │  NewsQuery   │    │
│  └──────────┘  └──────────────┘    │
│  ┌──────────┐  ┌──────────────┐    │
│  │ Promise  │  │ IssueIntake  │    │
│  └──────────┘  └──────────────┘    │
└─────────────────────────────────────┘
      ↓
┌─────────────┐
│  Response   │ ← Format for WhatsApp
└─────────────┘
```

### Cost Levels

| Level | Description | Example |
|-------|-------------|---------|
| FREE | Database + rules only | Rep lookup |
| CHEAP | Small model call | Intent clarification |
| MEDIUM | Standard model call | Complex query |
| EXPENSIVE | Multiple LLM calls | Multi-step reasoning |

### Agent Registry

| Agent | Tier | Cost | Intents Handled |
|-------|------|------|-----------------|
| gatekeeper | 1 | FREE | User recognition |
| classifier | 1 | CHEAP | All intents |
| router | 1 | FREE | All intents |
| rep_lookup | 2 | FREE | REP_LOOKUP |
| politician_profile | 2 | FREE | POLITICIAN_INFO |
| election_info | 2 | FREE | ELECTION_INFO, VOTER_REG |
| news_query | 2 | CHEAP | NEWS_QUERY, TRENDING |
| promise_lookup | 2 | FREE | PROMISE_LOOKUP |
| issue_intake | 4 | CHEAP | REPORT_ISSUE |
| fallback | 5 | FREE | UNKNOWN |
| data_collector | 6 | FREE | Analytics |

---

## Troubleshooting

### "Agent 'X' not found"

```
[abc123] Agent 'foo' not found, using fallback
```

**Cause:** Router is trying to dispatch to an unregistered agent.

**Fix:**
1. Check agent is imported in `app/agents/__init__.py`
2. Check agent has `@register_agent` decorator
3. Verify agent name matches router mapping

### "Max handoffs exceeded"

```
[abc123] Max handoffs (10) exceeded
```

**Cause:** Infinite loop in agent chain.

**Fix:**
1. Check agent outputs have correct `handoff_to`
2. Verify no circular handoffs
3. Check classifier is returning valid intents

### High Error Rate

If error rate exceeds normal:

1. Check `AUTO_FALLBACK_ON_ERROR=true`
2. Temporarily reduce rollout: `V5_ROLLOUT_PERCENTAGE=0`
3. Review logs for common errors
4. Fix issues, redeploy, resume rollout

### Slow Response Times

If p99 latency increases:

1. Enable `DEBUG_AGENTS=true` temporarily
2. Check agent timing breakdown in logs
3. Identify slow agents
4. Consider caching: `ENABLE_CACHING=true`

---

## Emergency Contacts

- **On-call:** Check #decide9ja-alerts Slack channel
- **Rollback authority:** Any team member can set `USE_V5=false`

---

## Version History

| Date | Version | Changes |
|------|---------|---------|
| 2024-01-XX | 5.0.0 | Initial multi-agent architecture |

---

## Quick Reference

```bash
# Enable V5 fully
USE_V5=true

# Disable V5 (rollback)
USE_V5=false

# Gradual rollout (10%)
USE_V5=false
V5_ROLLOUT_PERCENTAGE=10

# Debug mode (staging only)
DEBUG_AGENTS=true
LOG_HANDOFFS=true
LOG_RESPONSE_TIMES=true
```
