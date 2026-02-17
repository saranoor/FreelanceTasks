#!/usr/bin/env python3
"""
scrape_western_dealers.py
=======================

Purpose
-------
Scrape the WESTERN® dealer locator (https://westernplows.com/dealers/) for ALL dealers
in the USA and Canada, using a pre-built list of postal codes to "fan out" searches.

The site does NOT provide an "export all dealers" feature; it returns the nearest
dealers for a given ZIP/Postal Code. This script:
  1) Iterates over many ZIP/Postal Codes across US + Canada
  2) Collects unique Dealer Detail page URLs
  3) Scrapes dealer details (name, address, phone)
  4) De-duplicates dealers across overlapping searches
  5) Writes results to an Excel file

Deliverable Columns
-------------------
- Dealer Name
- Country
- State        (US state or Canadian province abbreviation)
- Address      (single-line address)
- Phone
- Email        (not provided by Western dealer pages; left blank)

Inputs
------
A CSV file containing the ZIP/Postal codes to use (default: postal_codes_us_ca.csv).
This repo includes a ready-to-run file; see that CSV for the exact codes used.

Install / Requirements
----------------------
Python 3.10+ recommended.

pip install -U pandas openpyxl requests beautifulsoup4 playwright tqdm

Playwright browser install (one-time):
    playwright install chromium

Run
---
    python scrape_western_dealers.py \
        --postal-codes-file postal_codes_us_ca.csv \
        --output western_dealers_us_ca.xlsx

Useful options:
    --headless          Run browser headless (default: False)
    --limit 50          Only run first N postal codes (for testing)
    --min-delay 0.8     Minimum delay between searches
    --max-delay 1.8     Maximum delay between searches
    --threads 4         Threads for downloading dealer detail pages (default 4)

Notes / Responsible Scraping
----------------------------
- Keep delays enabled. Dealer-locators often rate-limit or block abusive traffic.
- If you start getting CAPTCHAs or empty results, stop and increase delays.
- Always comply with the website's Terms of Service and applicable laws.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

# Playwright is used only to interact with the locator UI (it is JS-driven).
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


LOCATOR_URL = "https://westernplows.com/dealers/"
DEALER_URL_KEYWORD = "/dealer-details/"  # dealer detail pages contain this path fragment

DEFAULT_OUTPUT = "western_dealers_us_ca.xlsx"


@dataclasses.dataclass(frozen=True)
class Dealer:
    dealer_name: str
    country: str
    state: str
    address: str
    phone: str
    email: str = ""


US_STATE_CODES = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","DC","FL","GA","HI","ID","IL","IN","IA","KS","KY","LA","ME","MD","MA","MI","MN",
    "MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA",
    "WV","WI","WY","PR"
}
CA_PROVINCE_CODES = {"AB","BC","MB","NB","NL","NS","NT","NU","ON","PE","QC","SK","YT"}


def read_postal_codes(csv_path: Path, limit: Optional[int] = None) -> list[str]:
    df = pd.read_csv(csv_path, dtype=str).fillna("")
    if "postal_code" not in df.columns or "country" not in df.columns:
        raise ValueError(f"{csv_path} must contain at least columns: country, postal_code")

    # Keep US + CA (the CSV may contain other rows if user extends it).
    df = df[df["country"].isin(["US", "CA"])].copy()

    codes = df["postal_code"].astype(str).str.strip().tolist()
    # Normalize formatting:
    # - US ZIP: keep as 5-digit string
    # - CA: allow either 'A1A 1A1' or 'A1A1A1' (we store with space; search often works either way).
    cleaned: list[str] = []
    for c in codes:
        c = c.strip().upper()
        if not c:
            continue
        cleaned.append(c)
    if limit:
        cleaned = cleaned[:limit]
    return cleaned


def jitter_sleep(min_s: float, max_s: float) -> None:
    time.sleep(random.uniform(min_s, max_s))


def try_accept_cookies(page) -> None:
    # Best-effort cookie banner dismissal (safe to ignore failures).
    candidates = [
        ("button", re.compile(r"accept", re.I)),
        ("button", re.compile(r"agree", re.I)),
        ("text", re.compile(r"accept all", re.I)),
    ]
    for kind, pattern in candidates:
        try:
            if kind == "button":
                locator = page.get_by_role("button", name=pattern)
            else:
                locator = page.get_by_text(pattern)
            if locator.count() > 0:
                locator.first.click(timeout=1500)
                break
        except Exception:
            pass


def get_search_input(page):
    # The Western locator has a single search input with placeholder "Enter Zip code, city and State".
    selectors = [
        'input[placeholder*="Zip"]',
        'input[placeholder*="ZIP"]',
        'input[aria-label*="Zip"]',
        'input[type="text"]',
        'input',
    ]
    for sel in selectors:
        loc = page.locator(sel)
        try:
            if loc.count() > 0:
                # Prefer visible inputs
                for i in range(min(loc.count(), 5)):
                    candidate = loc.nth(i)
                    if candidate.is_visible():
                        return candidate
        except Exception:
            continue
    raise RuntimeError("Could not find the ZIP/postal search input on the Western locator page.")


def run_locator_and_collect_dealer_urls(
    postal_codes: list[str],
    headless: bool,
    min_delay: float,
    max_delay: float,
    cache_path: Path,
) -> set[str]:
    """
    Uses Playwright to:
      - Open the locator page
      - Run a search for each postal code
      - Collect dealer detail URLs from the results
    """
    dealer_urls: set[str] = set()

    # Load cached urls if present (resume support)
    if cache_path.exists():
        try:
            dealer_urls.update(json.loads(cache_path.read_text(encoding="utf-8")))
            print(f"[resume] Loaded {len(dealer_urls):,} cached dealer URLs from {cache_path}")
        except Exception:
            print(f"[warn] Could not parse cache file {cache_path}; starting fresh.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            viewport={"width": 1400, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        page.goto(LOCATOR_URL, wait_until="domcontentloaded", timeout=60000)
        try_accept_cookies(page)

        search_input = get_search_input(page)

        # If the page is scrolled / overlays exist, this may help.
        page.keyboard.press("Escape")

        for idx, code in enumerate(tqdm(postal_codes, desc="Searching postal codes")):
            try:
                # Clear and enter new code
                search_input.click(timeout=5000)
                search_input.fill("")
                search_input.type(code, delay=30)
                # Enter triggers search on this site
                search_input.press("Enter")
            except PlaywrightTimeoutError:
                print(f"[warn] Timeout entering search for code={code}; continuing.")
                continue
            except Exception as e:
                print(f"[warn] Failed search input for code={code}: {e}")
                continue

            # Allow results to update. Waiting on a specific selector is tricky (site changes),
            # so we do a small fixed wait and then scrape URLs.
            jitter_sleep(min_delay, max_delay)

            try:
                hrefs = page.eval_on_selector_all(
                    f'a[href*="{DEALER_URL_KEYWORD}"]',
                    "els => els.map(e => e.href)"
                )
                # Filter to Western domain and dealer-detail pages
                for h in hrefs:
                    if isinstance(h, str) and DEALER_URL_KEYWORD in h and h.startswith("https://westernplows.com/"):
                        dealer_urls.add(h.split("#")[0])
            except Exception:
                # If page is mid-transition, ignore.
                pass

            # Persist cache periodically
            if (idx + 1) % 25 == 0:
                cache_path.write_text(json.dumps(sorted(dealer_urls)), encoding="utf-8")

            jitter_sleep(min_delay, max_delay)

        cache_path.write_text(json.dumps(sorted(dealer_urls)), encoding="utf-8")
        context.close()
        browser.close()

    return dealer_urls


def normalize_whitespace(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def guess_country_and_state_from_address(address: str) -> tuple[str, str]:
    """
    Given a full single-line address string like:
        "195 South Plank Road Newburgh, NY 12550"
        "128 Main St Toronto, ON M5V 2T6"
    Return (country, state/province). If we can't confidently detect, return ("", "").
    """
    a = normalize_whitespace(address).upper()

    # Canada: postal code pattern
    if re.search(r"\b[ABCEGHJ-NPRSTVXY]\d[ABCEGHJ-NPRSTV-Z][ -]?\d[ABCEGHJ-NPRSTV-Z]\d\b", a):
        # Province code is usually after comma, before postal code: ", ON M5V 2T6"
        m = re.search(r",\s*([A-Z]{2})\s+[ABCEGHJ-NPRSTVXY]\d", a)
        if m and m.group(1) in CA_PROVINCE_CODES:
            return "CA", m.group(1)
        return "CA", ""

    # US: ZIP pattern
    m_zip = re.search(r"\b(\d{5})(?:-\d{4})?\b", a)
    if m_zip:
        m = re.search(r",\s*([A-Z]{2})\s+\d{5}\b", a)
        if m and m.group(1) in US_STATE_CODES:
            return "US", m.group(1)
        return "US", ""

    return "", ""


def extract_field_after_label(soup: BeautifulSoup, label_regex: re.Pattern) -> str:
    """
    Find an element whose text matches label_regex (e.g. r'^Address:$'),
    then return the text of the next meaningful sibling/element.
    """
    label_el = soup.find(string=label_regex)
    if not label_el:
        # Sometimes labels are inside tags with extra whitespace/case
        for candidate in soup.find_all(["h2", "h3", "h4", "strong", "p", "span"]):
            if candidate.get_text(strip=True) and label_regex.search(candidate.get_text(strip=True)):
                label_el = candidate
                break

    if not label_el:
        return ""

    # If label_el is a NavigableString, get its parent; otherwise keep.
    if not hasattr(label_el, "find_next"):
        label_el = label_el.parent

    # Try next elements in document order
    nxt = label_el.find_next()
    # Skip the label itself
    if nxt and hasattr(nxt, "get_text") and label_regex.search(nxt.get_text(strip=True)):
        nxt = nxt.find_next()

    # Keep moving until we hit non-empty text that isn't another label
    for _ in range(8):
        if not nxt:
            break
        txt = normalize_whitespace(nxt.get_text(" ", strip=True))
        if txt and not label_regex.search(txt) and txt.lower() not in {"address", "phone"}:
            return txt
        nxt = nxt.find_next()

    return ""


def parse_western_dealer_page(url: str, session: requests.Session, timeout_s: int = 30) -> Optional[Dealer]:
    try:
        resp = session.get(url, timeout=timeout_s)
        if resp.status_code != 200:
            return None
    except requests.RequestException:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # Dealer name
    h1 = soup.find("h1")
    dealer_name = normalize_whitespace(h1.get_text(" ", strip=True)) if h1 else ""
    if not dealer_name:
        return None

    # Address + Phone
    address = extract_field_after_label(soup, re.compile(r"^Address:?\s*$", re.I))
    phone = extract_field_after_label(soup, re.compile(r"^Phone:?\s*$", re.I))

    # Fall back: tel: links
    if not phone:
        tel = soup.find("a", href=re.compile(r"^tel:", re.I))
        if tel:
            phone = normalize_whitespace(tel.get_text(" ", strip=True))

    # Clean & normalize
    address = normalize_whitespace(address)
    phone = normalize_whitespace(phone)

    country, state = guess_country_and_state_from_address(address)

    # Build a single-line address (keep as-is; do not attempt USPS normalization)
    return Dealer(
        dealer_name=dealer_name,
        country=country,
        state=state,
        address=address,
        phone=phone,
        email=""
    )


def dedupe_dealers(dealers: Iterable[Dealer]) -> list[Dealer]:
    """
    De-duplicate by a robust key. Addresses tend to be more stable than names,
    but we include both (normalized) to reduce accidental merges.
    """
    def key(d: Dealer) -> str:
        name = re.sub(r"[^A-Z0-9]+", "", d.dealer_name.upper())
        addr = re.sub(r"[^A-Z0-9]+", "", d.address.upper())
        return f"{d.country}|{d.state}|{addr}|{name}"

    seen = set()
    out: list[Dealer] = []
    for d in dealers:
        k = key(d)
        if k in seen:
            continue
        seen.add(k)
        out.append(d)
    return out


def write_excel(dealers: list[Dealer], out_path: Path) -> None:
    rows = []
    for d in dealers:
        rows.append({
            "Dealer Name": d.dealer_name,
            "Country": d.country,
            "State": d.state,
            "Address": d.address,
            "Phone": d.phone,
            "Email": d.email,
        })
    df = pd.DataFrame(rows)
    df.to_excel(out_path, index=False)
    print(f"[ok] Wrote {len(df):,} unique dealers to: {out_path.resolve()}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Scrape Western dealer locator (US + CA) into Excel.")
    ap.add_argument("--postal-codes-file", type=Path, default=Path("postal_codes_us_ca.csv"))
    ap.add_argument("--output", type=Path, default=Path(DEFAULT_OUTPUT))
    ap.add_argument("--headless", action="store_true", help="Run Playwright headless (default: visible browser).")
    ap.add_argument("--limit", type=int, default=None, help="Limit number of postal codes (testing).")
    ap.add_argument("--min-delay", type=float, default=0.8, help="Min delay between searches (seconds).")
    ap.add_argument("--max-delay", type=float, default=1.8, help="Max delay between searches (seconds).")
    ap.add_argument("--threads", type=int, default=4, help="Threads for downloading dealer detail pages.")
    args = ap.parse_args()

    if args.min_delay < 0 or args.max_delay < args.min_delay:
        raise SystemExit("--min-delay must be >= 0 and --max-delay must be >= --min-delay")

    postal_codes = read_postal_codes(args.postal_codes_file, limit=args.limit)
    if not postal_codes:
        raise SystemExit("No postal codes loaded. Check the CSV file.")

    cache_path = Path("western_dealer_urls_cache.json")

    print(f"[info] Postal codes: {len(postal_codes):,}")
    print("[info] Launching browser to collect dealer detail URLs ...")
    dealer_urls = run_locator_and_collect_dealer_urls(
        postal_codes=postal_codes,
        headless=args.headless,
        min_delay=args.min_delay,
        max_delay=args.max_delay,
        cache_path=cache_path,
    )
    print(f"[info] Collected {len(dealer_urls):,} unique dealer detail URLs.")

    if not dealer_urls:
        raise SystemExit("No dealer URLs collected. The site may have blocked requests or the selector logic changed.")

    # Scrape dealer details
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        )
    })

    dealers: list[Dealer] = []
    urls = sorted(dealer_urls)

    print("[info] Downloading + parsing dealer pages ...")
    with ThreadPoolExecutor(max_workers=max(1, args.threads)) as ex:
        futs = {ex.submit(parse_western_dealer_page, u, session): u for u in urls}
        for fut in tqdm(as_completed(futs), total=len(futs), desc="Scraping dealer pages"):
            d = fut.result()
            if d:
                dealers.append(d)

    dealers = dedupe_dealers(dealers)
    write_excel(dealers, args.output)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[exit] Interrupted by user.")
        sys.exit(130)
