import time
import json
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

def setup_selenium():
    """Set up Selenium with a visible Chrome browser."""
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(300)  # 5-minute timeout for slow pages
    print("Browser opened successfully!")
    return driver

def handle_popups(driver):
    """Handle terms and conditions or other popups."""
    try:
        accept_button = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'ACCEPT') or contains(text(), 'Accept')]"))
        )
        accept_button.click()
        print("Clicked 'ACCEPT' on popup")
        time.sleep(2)
    except Exception:
        print("No popup found or couldn’t click it.")

def scrape_products(driver):
    """Scrape product data from the Popmart collections page."""
    try:
        # Wait for product elements to load
        WebDriverWait(driver, 120).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.index_productItemContainer_ZB9n0, div[class*='productItem']"))
        )
        soup = BeautifulSoup(driver.page_source, "html.parser")
        product_items = soup.select("div.index_productItemContainer_ZB9n0, div[class*='productItem']")
        products = {}
        for item in product_items:
            title_elem = item.select_one("h2.index_itemUsTitle__70Lxa")
            price_elem = item.select_one("div.index_itemPrice__AQQmy")
            title = title_elem.text.strip() if title_elem else "Unknown"
            price = price_elem.text.strip() if price_elem else "Unknown"
            is_new = bool(item.select_one("span.ant-tag.index_tagType__EQIMP[style*='rgb(255, 179, 0)']"))
            in_stock = not bool(item.select_one("span.ant-tag.index_tagType__EQIMP[style*='rgb(153, 153, 153)']"))
            products[title] = {"price": price, "is_new": is_new, "in_stock": in_stock}
        return products
    except Exception as e:
        print(f"Error scraping products: {e}")
        return {}

def load_previous_data(filename="previous_products.json"):
    """Load previously saved product data."""
    if os.path.exists(filename):
        with open(filename, "r") as f:
            return json.load(f)
    return {}

def save_current_data(products, filename="previous_products.json"):
    """Save current product data to a file."""
    with open(filename, "w") as f:
        json.dump(products, f)

def check_for_changes(previous, current):
    """Compare previous and current products, return new or restocked items."""
    new_or_restocked = []
    for title, data in current.items():
        if title not in previous:
            if data["in_stock"]:
                new_or_restocked.append(f"NEW: {title} - {data['price']}")
        elif not previous[title]["in_stock"] and data["in_stock"]:
            new_or_restocked.append(f"RESTOCKED: {title} - {data['price']}")
    return new_or_restocked

def main():
    driver = setup_selenium()
    try:
        # Navigate to Popmart collections page
        driver.get("https://www.popmart.com/us/collection/1")
        handle_popups(driver)

        # Scrape current product data
        current_products = scrape_products(driver)
        if not current_products:
            print("No products scraped. Check the page or selectors.")
            return

        # Load previous product data
        previous_products = load_previous_data()

        # Check for new or restocked products
        changes = check_for_changes(previous_products, current_products)
        if changes:
            print("\nALERTS:")
            for change in changes:
                print(change)
        else:
            print("No new or restocked products found.")

        # Save current data for next run
        save_current_data(current_products)

        # Keep browser open for manual inspection
        print("\nBrowser will stay open. Press Enter to close it.")
        input()
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
