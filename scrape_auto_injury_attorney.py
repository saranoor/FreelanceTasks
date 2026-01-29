# # from selenium import webdriver
# # from selenium.webdriver.common.by import By
# # from selenium.webdriver.support.ui import WebDriverWait
# # from selenium.webdriver.support import expected_conditions as EC

# # # 1) setup driver
# # driver = webdriver.Chrome()
# # driver.get("https://www.martindale.com/search/attorneys-law-firms-articles/?term=Automobile%20Accidents%20near%20Los%20Angeles%2C%20CA")
# # print("results__result-row" in driver.page_source)

# # wait = WebDriverWait(driver, 10)

# # # 1. Wait for the main container you found to load
# # wait = WebDriverWait(driver, 50)
# # # Using CSS_SELECTOR to handle the specific class name more reliably
# # try:
# #     container = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.results__result-row")))
# #     print("Container found!")
# # except:
# #     # If it fails, let's print the page source to see what the browser is actually seeing
# #     with open("debug.html", "w", encoding="utf-8") as f:
# #         f.write(driver.page_source)
# #     print("Timed out. Saved page source to debug.html for inspection.")

# import undetected_chromedriver as uc
# from selenium.webdriver.common.by import By
# import time

# options = uc.ChromeOptions()
# # Adding these helps bypass deeper detection
# options.add_argument('--disable-popup-blocking')
# options.add_argument('--no-first-run')
# options.add_argument('--no-service-autorun')
# options.add_argument('--password-manager-enabled=false')
# # This replaces your standard driver = webdriver.Chrome()
# driver = uc.Chrome(version_main=122) 
# driver.get("https://www.google.com")
# time.sleep(3) # Wait like a human would
# url = "https://www.martindale.com/search/attorneys-law-firms-articles/?term=Automobile%20Accidents%20near%20Los%20Angeles%2C%20CA"
# driver.get(url)

# # Now, solve the captcha manually if it appears. 
# # Because you are using 'uc', it should actually LET YOU THROUGH this time.
# input("Solve the captcha, wait for the attorneys to appear, then press Enter...")

# # Now try to grab your container
# try:
#     container = driver.find_element(By.CSS_SELECTOR, ".results__result-row")
#     print("Success! The page is fully loaded.")
# except:
#     print("Still can't find it. Check if the page redirected.")

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

chrome_options = Options()
chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")

# This connects to the window YOU just opened manually
driver = webdriver.Chrome(options=chrome_options)

# Now go to the site. Cloudflare almost never blocks this because it's a real browser.
url = "https://www.martindale.com/search/attorneys-law-firms-articles/?term=Automobile%20Accidents%20near%20Los%20Angeles%2C%20CA"
driver.get(url)

import pandas as pd
from selenium.webdriver.common.by import By

# 1. Find all cards
cards = driver.find_elements(By.CSS_SELECTOR, "div.card")

data_list = []

print(f"Processing {len(cards)} cards...")

for card in cards:
    try:
        # CHECK FOR SPONSORED LABEL
        # We try to find the label; if it exists, we skip this card.
        sponsored_check = card.find_elements(By.CSS_SELECTOR, ".sponsored-label")
        if len(sponsored_check) > 0:
            continue  # Skip this card because it's sponsored

        # 2. Extract Data for Non-Sponsored results
        name = card.find_element(By.CSS_SELECTOR, "li.detail_title h3").text.strip()
        
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

        # 3. Append to our list
        data_list.append({
            "Attorney/Firm Name": name,
            "Location": location,
            "Phone": phone,
            "Website": website
        })

    except Exception as e:
        continue

# 4. Convert to DataFrame and Save to Excel
if data_list:
    df = pd.DataFrame(data_list)
    file_name = "attorneys_results.xlsx"
    df.to_excel(file_name, index=False)
    print(f"Success! Saved {len(data_list)} non-sponsored results to {file_name}")
else:
    print("No non-sponsored results found.")
