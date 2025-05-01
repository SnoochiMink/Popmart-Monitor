import requests
from bs4 import BeautifulSoup
import json
import time
import logging
import os
import random
from datetime import datetime
import colorama
from colorama import Fore, Style
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Initialize colorama for colored output
colorama.init()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("popmart_monitor.log"), logging.StreamHandler()]
)

class PopmartMonitor:
    def __init__(self, use_selenium=True):
        self.base_url = "https://www.popmart.com"
        self.products_url = "https://www.popmart.com/us/collection/1"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://www.popmart.com/",
            "Connection": "keep-alive"
        }
        self.use_selenium = use_selenium
        self.known_products = self.load_known_products()
        self.all_products = []
        self.driver = None
        if self.use_selenium:
            self.driver = self.setup_selenium()

    def setup_selenium(self):
        """Set up Selenium WebDriver with enhanced options to suppress WebGL and mimic a real browser."""
        try:
            options = Options()
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")  # More aggressive than --disable-webgl
            options.add_argument("--disable-webgl")  # Still include for good measure
            options.add_argument("--disable-accelerated-2d-canvas")
            options.add_argument("--disable-accelerated-video-decode")
            options.add_argument("window-size=1920,1080")
            options.add_argument(f"user-agent={self.headers['User-Agent']}")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_argument("--disable-blink-features=AutomationControlled")
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            driver.set_page_load_timeout(300)  # 5 minutes
            logging.info("Selenium WebDriver initialized")
            return driver
        except Exception as e:
            logging.error(f"Failed to initialize Selenium: {e}")
            self.use_selenium = False
            return None

    def load_known_products(self):
        """Load previously seen products from a JSON file."""
        try:
            if os.path.exists("known_products.json"):
                with open("known_products.json", "r") as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logging.error(f"Failed to load known products: {e}")
            return {}

    def save_known_products(self):
        """Save known products to a JSON file."""
        try:
            with open("known_products.json", "w") as f:
                json.dump(self.known_products, f, indent=2)
        except Exception as e:
            logging.error(f"Failed to save known products: {e}")

    def fetch_website(self, url, use_selenium=False, retries=3, delay=5):
        """Fetch and parse a webpage with retries and enhanced diagnostics."""
        for attempt in range(retries):
            if use_selenium and self.use_selenium and self.driver:
                try:
                    self.driver.get(url)
                    # Handle terms and conditions popup
                    try:
                        logging.info("Waiting for terms and conditions popup...")
                        accept_button = WebDriverWait(self.driver, 60).until(
                            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'ACCEPT') or contains(text(), 'Accept')]"))
                        )
                        accept_button.click()
                        logging.info("Clicked accept button")
                        time.sleep(2)
                    except Exception as e:
                        logging.info(f"No terms popup found or failed to click: {e}")

                    # Wait longer for product items to load
                    logging.info("Waiting for product items to load...")
                    WebDriverWait(self.driver, 120).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div.index_productItem__Z0Lxa, div[class*='productItem']"))
                    )
                    html = self.driver.page_source
                    logging.info(f"Fetched {url} using Selenium")
                    return BeautifulSoup(html, "html.parser")
                except Exception as e:
                    logging.error(f"Selenium failed for {url} (attempt {attempt+1}/{retries}): {e}")
                    if self.driver:
                        self.driver.save_screenshot(f"debug_screenshot_attempt_{attempt+1}.png")
                        with open(f"debug_page_source_attempt_{attempt+1}.html", "w", encoding="utf-8") as f:
                            f.write(self.driver.page_source)
                        logs = self.driver.get_log('browser')
                        for log in logs:
                            logging.error(f"Browser log: {log['message']}")
                    if attempt == retries - 1:
                        return None
                    time.sleep(delay)
            else:
                try:
                    response = requests.get(url, headers=self.headers, timeout=30)
                    response.raise_for_status()
                    logging.info(f"Fetched {url} - Status: {response.status_code}")
                    return BeautifulSoup(response.content, "html.parser")
                except requests.RequestException as e:
                    logging.error(f"Failed to fetch {url} (attempt {attempt+1}/{retries}): {e}")
                    if attempt == retries - 1:
                        return None
                    time.sleep(delay)
        return None

    def get_product_pages(self):
        """Retrieve product info from the collections page."""
        product_list = []
        soup = self.fetch_website(self.products_url, use_selenium=self.use_selenium)
        if not soup:
            logging.warning("No soup object returned for product pages")
            with open("debug_collection.html", "w", encoding="utf-8") as f:
                f.write("No content fetched")
            return []

        product_items = soup.select("div.index_productItem__Z0Lxa, div[class*='productItem']")
        logging.info(f"Found {len(product_items)} product items")

        if not product_items:
            logging.warning("No product items found. Saving HTML for debugging")
            with open("debug_collection.html", "w", encoding="utf-8") as f:
                f.write(str(soup.prettify()))

        for item in product_items:
            link_element = item.select_one("a[href*='/product/']")
            if not link_element or "href" not in link_element.attrs:
                continue
            href = link_element["href"]
            full_url = href if href.startswith("http") else self.base_url + href

            title_elem = item.select_one("h2.index_itemUsTitle__70Lxa")
            title = title_elem.text.strip() if title_elem else "Unknown Product"

            price_elem = item.select_one("div.index_itemPrice__AQQmy")
            price = price_elem.text.strip() if price_elem else "Unknown Price"

            is_new = bool(item.select_one("span.ant-tag.index_tagType__EQIMP[style*='rgb(255, 179, 0)']"))
            is_out_of_stock = bool(item.select_one("span.ant-tag.index_tagType__EQIMP[style*='rgb(153, 153, 153)']"))

            product_info = {
                "url": full_url,
                "title": title,
                "price": price,
                "is_new": is_new,
                "is_out_of_stock": is_out_of_stock,
                "in_stock": not is_out_of_stock
            }
            product_list.append(product_info)

        logging.info(f"Collected {len(product_list)} products")
        return product_list

    def check_product_stock(self, product_info):
        """Check product details and stock status on the product page."""
        product_url = product_info["url"]
        soup = self.fetch_website(product_url, use_selenium=False)
        if not soup:
            logging.warning(f"No soup object for {product_url}")
            return None

        try:
            title = product_info["title"]
            price = product_info["price"]

            add_to_bag = (
                soup.select_one(".add-to-bag") or
                soup.select_one(".add-to-cart") or
                soup.select_one("[data-add-to-cart]") or
                soup.select_one("button:contains('Add to Bag')") or
                soup.select_one("button:contains('Add to bag')")
            )
            out_of_stock = (
                soup.select_one(".sold-out") or
                soup.select_one(".out-of-stock") or
                soup.select_one(".product-unavailable") or
                soup.select_one("button:disabled")
            )
            in_stock = bool(add_to_bag and not out_of_stock)

            return {
                "url": product_url,
                "title": title,
                "price": price,
                "is_new": product_info["is_new"],
                "in_stock": in_stock
            }
        except Exception as e:
            logging.error(f"Error processing product {product_url}: {e}")
            return None

    def display_new_product_alert(self, product):
        """Display an alert for a new product labeled 'NEW'."""
        print("\n" + "=" * 60)
        print(f"{Fore.GREEN}🌟 NEW PRODUCT ALERT! 🌟{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Product:{Style.RESET_ALL} {product['title']}")
        print(f"{Fore.YELLOW}Price:{Style.RESET_ALL} {product['price']}")
        print(f"{Fore.YELLOW}URL:{Style.RESET_ALL} {product['url']}")
        print(f"{Fore.YELLOW}Time:{Style.RESET_ALL} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60 + "\n")

    def display_restock_alert(self, product):
        """Display a restock alert."""
        print("\n" + "=" * 60)
        print(f"{Fore.GREEN}🚨 RESTOCK ALERT! 🚨{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Product:{Style.RESET_ALL} {product['title']}")
        print(f"{Fore.YELLOW}Price:{Style.RESET_ALL} {
