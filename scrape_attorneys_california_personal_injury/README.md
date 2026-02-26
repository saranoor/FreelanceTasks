# Martindale Attorney Directory Scraper

A Python-based automation tool designed to extract non-sponsored attorney listings from Martindale-Hubbell. It focuses on gathering contact details for specialized legal professionals (e.g., Automobile Accident attorneys) across multiple search result pages.

## 🛡️ Anti-Bot Bypass Strategy

Unlike traditional scrapers that get blocked by Cloudflare or PerimiterX, this script uses the **"Remote Debugging"** method.

By connecting to a pre-existing Chrome instance, the script inherits your "human" cookies, browser history, and solved CAPTCHAs, making it nearly indistinguishable from a real user.

## 🛠️ Requirements

* **Python 3.x**
* **Selenium & Pandas**
* **Google Chrome Browser**

### Installation

```bash
pip install selenium pandas openpyxl

```

## 🚀 Setup & Usage

### 1. Launch Chrome in Debug Mode

You **must** start Chrome via the command line with a debugging port open before running the script. Close all other Chrome windows first.

**Windows:**

```cmd
chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\sel_temp"

```

**macOS:**

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir="~/sel_temp"

```

### 2. Prepare the Search

In the Chrome window that just opened, navigate to the [Martindale]() search results page you wish to scrape.

### 3. Run the Script

```bash
chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\selenum\ChromeProfile"
python scrape_auto_injury_attorney.py

```

## ✨ Key Features

* **Sponsored Listing Filter:** Automatically detects and skips "Sponsored" or "Paid Advertisement" cards to ensure you only collect organic search results.
* **Incremental Saving:** The script saves data to `attorneys_results.xlsx` **after every page**. If the script is interrupted, you won't lose your data.
* **Smart Pagination:** Uses JavaScript execution to scroll to and click the "Next" arrow, handling dynamic page loads.
* **Data Points Collected:**
* Attorney/Firm Name
* Office Location
* Phone Number
* Website URL



## 📂 Output

The script generates (or appends to) `attorneys_results.xlsx` in the same directory.

| Name | Location | Phone | Website |
| --- | --- | --- | --- |
| Law Offices of John Doe | Los Angeles, CA | (555) 123-4567 | [https://example.com]() |
| Jane Smith & Associates | San Francisco, CA | (555) 987-6543 | [https://janesmith.law]() |

---

**Note:** *This tool is for personal research and educational use. Please respect the Martindale Terms of Service and ensure your scraping frequency does not overwhelm their servers.*
