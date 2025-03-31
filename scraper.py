import os
import logging
import time
from typing import List, Dict, Optional
from datetime import datetime, timezone
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class LinkedInScraper:
    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        headless: bool = True,
        max_results: int = 100,
        scraping_delay: float = 2.0,
        max_scrolls: int = 5
    ):
        """
        Initialize LinkedIn Scraper
        
        Args:
            username: LinkedIn username
            password: LinkedIn password
            headless: Whether to run Chrome in headless mode
            max_results: Maximum number of results to scrape per company
            scraping_delay: Delay between actions in seconds
            max_scrolls: Maximum number of scrolls to perform
        """
        self.username = username or os.getenv('LINKEDIN_USERNAME')
        self.password = password or os.getenv('LINKEDIN_PASSWORD')
        self.headless = headless
        self.max_results = max_results
        self.scraping_delay = scraping_delay
        self.max_scrolls = max_scrolls
        self.driver = None
        self.console = Console()
        
        if not self.username or not self.password:
            raise ValueError("LinkedIn credentials not found. Please provide them or set environment variables.")

    def setup_driver(self):
        """Initialize Chrome WebDriver with configured options"""
        try:
            chrome_options = Options()
            if self.headless:
                chrome_options.add_argument('--headless')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            
            # Use webdriver_manager to handle driver installation
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.implicitly_wait(10)
            logger.info("Chrome WebDriver initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Chrome WebDriver: {str(e)}")
            raise

    def login(self):
        """Login to LinkedIn"""
        try:
            self.console.print("[yellow]Logging in to LinkedIn...[/yellow]")
            self.driver.get('https://www.linkedin.com/login')
            
            # Wait for and fill in username
            username_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            username_field.send_keys(self.username)
            
            # Fill in password
            password_field = self.driver.find_element(By.ID, "password")
            password_field.send_keys(self.password)
            
            # Click login button
            self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
            time.sleep(5)  # Wait for login to complete
            
            # Verify login success
            if "feed" not in self.driver.current_url:
                raise Exception("Login failed - redirected to unexpected page")
            
            logger.info("Successfully logged in to LinkedIn")
            self.console.print("[green]Login successful![/green]")
            
        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            raise

    def scrape_company(self, company_name: str, company_url: str) -> List[Dict]:
        """
        Scrape job changes for a specific company
        
        Args:
            company_name: Name of the company to scrape
            company_url: LinkedIn company URL
            
        Returns:
            List of dictionaries containing employee information
        """
        try:
            self.console.print(f"[cyan]Scraping {company_name}...[/cyan]")
            self.driver.get(company_url)
            time.sleep(self.scraping_delay)
            
            # Navigate to "People" tab
            people_tab = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "a[data-control-name='page_member_main_nav_people_tab']"))
            )
            people_tab.click()
            time.sleep(self.scraping_delay)
            
            # Get employee list
            employees = []
            scroll_count = 0
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=self.console
            ) as progress:
                task = progress.add_task(f"Scraping {company_name} employees...", total=self.max_scrolls)
                
                while scroll_count < self.max_scrolls:
                    # Scroll to load more
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(2)
                    
                    # Get current page employees
                    employee_cards = self.driver.find_elements(By.CSS_SELECTOR, ".reusable-search__result-container")
                    
                    for card in employee_cards:
                        try:
                            name = card.find_element(By.CSS_SELECTOR, ".entity-result__title-text").text
                            position = card.find_element(By.CSS_SELECTOR, ".entity-result__primary-subtitle").text
                            profile_url = card.find_element(By.CSS_SELECTOR, "a.app-aware-link").get_attribute("href")
                            
                            employees.append({
                                "name": name,
                                "company": company_name,
                                "position": position,
                                "profile_url": profile_url,
                                "scraped_at": datetime.now(timezone.utc)
                            })
                        except NoSuchElementException:
                            continue
                    
                    scroll_count += 1
                    progress.update(task, advance=1)
                    
                    # Break if we have enough results
                    if len(employees) >= self.max_results:
                        break
            
            logger.info(f"Found {len(employees)} employees for {company_name}")
            return employees[:self.max_results]
            
        except Exception as e:
            logger.error(f"Error scraping company {company_name}: {str(e)}")
            return []

    def scrape_multiple_companies(self, companies: List[Dict]) -> List[Dict]:
        """
        Scrape multiple companies
        
        Args:
            companies: List of dictionaries containing company information
                     Each dict should have 'name' and 'url' keys
            
        Returns:
            List of dictionaries containing all employee information
        """
        all_employees = []
        
        try:
            self.setup_driver()
            self.login()
            
            for company in companies:
                employees = self.scrape_company(company['name'], company['url'])
                all_employees.extend(employees)
                
                # Add delay between companies to avoid rate limiting
                time.sleep(self.scraping_delay * 2)
            
            return all_employees
            
        except Exception as e:
            logger.error(f"Error during multi-company scraping: {str(e)}")
            return all_employees
        finally:
            self.close()

    def close(self):
        """Close the WebDriver"""
        if self.driver:
            self.driver.quit()
            logger.info("Chrome WebDriver closed")

def main():
    """Example usage of the scraper"""
    # Example companies to scrape
    companies = [
        {
            "name": "TCS",
            "url": "https://www.linkedin.com/company/tata-consultancy-services"
        },
        {
            "name": "Infosys",
            "url": "https://www.linkedin.com/company/infosys"
        }
    ]
    
    try:
        scraper = LinkedInScraper(
            headless=True,
            max_results=50,
            scraping_delay=2.0
        )
        
        results = scraper.scrape_multiple_companies(companies)
        print(f"\nFound {len(results)} total employees")
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main() 