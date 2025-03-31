import os
import sys
import logging
import json
import time
from datetime import datetime, timezone
from typing import List, Dict, Optional
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from tqdm import tqdm
import pandas as pd
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Initialize rich console
console = Console()

# Database setup
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/job_changes')
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Scraping Configuration
MAX_RESULTS_PER_COMPANY = int(os.getenv('MAX_RESULTS_PER_COMPANY', '100'))
SCRAPING_DELAY = float(os.getenv('SCRAPING_DELAY', '2.0'))
COMPANIES_TO_TRACK = json.loads(os.getenv('COMPANIES_TO_TRACK', '[]'))

# Chrome WebDriver Configuration
CHROME_OPTIONS = {
    'headless': os.getenv('CHROME_HEADLESS', 'true').lower() == 'true',
    'disable_gpu': os.getenv('CHROME_DISABLE_GPU', 'true').lower() == 'true',
    'no_sandbox': os.getenv('CHROME_NO_SANDBOX', 'true').lower() == 'true',
    'disable_dev_shm_usage': os.getenv('CHROME_DISABLE_DEV_SHM', 'true').lower() == 'true'
}

class LinkedInScraper:
    def __init__(self):
        self.driver = None
        self.setup_driver()

    def setup_driver(self):
        """Initialize Chrome WebDriver with configured options"""
        chrome_options = Options()
        for option, value in CHROME_OPTIONS.items():
            if value:
                chrome_options.add_argument(f'--{option}')
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.implicitly_wait(10)

    def login(self):
        """Login to LinkedIn"""
        try:
            self.driver.get('https://www.linkedin.com/login')
            username = os.getenv('LINKEDIN_USERNAME')
            password = os.getenv('LINKEDIN_PASSWORD')
            
            if not username or not password:
                raise ValueError("LinkedIn credentials not found in environment variables")

            username_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            password_field = self.driver.find_element(By.ID, "password")
            
            username_field.send_keys(username)
            password_field.send_keys(password)
            
            self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
            time.sleep(5)  # Wait for login to complete
            
        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            raise

    def scrape_company(self, company_name: str, company_url: str) -> List[Dict]:
        """Scrape job changes for a specific company"""
        try:
            self.driver.get(company_url)
            time.sleep(SCRAPING_DELAY)
            
            # Navigate to "People" tab
            people_tab = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "a[data-control-name='page_member_main_nav_people_tab']"))
            )
            people_tab.click()
            time.sleep(SCRAPING_DELAY)
            
            # Get employee list
            employees = []
            scroll_count = 0
            max_scrolls = 5  # Limit scrolling to prevent infinite loops
            
            while scroll_count < max_scrolls:
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
                            "profile_url": profile_url
                        })
                    except NoSuchElementException:
                        continue
                
                scroll_count += 1
            
            return employees[:MAX_RESULTS_PER_COMPANY]
            
        except Exception as e:
            logger.error(f"Error scraping company {company_name}: {str(e)}")
            return []

    def close(self):
        """Close the WebDriver"""
        if self.driver:
            self.driver.quit()

def save_job_changes(changes: List[Dict]):
    """Save job changes to database"""
    db = SessionLocal()
    try:
        for change in changes:
            existing = db.query(JobChange).filter(
                JobChange.name == change["name"],
                JobChange.company == change["company"],
                JobChange.profile_url == change["profile_url"]
            ).first()
            
            if not existing:
                job_change = JobChange(
                    name=change["name"],
                    company=change["company"],
                    old_position=change["old_position"],
                    new_position=change["new_position"],
                    change_date=change["change_date"],
                    profile_url=change["profile_url"]
                )
                db.add(job_change)
        
        db.commit()
        logger.info(f"Saved {len(changes)} job changes to database")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving job changes: {str(e)}")
        raise
    finally:
        db.close()

def process_changes(employees: List[Dict]) -> List[Dict]:
    """Process employee data to identify changes"""
    changes = []
    db = SessionLocal()
    try:
        for employee in employees:
            existing = db.query(JobChange).filter(
                JobChange.name == employee["name"],
                JobChange.company == employee["company"],
                JobChange.profile_url == employee["profile_url"]
            ).first()
            
            if existing:
                if existing.new_position != employee["position"]:
                    changes.append({
                        "name": employee["name"],
                        "company": employee["company"],
                        "old_position": existing.new_position,
                        "new_position": employee["position"],
                        "change_date": datetime.now(timezone.utc),
                        "profile_url": employee["profile_url"]
                    })
            else:
                changes.append({
                    "name": employee["name"],
                    "company": employee["company"],
                    "old_position": None,
                    "new_position": employee["position"],
                    "change_date": datetime.now(timezone.utc),
                    "profile_url": employee["profile_url"]
                })
    finally:
        db.close()
    return changes

def main():
    """Main scraping function"""
    console.print("[bold blue]Starting LinkedIn Job Change Scraper[/bold blue]")
    
    if not COMPANIES_TO_TRACK:
        console.print("[red]No companies configured for tracking. Please update COMPANIES_TO_TRACK in .env file[/red]")
        return
    
    scraper = LinkedInScraper()
    try:
        # Login to LinkedIn
        console.print("[yellow]Logging in to LinkedIn...[/yellow]")
        scraper.login()
        
        # Create progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            # Create main task
            main_task = progress.add_task(
                "[cyan]Scraping companies...",
                total=len(COMPANIES_TO_TRACK)
            )
            
            total_changes = 0
            for company in COMPANIES_TO_TRACK:
                company_name = company['name']
                company_url = company['url']
                
                # Update progress description
                progress.update(main_task, description=f"[cyan]Scraping {company_name}...")
                
                # Scrape company
                employees = scraper.scrape_company(company_name, company_url)
                
                # Process changes
                changes = process_changes(employees)
                
                # Save changes
                if changes:
                    save_job_changes(changes)
                    total_changes += len(changes)
                
                # Update progress
                progress.update(main_task, advance=1)
        
        # Print summary
        console.print(f"\n[green]Scraping completed successfully![/green]")
        console.print(f"[blue]Total changes found: {total_changes}[/blue]")
        
    except Exception as e:
        console.print(f"[red]Error during scraping: {str(e)}[/red]")
        logger.error(f"Scraping error: {str(e)}")
    finally:
        scraper.close()

if __name__ == "__main__":
    main()
