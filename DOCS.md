# Technical Documentation — Local Leads Extractor

---

## Table of Contents

- [Core Concepts](#core-concepts)
- [Architecture Overview](#architecture-overview)
- [Project Structure](#project-structure)
- [Complete Workflow](#complete-workflow)
- [Data Schema](#data-schema)
- [How Scraping Works](#how-scraping-works)
- [Resume & Backup System](#resume--backup-system)
- [Data Cleaning Pipeline](#data-cleaning-pipeline)
- [Excel Export](#excel-export)
- [Configuration Reference](#configuration-reference)
- [Adding a New City](#adding-a-new-city)
- [Adding a New Domain](#adding-a-new-domain)
- [Known Limitations](#known-limitations)
- [Troubleshooting](#troubleshooting)

---

## Core Concepts

### What is a "Lead"?
A lead is a single business entry scraped from Google Maps. It includes contact details, location, ratings, and optionally website-enriched data like email and revenue estimate. Each lead maps to one row in the final Excel output.

### What is a "Domain"?
A domain is a business category — e.g. Dental Clinics, Real Estate. Each domain has a set of search queries defined in `config/domains.json`. The scraper runs all queries for each zone and deduplicates the results.

### What is a "Zone"?
A zone is a neighbourhood or area within a city — e.g. Banjara Hills, Hitech City. Scraping by zone rather than the whole city produces more granular, complete results since Google Maps caps results per search to ~20 listings.

### Why no API key?
This tool uses browser automation (Playwright) to scrape Google Maps directly, the same way a human would browse it. The Google Maps Platform API is paid; this approach is completely free.

---

## Architecture Overview

```
run.py  (orchestrator)
│
├── GoogleMapsScraper       ← Playwright browser, collects place URLs + details
│   └── maps_scraper.py
│
├── WebsiteScraper          ← requests + BeautifulSoup, enriches leads from websites
│   └── website_scraper.py
│
├── DataCleaner             ← cleans, validates, deduplicates leads
│   └── data_cleaner.py
│
├── ExcelExporter           ← openpyxl, writes formatted .xlsx files
│   └── excel_exporter.py
│
├── Helpers / Utils
│   └── utils/helpers.py
│
└── Config
    ├── config/domains.json
    └── config/cities.json
```

**Data flow:**

```
Google Maps
    ↓  (Playwright)
Raw BusinessLead objects
    ↓  (WebsiteScraper — optional enrichment)
Enriched leads
    ↓  (zone JSON backup saved here)
DataCleaner
    ↓
Clean, deduplicated leads
    ↓
ExcelExporter
    ↓
.xlsx file(s)
```

---

## Project Structure

```
Lead Generation/
│
├── run.py                      # Entry point and orchestrator
│
├── scraper/
│   ├── __init__.py
│   ├── maps_scraper.py         # Google Maps browser scraper
│   ├── website_scraper.py      # Website email / revenue enrichment
│   ├── data_cleaner.py         # Cleaning, validation, deduplication
│   └── excel_exporter.py       # Excel file generation
│
├── utils/
│   └── helpers.py              # Logging, progress tracker, file utils
│
├── config/
│   ├── domains.json            # Domain definitions and search queries
│   └── cities.json             # City and zone definitions
│
├── output/                     # Generated at runtime (gitignored)
│   ├── *.xlsx                  # Final Excel files
│   └── backups/
│       └── *.json              # Per-zone JSON backups
│
├── logs/                       # Generated at runtime (gitignored)
│   └── *.log
│
├── requirements.txt
├── .gitignore
├── README.md
└── DOCS.md
```

---

## Complete Workflow

### Step-by-step execution of `python run.py`

```
1. Load config/domains.json and config/cities.json

2. Scan output/backups/ to determine which zones already have JSON backups
   → zones with backups: skip scraping, load from file
   → zones without backups: add to pending queue

3. If any zones are pending → launch Chromium browser (one instance, kept open)

4. For each domain (e.g. Dental Clinics):

   a. Load cached zone data into domain_raw_leads list
      → pre-populate _seen_urls so those places are never re-visited

   b. For each pending zone:
      i.   Run all search queries for that zone on Google Maps
      ii.  Scroll the results feed to load all listings
      iii. Collect all unique /maps/place/... URLs
      iv.  Visit each place page and extract details
      v.   Enrich leads that have websites (email, revenue, team size)
      vi.  Save zone JSON backup immediately to output/backups/

   c. Run DataCleaner on all raw leads for this domain
      → clean phone numbers, strip address prefixes, validate, deduplicate

   d. Export per-domain Excel: output/leads__dental_clinics__hyderabad.xlsx

5. After all domains finish:
   → Close browser
   → Export combined Excel: output/leads__hyderabad__YYYYMMDD.xlsx
      (Summary sheet + one sheet per domain)
```

---

## Data Schema

### BusinessLead fields

| Field | Source | Description |
|---|---|---|
| `business_name` | Google Maps `h1` | Business name |
| `type` | Maps category button | Business category/type |
| `domain` | Config | Which domain this lead belongs to (e.g. "Dental Clinics") |
| `phone` | Maps `button[data-tooltip="Copy phone number"]` | Phone number, cleaned to +91 format |
| `email` | Business website | Extracted via regex from website pages |
| `website` | Maps `a[data-tooltip="Open website"]` | Business website URL |
| `address` | Maps `button[data-tooltip="Copy address"]` | Full street address, "Address:" prefix stripped |
| `city` | Config | City name (e.g. "Hyderabad") |
| `zone` | Config | Zone/neighbourhood name |
| `rating` | Maps `[aria-label*=" stars"]` | Star rating (e.g. "4.3") |
| `review_count` | Maps `[aria-label*="reviews"]` | Number of reviews |
| `revenue_estimate` | Business website | Estimated team size tier from website text |
| `team_size` | Business website | Team info (LinkedIn link or description) |
| `creation_date` | Runtime | Date the record was scraped |
| `data_source` | Hardcoded | Always "Google Maps" |
| `google_maps_url` | Runtime | Full URL to the Maps place page |

**Excluded from Excel output** (stored in JSON backups only):
`services`, `hours`, `latitude`, `longitude`, `place_id`

### Phone number format
After cleaning, Indian numbers are standardised to: `+91 XXXXX XXXXX`

---

## How Scraping Works

### Phase 1 — Collecting place URLs

The scraper navigates to:
```
https://www.google.com/maps/search/dental+clinics+in+Banjara+Hills,+Hyderabad
```

It waits for `div[role="feed"]` (the results sidebar), then scrolls it in 800px increments, collecting all `a[href*="/maps/place/"]` links. Scrolling stops when:
- The "You've reached the end" message appears
- Three consecutive scroll attempts yield no new links
- 25 scroll attempts reached (safety cap)

This approach is necessary because Google Maps lazy-loads results as you scroll.

### Phase 2 — Extracting place details

For each collected URL, the scraper opens a new page and extracts data using stable, accessibility-based selectors:

| Data | Selector strategy |
|---|---|
| Name | `h1` (first) — very stable |
| Category | `button.DkEaL` with fallbacks |
| Rating | `[aria-label*=" stars"]` → parse number from aria-label |
| Reviews | `[aria-label*="reviews"]` → parse number from aria-label |
| Phone | `button[data-tooltip="Copy phone number"]` → aria-label |
| Address | `button[data-tooltip="Copy address"]` → aria-label |
| Website | `a[data-tooltip="Open website"]` → href |

**Why `data-tooltip` and `aria-label`?**  
Google Maps uses obfuscated, frequently-changing CSS class names. Accessibility attributes like `data-tooltip` and `aria-label` are tied to functionality rather than styling and are far more stable across Google Maps updates.

### Phase 3 — Website enrichment

For each lead that has a `website` URL, the `WebsiteScraper` makes an HTTP request and:
- Scans the page HTML and `mailto:` links for email addresses
- Checks `/contact`, `/about`, `/reach` pages for additional emails
- Looks for team-size indicator keywords to estimate revenue tier
- Looks for LinkedIn links to capture team info

### Browser setup

The browser is launched once per run (not per zone) and uses:
- Realistic Chrome 124 user agent string
- `--disable-blink-features=AutomationControlled` flag
- `navigator.webdriver` property overridden to `undefined`
- `en-US` locale
- Random delays between 2–4 seconds between requests

---

## Resume & Backup System

### Backup file naming
```
output/backups/{domain_key}__{city_key}__{zone_safe}.json
```
Example: `dental_clinics__hyderabad__banjara_hills.json`

- No timestamp in the filename — this makes them findable on re-run
- `zone_safe` = zone name lowercased with spaces replaced by `_`

### Resume logic on re-run

```python
for each domain:
    for each zone:
        if backup file exists:
            load from JSON → skip scraping
            add google_maps_url values to _seen_urls (no re-visiting)
        else:
            scrape zone → save backup immediately after
```

The `_seen_urls` set lives on the `GoogleMapsScraper` instance. Any place URL already seen (from cache or earlier in the same run) is never re-scraped, preventing duplicates across overlapping zone searches.

### When to delete backups
Delete zone backup files when you want to force a fresh scrape for those zones — e.g. after a few weeks when data may be stale. Delete all files in `output/backups/` to start completely fresh.

---

## Data Cleaning Pipeline

Runs via `DataCleaner.clean_all()` after all zones for a domain are collected.

### Step 1 — Per-lead cleaning

| Field | Operation |
|---|---|
| `business_name` | Strip whitespace, remove Google Maps artifacts (`·`, `—`, ` Maps`, etc.) |
| `phone` | Strip non-digits, validate length, format as `+91 XXXXX XXXXX` |
| `email` | Lowercase, regex validate, filter fake domains (example.com, test.com, etc.) |
| `address` | Strip `Address:` prefix, remove status indicators ("Open now", "Closed"), append city if missing |
| `rating` | Extract numeric value from string |
| `review_count` | Extract numeric value, remove commas |

### Step 2 — Validation

A lead is **kept** if it has a `business_name` AND at least one of:
- Phone number
- Email address
- Website URL
- Address
- Rating

A lead is **discarded** if it has only a name and nothing else useful.

### Step 3 — Deduplication

Duplicate key: `{lowercased_name}|{first_30_chars_of_address}`

When two leads share the same key, the one with more filled fields (phone, email, website, rating) is kept.

### Step 4 — Sorting

Final dataset is sorted by rating descending — highest-rated businesses appear first in the Excel output.

---

## Excel Export

### Per-domain Excel (`leads__dental_clinics__hyderabad.xlsx`)
- One sheet named after the domain
- Exported immediately after that domain's zones finish
- Allows partial results to be usable even if the script is stopped before all domains complete

### Combined Excel (`leads__hyderabad__YYYYMMDD.xlsx`)
- Created after all domains finish
- Sheet 1: **Summary** — extraction date, city, total counts, per-domain breakdown
- Sheet 2–5: One sheet per domain

### Excel formatting
- Header row: dark blue fill, white bold text, centre-aligned
- All columns: auto-sized (max width 50 characters)
- Header row frozen (stays visible while scrolling)
- Auto-filter enabled on all columns

### Columns included in Excel output

| Column | Description |
|---|---|
| business_name | Business name |
| type | Category |
| domain | Domain group |
| phone | Cleaned phone number |
| email | Email (if found on website) |
| website | Website URL |
| address | Street address (prefix stripped) |
| city | City |
| zone | Neighbourhood |
| rating | Star rating |
| review_count | Number of reviews |
| revenue_estimate | Estimated size tier |
| team_size | Team info |
| creation_date | Date scraped |
| extraction_date | Timestamp of Excel export |
| google_maps_url | Direct Maps link |
| data_source | Always "Google Maps" |

---

## Configuration Reference

### `config/domains.json`

```json
{
  "domain_key": {
    "name": "Display Name",
    "search_queries": [
      "search query with {city} placeholder",
      "another query in {city}"
    ],
    "fields": ["field1", "field2", ...]
  }
}
```

The `{city}` placeholder is replaced at runtime with `"{zone}, {city}"` — e.g. `"Banjara Hills, Hyderabad"`.

### `config/cities.json`

```json
{
  "city_key": {
    "name": "Display Name",
    "state": "State Name",
    "country": "India",
    "zones": ["Zone 1", "Zone 2", ...],
    "coordinates": { "lat": 17.385, "lng": 78.486 }
  }
}
```

---

## Adding a New City

1. Add an entry to `config/cities.json`:

```json
"mumbai": {
  "name": "Mumbai",
  "state": "Maharashtra",
  "country": "India",
  "zones": ["Bandra", "Andheri", "Powai", "Lower Parel", "Juhu"],
  "coordinates": { "lat": 19.0760, "lng": 72.8777 }
}
```

2. In `run.py`, change:

```python
city_key = 'mumbai'
```

3. Run `python run.py`. Zone backups are city-namespaced so Hyderabad backups won't interfere.

---

## Adding a New Domain

1. Add an entry to `config/domains.json`:

```json
"gyms_fitness": {
  "name": "Gyms & Fitness",
  "search_queries": [
    "gyms in {city}",
    "fitness centres in {city}",
    "CrossFit in {city}"
  ],
  "fields": ["business_name", "type", "address", "phone", "website",
             "rating", "review_count", "email", "city", "zone", "creation_date"]
}
```

2. Run `python run.py`. The new domain is automatically picked up.

---

## Known Limitations

| Limitation | Detail |
|---|---|
| Google Maps result cap | Google Maps shows a maximum of ~120 results per search query regardless of how much you scroll. Using zone-based and query-varied searches mitigates this. |
| No historical data | Google Maps doesn't expose business creation dates. The `creation_date` field is the date the record was scraped, not when the business was founded. |
| Email availability | Most small Indian businesses don't publish emails on their websites. Expect email coverage of 10–30% depending on domain. |
| Revenue estimate accuracy | Revenue estimates are based on keyword heuristics on the business website and should be treated as rough indicators only. |
| Dynamic selectors | Google Maps occasionally updates its HTML structure. If scraping suddenly returns 0 results for a zone, Google may have changed a selector. Check `maps_scraper.py` and update accordingly. |
| Bot detection | Running too fast (delay < 1s) or too many requests may trigger a CAPTCHA. If this happens, increase `delay_range` and set `headless=False` to monitor. |

---

## Troubleshooting

**Zones return 0 leads**
- Set `headless=False` and watch the browser
- Check if Google is showing a CAPTCHA or consent screen
- The results feed selector `div[role="feed"]` may have changed — inspect the page and update `maps_scraper.py`

**`playwright install` fails**
```bash
pip install playwright
playwright install chromium
```

**Address still showing "Address:" prefix**
- Delete the affected zone backup JSON files in `output/backups/`
- Re-run — they will be re-scraped and the cleaner will strip the prefix

**Script crashes mid-domain**
- All completed zones are already backed up
- Simply re-run `python run.py` — it resumes automatically

**Excel file not created**
- If the script was interrupted before a domain finished, the per-domain Excel won't exist yet
- The combined Excel is only created after all domains complete
- Re-run to completion; zone backups ensure no re-scraping

**Import errors on run**
- Make sure your virtual environment is activated
- Run `pip install -r requirements.txt` again
