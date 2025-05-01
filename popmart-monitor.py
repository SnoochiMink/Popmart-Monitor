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
    def __init__(self, use_selenium=False):
        self.base_url = "https://www.popmart.com"
        self.products_url = "https://www.popmart.com/us/collection/1"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://www.popmart.com/",
            "Connection": "keep-alive"
        }
        self.use_selenium = use_selenium
        self.known_products = self.load_known_products()
        self.all_products = []
        if self.use_selenium:
            self.driver = self.setup_selenium()

    def setup_selenium(self):
        """Set up Selenium WebDriver."""
        try:
            options = Options()
            options.add_argument("--headless")
            options.add_argument(f"user-agent={self.headers['User-Agent']}")
            service = Service()  # Assumes chromedriver is in PATH
            driver = webdriver.Chrome(service=service, options=options)
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

    def fetch_website(self, url, use_selenium=False):
        """Fetch and parse a webpage."""
        if use_selenium and self.use_selenium and self.driver:
            try:
                self.driver.get(url)
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.index_productItem__Z0Lxa"))
                )
                html = self.driver.page_source
                return BeautifulSoup(html, "html.parser")
            except Exception as e:
                logging.error(f"Selenium failed for {url}: {e}")
                return None
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            logging.info(f"Fetched {url} - Status: {response.status_code}")
            return BeautifulSoup(response.content, "html.parser")
        except requests.RequestException as e:
            logging.error(f"Failed to fetch {url}: {e}")
            return None

    def get_product_pages(self):
        """Retrieve all product page links from the collections page."""
        product_links = []
        soup = self.fetch_website(self.products_url, use_selenium=self.use_selenium)
        if not soup:
            logging.warning("No soup object returned for product pages")
            with open("debug_collection.html", "w", encoding="utf-8") as f:
                f.write("No content fetched")
            return []

        # Updated selectors based on HTML structure
        product_items = soup.select("div.index_productItem__Z0Lxa, div[class*='productItem']")
        logging.info(f"Found {len(product_items)} product items")

        if not product_items:
            logging.warning("No product items found. Saving HTML for debugging")
            with open("debug_collection.html", "w", encoding="utf-8") as f:
                f.write(str(soup.prettify()))

        for item in product_items:
            link_element = item.select_one("a[href*='/product/']")
            if link_element and "href" in link_element.attrs:
                href = link_element["href"]
                full_url = href if href.startswith("http") else self.base_url + href
                if full_url not in product_links:
                    product_links.append(full_url)

        logging.info(f"Collected {len(product_links)} unique product links")
        return product_links

    def check_product_stock(self, product_url):
        """Check product details and stock status."""
        soup = self.fetch_website(product_url)
        if not soup:
            logging.warning(f"No soup object for {product_url}")
            return None

        try:
            # Extract product title
            product_title_elem = (
                soup.select_one("h2.index_itemUsTitle__7oLxa") or
                soup.select_one("h2[class*='itemUsTitle']") or
                soup.select_one(".product-title h1") or
                soup.select_one(".product-info h1") or
                soup.select_one(".product-name") or
                soup.select_one("h1.title")
            )
            if not product_title_elem:
                logging.warning(f"No title element found for {product_url}")
            product_title = product_title_elem.text.strip() if product_title_elem else "Unknown Product"

            # Extract price
            price_elem = (
                soup.select_one(".product-price .price") or
                soup.select_one(".price") or
                soup.select_one(".product-info .money") or
                soup.select_one(".money")
            )
            price = price_elem.text.strip() if price_elem else "Unknown Price"

            # Check stock status
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
                "title": product_title,
                "price": price,
                "in_stock": in_stock
            }
        except Exception as e:
            logging.error(f"Error processing product {product_url}: {e}")
            return None

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
        """Display a random product pick."""
        if not self.all_products:
            print(f"{Fore.MAGENTA}No products available for random pick.{Style.RESET_ALL}")
            return

        random_product = random.choice(self.all_products)
        print("\n" + "-" * 60)
        print(f"{Fore.MAGENTA}✨ RANDOM PICK OF THE CYCLE ✨{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Product: {random_product['title']}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Price:{Style.RESET_ALL} {random_product['price']}")
        print(f"{Fore.YELLOW}URL:{Style.RESET_ALL} {random_product['url']}")
        print(f"{Fore.YELLOW}In Stock:{Style.RESET_ALL} {'Yes' if random_product['in_stock'] else 'No'}")
        print("-" * 60 + "\n")

    def run(self):
        """Run the main monitoring loop."""
        print(f"{Fore.CYAN}Checking Popmart for restocks...{Style.RESET_ALL}")
        logging.info("Starting restock check")

        product_links = self.get_product_pages()
        restocked_products = []
        self.all_products = []

        for link in product_links:
            product_info = self.check_product_stock(link)
            if not product_info:
                continue

            self.all_products.append(product_info)
            product_id = product_info["url"]

            if product_id in self.known_products:
                if not self.known_products[product_id]["in_stock"] and product_info["in_stock"]:
                    logging.info(f"Restock detected: {product_info['title']}")
                    restocked_products.append(product_info)
                    self.display_restock_alert(product_info)
            else:
                if product_info["in_stock"]:
                    logging.info(f"New product in stock: {product_info['title']}")
                    restocked_products.append(product_info)
                    self.display_restock_alert(product_info)

            self.known_products[product_id] = {
                "title": product_info["title"],
                "in_stock": product_info["in_stock"],
                "last_checked": datetime.now().isoformat()
            }
            time.sleep(1)

        self.save_known_products()
        print(f"{Fore.CYAN}Check complete. Found {len(restocked_products)} restocked/new products.{Style.RESET_ALL}")
        logging.info(f"Check complete. Found {len(restocked_products)} restocked/new products.")
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
        print(f"{Fore.CYAN}Popmart Restock Monitor Started{Style.RESET_ALL}")
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
