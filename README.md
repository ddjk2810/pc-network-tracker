# Procore Construction Network Tracker

Automated daily scraper that collects contractor counts from the [Procore Construction Network](https://network.procore.com/).

## Data Collected

The scraper tracks the following counts daily:

| Category | Description |
|----------|-------------|
| Total | All contractors in the network |
| General Contractors | General contracting companies |
| Owners | Owner/Real Estate Developers |
| Specialty Contractors | Trade-specific contractors |
| Architects | Architecture firms |
| Engineers | Engineering firms |
| Consultants | Construction consultants |
| Suppliers | Material and equipment suppliers |

## Data Output

Data is saved to `data/procore_network_counts.csv` with the following columns:
- `timestamp` - UTC timestamp of data collection
- One column per company type with the count

## Setup

### Prerequisites
- Python 3.10+
- pip

### Local Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd procore

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Run the scraper
python scraper.py
```

### GitHub Actions (Automated)

The repository includes a GitHub Actions workflow that runs automatically:
- **Schedule**: Daily at 6:00 AM UTC
- **Manual trigger**: Use "Run workflow" button in GitHub Actions tab

The workflow automatically commits new data to the repository.

## Files

```
procore/
├── .github/
│   └── workflows/
│       └── daily-scrape.yml  # GitHub Actions workflow
├── data/
│   └── procore_network_counts.csv  # Collected data
├── scraper.py                # Main scraper script
├── requirements.txt          # Python dependencies
├── .gitignore
└── README.md
```

## Historical Data

The Procore Construction Network does not provide historical data through its public interface. This tracker creates historical records from the date you start running it.

For older historical data, you may check:
- [Wayback Machine](https://web.archive.org/web/*/https://network.procore.com/search) - May have archived snapshots with visible counts
- Procore press releases or annual reports - May mention network size at specific dates

## Notes

- Data collection uses browser automation (Playwright) to handle the site's dynamic JavaScript content
- The scraper respects the website by making requests at reasonable intervals
- Counts may fluctuate as contractors join/leave the network or update their profiles
