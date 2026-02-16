# Decide9ja - Nigerian Election Intelligence Platform

[![Status](https://img.shields.io/badge/Status-Active-brightgreen)]()
[![Version](https://img.shields.io/badge/Version-2.0.0-blue)]()
[![Scraper](https://img.shields.io/badge/Scraper-Philip%20Active-orange)]()

## 🎯 Mission

Comprehensive Nigerian election intelligence platform combining historical archives, real-time data, and predictive analytics.

## 🏗️ Architecture

```
Decide9ja/
├── 📁 data/
│   ├── archiving/          # Historical newspaper archives (Philip)
│   ├── catalogs/           # Master indexes & metadata
│   ├── raw/                # Raw scraped data
│   └── processed/          # Cleaned, OCR'd, analyzed data
├── 📁 src/
│   ├── scraper/            # Archivi.ng scraper (Philip)
│   ├── ocr/                # Tesseract OCR pipeline
│   ├── catalog/            # Index & search system
│   ├── api/                # REST API endpoints
│   └── utils/              # Utilities & helpers
├── 📁 config/              # Configuration files
├── 📁 logs/                # Scraping & processing logs
├── 📁 memory/              # Agent memory & progress tracking
├── 📁 docs/                # Documentation
└── 📁 tests/               # Test suites
```

## 🤖 Active Agents (Part of the Agent Fleet - see MEMORY.md for full list)

| Agent | Role | Status | Location |
|-------|------|--------|----------|
| 🔍 **Philip** | Archivi.ng Scraper | 🟢 Nonstop | `src/scraper/` |
| 🗳️ **Thomas** | Decide9ja Monitor | 🟢 Active | Project watchdog |
| 📖 **John** | AI Research | 🟢 Nonstop | Memory & docs |
| ⚔️ **Fleet Alpha** | Abuja Newsweek (REDEPLOYED 2015-2025) | 🟢 Full Content | `data/archiving/` |
| ⚔️ **Fleet Omega** | Akeebatas Scraper (2010-2000) | 🟢 Running | `data/archiving/` |
| 🔍 **Judas** | OCR Processor | 🟢 Running | `src/ocr/` |

## 📰 Archiving Mission

**Target**: 43 Nigerian newspapers (2026 → 1900)
- **Current**: All 43 newspapers in progress
- **Method**: Daily backwards scraping (2026 → 1900)
- **Storage**: `data/archiving/{newspaper}/{YYYY}/{MM-DD}/`
- **Processing**: Download → OCR → Catalog → Index

## 🚀 Quick Start

```bash
# Install dependencies
cd /Volumes/Crucial\ X10/Decide9ja
npm install

# Start archivi.ng scraper (Philip)
npm run scrape:archiving

# Run OCR on downloaded images
npm run ocr:process

# Build catalog index
npm run catalog:build

# Start API server
npm run api:start
```

## 📊 Progress Tracking

- **Issues Archived**: See `memory/SCRAPING_PROGRESS.md`
- **Agent Reports**: WhatsApp updates every 5 min
- **Storage Stats**: See `data/catalogs/storage_stats.json`

## 🔧 Configuration

- **Scraper Config**: `config/scraper.json`
- **OCR Settings**: `config/ocr.json`
- **API Keys**: `.env` (not committed)

## 📝 Documentation

- **System Design**: `docs/ARCHITECTURE.md`
- **Scraper Guide**: `docs/SCRAPER_GUIDE.md`
- **API Reference**: `docs/API.md`

## 🛡️ Industry Standards

- ✅ Structured logging
- ✅ Error handling & recovery
- ✅ Incremental backups
- ✅ Data validation
- ✅ Monitoring & alerts
- ✅ Git version control
- ✅ Environment configs

---

**Last Updated**: 2026-02-05  
**Maintained By**: Agent Fleet (7 Disciples)

## 🤝 Contributing

Contributions are welcome! Please ensure all documentation changes are consistent with project goals and agent memory (`MEMORY.md`).

## ✍️ Documentation Practices

- Keep `MEMORY.md` updated with significant decisions, project progress, and agent roles.
- Ensure `README.md` reflects the most current project status.
- Add specific `docs/` for detailed guides and technical specifications.
