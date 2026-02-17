#!/usr/bin/env python3
"""
scrape_buyers_dealers.py
=======================

Purpose
-------
Scrape the Buyers Products "Where To Buy" dealer locator for ALL dealers in the USA and Canada
that carry ANY of the following product families:

  - SnowDogg® Snow Plows
  - SaltDogg® Spreaders
  - ScoopDogg® by Buyers Snow Pushers

Locator:
    https://www.buyersproducts.com/dealerlocator

Important: This locator is a JavaScript single-page app, so we use Playwright to:
  - Load the app
  - Select product families (best-effort; UI can change)
  - Enter a ZIP/Postal Code
  - Trigger the "closest" search/sort
  - Capture JSON responses from the app's network calls and extract dealer records

Deliverable Columns
-------------------
- Dealer Name
- Country
- State        (US state or Canadian province abbreviation)
- Address      (single-line address)
- Phone
- Email        (not required for Buyers; left blank)

Inputs
------
A CSV file containing postal codes to use (default: postal_codes_us_ca.csv).

Install / Requirements
----------------------
Python 3.10+ recommended.

pip install -U pandas openpyxl requests beautifulsoup4 playwright tqdm

Playwright browser install (one-time):
    playwright install chromium

Run
---
    python scrape_buyers_dealers.py \
        --postal-codes-file postal_codes_us_ca.csv \
        --output buyers_dealers_us_ca.xlsx

Notes / Responsible Scraping
----------------------------
- Keep delays enabled. Dealer-locators often rate-limit or block abusive traffic.
- If you start getting CAPTCHAs or empty results, stop and increase delays.
- Always comply with the website's Terms of Service and applicable laws.

Debugging / Selector Adjustments
--------------------------------
Because this is a JS app, the exact CSS selectors may change. This script is written
to be resilient by primarily extracting dealer data from JSON network responses.
If the UI changes and product-selection/search triggers fail, a developer may need
to update the selectors in:
    - get_postal_input()
    - select_product_families()
    - trigger_search()

This script prints warnings (but continues) when it cannot confidently interact
with a specific UI element.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import random
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd
from tqdm import tqdm
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


LOCATOR_URL = "https://www.buyersproducts.com/dealerlocator"
DEFAULT_OUTPUT = "buyers_dealers_us_ca.xlsx"

PRODUCT_FAMILIES = [
    "SnowDogg",
    "SaltDogg",
    "ScoopDogg",
]


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


def read_postal_codes(csv_path: Path, limit: Optional[int] = None) -> list[tuple[str, str]]:
    """
    Returns list of (country, postal_code).
    Expects CSV columns: country, postal_code.
    """
    df = pd.read_csv(csv_path, dtype=str).fillna("")
    if "postal_code" not in df.columns or "country" not in df.columns:
        raise ValueError(f"{csv_path} must contain at least columns: country, postal_code")
    df = df[df["country"].isin(["US", "CA"])].copy()
    df["postal_code"] = df["postal_code"].astype(str).str.strip()
    out: list[tuple[str, str]] = []
    for _, row in df.iterrows():
        c = row["country"].strip().upper()
        pc = row["postal_code"].strip().upper()
        if not pc:
            continue
        out.append((c, pc))
    if limit:
        out = out[:limit]
    return out


def jitter_sleep(min_s: float, max_s: float) -> None:
    time.sleep(random.uniform(min_s, max_s))


def normalize_whitespace(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def try_accept_cookies(page) -> None:
    # Best-effort cookie banner dismissal (safe to ignore failures).
    for pattern in [re.compile(r"accept", re.I), re.compile(r"agree", re.I), re.compile(r"got it", re.I)]:
        try:
            btn = page.get_by_role("button", name=pattern)
            if btn.count() > 0 and btn.first.is_visible():
                btn.first.click(timeout=1500)
                return
        except Exception:
            pass


def get_postal_input(page):
    """
    Best-effort locator for a ZIP / postal code input.
    The app UI changes over time; we attempt several strategies.
    """
    selectors = [
        'input[placeholder*="ZIP"]',
        'input[placeholder*="Zip"]',
        'input[placeholder*="Postal"]',
        'input[aria-label*="ZIP"]',
        'input[aria-label*="Zip"]',
        'input[aria-label*="Postal"]',
        'input[type="search"]',
        'input[type="text"]',
        'input',
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel)
            if loc.count() == 0:
                continue
            for i in range(min(loc.count(), 8)):
                cand = loc.nth(i)
                if cand.is_visible() and cand.is_enabled():
                    # Avoid picking the header site-search input if present
                    ph = (cand.get_attribute("placeholder") or "").lower()
                    aria = (cand.get_attribute("aria-label") or "").lower()
                    if "search" in ph or "search" in aria:
                        continue
                    return cand
        except Exception:
            continue
    raise RuntimeError("Could not find the ZIP/postal input on the Buyers dealer locator page.")


def click_text_if_present(page, text_pattern: re.Pattern, timeout_ms: int = 800) -> bool:
    """
    Click the first visible element that matches text_pattern.
    """
    try:
        loc = page.get_by_text(text_pattern)
        if loc.count() > 0 and loc.first.is_visible():
            loc.first.click(timeout=timeout_ms)
            return True
    except Exception:
        pass
    return False


def select_product_families(page) -> None:
    """
    Best-effort: select SnowDogg, SaltDogg, ScoopDogg simultaneously.
    Implementation tries:
      1) checkbox/radio labels
      2) clicking visible text labels
      3) typing into any "product" multi-select input (if present)

    If selection cannot be confirmed, we warn and continue (script still tries to extract dealers).
    """
    # 1) Try checkbox-like behavior by labels
    for fam in PRODUCT_FAMILIES:
        selected = False
        # label click
        try:
            lbl = page.locator(f'label:has-text("{fam}")')
            if lbl.count() > 0 and lbl.first.is_visible():
                lbl.first.click(timeout=1200)
                selected = True
        except Exception:
            pass
        if selected:
            continue

        # 2) Click text
        if click_text_if_present(page, re.compile(re.escape(fam), re.I)):
            continue

        # 3) Multi-select input (common in SPAs)
        try:
            ms = page.locator('input[placeholder*="Product"], input[aria-label*="Product"], input[placeholder*="Select"]')
            if ms.count() > 0 and ms.first.is_visible():
                ms.first.click(timeout=1200)
                ms.first.fill(fam)
                ms.first.press("Enter")
                selected = True
        except Exception:
            pass

        if not selected:
            print(f"[warn] Could not confidently select product family '{fam}'. UI may have changed.")


def trigger_search(page) -> None:
    """
    Best-effort to trigger/update results after entering postal code:
      - Press Enter
      - Click a Search / Find / Go button if present
      - Click/select 'Closest' if it's a button or dropdown option
    """
    # Pressing Enter in the input usually triggers search
    try:
        page.keyboard.press("Enter")
    except Exception:
        pass

    # Click explicit search buttons if present
    for pat in [re.compile(r"search", re.I), re.compile(r"find", re.I), re.compile(r"go", re.I), re.compile(r"submit", re.I)]:
        try:
            btn = page.get_by_role("button", name=pat)
            if btn.count() > 0 and btn.first.is_visible():
                btn.first.click(timeout=1200)
                break
        except Exception:
            pass

    # Ensure "closest" is selected if there is a control for it
    # (some UIs have a "Closest" button or dropdown option)
    try:
        # 1) button
        btn = page.get_by_role("button", name=re.compile(r"closest", re.I))
        if btn.count() > 0 and btn.first.is_visible():
            btn.first.click(timeout=1200)
            return
    except Exception:
        pass

    # 2) select dropdown
    try:
        selects = page.locator("select")
        if selects.count() > 0:
            for i in range(min(selects.count(), 6)):
                sel = selects.nth(i)
                if not sel.is_visible():
                    continue
                # Try selecting an option that includes "closest"
                options = sel.locator("option")
                for j in range(options.count()):
                    opt_text = (options.nth(j).text_content() or "").lower()
                    if "closest" in opt_text:
                        value = options.nth(j).get_attribute("value")
                        if value is not None:
                            sel.select_option(value=value)
                            return
    except Exception:
        pass


def looks_like_dealer_dict(d: Dict[str, Any]) -> bool:
    """
    Heuristic: dict looks like a dealer/location if it has:
      - a name-ish key
      - AND some address-ish keys
    """
    keys = {k.lower() for k in d.keys()}
    has_name = any(k in keys for k in ["name", "dealername", "locationname", "company", "title"])
    has_addr = any(k in keys for k in ["address", "address1", "street", "street1", "line1"]) or \
               (("city" in keys) and (("state" in keys) or ("province" in keys)) and (("zip" in keys) or ("postal" in keys) or ("postalcode" in keys)))
    return has_name and has_addr


def walk_json(obj: Any, found: List[Dict[str, Any]]) -> None:
    if isinstance(obj, dict):
        if looks_like_dealer_dict(obj):
            found.append(obj)
        for v in obj.values():
            walk_json(v, found)
    elif isinstance(obj, list):
        for it in obj:
            walk_json(it, found)


def extract_dealers_from_json_blobs(blobs: List[Any]) -> List[Dealer]:
    """
    Given a list of JSON responses, recursively find dealer-like dicts and map them to Dealer records.
    """
    raw_dicts: List[Dict[str, Any]] = []
    for b in blobs:
        walk_json(b, raw_dicts)

    dealers: List[Dealer] = []
    for d in raw_dicts:
        # Normalize keys (case-insensitive)
        lk = {k.lower(): k for k in d.keys()}

        def get_any(*names: str) -> str:
            for nm in names:
                k = lk.get(nm.lower())
                if k is None:
                    continue
                val = d.get(k)
                if val is None:
                    continue
                if isinstance(val, (str, int, float)):
                    s = str(val).strip()
                    if s:
                        return s
            return ""

        name = get_any("name", "dealerName", "locationName", "company", "title")
        if not name:
            continue

        line1 = get_any("address", "address1", "street", "street1", "line1")
        line2 = get_any("address2", "street2", "line2")
        city = get_any("city", "town")
        state = get_any("state", "province", "region", "stateCode", "provinceCode")
        postal = get_any("zip", "zipCode", "postal", "postalCode", "postcode")
        country = get_any("country", "countryCode")

        phone = get_any("phone", "phoneNumber", "telephone", "tel")

        # Build address
        city_state_postal = normalize_whitespace(" ".join([x for x in [city + ", " + state if city and state else city or state, postal] if x]))
        addr_parts = [p for p in [line1, line2, city_state_postal] if p]
        address = normalize_whitespace(", ".join(addr_parts))

        # Normalize country
        c = country.strip().upper()
        if c in {"UNITED STATES", "USA"}:
            c = "US"
        if c in {"CANADA"}:
            c = "CA"
        if c not in {"US", "CA"}:
            c = ""  # we will fill fallback later

        # Normalize state/province
        st = state.strip().upper()
        if len(st) == 2:
            # keep
            pass
        else:
            # Some APIs return full state/province names; keep as-is.
            st = state.strip()

        dealers.append(Dealer(
            dealer_name=normalize_whitespace(name),
            country=c,
            state=st,
            address=address,
            phone=normalize_whitespace(phone),
            email="",
        ))

    return dealers


def dedupe_dealers(dealers: Iterable[Dealer]) -> List[Dealer]:
    def norm(s: str) -> str:
        return re.sub(r"[^A-Z0-9]+", "", (s or "").upper())

    seen = set()
    out: List[Dealer] = []
    for d in dealers:
        k = f"{d.country}|{norm(d.state)}|{norm(d.address)}|{norm(d.dealer_name)}|{norm(d.phone)}"
        if k in seen:
            continue
        seen.add(k)
        out.append(d)
    return out


def write_excel(dealers: List[Dealer], out_path: Path) -> None:
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
    ap = argparse.ArgumentParser(description="Scrape Buyers Products dealer locator into Excel.")
    ap.add_argument("--postal-codes-file", type=Path, default=Path("postal_codes_us_ca.csv"))
    ap.add_argument("--output", type=Path, default=Path(DEFAULT_OUTPUT))
    ap.add_argument("--headless", action="store_true", help="Run Playwright headless (default: visible browser).")
    ap.add_argument("--limit", type=int, default=None, help="Limit number of postal codes (testing).")
    ap.add_argument("--min-delay", type=float, default=0.8, help="Min delay between searches (seconds).")
    ap.add_argument("--max-delay", type=float, default=1.8, help="Max delay between searches (seconds).")
    ap.add_argument("--save-debug-json", type=Path, default=None, help="Optional: write captured JSON blobs to this file (JSONL).")
    args = ap.parse_args()

    if args.min_delay < 0 or args.max_delay < args.min_delay:
        raise SystemExit("--min-delay must be >= 0 and --max-delay must be >= --min-delay")

    postal_pairs = read_postal_codes(args.postal_codes_file, limit=args.limit)
    if not postal_pairs:
        raise SystemExit("No postal codes loaded. Check the CSV file.")

    all_dealers: List[Dealer] = []
    debug_fp = None
    if args.save_debug_json:
        debug_fp = open(args.save_debug_json, "w", encoding="utf-8")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        context = browser.new_context(
            viewport={"width": 1400, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        json_blobs: List[Any] = []

        def on_response(resp):
            # Capture likely JSON responses (best-effort)
            try:
                ct = (resp.headers.get("content-type") or "").lower()
                url = resp.url.lower()
                if "application/json" in ct or url.endswith(".json"):
                    # Heuristic: keep only URLs likely related to locator
                    if any(k in url for k in ["dealer", "locator", "location", "store", "search", "api"]):
                        try:
                            data = resp.json()
                            json_blobs.append(data)
                            if debug_fp:
                                debug_fp.write(json.dumps({"url": resp.url, "json": data}) + "\n")
                                debug_fp.flush()
                        except Exception:
                            pass
            except Exception:
                pass

        page.on("response", on_response)

        page.goto(LOCATOR_URL, wait_until="domcontentloaded", timeout=60000)
        try_accept_cookies(page)
        # Best-effort product selection once at start
        select_product_families(page)

        postal_input = get_postal_input(page)

        for (country_hint, postal_code) in tqdm(postal_pairs, desc="Postal codes"):
            # Reset blobs for this search
            json_blobs.clear()

            try:
                postal_input.click(timeout=5000)
                postal_input.fill("")
                postal_input.type(postal_code, delay=30)
                trigger_search(page)
            except PlaywrightTimeoutError:
                print(f"[warn] Timeout interacting with postal input for {postal_code}; continuing.")
                continue
            except Exception as e:
                print(f"[warn] Failed to trigger search for {postal_code}: {e}")
                continue

            # Give the app time to fetch and render
            jitter_sleep(args.min_delay, args.max_delay)

            dealers = extract_dealers_from_json_blobs(list(json_blobs))

            # Fill missing country with the hint from postal_codes_us_ca.csv
            fixed: List[Dealer] = []
            for d in dealers:
                c = d.country or country_hint
                st = d.state
                # Clean state/province if full name
                if isinstance(st, str):
                    st_up = st.strip().upper()
                    if len(st_up) == 2:
                        st = st_up
                fixed.append(dataclasses.replace(d, country=c))

            all_dealers.extend(fixed)

            jitter_sleep(args.min_delay, args.max_delay)

        context.close()
        browser.close()

    if debug_fp:
        debug_fp.close()

    unique = dedupe_dealers(all_dealers)
    write_excel(unique, args.output)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[exit] Interrupted by user.")
        sys.exit(130)
