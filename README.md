# DECIDE9JA - INEC Data Scraper

Scrapes Nigerian electoral data from INEC for the Decide9ja political intelligence platform.

## What This Scrapes

| File | Records | Source |
|------|---------|--------|
| `parties.json` | 18 | inecnigeria.org/political-parties |
| `states.json` | 37 | Nigerian Constitution |
| `lgas.json` | 774 | Nigerian Constitution |
| `senatorial_districts.json` | 109 | Nigerian Constitution |

## Quick Start

### Option 1: Run in Google Antigravity

1. Open this folder in Antigravity
2. Tell the agent:
   ```
   Run the scrape_inec.py script to collect INEC data
   ```
3. Data will be saved to `data/processed/`

### Option 2: Run Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run scraper
python scrape_inec.py
```

### Option 3: Use the Pre-Generated Data

The `data/processed/` folder already contains the scraped data. You can use it directly.

## Output Structure

```
data/
├── raw/                          # Raw HTML pages (for debugging)
└── processed/
    ├── parties.json              # Political parties
    ├── states.json               # Nigerian states
    ├── lgas.json                 # Local Government Areas
    ├── senatorial_districts.json # 109 senatorial districts
    └── _summary.json             # Scrape metadata
```

## Data Schema

### parties.json
```json
{
  "id": "apc",
  "name": "All Progressives Congress",
  "abbreviation": "APC",
  "chairman": "Dr. Abdullahi Umar Ganduje",
  "secretary": "...",
  "treasurer": "...",
  "logo_url": "...",
  "source_url": "https://inecnigeria.org/political-parties/",
  "scraped_at": "2025-12-27T..."
}
```

### states.json
```json
{
  "id": "lagos",
  "name": "Lagos",
  "capital": "Ikeja",
  "region": "South-West",
  "lgas": ["Agege", "Alimosho", ...],
  "senatorial_districts": ["Lagos Central", "Lagos East", "Lagos West"],
  "federal_constituencies": 11,
  "state_constituencies": 20
}
```

### lgas.json
```json
{
  "id": "lagos_alimosho",
  "name": "Alimosho",
  "state": "Lagos",
  "state_id": "lagos"
}
```

## Next Steps: Add Candidate Data

This scraper provides the foundation data. You still need to manually curate:

1. **Candidate profiles** - Not available via scraping (need manual research)
2. **Policy positions** - From manifestos, interviews, debates
3. **Campaign promises** - From campaign events
4. **Voting records** - From National Assembly (partial scraping possible)

### Candidate Data Template

Create `data/candidates/` with files like:

```json
{
  "id": "tinubu_bola_2023_president",
  "name": "Bola Ahmed Tinubu",
  "party_id": "apc",
  "position_sought": "President",
  "election_year": 2023,
  "state_of_origin": "Lagos",
  "bio": {
    "birth_year": 1952,
    "education": [...],
    "career": [...]
  },
  "positions": [
    {
      "issue": "Economy",
      "stance": "Pro-business, privatization",
      "quotes": [
        {
          "text": "We will create 1 million tech jobs",
          "source": "Campaign rally, Lagos",
          "date": "2022-11-15",
          "url": "https://..."
        }
      ]
    }
  ]
}
```

## Antigravity Mission Prompts

### Extend the Scraper

```
MISSION: Add candidate scraping

Look at the scrape_inec.py file and extend it to also scrape:
1. Candidate lists from INEC when they publish them
2. BudgIT data on budget allocations
3. News articles about candidates from Premium Times

Save all scraped data in the data/processed folder.
```

### Create Candidate Database

```
MISSION: Create candidate database

Research and create JSON files for the top 20 candidates for 2027:
- Presidential candidates from major parties
- Lagos gubernatorial candidates
- Oyo gubernatorial candidates

For each candidate, find:
- Basic bio (Wikipedia, news)
- 3-5 policy positions with source URLs
- Notable quotes

Save to data/candidates/{name}.json
```

## Troubleshooting

### Scraper returns few parties
INEC's website structure may have changed. The scraper falls back to a known parties database in this case.

### Rate limiting
The scraper waits 2 seconds between requests to be respectful. Don't decrease this.

### Missing data
Some fields (founded_year, ideology, colors) require manual enrichment or Wikipedia scraping.

## License

MIT - Use this for civic good.
