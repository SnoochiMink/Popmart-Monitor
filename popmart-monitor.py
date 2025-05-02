import time
import os
import json
import datetime
import platform
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException
from colorama import init, Fore, Back, Style

# Conditionally import modules based on OS
SYSTEM = platform.system()
if SYSTEM == "Windows":
    import winsound  # Windows-only sound module
else:
    # Alternative beep function for Linux/Mac
    def beep(frequency, duration):
        print('\a')  # ASCII bell character
        time.sleep(duration/1000)

# Initialize colorama
init(autoreset=True)

# Try to import plyer for notifications, but make it optional
try:
    from plyer import notification
    NOTIFICATIONS_AVAILABLE = True
except ImportError:
    NOTIFICATIONS_AVAILABLE = False
    print(f"{Fore.YELLOW}Desktop notifications not available. Install 'plyer' package if needed.{Style.RESET_ALL}")

# Configuration
CONFIG = {
    "url": "https://www.popmart.com/us/collection/1",
    "check_interval": 300,  # seconds between checks (5 minutes)
    "alert_methods": {
        "terminal": True,
        "desktop_notification": False,  # Default to off now
        "sound": True
    },
    "filters": {
        "only_new_tag": False,  # If True, only alerts for items with the NEW tag
        "max_price": None,      # Set a maximum price to filter alerts (e.g. 50.00)
        "keywords": []          # List of keywords to match in product titles (e.g. ["disney", "hello kitty"])
    },
    "product_selectors": {
        "container": "div.index_productItemContainer_fDwtr",
        "title": "h2.index_itemUsTitle_7oLxa",
        "price": "div.index_itemPrice_AQoMy",
        "tag": "span.ant-tag.ant-tag-has-color.index_tagStyle_g01MP",
        "brand": "div.index_itemSubTitle_mX6v"
    },
    "database_file": "product_database.json"
}

# Create or load product database
def load_product_database():
    if os.path.exists(CONFIG["database_file"]):
        try:
            with open(CONFIG["database_file"], "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"{Fore.RED}Error loading database: {e}")
            return {}
    else:
        return {}

# Save product database
def save_product_database(database):
    try:
        with open(CONFIG["database_file"], "w") as f:
            json.dump(database, f, indent=4)
    except Exception as e:
        print(f"{Fore.RED}Error saving database: {e}")

# Set up Selenium with a visible browser
def setup_selenium():
    print(f"{Fore.CYAN}Setting up browser...{Style.RESET_ALL}")
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.set_page_load_timeout(300)  # 5 minutes for initial page load
    print(f"{Fore.GREEN}Browser opened successfully!{Style.RESET_ALL}")
    return driver

# Trigger alerts based on new or restocked products
def trigger_alert(product_title, product_price, is_new=False, brand="Unknown Brand", has_new_tag=False):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Determine alert type
    if has_new_tag:
        alert_type = "NEW TAGGED PRODUCT"
        bg_color = Back.RED
    elif is_new:
        alert_type = "NEW PRODUCT"
        bg_color = Back.MAGENTA
    else:
        alert_type = "RESTOCK"
        bg_color = Back.BLUE
    
    # Terminal alert
    if CONFIG["alert_methods"]["terminal"]:
        print(f"\n{bg_color}{Fore.WHITE}{alert_type} ALERT! - {timestamp}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Brand: {Fore.WHITE}{brand}")
        print(f"{Fore.YELLOW}Title: {Fore.WHITE}{product_title}")
        print(f"{Fore.YELLOW}Price: {Fore.GREEN}{product_price}")
        print(f"{Fore.CYAN}{'='*50}{Style.RESET_ALL}")
    
    # Desktop notification
    if CONFIG["alert_methods"]["desktop_notification"] and NOTIFICATIONS_AVAILABLE:
        try:
            notification.notify(
                title=f"{alert_type}: {brand}",
                message=f"Item: {product_title}\nPrice: {product_price}\nDetected at: {timestamp}",
                app_name="Product Alert Bot",
                timeout=10
            )
        except Exception as e:
            print(f"{Fore.RED}Notification error: {e}")
    
    # Sound alert
    if CONFIG["alert_methods"]["sound"]:
        try:
            if SYSTEM == "Windows":
                winsound.Beep(1000, 500)
                time.sleep(0.2)
                winsound.Beep(1500, 500)
            else:
                # Use alternative beep for Linux/Mac
                beep(1000, 500)
                time.sleep(0.2)
                beep(1500, 500)
        except Exception as e:
            print(f"{Fore.RED}Sound alert error: {e}")

# Scrape product data and check for new/restocked items
def scrape_products(driver, database):
    try:
        print(f"{Fore.CYAN}Waiting for product elements to load...{Style.RESET_ALL}")
        # Wait up to 180 seconds for product elements to appear
        WebDriverWait(driver, 180).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, CONFIG["product_selectors"]["container"]))
        )
        print(f"{Fore.GREEN}Product elements found!{Style.RESET_ALL}")
        
        products = driver.find_elements(By.CSS_SELECTOR, CONFIG["product_selectors"]["container"])
        print(f"{Fore.CYAN}Found {len(products)} products on page{Style.RESET_ALL}")
        
        # Store current scan results to compare with database
        current_products = {}
        
        for i, product in enumerate(products):
            try:
                title = product.find_element(By.CSS_SELECTOR, CONFIG["product_selectors"]["title"]).text or "Unknown"
                price = product.find_element(By.CSS_SELECTOR, CONFIG["product_selectors"]["price"]).text or "Unknown"
                
                # Check for brand/subtitle
                try:
                    brand = product.find_element(By.CSS_SELECTOR, CONFIG["product_selectors"]["brand"]).text or "Unknown Brand"
                except:
                    brand = "Unknown Brand"
                
                # Check for "NEW" tag
                is_new_tag = False
                try:
                    tag_element = product.find_element(By.CSS_SELECTOR, CONFIG["product_selectors"]["tag"])
                    if "NEW" in tag_element.text:
                        is_new_tag = True
                except:
                    pass
                
                # Generate a unique ID for the product based on title and price
                product_id = f"{title}_{price}".replace(" ", "_").lower()
                
                # Store current product data
                current_products[product_id] = {
                    "title": title,
                    "price": price,
                    "brand": brand,
                    "has_new_tag": is_new_tag,
                    "last_seen": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                # Prepare product data
                product_data = current_products[product_id]
                
                # Check if this is a new product
                if product_id not in database:
                    print(f"{Fore.GREEN}New product found: {brand} - {title} - {price}{Style.RESET_ALL}")
                    
                    # Apply filters before triggering alert
                    if apply_filters(product_data):
                        trigger_alert(title, price, is_new=True, brand=brand, has_new_tag=is_new_tag)
                    else:
                        print(f"{Fore.YELLOW}Product filtered out by settings: {brand} - {title}{Style.RESET_ALL}")
                    
                    database[product_id] = current_products[product_id]
                else:
                    # Update last_seen timestamp
                    database[product_id]["last_seen"] = current_products[product_id]["last_seen"]
                    
                    # Check if any details changed
                    if (database[product_id]["title"] != title or 
                        database[product_id]["price"] != price or 
                        database[product_id]["brand"] != brand):
                        print(f"{Fore.YELLOW}Product details changed: {brand} - {title} - {price}{Style.RESET_ALL}")
                        
                        # Apply filters before triggering alert
                        if apply_filters(product_data):
                            trigger_alert(title, price, is_new=False, brand=brand, has_new_tag=is_new_tag)
                        else:
                            print(f"{Fore.YELLOW}Updated product filtered out by settings: {brand} - {title}{Style.RESET_ALL}")
                        
                        database[product_id] = current_products[product_id]
                
            except Exception as e:
                print(f"{Fore.RED}Error scraping product #{i+1}: {e}{Style.RESET_ALL}")
        
        # Save the updated database
        save_product_database(database)
        
        return current_products
    
    except TimeoutException:
        print(f"{Fore.RED}Timeout: Product elements didn't load within 180 seconds. Check selectors or page behavior.{Style.RESET_ALL}")
        return {}
    except Exception as e:
        print(f"{Fore.RED}Error scraping products: {e}{Style.RESET_ALL}")
        return {}

# Run continuous monitoring
def monitor_products(driver, database):
    try:
        while True:
            print(f"\n{Fore.CYAN}===== Checking for product updates at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====={Style.RESET_ALL}")
            
            # Refresh the page to get latest data
            driver.refresh()
            
            # Scrape the products
            scrape_products(driver, database)
            
            # Wait for the configured interval before checking again
            print(f"{Fore.CYAN}Waiting {CONFIG['check_interval']} seconds before next check...{Style.RESET_ALL}")
            time.sleep(CONFIG['check_interval'])
            
    except KeyboardInterrupt:
        print(f"{Fore.YELLOW}Monitoring stopped by user.{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Error during monitoring: {e}{Style.RESET_ALL}")

# Main function
def apply_filters(product_data):
    """Apply filters to decide if an alert should be triggered"""
    # Skip if only_new_tag is enabled and this product doesn't have the NEW tag
    if CONFIG["filters"]["only_new_tag"] and not product_data.get("has_new_tag", False):
        return False
    
    # Skip if price is above max_price (if set)
    if CONFIG["filters"]["max_price"]:
        try:
            # Extract numeric price (handles formats like "$20.99")
            price_str = product_data.get("price", "0")
            price_numeric = float(''.join(c for c in price_str if c.isdigit() or c == '.'))
            if price_numeric > CONFIG["filters"]["max_price"]:
                return False
        except:
            # If price parsing fails, don't filter
            pass
    
    # Skip if keywords are set and none match the title
    if CONFIG["filters"]["keywords"] and len(CONFIG["filters"]["keywords"]) > 0:
        title = product_data.get("title", "").lower()
        brand = product_data.get("brand", "").lower()
        combined_text = f"{title} {brand}".lower()
        
        if not any(keyword.lower() in combined_text for keyword in CONFIG["filters"]["keywords"]):
            return False
    
    # All filters passed
    return True

def main():
    print(f"{Fore.MAGENTA}===== PRODUCT ALERT BOT ====={Style.RESET_ALL}")
    print(f"{Fore.CYAN}Loading product database...{Style.RESET_ALL}")
    database = load_product_database()
    
    # Show current configuration
    print(f"{Fore.CYAN}Current settings:{Style.RESET_ALL}")
    print(f"  URL: {CONFIG['url']}")
    print(f"  Check interval: {CONFIG['check_interval']} seconds")
    print(f"  Running on: {SYSTEM}")
    print(f"  Alerts: Terminal={CONFIG['alert_methods']['terminal']}, " +
          f"Sound={CONFIG['alert_methods']['sound']}, " +
          f"Desktop Notifications={'Available' if NOTIFICATIONS_AVAILABLE and CONFIG['alert_methods']['desktop_notification'] else 'Disabled'}")
    
    if CONFIG["filters"]["only_new_tag"]:
        print(f"  Filter: Only showing items with NEW tag")
    if CONFIG["filters"]["max_price"]:
        print(f"  Filter: Maximum price ${CONFIG['filters']['max_price']}")
    if CONFIG["filters"]["keywords"]:
        print(f"  Filter: Matching keywords: {', '.join(CONFIG['filters']['keywords'])}")
    
    driver = setup_selenium()
    try:
        # Load the page
        print(f"{Fore.CYAN}Navigating to {CONFIG['url']}...{Style.RESET_ALL}")
        driver.get(CONFIG["url"])
        print(f"{Fore.GREEN}Page load attempted.{Style.RESET_ALL}")
        
        # Wait for manual intervention
        print(f"{Fore.YELLOW}Please accept any terms and agreements manually if needed.{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Press Enter when ready to begin monitoring...{Style.RESET_ALL}")
        input()
        
        # Start continuous monitoring
        monitor_products(driver, database)
        
    except Exception as e:
        print(f"{Fore.RED}An error occurred: {e}{Style.RESET_ALL}")
    finally:
        print(f"{Fore.YELLOW}Closing browser...{Style.RESET_ALL}")
        driver.quit()

if __name__ == "__main__":
    main()
