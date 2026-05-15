import json
import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scraper.maps_scraper import GoogleMapsScraper, BusinessLead
from scraper.website_scraper import WebsiteScraper
from scraper.excel_exporter import ExcelExporter
from scraper.data_cleaner import DataCleaner
from utils.helpers import (
    setup_logger, ProgressTracker, random_delay,
    print_header, print_success, print_error, print_info,
    get_timestamp, ensure_dir, load_domain_config, load_city_config,
    build_maps_search_url, save_json
)

BACKUP_DIR = 'output/backups'
OUTPUT_DIR = 'output'


# ── Backup helpers ──────────────────────────────────────────────────────────

def zone_backup_path(domain_key: str, city_key: str, zone: str) -> str:
    """Stable filename for a zone backup — no timestamp so it's findable on re-run."""
    zone_safe = zone.lower().replace(' ', '_').replace('/', '_')
    return os.path.join(BACKUP_DIR, f"{domain_key}__{city_key}__{zone_safe}.json")


def load_zone_backup(path: str):
    """Load BusinessLead list from a zone JSON backup. Returns None if missing/corrupt."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return [BusinessLead(**d) for d in data]
    except Exception:
        return None


def save_zone_backup(leads: list, path: str):
    ensure_dir(os.path.dirname(path))
    save_json([lead.__dict__ for lead in leads], path)


# ── Excel helpers ───────────────────────────────────────────────────────────

def export_domain_excel(domain_name: str, leads: list,
                        domain_key: str, city_key: str) -> str:
    """Write a single-domain Excel file right after that domain finishes."""
    ensure_dir(OUTPUT_DIR)
    path = os.path.join(OUTPUT_DIR, f'leads__{domain_key}__{city_key}.xlsx')
    exporter = ExcelExporter(path)
    exporter.add_domain_sheet(domain_name, leads)
    exporter.save()
    return path


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    logger = setup_logger()

    print_header("LOCAL LEADS EXTRACTOR - Google Maps Scraper")
    logger.info("Starting extraction process")

    # Load configs
    try:
        with open('config/domains.json', 'r', encoding='utf-8') as f:
            domains = json.load(f)
        with open('config/cities.json', 'r', encoding='utf-8') as f:
            cities = json.load(f)
        print_success("Configuration files loaded")
    except FileNotFoundError as e:
        print_error(f"Config file not found: {e}")
        return
    except json.JSONDecodeError as e:
        print_error(f"Invalid JSON in config: {e}")
        return

    city_key = 'hyderabad'  # Change for other cities
    city_config = cities.get(city_key)

    if not city_config:
        print_error(f"City '{city_key}' not found in config!")
        return

    print_info(f"Target City: {city_config['name']}")
    print_info(f"Zones: {len(city_config['zones'])}")
    print_info(f"Domains: {', '.join(domains.keys())}")

    ensure_dir(BACKUP_DIR)
    ensure_dir(OUTPUT_DIR)

    # ── Decide which zones still need scraping ──────────────────────────────
    # zone_status[domain_key][zone] = True if backup already exists
    zone_status = {}
    any_zone_needs_scraping = False

    for domain_key, domain_config in domains.items():
        zone_status[domain_key] = {}
        for zone in city_config['zones']:
            path = zone_backup_path(domain_key, city_key, zone)
            cached = os.path.exists(path)
            zone_status[domain_key][zone] = cached
            if not cached:
                any_zone_needs_scraping = True

    # ── Initialise components ───────────────────────────────────────────────
    maps_scraper = GoogleMapsScraper(headless=False, delay_range=(2, 4))
    web_scraper = WebsiteScraper()
    data_cleaner = DataCleaner()

    all_domain_leads = {}
    total_raw_leads = 0

    # Only open the browser if there is actually something left to scrape
    if any_zone_needs_scraping:
        print_info("Launching browser ...")
        maps_scraper.start()
    else:
        print_info("All zones already backed up — loading entirely from cache.")

    try:
        for domain_key, domain_config in domains.items():
            print_header(f"DOMAIN: {domain_config['name']}")
            logger.info(f"Starting domain: {domain_config['name']}")

            domain_raw_leads = []
            cached_zones   = [z for z in city_config['zones'] if     zone_status[domain_key][z]]
            pending_zones  = [z for z in city_config['zones'] if not zone_status[domain_key][z]]

            print_info(f"  Loaded from cache : {len(cached_zones)} zones")
            print_info(f"  Still to scrape   : {len(pending_zones)} zones")

            # ── Load completed zones from backup ────────────────────────────
            for zone in cached_zones:
                path = zone_backup_path(domain_key, city_key, zone)
                cached_leads = load_zone_backup(path)
                if cached_leads is not None:
                    domain_raw_leads.extend(cached_leads)
                    # Pre-populate seen_urls so we never re-visit these places
                    for lead in cached_leads:
                        if lead.google_maps_url:
                            maps_scraper._seen_urls.add(
                                lead.google_maps_url.split('?')[0]
                            )
                    print_info(f"  [cache] {zone}: {len(cached_leads)} leads")
                else:
                    print_error(f"  [cache] {zone}: backup corrupt — will re-scrape")
                    pending_zones.append(zone)

            # ── Scrape remaining zones ──────────────────────────────────────
            if pending_zones:
                tracker = ProgressTracker(
                    total_items=len(pending_zones),
                    name=f"Scraping {domain_config['name']}"
                )

                for zone in pending_zones:
                    print_info(f"Scraping zone: {zone}")

                    try:
                        leads = maps_scraper.scrape_domain(
                            domain_key=domain_key,
                            domain_config=domain_config,
                            city=city_config['name'],
                            zone=zone
                        )

                        # Enrich with website data
                        for lead in leads:
                            if lead.website:
                                print_info(f"  Scraping website: {lead.website[:50]}...")
                                try:
                                    lead.email = web_scraper.extract_email(lead.website)
                                    lead.revenue_estimate = web_scraper.estimate_revenue(
                                        lead.website, lead.type
                                    )
                                    lead.team_size = web_scraper.extract_team_info(lead.website)
                                except Exception as e:
                                    logger.warning(f"Website scrape failed for {lead.website}: {e}")

                            lead.creation_date = datetime.now().strftime('%Y-%m-%d')

                        # ✅ Save zone backup immediately after scraping
                        zone_path = zone_backup_path(domain_key, city_key, zone)
                        save_zone_backup(leads, zone_path)
                        print_success(f"Zone backup saved: {zone} ({len(leads)} leads)")

                        domain_raw_leads.extend(leads)
                        tracker.update(increment=1, status=f"+{len(leads)} leads")
                        logger.info(f"Zone {zone}: {len(leads)} leads")

                    except Exception as e:
                        print_error(f"Error scraping {zone}: {e}")
                        logger.error(f"Zone {zone} failed: {e}", exc_info=True)
                        tracker.update(increment=1, status="Error")

                tracker.finish()

            # ── All zones done for this domain — clean + export Excel ───────
            print_info(f"Cleaning data for {domain_config['name']}...")
            cleaned_leads = data_cleaner.clean_all(domain_raw_leads)

            all_domain_leads[domain_config['name']] = cleaned_leads
            total_raw_leads += len(domain_raw_leads)

            print_success(
                f"{domain_config['name']}: {len(cleaned_leads)} clean leads "
                f"(from {len(domain_raw_leads)} raw)"
            )

            # ✅ Export per-domain Excel as soon as this domain is fully done
            domain_excel_path = export_domain_excel(
                domain_config['name'], cleaned_leads, domain_key, city_key
            )
            print_success(f"Domain Excel saved: {domain_excel_path}")
            logger.info(f"Domain Excel: {domain_excel_path}")

    finally:
        if any_zone_needs_scraping:
            maps_scraper.stop()
            print_info("Browser closed.")

    # ── Combined Excel (all domains, one file) ──────────────────────────────
    total_clean_leads = sum(len(leads) for leads in all_domain_leads.values())

    print_header("EXPORTING COMBINED EXCEL")

    combined_file = os.path.join(
        OUTPUT_DIR,
        f'leads__{city_key}__{datetime.now().strftime("%Y%m%d")}.xlsx'
    )
    exporter = ExcelExporter(combined_file)

    stats = {
        'city': city_config['name'],
        'total_domains': len(domains),
        'total_raw_leads': total_raw_leads,
        'total_clean_leads': total_clean_leads,
        'domain_counts': {k: len(v) for k, v in all_domain_leads.items()},
        'cleaning_stats': data_cleaner.get_stats(),
        'extraction_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    exporter.add_summary_sheet(stats)

    for domain_name, leads in all_domain_leads.items():
        exporter.add_domain_sheet(domain_name, leads)
        print_success(f"Sheet added: {domain_name} ({len(leads)} rows)")

    exporter.save()

    print_header("EXTRACTION COMPLETE!")
    print_success(f"Combined Excel : {combined_file}")
    print_info(f"Individual Excel files in: {OUTPUT_DIR}/")
    print_info(f"Total raw leads   : {total_raw_leads}")
    print_info(f"Total clean leads : {total_clean_leads}")
    print_info(f"Removed           : {total_raw_leads - total_clean_leads}")

    logger.info("Extraction complete")
    logger.info(f"Final stats: {stats}")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print_error("\n\nInterrupted. All completed zones are saved in output/backups/")
        print_info("Re-run the script to resume from where you left off.")
        sys.exit(1)
    except Exception as e:
        print_error(f"\n\nFatal error: {e}")
        raise
