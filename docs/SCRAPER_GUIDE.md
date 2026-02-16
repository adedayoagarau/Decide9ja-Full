# Archivi.ng Scraper Configuration

## Mission
Scrape 10 Nigerian newspapers from archivi.ng (2026-02-05 → 2020-01-01)

## Target Newspapers
1. PM News - ACTIVE
2. The Guardian
3. Vanguard
4. Punch
5. Daily Trust
6. ThisDay
7. Tribune
8. Sun
9. Nation
10. Leadership

## Date Range
- **Start**: 2026-02-05 (today)
- **End**: 2020-01-01
- **Total Days**: ~2,191 days per newspaper
- **Estimated Issues**: ~21,910

## Storage Structure
```
data/archiving/
├── pmnews/
│   ├── 2026/
│   │   ├── 02/
│   │   │   ├── 05/
│   │   │   │   ├── metadata.json
│   │   │   │   ├── issue_001.jpg
│   │   │   │   └── issue_001_ocr.txt
│   │   │   └── 04/
│   │   └── 01/
│   ├── 2025/
│   └── ... (back to 2020)
├── guardian/
└── ...
```

## Progress Tracking
- **File**: `memory/SCRAPING_PROGRESS.json`
- **Updated**: After every date processed
- **Fields**:
  - currentNewspaper (index)
  - currentDate (YYYY-MM-DD)
  - totalIssues (count)
  - lastRun (timestamp)
  - newspapers (object with per-paper stats)

## Configuration
See `src/scraper/archiving.js`:
- concurrency: 2
- delay: 3000ms between requests
- timeout: 60000ms
- retries: 3
- headless: true

## Logs
- **Info**: `logs/archiving.log`
- **Errors**: `logs/archiving-error.log`

## Running
```bash
npm run scrape:archiving
```

## Monitoring
Agent Philip runs every 5 minutes.
Reports progress to WhatsApp.

Last Updated: 2026-02-05 09:45 PST
