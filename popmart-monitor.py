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
    def __init__(self):
        self.base_url = "https://www.popmart.com"
        self.products_url = "https://www.popmart.com/us/collection/1"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5"
        }
        self.known_products = self.load_known_products()
        self.all_products = []  # Store all products for random picks

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

    def fetch_website(self, url):
        """Fetch and parse a webpage using BeautifulSoup."""
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return BeautifulSoup(response.content, "html.parser")
        except requests.RequestException as e:
            logging.error(f"Failed to fetch {url}: {e}")
            return None

    def get_product_pages(self):
        """Retrieve all product page links from the collections page."""
        product_links = []
        soup = self.fetch_website(self.products_url)
        if not soup:
            logging.warning("No soup object returned for product pages.")
            return []

        # Try multiple selectors for product cards
        product_items = soup.select(".product-card, .product-item, .collection-item, .index_item")
        for item in product_items:
            link_element = item.select_one("a")
            if link_element and "href" in link_element.attrs:
                href = link_element["href"]
                full_url = href if href.startswith("http") else self.base_url + href
                product_links.append(full_url)

        logging.info(f"Found {len(product_links)} product links")
        return product_links

    def check_product_stock(self, product_url):
        """Check product details and stock status."""
        soup = self.fetch_website(product_url)
        if not soup:
            logging.warning(f"No soup object for {product_url}")
            return None

        try:
            # Extract product title with provided selector and fallbacks
            product_title_elem = (
                soup.select_one("h2.index_itemUsTitle__7oLxa") or  # Primary selector
                soup.select_one("h2[class*='itemUsTitle']") or     # Partial match for CSS modules
                soup.select_one(".product-title h1") or
                soup.select_one(".product-info h1") or
                soup.select_one(".product-name") or
                soup.select_one("h1.title")
            )
            if not product_title_elem:
                logging.warning(f"No title element found for {product_url}")
            product_title = product_title_elem.text.strip() if product_title_elem else "Unknown Product"

            # Extract price with multiple selectors
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
        """Display a restock alert in the terminal."""
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

            # Check for new or restocked products
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

            # Update known products
            self.known_products[product_id] = {
                "title": product_info["title"],
                "in_stock": product_info["in_stock"],
                "last_checked": datetime.now().isoformat()
            }
            time.sleep(1)  # Avoid overwhelming the server

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

if __name__ == "__main__":
    monitor = PopmartMonitor()
    try:
        print(f"{Fore.CYAN}Popmart Restock Monitor Started{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Press Ctrl+C to exit{Style.RESET_ALL}")

        monitor.run()  # Initial run
        while True:
            print(f"\n{Fore.CYAN}Waiting 10 minutes before next check...{Style.RESET_ALL}")
            monitor.wait_with_random_picks(total_wait_minutes=10, random_pick_minutes=3)
            monitor.run()

    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Stopping monitor...{Style.RESET_ALL}")
        monitor.save_known_products()
        print(f"{Fore.GREEN}Data saved. Exiting.{Style.RESET_ALL}")
