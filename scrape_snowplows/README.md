# Fisher Plows Dealer Locator Scraper

An automated data collection tool to scrape **all** FISHER® dealer locations across the United States and Canada. Since the official dealer locator only shows local results based on proximity, this script "fans out" by searching across a comprehensive list of postal codes to ensure total geographic coverage.

## 🛠️ How It Works

The scraper operates in two distinct phases:

1. **Discovery Phase (Playwright):** Launches a Chromium browser to interact with the JavaScript-heavy dealer locator. It inputs postal codes from a CSV, triggers searches, and collects unique "Dealer Detail" URLs.
2. **Extraction Phase (Requests/BeautifulSoup):** Uses high-speed concurrent threading to visit each unique dealer page, parsing out names, addresses, and phone numbers.

## 📋 Requirements

* **Python 3.10+**
* **Playwright** (for browser automation)
* **Pandas & Openpyxl** (for data handling and Excel export)
* **BeautifulSoup4** (for HTML parsing)

### Installation

```bash
# Install Python dependencies
pip install -U pandas openpyxl requests beautifulsoup4 playwright tqdm

# Install the Playwright browser engine
playwright install chromium

```

## 🚀 Usage

### Basic Run

To run the scraper with default settings (using `postal_codes_us_ca.csv` as input):

```bash
python scrape_fisher_dealers.py

```

### Advanced Configuration

You can customize the behavior using command-line arguments:

```bash
python scrape_fisher_dealers.py \
    --postal-codes-file my_codes.csv \
    --output final_dealers.xlsx \
    --headless \
    --threads 8 \
    --limit 100

```

| Argument | Description |
| --- | --- |
| `--postal-codes-file` | Path to your CSV containing `country` and `postal_code` columns. |
| `--output` | The filename for the final Excel report. |
| `--headless` | Run without a visible browser window (faster, less intrusive). |
| `--limit` | Only process the first N postal codes (ideal for testing). |
| `--threads` | Number of concurrent workers for parsing dealer pages (default: 4). |
| `--min-delay / --max-delay` | Set the range for "jitter" sleeps to avoid bot detection. |

## 📦 Deliverables

The script produces an Excel file (`fisher_dealers_us_ca.xlsx`) with the following columns:

* **Dealer Name**
* **Country** (US or CA)
* **State/Province** (e.g., NY, ON)
* **Address** (Full single-line address)
* **Phone**
* **Email** (Placeholder)

## 🛡️ Responsible Scraping Features

* **Session Resumption:** The script saves a `fisher_dealer_urls_cache.json` file. If the script crashes or is stopped, it can reload previously discovered URLs.
* **De-duplication:** Automatically removes duplicate entries caused by overlapping search radii.
* **Human-like Behavior:** Includes random "jitter" delays and user-agent spoofing to minimize the load on Fisher's servers and prevent IP blocking.

---

**Note:** *This tool is for educational and research purposes. Ensure you comply with the website's terms of service and do not use the data in violation of privacy laws.*
