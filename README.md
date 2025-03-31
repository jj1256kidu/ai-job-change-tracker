# AI Job Change Tracker

A Streamlit application that tracks professionals who have recently changed jobs by scraping LinkedIn-related job change data from public Google search results.

## Features

- 🔍 Automated scraping of job changes from Google search results
- 📊 Interactive dashboard with real-time analytics
- 📈 Visualizations using Plotly
- 🔄 Daily automated updates via GitHub Actions
- 🗄️ PostgreSQL database for data storage
- 🎨 Modern UI with Streamlit

## Tech Stack

- **Frontend**: Streamlit, Plotly
- **Backend**: Python, FastAPI
- **Database**: PostgreSQL
- **Scraping**: Selenium, BeautifulSoup4
- **Deployment**: Streamlit Cloud

## Prerequisites

- Python 3.9+
- PostgreSQL
- Chrome/Chromium (for Selenium)
- Git

## Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/ai-job-change-tracker.git
   cd ai-job-change-tracker
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up the database:
   ```bash
   psql -U postgres -f init_db.sql
   ```

5. Create a `.env` file:
   ```bash
   cp .env.example .env
   ```
   Then edit `.env` with your database credentials.

6. Install Chrome WebDriver:
   ```bash
   python install_dependencies.py
   ```

## Running the Application

1. Start the Streamlit app:
   ```bash
   streamlit run app.py
   ```

2. Access the dashboard at http://localhost:8501

## Project Structure

```
ai-job-change-tracker/
├── .github/
│   └── workflows/
│       └── scrape.yml          # GitHub Actions workflow
├── .streamlit/
│   └── config.toml            # Streamlit configuration
├── backend/
│   └── main.py               # FastAPI backend
├── .env.example              # Example environment variables
├── .gitignore               # Git ignore rules
├── app.py                   # Main Streamlit application
├── init_db.sql             # Database initialization script
├── install_dependencies.py  # Dependency installation script
├── requirements.txt        # Python dependencies
├── run_scraper.py         # Scraper execution script
├── scraper.py             # Web scraping module
└── README.md              # Project documentation
```

## Features in Detail

### Dashboard
- Real-time job change tracking
- Interactive visualizations
- Company and keyword filtering
- Responsive design

### Scraping
- Automated data collection
- Multiple company tracking
- Duplicate detection
- Error handling

### Data Analysis
- Daily trends
- Company distribution
- Weekly/monthly statistics
- Custom filtering

## Deployment

### Local Deployment
1. Follow the setup instructions above
2. Run the application using `streamlit run app.py`

### Streamlit Cloud Deployment
1. Push your code to GitHub
2. Go to https://share.streamlit.io/
3. Connect your GitHub repository
4. Set the main file path to `app.py`
5. Add your environment variables
6. Deploy!

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- LinkedIn for providing public profile data
- Google Search for enabling data discovery
- The open-source community for the tools and libraries used in this project
