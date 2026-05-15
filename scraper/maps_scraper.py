import re
import time
import random
from dataclasses import dataclass
from typing import List, Dict, Optional, Set

from playwright.sync_api import (
    sync_playwright, Browser, BrowserContext, Page,
    TimeoutError as PlaywrightTimeout,
)


@dataclass
class BusinessLead:
    business_name: str = ""
    type: str = ""
    domain: str = ""
    address: str = ""
    phone: str = ""
    website: str = ""
    rating: str = ""
    review_count: str = ""
    hours: str = ""
    services: str = ""
    email: str = ""
    revenue_estimate: str = ""
    team_size: str = ""
    city: str = ""
    zone: str = ""
    creation_date: str = ""
    data_source: str = "Google Maps"
    latitude: str = ""
    longitude: str = ""
    place_id: str = ""
    google_maps_url: str = ""


class GoogleMapsScraper:
    """
    Scrapes Google Maps search results using Playwright.
    Call start() once before scraping, stop() once when done.
    """

    def __init__(self, headless: bool = True, delay_range: tuple = (2, 4)):
        self.headless = headless
        self.delay_range = delay_range
        self._pw = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        # Track already-visited place URLs globally to avoid re-scraping
        self._seen_urls: Set[str] = set()

    # ------------------------------------------------------------------ #
    #  Browser lifecycle                                                   #
    # ------------------------------------------------------------------ #

    def start(self):
        """Launch the browser. Call once before any scrape_domain() calls."""
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=self.headless,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
            ],
        )
        self._context = self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768},
            locale="en-US",
        )
        # Hide the webdriver flag so Google doesn't detect automation
        self._context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

    def stop(self):
        """Close the browser. Call once after all scraping is done."""
        try:
            if self._browser:
                self._browser.close()
            if self._pw:
                self._pw.stop()
        except Exception:
            pass
        self._browser = None
        self._context = None
        self._pw = None

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _delay(self, lo: float = None, hi: float = None):
        a = lo if lo is not None else self.delay_range[0]
        b = hi if hi is not None else self.delay_range[1]
        time.sleep(random.uniform(a, b))

    def _dismiss_consent(self, page: Page):
        """Click through Google's cookie / consent banner if shown."""
        for selector in [
            'button:has-text("Accept all")',
            'button:has-text("Agree")',
            'button:has-text("I agree")',
        ]:
            try:
                btn = page.locator(selector).first
                if btn.is_visible(timeout=2500):
                    btn.click()
                    self._delay(1, 2)
                    return
            except Exception:
                continue

    def _collect_place_urls(self, page: Page) -> List[str]:
        """
        Scroll the Google Maps result feed and collect all unique place URLs.

        Google Maps puts each result as:
            <a href="/maps/place/...">  inside  <div role="feed">

        We scroll incrementally until no new links appear or the
        "You've reached the end" message shows.
        """
        try:
            page.wait_for_selector('div[role="feed"]', timeout=12000)
        except PlaywrightTimeout:
            print("        [warn] Results feed not found – skipping")
            return []

        collected: Set[str] = set()
        prev_count = 0
        no_change_rounds = 0

        for _ in range(25):
            # Harvest links visible right now
            links = page.locator('div[role="feed"] a[href*="/maps/place/"]').all()
            for link in links:
                try:
                    href = link.get_attribute("href") or ""
                    if href:
                        collected.add(href.split("?")[0])  # strip query params
                except Exception:
                    pass

            # Check for end-of-list indicator
            try:
                feed_text = page.locator('div[role="feed"]').inner_text(timeout=2000)
                if re.search(
                    r"you.ve reached the end|no more results|end of list",
                    feed_text,
                    re.I,
                ):
                    break
            except Exception:
                pass

            new_count = len(collected)
            if new_count == prev_count:
                no_change_rounds += 1
                if no_change_rounds >= 3:
                    break
            else:
                no_change_rounds = 0
            prev_count = new_count

            # Scroll feed down
            try:
                page.locator('div[role="feed"]').evaluate(
                    "node => node.scrollBy(0, 800)"
                )
            except Exception:
                break
            self._delay(1.5, 2.5)

        return list(collected)

    # ------------------------------------------------------------------ #
    #  Detail extraction helpers                                           #
    # ------------------------------------------------------------------ #

    def _tooltip_text(self, page: Page, tooltip: str) -> str:
        """
        Return the aria-label (= full text) of a button whose
        data-tooltip attribute matches 'tooltip'.
        """
        try:
            el = page.locator(f'button[data-tooltip="{tooltip}"]').first
            if el.count() > 0 and el.is_visible(timeout=2000):
                return (
                    el.get_attribute("aria-label")
                    or el.inner_text(timeout=2000)
                ).strip()
        except Exception:
            pass
        return ""

    def _tooltip_href(self, page: Page, tooltip: str) -> str:
        """Return the href of an <a> whose data-tooltip matches."""
        try:
            el = page.locator(f'a[data-tooltip="{tooltip}"]').first
            if el.count() > 0 and el.is_visible(timeout=2000):
                return (el.get_attribute("href") or "").strip()
        except Exception:
            pass
        return ""

    def _extract_place_details(
        self,
        page: Page,
        url: str,
        domain: str,
        city: str,
        zone: str,
    ) -> BusinessLead:
        lead = BusinessLead(domain=domain, city=city, zone=zone, google_maps_url=url)

        # ── Name (h1 is very stable on Google Maps place pages) ───────────
        try:
            h1 = page.locator("h1").first
            h1.wait_for(state="visible", timeout=7000)
            lead.business_name = h1.inner_text(timeout=3000).strip()
        except Exception:
            pass

        # ── Category / business type ──────────────────────────────────────
        # Google renders this as a small button below the name.
        # Try multiple selectors since class names change.
        for cat_sel in [
            "button.DkEaL",
            "div[jsaction*='category']",
            "span.mgr77e",
        ]:
            try:
                el = page.locator(cat_sel).first
                if el.count() > 0 and el.is_visible(timeout=1500):
                    text = el.inner_text(timeout=1500).strip()
                    if text:
                        lead.type = text
                        break
            except Exception:
                continue

        # ── Rating ────────────────────────────────────────────────────────
        # The stars widget has aria-label="4.3 stars" or similar.
        try:
            el = page.locator('[aria-label*=" stars"]').first
            if el.count() > 0:
                aria = el.get_attribute("aria-label") or ""
                m = re.search(r"([\d.]+)", aria)
                if m:
                    lead.rating = m.group(1)
        except Exception:
            pass

        # ── Review count ──────────────────────────────────────────────────
        try:
            el = page.locator('[aria-label*="reviews"]').first
            if el.count() > 0:
                aria = el.get_attribute("aria-label") or ""
                m = re.search(r"([\d,]+)", aria)
                if m:
                    lead.review_count = m.group(1).replace(",", "")
        except Exception:
            pass

        # ── Phone ─────────────────────────────────────────────────────────
        raw = self._tooltip_text(page, "Copy phone number")
        if raw:
            lead.phone = re.sub(r"^Phone[:\s]+", "", raw).strip()

        # ── Address ───────────────────────────────────────────────────────
        raw_addr = self._tooltip_text(page, "Copy address")
        if raw_addr:
            lead.address = re.sub(r'^Address[:\s]+', '', raw_addr, flags=re.IGNORECASE).strip()

        # ── Website ───────────────────────────────────────────────────────
        lead.website = self._tooltip_href(page, "Open website")
        if not lead.website:
            try:
                el = page.locator('a[data-item-id="authority"]').first
                if el.count() > 0:
                    lead.website = el.get_attribute("href") or ""
            except Exception:
                pass

        # ── Hours ─────────────────────────────────────────────────────────
        for hours_sel in [
            '[aria-label*="Monday"]',
            '[aria-label*="Open · Closes"]',
            '[aria-label*="Closed · Opens"]',
            "div.t39EBf",
        ]:
            try:
                el = page.locator(hours_sel).first
                if el.count() > 0 and el.is_visible(timeout=1500):
                    text = (
                        el.get_attribute("aria-label")
                        or el.inner_text(timeout=1500)
                    ).strip()
                    if text:
                        lead.hours = text[:200]
                        break
            except Exception:
                continue

        # ── Coordinates from redirected URL ───────────────────────────────
        m = re.search(r"@([-\d.]+),([-\d.]+)", page.url)
        if m:
            lead.latitude = m.group(1)
            lead.longitude = m.group(2)

        return lead

    # ------------------------------------------------------------------ #
    #  Public scraping method                                              #
    # ------------------------------------------------------------------ #

    def scrape_domain(
        self,
        domain_key: str,
        domain_config: Dict,
        city: str,
        zone: str,
    ) -> List[BusinessLead]:
        """
        Scrape all listings for one domain in one city zone.
        Requires start() to have been called first.
        """
        if self._context is None:
            raise RuntimeError("Call start() before scrape_domain()")

        queries = [
            q.format(city=f"{zone}, {city}")
            for q in domain_config["search_queries"]
        ]

        # ── Step 1: collect place URLs from all search queries ─────────────
        zone_new_urls: List[str] = []
        for query in queries:
            search_url = (
                "https://www.google.com/maps/search/"
                + query.replace(" ", "+")
            )
            print(f"        Query: {query}")

            list_page = self._context.new_page()
            try:
                list_page.goto(
                    search_url, wait_until="domcontentloaded", timeout=30000
                )
                self._dismiss_consent(list_page)
                self._delay(2, 3)

                found_urls = self._collect_place_urls(list_page)
                new_for_query = [
                    u for u in found_urls if u not in self._seen_urls
                ]
                self._seen_urls.update(new_for_query)
                zone_new_urls.extend(new_for_query)
                print(
                    f"        → {len(found_urls)} places found, "
                    f"{len(new_for_query)} are new"
                )
            except Exception as e:
                print(f"        [search error] {e}")
            finally:
                list_page.close()

        if not zone_new_urls:
            return []

        # ── Step 2: visit each place page and extract details ──────────────
        leads: List[BusinessLead] = []
        print(f"        Fetching details for {len(zone_new_urls)} places …")

        for idx, place_url in enumerate(zone_new_urls, 1):
            detail_page = self._context.new_page()
            try:
                detail_page.goto(
                    place_url, wait_until="domcontentloaded", timeout=30000
                )
                self._delay(1.5, 2.5)

                lead = self._extract_place_details(
                    detail_page, place_url, domain_config["name"], city, zone
                )
                if lead.business_name:
                    leads.append(lead)
                    print(
                        f"        [{idx}/{len(zone_new_urls)}] ✓ "
                        f"{lead.business_name} | "
                        f"{lead.phone or '—'} | "
                        f"{(lead.address or '—')[:45]}"
                    )
                else:
                    print(f"        [{idx}] skipped (could not extract name)")
            except Exception as e:
                print(f"        [{idx}] error: {e}")
            finally:
                detail_page.close()

        return leads
