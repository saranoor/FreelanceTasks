from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

chrome_options = Options()
chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")

# This connects to the window YOU just opened manually
driver = webdriver.Chrome(options=chrome_options)

# Now go to the site. Cloudflare almost never blocks this because it's a real browser.
# url = "https://www.martindale.com/search/attorneys-law-firms-articles/?term=Automobile%20Accidents%20near%20Los%20Angeles%2C%20CA"
url = "https://www.martindale.com/search/attorneys/?term=Automobile%20Accidents%20near%20Los%20Angeles%2C%20CA&params=eyJ0eXBlIjoicGVvcGxlIiwidGVybSI6IkF1dG9tb2JpbGUgQWNjaWRlbnRzIG5lYXIgTG9zIEFuZ2VsZXMsIENBIiwicGFnZVRpdGxlIjoibDpMb3MgQW5nZWxlcywgQ0F8YTpBdXRvbW9iaWxlIEFjY2lkZW50cyIsImluaXRpYWxVcmwiOnsiZ2VvTG9jYXRpb25GYWNldCI6WyJMb3MgQW5nZWxlcywgQ0EiXSwic2VhcmNoU2VlZCI6IjE3MDU3NzUzNTIiLCJrZXl3b3JkIjoiIiwicHJhY3RpY2VBcmVhcyI6WyJBdXRvbW9iaWxlIEFjY2lkZW50cyJdfSwicHJhY3RpY2VBcmVhcyI6WyJBdXRvbW9iaWxlIEFjY2lkZW50cyIsIlBlcnNvbmFsIEluanVyeSJdLCJwcmFjdGljZUFyZWFzUmVjZW50cyI6WyJBdXRvbW9iaWxlIEFjY2lkZW50cyJdLCJnZW9Mb2NhdGlvbkZhY2V0IjpbIkxvcyBBbmdlbGVzLCBDQSIsIlNhbiBGcmFuY2lzY28sIENBIl0sImdlb0xvY2F0aW9uRmFjZXRSZWNlbnRzIjpbIkxvcyBBbmdlbGVzLCBDQSJdLCJwYWdlIjoxLCJsaW1pdCI6MzAsIm9mZnNldCI6MCwic29ydCI6IiIsInNvcnRUeXBlIjoiIiwiY2xlYXJQYXJhbXMiOmZhbHNlLCJrZXl3b3JkIjoiIn0="
driver.get(url)

# import pandas as pd
# from selenium.webdriver.common.by import By

# # 1. Find all cards
# cards = driver.find_elements(By.CSS_SELECTOR, "div.card")

# data_list = []

# print(f"Processing {len(cards)} cards...")

# for card in cards:
#     try:
#         # CHECK FOR SPONSORED LABEL
#         # We try to find the label; if it exists, we skip this card.
#         sponsored_check = card.find_elements(By.CSS_SELECTOR, ".sponsored-label")
#         if len(sponsored_check) > 0:
#             continue  # Skip this card because it's sponsored

#         # 2. Extract Data for Non-Sponsored results
#         name = card.find_element(By.CSS_SELECTOR, "li.detail_title h3").text.strip()
        
#         try:
#             location = card.find_element(By.CSS_SELECTOR, "li.detail_location").text.replace("location", "").strip()
#         except:
#             location = "N/A"

#         try:
#             phone = card.find_element(By.CSS_SELECTOR, ".callTrackingNumber .button-text").text.strip()
#         except:
#             phone = "N/A"

#         try:
#             website = card.find_element(By.CSS_SELECTOR, "a.webstats-website-click").get_attribute("href")
#         except:
#             website = "N/A"

#         # 3. Append to our list
#         data_list.append({
#             "Attorney/Firm Name": name,
#             "Location": location,
#             "Phone": phone,
#             "Website": website
#         })

#     except Exception as e:
#         continue

# # 4. Convert to DataFrame and Save to Excel
# if data_list:
#     df = pd.DataFrame(data_list)
#     file_name = "attorneys_results.xlsx"
#     df.to_excel(file_name, index=False)
#     print(f"Success! Saved {len(data_list)} non-sponsored results to {file_name}")
# else:
#     print("No non-sponsored results found.")

import os
import pandas as pd
import time
from selenium.webdriver.common.by import By

file_name = "attorneys_results.xlsx"

while True:
    page_data = [] # Reset for each page
    print(f"Scraping current page...")
    
    # 1. Your existing extraction logic
    cards = driver.find_elements(By.CSS_SELECTOR, "div.card")
    for card in cards:
        try:
            if len(card.find_elements(By.CSS_SELECTOR, ".sponsored-label")) > 0:
                continue
            
            # Extract details
            name = card.find_element(By.CSS_SELECTOR, "li.detail_title h3").text.strip()
            # ... (extract phone, location, website as we did before) ...
            try:
                location = card.find_element(By.CSS_SELECTOR, "li.detail_location").text.replace("location", "").strip()
            except:
                location = "N/A"

            try:
                phone = card.find_element(By.CSS_SELECTOR, ".callTrackingNumber .button-text").text.strip()
            except:
                phone = "N/A"

            try:
                website = card.find_element(By.CSS_SELECTOR, "a.webstats-website-click").get_attribute("href")
            except:
                website = "N/A"

            page_data.append({
                "Name": name, 
                "Location": location, 
                "Phone": phone, 
                "Website": website
            })
        except:
            continue

    # 2. APPEND TO EXCEL IMMEDIATELY
    if page_data:
        new_df = pd.DataFrame(page_data)
        
        if not os.path.isfile(file_name):
            # If file doesn't exist, create it
            new_df.to_excel(file_name, index=False)
            total_count = len(new_df)
        else:
            # If it exists, read existing, append, and save
            existing_df = pd.read_excel(file_name)
            updated_df = pd.concat([existing_df, new_df], ignore_index=True)
            updated_df.to_excel(file_name, index=False)
            total_count = len(updated_df)
        print(f"Saved {len(page_data)} items. Total now in file: {total_count}")
        # print(f"Saved {len(page_data)} items. Total now: {len(updated_df) if os.path.isfile(file_name) else len(page_data)}")

    # 3. PAGINATION: Click Next
    try:
        next_button = driver.find_element(By.CSS_SELECTOR, "a.arrow[rel='next']")
        driver.execute_script("arguments[0].scrollIntoView();", next_button)
        time.sleep(2)
        next_button.click()
        time.sleep(5) # Give it time to load
    except:
        print("Final page reached.")
        break