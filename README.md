# Local Leads Extractor

A free, local, browser-automation tool that scrapes business leads from Google Maps across multiple domains and cities, and exports them into clean, formatted Excel files — with full resume support if the run is interrupted.

---

## Table of Contents

- [Overview](#overview)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Running the Project](#running-the-project)
- [Output](#output)
- [Documentation](#documentation)

---

## Overview

This tool automates the collection of business lead data from Google Maps for the following domains:

| Domain | What it scrapes |
|---|---|
| **Dental Clinics** | Dentists, orthodontists, dental hospitals |
| **Dermatology Clinics** | Skin doctors, cosmetologists, dermatologists |
| **Real Estate** | Agents, property dealers, builders, consultants |
| **Interiors & Architects** | Interior designers, architects, decoration firms |

For each business it captures: name, category, phone, email, website, address, rating, review count, revenue estimate, team size, and more.

**Key features:**
- 100% free — no API keys, no paid services
- Zone-by-zone scraping across 15 key areas of Hyderabad (configurable)
- Auto-resume — if stopped midway, re-running picks up from the last completed zone
- Per-domain Excel export as each domain finishes, plus a combined Excel at the end
- Website enrichment — extracts emails and estimates revenue from business websites

---

## Tech Stack

| Layer | Tool |
|---|---|
| Browser automation | [Playwright](https://playwright.dev/python/) |
| HTML parsing | [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) |
| Excel export | [openpyxl](https://openpyxl.readthedocs.io/) + [pandas](https://pandas.pydata.org/) |
| HTTP requests | [requests](https://requests.readthedocs.io/) |
| Language | Python 3.10+ |

---

## Prerequisites

- Python 3.10 or higher
- pip
- A working internet connection

---

## Installation

**1. Clone or download the project**

```bash
git clone <your-repo-url>
cd "Lead Generation"
```

**2. Create a virtual environment (recommended)**

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac / Linux
source venv/bin/activate
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

**4. Install Playwright browsers**

```bash
playwright install chromium
```

---

## Running the Project

```bash
python run.py
```

The script will:

1. Check `output/backups/` for any previously completed zones
2. Skip zones that are already backed up and load them from cache
3. Open a Chrome browser and scrape any remaining zones
4. After each zone completes, save a JSON backup immediately
5. After all zones for a domain finish, export a per-domain Excel file
6. After all domains finish, export a combined Excel with all sheets

**To stop and resume later:** Press `Ctrl+C` at any time. All completed zones are saved. Re-run `python run.py` to continue from where it stopped.

### Configuration

| File | What to change |
|---|---|
| `config/cities.json` | Add cities or change which zones are scraped |
| `config/domains.json` | Add new business domains and search queries |
| `run.py` line 56 | `headless=False` → `headless=True` to run without a visible browser (faster) |
| `run.py` line 56 | `delay_range=(2, 4)` → `(1, 2)` to scrape faster (higher bot-detection risk) |
| `run.py` line 62 | `city_key = 'hyderabad'` → change to another city key |

---

## Output

```
output/
├── leads__hyderabad__20260515.xlsx             ← combined all-domain Excel
├── leads__dental_clinics__hyderabad.xlsx       ← per-domain Excel
├── leads__dermatology_clinics__hyderabad.xlsx
├── leads__real_estate__hyderabad.xlsx
├── leads__interiors_architects__hyderabad.xlsx
└── backups/
    ├── dental_clinics__hyderabad__banjara_hills.json
    ├── dental_clinics__hyderabad__jubilee_hills.json
    └── ...  (one JSON per zone per domain)
```

Each Excel file contains:

- **Summary sheet** — total counts, extraction date, breakdown by domain
- **Domain sheets** — one row per business with all extracted fields

---

## Documentation

For architecture diagrams, full API reference, database schema, pipeline details, and development notes —

[View the full technical documentation in DOCS.md →](DOCS.md)
