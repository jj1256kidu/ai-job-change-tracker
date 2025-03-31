# LinkedIn Job Change Tracker

A Streamlit application that tracks job changes by scraping LinkedIn company pages. The application provides a user-friendly interface to monitor employee movements across different companies.

## Features

- LinkedIn company page scraping
- Real-time data visualization
- Interactive data tables
- Company and position analytics
- User-friendly interface

## Prerequisites

- Python 3.9+
- Chrome browser
- LinkedIn account
- PostgreSQL database (optional)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/linkedin-job-tracker.git
cd linkedin-job-tracker
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

4. Create a `.env` file in the root directory with the following variables:
```env
LINKEDIN_USERNAME=your_username
LINKEDIN_PASSWORD=your_password
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
MAX_RESULTS_PER_COMPANY=100
SCRAPING_DELAY=2.0
```

## Usage

1. Run the Streamlit application:
```bash
streamlit run app.py
```

2. Open your browser and navigate to `http://localhost:8501`

3. Add companies to track using the sidebar interface

4. Click "Start Scraping" to begin data collection

## Project Structure

```
linkedin-job-tracker/
├── app.py              # Main Streamlit application
├── scraper.py          # LinkedIn scraper module
├── requirements.txt    # Project dependencies
├── Procfile           # Deployment configuration
├── runtime.txt        # Python version specification
├── .env.example       # Example environment variables
├── .gitignore         # Git ignore rules
└── README.md          # Project documentation
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This tool is for educational purposes only. Please respect LinkedIn's terms of service and rate limits when using this application. 