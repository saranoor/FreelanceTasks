# TrainingPeaks Coaches Scraper

A Python-based web scraping script that extracts coach profile data from the TrainingPeaks Coaches directory using Selenium and exports structured results into CSV files.

## 📌 Overview

This project connects to an existing Chrome browser session (via remote debugging) to scrape coach listings and detailed contact information, including:

- Coach Name  
- Profile Link  
- Website  
- Address  
- Email (if available)  

The data is saved into structured CSV files for further analysis or processing.

---

## 🛠 Tech Stack

- Python
- Selenium (Chrome WebDriver)
- Pandas
- CSV
- Chrome Remote Debugging

---

## ⚙️ How It Works

### 1️⃣ Scrape Listing Page
- Navigates to: `https://www.trainingpeaks.com/coaches/search`
- Collects coach names and profile URLs
- Saves initial results to:



### 2️⃣ Scrape Individual Profiles
- Visits each coach’s profile page
- Extracts:
- Website
- Address
- Email (if available)
- Saves enriched dataset to:

### 📂 Output Files
coaches.csv — Basic coach listing data
coaches_complete.csv — Full dataset including contact details
