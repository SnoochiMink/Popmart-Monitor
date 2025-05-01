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

# Initialize colorama for colored terminal output
colorama.init()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("popmart_monitor.log"),
        logging.StreamHandler()
    ]
)

class PopmartMonitor:
    def __init__(self, use_selenium=True):
        self.base_url = "https://www.popmart.com"
        self.products_url = "https://www.popmart.com/us/collection/1"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.7103.59 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
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
        """Set up Selenium WebDriver using webdriver-manager."""
        try:
            options = Options()
            options.add_argument("--headless")  # Run in headless mode (no browser UI)
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            service = Service(ChromeDriverManager().install())  # Automatically manage ChromeDriver
            driver = webdriver.Chrome(service=service, options=options)
            driver.set_page_load_timeout(120)
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
        """Fetch and parse a webpage with retries, handling terms popup."""
        for attempt in range(retries):
            if use_selenium and self.use_selenium and self.driver:
                try:
                    self.driver.get(url)
                    # Handle terms and conditions popup
                    try:
                        accept_button = WebDriverWait(self.driver, 10).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, "div.policy_acceptBtn__ZNUI7"))
                        )
                        accept_button.click()
                        logging.info("Accepted terms and conditions popup")
                    except Exception as e:
                        logging.info(f"No terms popup found or failed to click: {e}")

                    # Wait for product items to load
                    WebDriverWait(self.driver, 30).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div.index_productItem__Z0Lxa"))
                    )
                    html = self.driver.page_source
                    logging.info(f"Fetched {url} using Selenium")
                    return BeautifulSoup(html, "html.parser")
                except Exception as e:
                    logging.error(f"Selenium failed for {url} (attempt {attempt+1}/{retries}): {e}")
                    if self.driver:
                        with open("debug_selenium.html", "w", encoding="utf-8") as f:
                            f.write(self.driver.page_source)
                    if attempt == retries - 1:
                        return None
                    time.sleep(delay)
            else:
                try:
                    response = requests.get(url, headers=self.headers, timeout=15)
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
        soup = self.fetch_website(self.products_url, use_selenium=self.use_selenium, retries=3, delay=5)
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
        soup = self.fetch_website(product_url, use_selenium=False, retries=3, delay=5)
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
        print(f"{Fore.YELLOW}Price:{Style.RESET_ALL} {product['price']}")
        print(f"{Fore.YELLOW}URL:{Style.RESET_ALL} {product['url']}")
        print(f"{Fore.YELLOW}Time:{Style.RESET_ALL} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60 + "\n")

    def display_random_pick(self):
        """Display a random 'NEW' product pick."""
        new_products = [p for p in self.all_products if p.get("is_new", False)]
        if not new_products:
            print(f"{Fore.MAGENTA}No new products available for random pick.{Style.RESET_ALL}")
            return

        random_product = random.choice(new_products)
        print("\n" + "-" * 60)
        print(f"{Fore.MAGENTA}✨ RANDOM NEW PRODUCT PICK ✨{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Product: {random_product['title']}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Price:{Style.RESET_ALL} {random_product['price']}")
        print(f"{Fore.YELLOW}URL:{Style.RESET_ALL} {random_product['url']}")
        print(f"{Fore.YELLOW}In Stock:{Style.RESET_ALL} {'Yes' if random_product['in_stock'] else 'No'}")
        print("-" * 60 + "\n")

    def run(self):
        """Run the main monitoring loop."""
        print(f"{Fore.CYAN}Checking Popmart for restocks and new products...{Style.RESET_ALL}")
        logging.info("Starting restock and new product check")

        product_list = self.get_product_pages()
        restocked_products = []
        new_products = []
        self.all_products = []

        for product_info in product_list:
            updated_product_info = self.check_product_stock(product_info)
            if not updated_product_info:
                continue

            self.all_products.append(updated_product_info)
            product_id = updated_product_info["url"]

            if product_id not in self.known_products:
                if updated_product_info["is_new"]:
                    logging.info(f"New 'NEW' product found: {updated_product_info['title']}")
                    new_products.append(updated_product_info)
                    self.display_new_product_alert(updated_product_info)

            if product_id in self.known_products:
                was_out_of_stock = not self.known_products[product_id]["in_stock"]
                is_now_in_stock = updated_product_info["in_stock"]
                if was_out_of_stock and is_now_in_stock:
                    logging.info(f"Product restocked: {updated_product_info['title']}")
                    restocked_products.append(updated_product_info)
                    self.display_restock_alert(updated_product_info)

            self.known_products[product_id] = {
                "title": updated_product_info["title"],
                "in_stock": updated_product_info["in_stock"],
                "is_new": updated_product_info["is_new"],
                "last_checked": datetime.now().isoformat()
            }
            time.sleep(1)

        self.save_known_products()
        print(f"{Fore.CYAN}Check complete. Found {len(new_products)} new 'NEW' products and {len(restocked_products)} restocked products.{Style.RESET_ALL}")
        logging.info(f"Check complete. Found {len(new_products)} new 'NEW' products and {len(restocked_products)} restocked products.")
        return restocked_products

    def wait_with_random_picks(self, total_wait_minutes=10, random_pick_minutes=3):
        """Wait with periodic random product picks."""
        total_seconds = total_wait_minutes * 60
        random_pick_seconds = random_pick_minutes * 60
        elapsed = 0

        while elapsed < total_seconds:
            remaining = total_seconds - elapsed
            mins, secs = divmod(remaining, 60)
            print(f"Next check in: {mins:02d}:{secs:02d}", end="\r")
            time.sleep(1)
            elapsed += 1

            if elapsed % random_pick_seconds == 0:
                self.display_random_pick()

        print("\n")

    def __del__(self):
        """Clean up Selenium driver."""
        if hasattr(self, 'driver') and self.driver:
            self.driver.quit()
            logging.info("Selenium WebDriver closed")

if __name__ == "__main__":
    monitor = PopmartMonitor(use_selenium=True)
    try:
        print(f"{Fore.CYAN}Popmart Restock and New Product Monitor Started{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Press Ctrl+C to exit{Style.RESET_ALL}")

        monitor.run()
        while True:
            print(f"\n{Fore.CYAN}Waiting 10 minutes before next check...{Style.RESET_ALL}")
            monitor.wait_with_random_picks(total_wait_minutes=10, random_pick_minutes=3)
            monitor.run()

    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Stopping monitor...{Style.RESET_ALL}")
        monitor.save_known_products()
        print(f"{Fore.GREEN}Data saved. Exiting.{Style.RESET_ALL}")
