import os
import sys
import logging
import pandas as pd
from datetime import datetime, timezone
from typing import List, Dict, Optional
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import streamlit as st
from dotenv import load_dotenv
import json
import re
from pathlib import Path

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Database setup
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/job_changes')
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Database Models
class JobChange(Base):
    __tablename__ = "job_changes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    company = Column(String)
    old_position = Column(String)
    new_position = Column(String)
    change_date = Column(DateTime)
    profile_url = Column(String)
    is_new = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)
    linkedin_url = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

# Create tables
Base.metadata.create_all(bind=engine)

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

# Database Operations
def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

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

# Streamlit Interface
def main():
    st.set_page_config(
        page_title="AI Job Change Tracker",
        page_icon="👨‍💼",
        layout="wide"
    )
    
    st.title("AI Job Change Tracker")
    
    # Sidebar
    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Go to",
        ["Dashboard", "Scrape Data", "Settings"]
    )
    
    if page == "Dashboard":
        show_dashboard()
    elif page == "Scrape Data":
        show_scrape_page()
    else:
        show_settings()

def show_dashboard():
    """Display the main dashboard"""
    st.header("Job Changes Dashboard")
    
    # Date range filter
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", datetime.now().date())
    with col2:
        end_date = st.date_input("End Date", datetime.now().date())
    
    # Company filter
    companies = get_companies()
    selected_companies = st.multiselect(
        "Select Companies",
        companies,
        default=companies
    )
    
    # Load and display data
    if st.button("Refresh Data"):
        with st.spinner("Loading data..."):
            df = load_job_changes(start_date, end_date, selected_companies)
            
            # Display metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Changes", len(df))
            with col2:
                st.metric("Unique People", df['name'].nunique())
            with col3:
                st.metric("Companies", df['company'].nunique())
            
            # Display data table
            st.dataframe(df)
            
            # Display charts
            st.subheader("Changes by Company")
            company_changes = df['company'].value_counts()
            st.bar_chart(company_changes)
            
            st.subheader("Changes Over Time")
            daily_changes = df.groupby('change_date').size()
            st.line_chart(daily_changes)

def show_scrape_page():
    """Display the scraping interface"""
    st.header("Scrape Job Changes")
    
    if st.button("Start Scraping"):
        with st.spinner("Scraping in progress..."):
            try:
                scraper = LinkedInScraper()
                scraper.login()
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for i, company in enumerate(COMPANIES_TO_TRACK):
                    status_text.text(f"Scraping {company['name']}...")
                    employees = scraper.scrape_company(company['name'], company['url'])
                    
                    # Process and save changes
                    changes = process_changes(employees)
                    save_job_changes(changes)
                    
                    progress_bar.progress((i + 1) / len(COMPANIES_TO_TRACK))
                
                scraper.close()
                st.success("Scraping completed successfully!")
                
            except Exception as e:
                st.error(f"Error during scraping: {str(e)}")
                logger.error(f"Scraping error: {str(e)}")

def show_settings():
    """Display settings interface"""
    st.header("Settings")
    
    # Company management
    st.subheader("Manage Companies")
    companies = get_companies()
    
    for company in companies:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.text(company)
        with col2:
            if st.button("Remove", key=f"remove_{company}"):
                remove_company(company)
    
    # Add new company
    new_company = st.text_input("Add New Company")
    new_url = st.text_input("Company LinkedIn URL")
    if st.button("Add Company"):
        if new_company and new_url:
            add_company(new_company, new_url)
            st.success(f"Added {new_company}")
        else:
            st.error("Please enter both company name and URL")

def get_companies() -> List[str]:
    """Get list of companies from database"""
    db = SessionLocal()
    try:
        companies = db.query(Company.name).filter(Company.is_active == True).all()
        return [company[0] for company in companies]
    finally:
        db.close()

def add_company(name: str, url: str):
    """Add new company to database"""
    db = SessionLocal()
    try:
        company = Company(name=name, linkedin_url=url)
        db.add(company)
        db.commit()
    finally:
        db.close()

def remove_company(name: str):
    """Remove company from database"""
    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.name == name).first()
        if company:
            company.is_active = False
            db.commit()
    finally:
        db.close()

def load_job_changes(start_date, end_date, companies) -> pd.DataFrame:
    """Load job changes from database"""
    db = SessionLocal()
    try:
        query = db.query(JobChange).filter(
            JobChange.company.in_(companies),
            JobChange.change_date.between(start_date, end_date)
        )
        return pd.read_sql(query.statement, db.bind)
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

if __name__ == "__main__":
    main()
