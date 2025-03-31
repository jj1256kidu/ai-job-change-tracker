import os
import sys
import subprocess
import platform
import json
from pathlib import Path
import logging
from typing import List, Dict
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('install.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Project dependencies
PYTHON_DEPENDENCIES = [
    'fastapi==0.104.1',
    'uvicorn==0.24.0',
    'sqlalchemy==2.0.23',
    'psycopg2-binary==2.9.9',
    'python-dotenv==1.0.0',
    'selenium==4.15.2',
    'pandas==2.1.3',
    'streamlit==1.29.0',
    'plotly==5.18.0',
    'requests==2.31.0',
    'beautifulsoup4==4.12.2',
    'webdriver-manager==4.0.1',
    'pytest==7.4.3',
    'black==23.11.0',
    'flake8==6.1.0',
    'mypy==1.7.1',
    'python-jose==3.3.0',
    'passlib==1.7.4',
    'python-multipart==0.0.6',
    'email-validator==2.1.0.post1',
    'aiofiles==23.2.1',
    'jinja2==3.1.2',
    'markdown==3.5.1',
    'pyyaml==6.0.1',
    'python-dateutil==2.8.2',
    'pytz==2023.3.post1',
    'tenacity==8.2.3',
    'tqdm==4.66.1',
    'rich==13.7.0',
    'click==8.1.7',
    'itsdangerous==2.1.2',
    'Werkzeug==3.0.1',
    'watchdog==3.0.0',
    'protobuf==4.25.1',
    'typing-extensions==4.8.0',
    'zipp==3.17.0',
    'importlib-metadata==6.1.0',
    'packaging==23.2',
    'certifi==2023.11.17',
    'charset-normalizer==3.3.2',
    'idna==3.6',
    'urllib3==2.1.0',
    'colorama==0.4.6',
    'h11==0.14.0',
    'starlette==0.27.0',
    'anyio==4.2.0',
    'sniffio==1.3.0',
    'httpcore==1.0.2',
    'httpx==0.25.2',
    'rfc3986==2.0.0',
    'multidict==6.0.4',
    'async-timeout==4.0.3',
    'frozenlist==1.4.0',
    'aiosignal==1.3.1',
    'attrs==23.2.0',
    'yarl==1.9.4',
    'markupsafe==2.1.3',
    'Jinja2==3.1.2',
    'altair==5.2.0',
    'toolz==0.12.1',
    'six==1.16.0',
    'numpy==1.26.2',
    'pytz==2023.3.post1',
    'tzdata==2023.3',
    'pandas-stubs==2.1.4.231228',
    'types-python-dateutil==2.8.19.14',
    'types-requests==2.31.0.20240106',
    'types-urllib3==1.26.25.14',
    'types-setuptools==68.2.0.0',
    'types-jsonschema==4.20.0.0',
    'types-psutil==5.9.5.20240106',
    'types-pytz==2023.3.0.20240106',
    'types-PyYAML==6.0.12.12',
    'types-redis==4.6.0.20240106',
    'types-urllib3==1.26.25.14',
    'types-requests==2.31.0.20240106',
    'types-setuptools==68.2.0.0',
    'types-jsonschema==4.20.0.0',
    'types-psutil==5.9.5.20240106',
    'types-pytz==2023.3.0.20240106',
    'types-PyYAML==6.0.12.12',
    'types-redis==4.6.0.20240106',
]

# Chrome WebDriver versions
CHROME_DRIVER_VERSIONS = {
    'Windows': '114.0.5735.90',
    'Darwin': '114.0.5735.90',
    'Linux': '114.0.5735.90'
}

def check_python_version() -> bool:
    """Check if Python version meets requirements"""
    required_version = (3, 8)
    current_version = sys.version_info[:2]
    if current_version < required_version:
        logger.error(f"Python {'.'.join(map(str, required_version))} or higher is required")
        return False
    return True

def create_virtual_environment() -> bool:
    """Create and activate virtual environment"""
    try:
        venv_path = Path('venv')
        if not venv_path.exists():
            logger.info("Creating virtual environment...")
            subprocess.run([sys.executable, '-m', 'venv', 'venv'], check=True)
            logger.info("Virtual environment created successfully")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to create virtual environment: {e}")
        return False

def get_pip_command() -> List[str]:
    """Get the appropriate pip command based on the OS"""
    if platform.system() == 'Windows':
        return ['venv\\Scripts\\pip']
    return ['venv/bin/pip']

def install_python_dependencies() -> bool:
    """Install Python dependencies"""
    try:
        pip_cmd = get_pip_command()
        logger.info("Installing Python dependencies...")
        
        # Upgrade pip first
        subprocess.run([*pip_cmd, 'install', '--upgrade', 'pip'], check=True)
        
        # Install dependencies
        for dep in PYTHON_DEPENDENCIES:
            logger.info(f"Installing {dep}...")
            subprocess.run([*pip_cmd, 'install', dep], check=True)
        
        logger.info("Python dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install Python dependencies: {e}")
        return False

def setup_database() -> bool:
    """Set up PostgreSQL database"""
    try:
        # Check if PostgreSQL is installed
        if platform.system() == 'Windows':
            subprocess.run(['psql', '--version'], check=True, capture_output=True)
        else:
            subprocess.run(['which', 'psql'], check=True, capture_output=True)
        
        # Create database and tables
        logger.info("Setting up database...")
        subprocess.run(['psql', '-U', 'postgres', '-f', 'init_db.sql'], check=True)
        logger.info("Database setup completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to setup database: {e}")
        return False
    except FileNotFoundError:
        logger.error("PostgreSQL is not installed or not in PATH")
        return False

def setup_chrome_driver() -> bool:
    """Set up Chrome WebDriver"""
    try:
        system = platform.system()
        version = CHROME_DRIVER_VERSIONS.get(system)
        if not version:
            logger.error(f"Unsupported operating system: {system}")
            return False
        
        logger.info("Setting up Chrome WebDriver...")
        subprocess.run([
            'webdriver-manager',
            'update',
            '--driver', 'chrome',
            '--version', version
        ], check=True)
        logger.info("Chrome WebDriver setup completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to setup Chrome WebDriver: {e}")
        return False

def create_env_file() -> bool:
    """Create .env file with default values"""
    try:
        env_path = Path('.env')
        if not env_path.exists():
            logger.info("Creating .env file...")
            env_content = """# Database Configuration
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/job_changes

# Scraping Configuration
MAX_RESULTS_PER_COMPANY=100
SCRAPING_DELAY=2.0
COMPANIES_TO_TRACK=[{"name": "TCS", "url": "https://www.linkedin.com/company/tata-consultancy-services"}]

# Chrome WebDriver Configuration
CHROME_HEADLESS=true
CHROME_DISABLE_GPU=true
CHROME_NO_SANDBOX=true
CHROME_DISABLE_DEV_SHM=true

# Application Configuration
DEBUG=false
LOG_LEVEL=INFO
TIMEZONE=UTC

# API Configuration
API_BASE_URL=http://localhost:8000
API_KEY=your_api_key_here

# Security Configuration
SECRET_KEY=your_secret_key_here
AUTH_ENABLED=false

# Email Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
NOTIFICATION_EMAIL=your_email@gmail.com

# GitHub Configuration
GITHUB_TOKEN=your_github_token
GITHUB_REPO=your_username/your_repo
"""
            env_path.write_text(env_content)
            logger.info("Created .env file with default values")
        return True
    except Exception as e:
        logger.error(f"Failed to create .env file: {e}")
        return False

def create_project_structure() -> bool:
    """Create project directory structure"""
    try:
        directories = [
            'backend',
            'frontend',
            'tests',
            'data',
            'logs',
            '.streamlit',
            '.github/workflows'
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
            logger.info(f"Created directory: {directory}")
        
        return True
    except Exception as e:
        logger.error(f"Failed to create project structure: {e}")
        return False

def main():
    """Main installation function"""
    logger.info("Starting installation process...")
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Create virtual environment
    if not create_virtual_environment():
        sys.exit(1)
    
    # Install Python dependencies
    if not install_python_dependencies():
        sys.exit(1)
    
    # Setup database
    if not setup_database():
        sys.exit(1)
    
    # Setup Chrome WebDriver
    if not setup_chrome_driver():
        sys.exit(1)
    
    # Create project structure
    if not create_project_structure():
        sys.exit(1)
    
    # Create .env file
    if not create_env_file():
        sys.exit(1)
    
    logger.info("Installation completed successfully!")
    logger.info("\nNext steps:")
    logger.info("1. Edit the .env file with your configuration")
    logger.info("2. Activate the virtual environment:")
    logger.info("   - Windows: .\\venv\\Scripts\\activate")
    logger.info("   - Unix/MacOS: source venv/bin/activate")
    logger.info("3. Run the application:")
    logger.info("   - Backend: uvicorn backend.main:app --reload")
    logger.info("   - Frontend: streamlit run app.py")

if __name__ == "__main__":
    main() 