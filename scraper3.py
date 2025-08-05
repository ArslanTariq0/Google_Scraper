import re
import time
import pandas as pd
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException

def setup_driver():
    options = Options()
    options.add_argument("--start-maximized")
    #options.add_argument("--headless")  # Uncomment for headless
    driver = webdriver.Chrome(options=options)
    return driver

def is_captcha_present(driver):
    try:
        driver.find_element(By.XPATH, "//div[contains(@class, 'captcha')]")
        return True
    except NoSuchElementException:
        return False

def wait_for_captcha_solution():
    time.sleep(20)  # Pause for manual CAPTCHA solving

def extract_urls_from_cite(driver, collected_urls, company_names):
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "search")))
    cite_elements = driver.find_elements(By.XPATH, "//cite")
    new_urls = []
    for cite in cite_elements:
        text = cite.text.strip()
        if text:
            url = text.split()[0].rstrip("/")
            if url not in collected_urls:
                collected_urls.add(url)
                new_urls.append(url)
                company_name = url.replace("http://", "").replace("https://", "").replace("www.", "").split('.')[0]
                company_names[company_name] = url
    return new_urls

def go_to_next_page(driver):
    try:
        next_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "pnnext"))
        )
        driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
        driver.execute_script("arguments[0].click();", next_button)
        return True
    except (TimeoutException, NoSuchElementException, ElementClickInterceptedException):
        return False

def fetch_html_sections(url):
    driver = setup_driver()
    html = ""
    start_time = time.time()
    try:
        driver.set_page_load_timeout(25)  # Hard limit for loading
        driver.get(url)
        elapsed = time.time() - start_time
        if elapsed < 25:
            time.sleep(max(0, 3 - elapsed))  # Adjust sleep if page loads quickly
        html = driver.page_source
    except Exception as e:
        print(f"[TIMEOUT/ERROR] Skipping {url}: {e}")
    finally:
        driver.quit()
    return html


def extract_contact_info(html):
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,7}'
    phone_pattern = r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
    address_pattern = (
        r'\d{1,5}\s+[\w\s\.,#-]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr'
        r'|Court|Ct|Way|Square|Sq|Circle|Cir|Trail|Trl|Parkway|Pkwy|Commons|Cmns)?'
        r'(?:\s+(?:Apt|Suite|Unit|#)\s*\w+)?\s*,?\s*'
        r'[\w\s]+,?\s*'
        r'(?:FL|fl|Florida|FLorida|CA|California),?\s*'
        r'\d{5}(?:-\d{4})?'
    )

    emails = re.findall(email_pattern, html)
    phones = re.findall(phone_pattern, html)
    addresses = re.findall(address_pattern, html)

    return {
        "emails": list(set(emails)),  # All unique emails
        "phone": phones[0] if phones else "",
        "address": addresses[0] if addresses else ""
    }

def save_to_excel_row(data, filename="company_contacts.xlsx"):
    file_exists = os.path.exists(filename)
    df = pd.DataFrame([data])
    if file_exists:
        df_existing = pd.read_excel(filename)
        df_combined = pd.concat([df_existing, df], ignore_index=True)
        df_combined.to_excel(filename, index=False)
    else:
        df.to_excel(filename, index=False)

def scrape_google_results(query, max_pages=1):
    driver = setup_driver()
    collected_urls = set()
    company_names = {}
    page_count = 0

    try:
        driver.get("https://www.google.com")
        wait = WebDriverWait(driver, 10)

        try:
            consent_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'I agree') or contains(text(),'Accept all')]"))
            )
            consent_button.click()
        except TimeoutException:
            pass

        search_box = wait.until(EC.presence_of_element_located((By.NAME, "q")))
        search_box.clear()
        search_box.send_keys(query)
        search_box.send_keys(Keys.RETURN)

        while page_count < max_pages:
            wait.until(EC.presence_of_element_located((By.ID, "search")))
            if is_captcha_present(driver):
                wait_for_captcha_solution()

            extract_urls_from_cite(driver, collected_urls, company_names)
            page_count += 1

            if not go_to_next_page(driver):
                break

            time.sleep(2)

    except Exception as e:
        print(f"Error during scraping: {e}")
    finally:
        driver.quit()

    for company, url in company_names.items():
        print(f"[PROCESSING] {company} - {url}")
        html = fetch_html_sections(url)
        info = extract_contact_info(html)

        data = {
            "company_name": company,
            "phone": info["phone"],
            "address": info["address"],
            "emails": ", ".join(info["emails"]),
            "website": url
        }

        save_to_excel_row(data)
        print(f"[SAVED] {company} → Excel")

if __name__ == "__main__":
    scrape_google_results("Law Business Companies in california", max_pages=1)
