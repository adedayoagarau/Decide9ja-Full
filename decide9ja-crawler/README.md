# Decide9ja News Crawler

Azure Function that crawls Nigerian news sites every 2 hours, analyzes sentiment, and stores results in Cosmos DB.

## What It Does

1. **Scrapes** political news from:
   - Punch
   - Premium Times
   - ThisDay
   - Vanguard
   - Channels TV

2. **Analyzes** each headline for:
   - Sentiment (positive/negative/neutral/mixed)
   - Politicians mentioned
   - Topics (economy, security, education, etc.)

3. **Stores** in Cosmos DB for:
   - Decide9ja bot to query
   - Dashboard visualization
   - Trend analysis

## Project Structure

```
decide9ja-crawler/
├── news_crawler/
│   ├── __init__.py      # Main function entry point
│   ├── function.json    # Timer trigger config (every 2 hours)
│   ├── scraper.py       # News site scrapers
│   ├── sentiment.py     # Azure AI Language integration
│   └── database.py      # Cosmos DB operations
├── host.json            # Azure Functions config
├── requirements.txt     # Python dependencies
├── local.settings.json  # Environment variables (DO NOT COMMIT)
└── README.md
```

## Setup

### 1. Create Azure Resources

**Azure AI Language Service:**
```bash
az cognitiveservices account create \
  --name decide9ja-language \
  --resource-group decide9ja-rg \
  --kind TextAnalytics \
  --sku F0 \
  --location westus2 \
  --yes
```

**Cosmos DB (Free Tier):**
```bash
az cosmosdb create \
  --name decide9ja-cosmos \
  --resource-group decide9ja-rg \
  --enable-free-tier true \
  --default-consistency-level Session
```

**Function App:**
```bash
az functionapp create \
  --name decide9ja-crawler \
  --resource-group decide9ja-rg \
  --consumption-plan-location westus2 \
  --runtime python \
  --runtime-version 3.11 \
  --functions-version 4 \
  --storage-account decide9jast
```

### 2. Get Your Keys

**Language Service:**
```bash
az cognitiveservices account keys list \
  --name decide9ja-language \
  --resource-group decide9ja-rg
```

**Cosmos DB:**
```bash
az cosmosdb keys list \
  --name decide9ja-cosmos \
  --resource-group decide9ja-rg
```

### 3. Configure Environment Variables

Update `local.settings.json` with your keys for local testing.

For Azure deployment:
```bash
az functionapp config appsettings set \
  --name decide9ja-crawler \
  --resource-group decide9ja-rg \
  --settings \
    AZURE_LANGUAGE_ENDPOINT="https://decide9ja-language.cognitiveservices.azure.com/" \
    AZURE_LANGUAGE_KEY="your-key" \
    COSMOS_ENDPOINT="https://decide9ja-cosmos.documents.azure.com:443/" \
    COSMOS_KEY="your-key"
```

### 4. Deploy

```bash
# Install Azure Functions Core Tools first
# https://docs.microsoft.com/azure/azure-functions/functions-run-local

# Deploy to Azure
func azure functionapp publish decide9ja-crawler
```

## Local Testing

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run locally
func start
```

## Query Examples

Once data is in Cosmos DB, Decide9ja bot can answer:

- "What's the news about Tinubu today?"
- "What's the sentiment on fuel subsidy?"
- "Show me positive news about the economy"
- "Which politicians are in the news this week?"

## Cost (Free Tier Limits)

| Service | Free Tier | Your Usage |
|---------|-----------|------------|
| Azure Functions | 1M executions/month | ~360/month (12/day) |
| AI Language | 5,000 records/month | ~2,250/month (75 articles × 30 days) |
| Cosmos DB | 1000 RU/s, 25GB | Well within limits |

**You should stay within free tier** unless you scale significantly.

## Adding More Sources

Edit `scraper.py` to add new sources:

```python
NEWS_SOURCES = {
    # ... existing sources ...
    'new_source': {
        'name': 'New Source Name',
        'url': 'https://newssite.com/politics/',
        'parser': 'parse_new_source'
    }
}

def parse_new_source(soup: BeautifulSoup, source_name: str) -> List[Dict]:
    # Implement parser
    pass
```

## Troubleshooting

**No articles scraped:**
- News sites may have changed their HTML structure
- Check `scraper.py` CSS selectors
- Test individual parsers locally

**Sentiment analysis failing:**
- Check Azure AI Language key is valid
- Check you haven't exceeded free tier (5,000/month)
- Fallback sentiment will be used automatically

**Cosmos DB errors:**
- Check connection string
- Ensure database/container exist
- Check RU/s limits
