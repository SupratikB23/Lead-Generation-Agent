# Lead Generation Agent

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

This tool automates the collection of business lead data from Google Maps for **any city** and **any business domain** you define. You configure your target cities, neighbourhoods, and business categories through simple JSON files — no code changes required.

**Example domains you can scrape:**<br>
Dental Clinics · Dermatology · Real Estate · Interior Designers · Restaurants · Gyms · Law Firms · Digital Marketing Agencies · Hospitals · Schools · CA Firms · Wedding Planners — or anything else on Google Maps.

**Example cities:**<br>
Hyderabad · Mumbai · Bangalore · Delhi · New York · London — any city with a Google Maps presence works.

For each business it captures: name, category, phone, email, website, address, rating, review count, revenue estimate, team size, and more.

**Key features:**
- 100% free — no API keys, no paid services
- Fully configurable — any city, any zone, any business domain via JSON
- Zone-by-zone scraping for complete coverage (Google Maps caps results per search)
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

### Step 1 — Set up your config files

The repo ships with example config files. Copy them and edit to match your targets:

```bash
cp config/cities_example.json config/cities.json
cp config/domains_example.json config/domains.json
```

> `cities.json` and `domains.json` are gitignored — they stay local to your machine.

**Edit `config/cities.json`** — add the city and zones you want to scrape:

```json
{
  "mumbai": {
    "name": "Mumbai",
    "state": "Maharashtra",
    "country": "India",
    "zones": ["Bandra", "Andheri", "Powai", "Lower Parel"]
  }
}
```

**Edit `config/domains.json`** - keep only the domains you need, or add new ones:

```json
{
  "restaurants": {
    "name": "Restaurants",
    "search_queries": [
      "restaurants in {city}",
      "cafes in {city}"
    ]
  }
}
```

The `{city}` placeholder is automatically replaced with `"{zone}, {city_name}"` at runtime (e.g. `"Bandra, Mumbai"`).

### Step 2 — Set your target city in `run.py`

Open `run.py` and set `city_key` on line 62 to match a key in your `cities.json`:

```python
city_key = 'mumbai'   # must match a key in config/cities.json
```

### Step 3 — Run

```bash
python run.py
```

The script will:

1. Check `output/backups/` for any previously completed zones
2. Skip zones already backed up and load them from cache
3. Open a Chrome browser and scrape any remaining zones
4. After each zone completes, save a JSON backup immediately
5. After all zones for a domain finish, export a per-domain Excel file
6. After all domains finish, export a combined Excel with all sheets

**To stop and resume later:** Press `Ctrl+C` at any time. All completed zones are saved. Re-run `python run.py` to continue from where it stopped.

### Optional tuning

| Setting | Location | Description |
|---|---|---|
| `headless=False` → `True` | `run.py` line 56 | Hide the browser window — runs faster |
| `delay_range=(2, 4)` → `(1, 2)` | `run.py` line 56 | Faster scraping (higher bot-detection risk) |
| Zones list | `config/cities.json` | Reduce zones to scrape fewer areas |
| Search queries | `config/domains.json` | Add or remove queries per domain |

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
