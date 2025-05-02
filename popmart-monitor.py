import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException

# Set up Selenium with a visible browser
def setup_selenium():
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.set_page_load_timeout(300)  # 5 minutes for initial page load
    print("Browser opened successfully!")
    return driver

# Scrape product data after manual intervention
def scrape_products(driver):
    try:
        print("Waiting for product elements to load...")
        # Wait up to 180 seconds for product elements to appear
        WebDriverWait(driver, 180).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div[class*='index_imgContainer']"))
        )
        print("Product elements found!")
        products = driver.find_elements(By.CSS_SELECTOR, "div[class*='index_imgContainer']")
        for product in products[:5]:  # Limit to 5 for testing
            try:
                title = product.find_element(By.CSS_SELECTOR, "h2[class*='index_itemUsTitle']").text or "Unknown"
                price = product.find_element(By.CSS_SELECTOR, "div[class*='index_itemPrice_AQoMy']").text or "Unknown"
                print(f"Found: {title} - {price}")
            except Exception as e:
                print(f"Error scraping product: {e}")
    except TimeoutException:
        print("Timeout: Product elements didn’t load within 180 seconds. Check selectors or page behavior.")
    except Exception as e:
        print(f"Error scraping products: {e}")

# Main function
def main():
    driver = setup_selenium()
    try:
        # Load the page
        print("Navigating to the site...")
        driver.get("https://www.example.com")  # Replace with your actual URL
        print("Page load attempted.")

        # Wait for your manual intervention
        print("Please accept the terms and agreements manually. Press Enter when done...")
        input()  # Pauses script until you press Enter

        # Scrape the products
        scrape_products(driver)

        print("Press Enter to close the browser.")
        input()
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
