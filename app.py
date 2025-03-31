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
import plotly.express as px
from scraper import LinkedInScraper

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

# Page configuration
st.set_page_config(
    page_title="LinkedIn Job Change Tracker",
    page_icon="👨‍💼",
    layout="wide"
)

# Custom CSS
st.markdown("""
    <style>
    .main {
        padding: 2rem;
    }
    .stButton>button {
        width: 100%;
        margin-top: 1rem;
    }
    .stTextInput>div>div>input {
        background-color: #f0f2f6;
    }
    </style>
    """, unsafe_allow_html=True)

def initialize_session_state():
    """Initialize session state variables"""
    if 'scraping_results' not in st.session_state:
        st.session_state.scraping_results = []
    if 'is_scraping' not in st.session_state:
        st.session_state.is_scraping = False

def scrape_companies(companies):
    """Run the scraper for given companies"""
    try:
        scraper = LinkedInScraper(
            headless=True,
            max_results=50,
            scraping_delay=2.0
        )
        results = scraper.scrape_multiple_companies(companies)
        return results
    except Exception as e:
        st.error(f"Error during scraping: {str(e)}")
        return []

def display_results(results):
    """Display scraping results in a table and charts"""
    if not results:
        st.warning("No results found.")
        return

    # Convert results to DataFrame
    df = pd.DataFrame(results)
    
    # Display summary metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Employees", len(df))
    with col2:
        st.metric("Unique Companies", df['company'].nunique())
    with col3:
        st.metric("Latest Update", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))

    # Display data table
    st.subheader("Employee Data")
    st.dataframe(df)

    # Visualizations
    st.subheader("Analytics")
    
    # Company distribution
    fig1 = px.pie(df, names='company', title='Employee Distribution by Company')
    st.plotly_chart(fig1, use_container_width=True)

    # Position distribution
    fig2 = px.bar(df['position'].value_counts().head(10), 
                  title='Top 10 Positions')
    st.plotly_chart(fig2, use_container_width=True)

def main():
    st.title("👨‍💼 LinkedIn Job Change Tracker")
    
    # Initialize session state
    initialize_session_state()
    
    # Sidebar for company input
    with st.sidebar:
        st.header("Add Companies")
        company_name = st.text_input("Company Name")
        company_url = st.text_input("LinkedIn Company URL")
        
        if st.button("Add Company"):
            if company_name and company_url:
                if 'companies' not in st.session_state:
                    st.session_state.companies = []
                st.session_state.companies.append({
                    "name": company_name,
                    "url": company_url
                })
                st.success(f"Added {company_name}")
                st.experimental_rerun()
            else:
                st.error("Please fill in both fields")

    # Display added companies
    if 'companies' in st.session_state and st.session_state.companies:
        st.subheader("Companies to Track")
        companies_df = pd.DataFrame(st.session_state.companies)
        st.dataframe(companies_df)
        
        if st.button("Start Scraping"):
            with st.spinner("Scraping in progress..."):
                st.session_state.is_scraping = True
                results = scrape_companies(st.session_state.companies)
                st.session_state.scraping_results = results
                st.session_state.is_scraping = False
                st.success("Scraping completed!")
                st.experimental_rerun()

    # Display results if available
    if st.session_state.scraping_results:
        display_results(st.session_state.scraping_results)

    # Footer
    st.markdown("---")
    st.markdown("""
        <div style='text-align: center'>
            <p>Built with ❤️ using Streamlit</p>
            <p>Last updated: {}</p>
        </div>
    """.format(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")), 
    unsafe_allow_html=True)

if __name__ == "__main__":
    main() 