# NYC ACRIS Mortgage Data Scraper

A Python utility designed to automate the retrieval of property party information (Grantors and Grantees) from the **NYC Department of Finance ACRIS (Automated City Register Information System)** via the NYC Open Data API.

## 📌 Overview

This script processes an Excel file containing NYC Document IDs, queries the Open Data API for each record, and extracts specific metadata:

* **Property Address**
* **Party Type 1 (Grantor/Borrower)**
* **Party Type 2 (Grantee/Lender)**

The final data is compiled and exported into a structured Excel spreadsheet for further analysis.

## 🚀 Features

* **Automated API Integration:** Uses the Socrata Open Data API (SODA) to fetch real-time public records.
* **Intelligent Extraction:** Specifically filters JSON responses to map "Party 1" and "Party 2" correctly.
* **Bulk Processing:** Iterates through Excel rows to handle multiple Document IDs in one run.
* **Excel Output:** Generates a clean `Mortgage_Results.xlsx` file ready for business use.

## 🛠️ Requirements

Ensure you have Python 3.x installed along with the following libraries:

```bash
pip install pandas requests openpyxl

```

## 📂 Project Structure

* `script.py`: The main Python execution script.
* `mortgages.xlsx`: Your input file containing a column named **DOCUMENT ID**.
* `Mortgage_Results.xlsx`: The generated output file (created after running).

## 🚦 How to Use

1. **Prepare Input:** Create an Excel file named `mortgages.xlsx` in the root directory. Ensure it has a header column titled `DOCUMENT ID`.
2. **Run the Script:**
```bash
python script.py

```


3. **View Results:** Once the terminal prints `Scraping complete`, open `Mortgage_Results.xlsx` to view the enriched data.

## 📊 Data Mapping Details

The script interacts with the [ACRIS - Real Property Parties]() dataset. It maps the data as follows:

| Field | Source | Description |
| --- | --- | --- |
| **party_type_1** | Party Type 1 | Typically the Grantor / Borrower |
| **party_type_2** | Party Type 2 | Typically the Grantee / Lender |
| **address_1** | address_1 | The primary street address associated with the ID |

---

**Note:** *This tool is intended for use with public data provided by NYC Open Data. Please be mindful of API rate limits when processing very large datasets.*
