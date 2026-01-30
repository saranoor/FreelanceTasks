from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
import csv
import pandas as pd 
import time

def scrape_data():
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")

    # This connects to the window YOU just opened manually
    driver = webdriver.Chrome(options=chrome_options)

    # Now go to the site. Cloudflare almost never blocks this because it's a real browser.
    # url = "https://www.martindale.com/search/attorneys-law-firms-articles/?term=Automobile%20Accidents%20near%20Los%20Angeles%2C%20CA"
    url = "https://www.trainingpeaks.com/coaches/search"
    driver.get(url)
    wait = WebDriverWait(driver, 40)
    result_list = wait.until(
        EC.presence_of_element_located((By.CLASS_NAME, "search-results-list"))
    )

    # Find all row divs within result-list
    row_divs = result_list.find_elements(By.CLASS_NAME, "row")
    data =[]

    i=0
    # Loop through each row div and extract the name
    for row in row_divs:
        if i==20:
            break
        try:
            # Find the h4 element with class 'profile-full-name'
            name_element = row.find_element(By.CLASS_NAME, "profile-full-name")
            profile_image_div = row.find_element(By.CLASS_NAME, "profile-image")
            profile_link = profile_image_div.find_element(By.TAG_NAME, "a").get_attribute("href")
            name = name_element.text.strip()
            
            # Clean up the name (remove extra dashes and spaces)
            name = name.replace("--", "").strip()
            
            if name:  # Only add non-empty names
                data.append({'name':name, 'link': profile_link})


        except Exception as e:
            # Skip if name element not found in this row
            continue
        i+=1
    for item in data:
        print(f"{item} \n")
    driver.quit()

    with open('coaches.csv', 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['name', 'link']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()  # Write column headers
        writer.writerows(data)  # Write all rows

        print("Data saved to coaches.csv")
    
    scrape_contact(data)
def remove_duplicates():
    # Read the CSV file
    df = pd.read_csv('coaches_complete.csv')

    # Remove duplicates
    df_clean = df.drop_duplicates()

    # Save back to CSV (overwriting the original file)
    df_clean.to_csv('coaches.csv', index=False, encoding='utf-8')

    print(f"Original rows: {len(df)}")
    print(f"After removing duplicates: {len(df_clean)}")
    print(f"Duplicates removed: {len(df) - len(df_clean)}")
    df_clean.to_csv('coaches_complete.csv', index=False)

def scrape_contact(coaches):
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")

    # This connects to the window YOU just opened manually
    driver = webdriver.Chrome(options=chrome_options)
    for coach in coaches:
        print(f"coach: {coach}")
        try:
            # Navigate to the coach's profile page
            driver.get(coach['link'])
            time.sleep(2)  # Wait for page to load
            
            # Wait for the contact section to load
            wait = WebDriverWait(driver, 10)
            contact_section = wait.until(
                EC.presence_of_element_located((By.ID, "coach-contact"))
            )
            
            # Initialize variables
            website = None
            address = None
            email = None
            
            # Extract website
            try:
                website_element = contact_section.find_element(By.CSS_SELECTOR, ".profile-website-url-container a")
                website = website_element.get_attribute("href")
            except:
                pass
            
            # Extract address
            try:
                address_element = contact_section.find_element(By.XPATH, "//strong[contains(text(), 'Address:')]/ancestor::div[@class='row']//p")
                address = address_element.text.strip().replace('\n', ', ')
            except:
                pass
            
            # Extract email (if exists in the contact section)
            try:
                email_element = contact_section.find_element(By.CSS_SELECTOR, "a[href^='mailto:']")
                email = email_element.get_attribute("href").replace("mailto:", "")
            except:
                pass
            
            # Add the scraped data to the coach dictionary
            coach['website'] = website
            coach['address'] = address
            coach['email'] = email
            
            print(f"Scraped {coach['name']}: Website={website}, Address={address}, Email={email}")
            
        except Exception as e:
            print(f"Error scraping {coach['name']}: {e}")
            coach['website'] = None
            coach['address'] = None
            coach['email'] = None
        df = pd.DataFrame(coaches)
        df.to_csv('coaches_complete.csv', index=False, encoding='utf-8')


if __name__ == '__main__':
    scrape_data()
    remove_duplicates()
