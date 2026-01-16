# Procore Network Tracker - Session Notes

## Project Overview

This project scrapes data from the Procore Construction Network (network.procore.com) to track contractor counts and search for ENR Top 400 contractors.

**Repository:** https://github.com/hlsansome-web/procore-network-tracker

## Files Structure

```
procore/
├── scraper.py                 # Company types & market sectors scraper
├── scraper_states.py          # US states scraper
├── scraper_enr.py             # ENR Top 400 contractor search
├── requirements.txt           # Python dependencies (playwright, pdfplumber)
├── ENR-2023-Top-400-National-Contractors.pdf  # Source PDF for ENR list
├── .github/
│   └── workflows/
│       └── daily-scrape.yml   # GitHub Actions workflow (runs daily at 6 AM UTC)
├── data/
│   ├── procore_network_counts.csv    # Company type & market sector counts
│   ├── procore_network_states.csv    # State-by-state counts
│   ├── enr_contractor_matches.csv    # Detailed ENR search results
│   └── enr_summary.csv               # ENR match summary (1/0 per date)
├── preview_search_terms.py    # Utility: preview search terms without scraping
└── test_search.py             # Utility: test matching logic on sample searches
```

## Scrapers

### 1. scraper.py - Company Types & Market Sectors
- Scrapes total contractor count
- Breaks down by company type: General Contractors, Owners, Specialty Contractors, Architects, Engineers, Consultants, Suppliers
- Breaks down by market sector: Commercial, Healthcare, Industrial and Energy, Infrastructure, Institutional, Residential
- Uses Playwright to click on filters (URL parameters don't work on this site)

### 2. scraper_states.py - US States
- Scrapes contractor counts for all 50 US states + DC
- Source: https://network.procore.com/us

### 3. scraper_enr.py - ENR Top 400 Contractors
- Extracts contractor names from ENR-2023-Top-400-National-Contractors.pdf
- Searches each contractor on Procore network
- Determines if there's a match based on matching logic (see below)
- Outputs detailed results and summary sheet

## ENR Scraper Details

### Search Term Cleaning Rules

1. **Remove "THE" prefix** - "THE TURNER CORP." → "TURNER"
2. **Keep "CONSTRUCTION"** - Unlike other suffixes, CONSTRUCTION is kept in the search term
3. **Keep "GROUP" for single words** - If removing GROUP leaves only one word, keep it
   - "WALSH GROUP" stays as "WALSH GROUP" (WALSH alone is one word)
   - "STO BUILDING GROUP" → "STO BUILDING" (two words remain)
4. **Remove common suffixes**: INC, CORP, LLC, LP, CO, COS, HOLDINGS, ENTERPRISES, COMPANIES, SERVICES, CONSTRUCTORS, BUILDERS, CONTRACTORS, & SONS, & ASSOCIATES, OF COS, & CO

### Manual Search Term Overrides (36 total)

```python
SEARCH_TERM_OVERRIDES = {
    19: "MCCARTHY HOLDINGS",
    28: "RYAN COMPANIES",
    40: "YATES CONSTRUCTION",
    54: "FCL BUILDERS",
    58: "HARVEY CLEARY",
    60: "KOKOSING",
    66: "J.T. MAGEN",
    72: "WEITZ COMPANY",
    92: "S&B ENGINEERS",
    94: "PJ DICK",
    121: "CATAMOUNT CONSTRUCTORS",
    123: "JINGOLI",
    178: "UNITED ENGINEERS",
    183: "FCI CONSTRUCTORS",
    213: "IOVINO ENTERPRISES",
    218: "MW BUILDERS",
    225: "CHINA CONSTRUCTION AMERICA",
    246: "NAN INC",
    257: "CROWDER CONSTRUCTORS",
    274: "CURRENT BUILDERS",
    279: "CAHILL CONTRACTORS",
    288: "RODGERS BUILDERS",
    290: "FRANA COMPANIES",
    295: "C. OVERAA & CO",
    324: "GARDNER BUILDERS",
    330: "LEOPARDO COMPANIES",
    340: "PRIMUS BUILDERS",
    356: "PENCE CONTRACTORS",
    367: "MORLEY BUILDERS",
    374: "CLARK CONTRACTORS",
    376: "BH INC",
    380: "S. M. WILSON",
    383: "BUTZ ENTERPRISES",
    388: "DESCOR BUILDERS",
    395: "WAGMAN CONSTRUCTION",
    398: "KIELY FAMILY",
}
```

### Matching Logic

A search result is considered a **match** if:

1. **Exact match** (case-insensitive, ignoring "The" prefix)
   - Search: "BECHTEL" → Result: "Bechtel" ✓

2. **Search term + allowed suffixes only**
   - Search: "BECHTEL" → Result: "Bechtel Corporation" ✓
   - Search: "GRANITE CONSTRUCTION" → Result: "Granite Construction Company" ✓

**NOT a match** if:
- Has a prefix: "TURNER" should NOT match "Whiting Turner"
- Has additional meaningful words: "TURNER" should NOT match "Turner Security"

**Allowed suffixes:**
- Inc, Corp, Corporation, LLC, LP, LLP
- Co, Company, Companies
- Construction, Constructors, Contractors, Contracting
- Builders, Builder, Building
- Group, Holdings, Holding
- Enterprises, Enterprise, Services, Service
- Industries, Industrial
- PC, NA, USA, US
- of, the, &, and

### Output Files

#### enr_contractor_matches.csv (Detailed Results)
```csv
timestamp,rank,original_name,search_term,exact_match,match_count,top_matches
2026-01-15 23:56:27 UTC,1,THE TURNER CORP.,TURNER,False,1293,Turner Security; Electronic Security; Whiting Turner
2026-01-15 23:56:27 UTC,2,BECHTEL,BECHTEL,True,47,Bechtel; Design and Engineering; Project Management
```

#### enr_summary.csv (Summary Sheet)
```csv
rank,contractor,2026-01-15,2026-01-16,...
1,TURNER,0,0,...
2,BECHTEL,1,1,...
3,MASTEC,1,1,...
```
- Each row is a contractor (by rank)
- Each column after contractor is a date
- Values: 1 = match found, 0 = no match

## GitHub Actions

The workflow runs daily at 6 AM UTC and:
1. Runs `scraper.py` (company types & market sectors)
2. Runs `scraper_states.py` (US states)
3. Runs `scraper_enr.py` (ENR Top 400)
4. Commits and pushes updated data files

Manual trigger available via workflow_dispatch.

## Dependencies

```
playwright>=1.40.0
pdfplumber>=0.10.0
```

GitHub Actions installs Chromium for Playwright:
```bash
playwright install chromium
playwright install-deps chromium
```

## Key Decisions Made

1. **URL parameters don't work** - The Procore site uses client-side JavaScript filtering, so we use Playwright to click on filter elements instead
2. **Keep CONSTRUCTION in search terms** - More specific searches yield better matches
3. **Strict matching logic** - Only match if result starts with search term and has no disqualifying words
4. **Manual overrides** - 36 contractors have custom search terms for better accuracy
5. **Summary sheet format** - Rows are contractors, columns are dates, values are 1/0 for easy historical tracking

## Session Date
2026-01-15
