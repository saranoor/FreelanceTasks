from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import os
import pandas as pd
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

chrome_options = Options()
chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")

driver = webdriver.Chrome(options=chrome_options)
driver.maximize_window()
url = "https://www.martindale.com/search/attorneys/?term=Automobile%20Accidents%20near%20Los%20Angeles%2C%20CA&params=eyJ0eXBlIjoicGVvcGxlIiwidGVybSI6IkF1dG9tb2JpbGUgQWNjaWRlbnRzIG5lYXIgTG9zIEFuZ2VsZXMsIENBIiwicGFnZVRpdGxlIjoibDpMb3MgQW5nZWxlcywgQ0F8YTpBdXRvbW9iaWxlIEFjY2lkZW50cyIsImluaXRpYWxVcmwiOnsiZ2VvTG9jYXRpb25GYWNldCI6WyJMb3MgQW5nZWxlcywgQ0EiXSwic2VhcmNoU2VlZCI6IjE3MDU3NzUzNTIiLCJrZXl3b3JkIjoiIiwicHJhY3RpY2VBcmVhcyI6WyJBdXRvbW9iaWxlIEFjY2lkZW50cyJdfSwicHJhY3RpY2VBcmVhcyI6WyJBdXRvbW9iaWxlIEFjY2lkZW50cyIsIlBlcnNvbmFsIEluanVyeSJdLCJwcmFjdGljZUFyZWFzUmVjZW50cyI6WyJBdXRvbW9iaWxlIEFjY2lkZW50cyJdLCJnZW9Mb2NhdGlvbkZhY2V0IjpbIkxvcyBBbmdlbGVzLCBDQSIsIlNhbiBGcmFuY2lzY28sIENBIl0sImdlb0xvY2F0aW9uRmFjZXRSZWNlbnRzIjpbIkxvcyBBbmdlbGVzLCBDQSJdLCJwYWdlIjoxLCJsaW1pdCI6MzAsIm9mZnNldCI6MCwic29ydCI6IiIsInNvcnRUeXBlIjoiIiwiY2xlYXJQYXJhbXMiOmZhbHNlLCJrZXl3b3JkIjoiIn0="
driver.get(url)

file_name = "attorneys_results.xlsx"

while True:
    page_data = []  # Reset for each page
    print(f"Scraping current page...")
    time.sleep(10)  # Wait for page to load, adjust as needed
    cards = driver.find_elements(By.CSS_SELECTOR, "div.card")
    print(f"Found {len(cards)} cards on this page.")
    for card in cards:
        print("Processing a card...")
        try:
            if len(card.find_elements(By.CSS_SELECTOR, ".sponsored-label")) > 0:
                continue

            name = card.find_element(By.CSS_SELECTOR, "li.detail_title h3").text.strip()
            try:
                location = (
                    card.find_element(By.CSS_SELECTOR, "li.detail_location")
                    .text.replace("location", "")
                    .strip()
                )
            except:
                location = "N/A"

            try:
                phone = card.find_element(
                    By.CSS_SELECTOR, ".callTrackingNumber .button-text"
                ).text.strip()
            except:
                phone = "N/A"

            try:
                website = card.find_element(
                    By.CSS_SELECTOR, "a.webstats-website-click"
                ).get_attribute("href")
            except:
                website = "N/A"

            page_data.append(
                {"Name": name, "Location": location, "Phone": phone, "Website": website}
            )
        except:
            print("Error extracting data from a card, skipping...")
            continue

    if page_data:
        new_df = pd.DataFrame(page_data)

        if not os.path.isfile(file_name):
            new_df.to_excel(file_name, index=False)
            total_count = len(new_df)
        else:
            existing_df = pd.read_excel(file_name)
            updated_df = pd.concat([existing_df, new_df], ignore_index=True)
            updated_df.to_excel(file_name, index=False)
            total_count = len(updated_df)
        print(f"Saved {len(page_data)} items. Total now in file: {total_count}")

    try:
        wait = WebDriverWait(driver, 15)

        next_selector = "a.arrow[rel='next']"

        next_button = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, next_selector))
        )

        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", next_button
        )
        time.sleep(1)  # Short pause for stability after scroll

        driver.execute_script("arguments[0].click();", next_button)

        print("Navigating to next page...")

        wait.until(EC.staleness_of(cards[0]))
    except:
        print("Final page reached.")
        break
