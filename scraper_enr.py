"""
ENR Top 400 Contractors - Procore Network Search Scraper

Searches for each ENR Top 400 contractor on the Procore Construction Network
and logs the number of matches found.
"""

import asyncio
import csv
import re
from datetime import datetime, timezone
from pathlib import Path

import pdfplumber
from playwright.async_api import async_playwright

# File paths
PDF_FILE = Path(__file__).parent / "ENR-2023-Top-400-National-Contractors.pdf"
DATA_FILE = Path(__file__).parent / "data" / "enr_contractor_matches.csv"
SUMMARY_FILE = Path(__file__).parent / "data" / "enr_summary.csv"
BASE_URL = "https://network.procore.com/search"
TIMEOUT_MS = 60000


def extract_contractors_from_pdf(pdf_path: Path) -> list[dict]:
    """Extract contractor names and ranks from the ENR PDF."""
    contractors = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            # Split into lines
            lines = text.split('\n')

            for line in lines:
                # Pattern: rank numbers followed by company name, location
                # Examples:
                # "1 1 THE TURNER CORP., New York, N.Y.† 16,256.3 ..."
                # "3 ** MASTEC INC., Coral Gables, Fla.† 11,605.0 ..."
                match = re.match(
                    r'^(\d+)\s+(?:\d+|\*\*)\s+([A-Z][A-Z0-9\s&\.\-\'/\|]+(?:,\s*[A-Za-z\s\.]+)?)',
                    line
                )
                if match:
                    rank = int(match.group(1))
                    firm_text = match.group(2).strip()

                    # Extract company name (before the location)
                    # Location pattern: ", City, State" or ", City, State†"
                    # Split on the pattern: comma + space + capitalized word + comma
                    location_match = re.search(r',\s+[A-Z][a-z]+[\w\s]*,\s+[A-Z][a-z]+\.?†?$', firm_text)
                    if location_match:
                        company_name = firm_text[:location_match.start()].strip()
                    else:
                        # Try simpler pattern - just take up to last comma pair
                        parts = firm_text.rsplit(',', 2)
                        if len(parts) >= 2:
                            company_name = parts[0].strip()
                        else:
                            company_name = firm_text

                    # Clean up the company name
                    company_name = company_name.rstrip(',').rstrip('†').strip()

                    if rank <= 400 and company_name and len(company_name) > 2:
                        contractors.append({
                            "rank": rank,
                            "original_name": company_name
                        })

    # Remove duplicates and sort by rank
    seen_ranks = set()
    unique_contractors = []
    for c in contractors:
        if c["rank"] not in seen_ranks:
            seen_ranks.add(c["rank"])
            unique_contractors.append(c)

    unique_contractors.sort(key=lambda x: x["rank"])
    return unique_contractors


# Manual overrides for specific ranks (rank -> search term)
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


def clean_company_name(name: str, rank: int = None) -> str:
    """Clean company name by removing common suffixes."""
    # Check for manual override first
    if rank and rank in SEARCH_TERM_OVERRIDES:
        return SEARCH_TERM_OVERRIDES[rank]

    cleaned = name.strip()

    # Remove "THE" from the beginning
    cleaned = re.sub(r'^THE\s+', '', cleaned, flags=re.IGNORECASE)

    # Remove common suffixes (but keep CONSTRUCTION)
    suffixes = [
        r'\s+INC\.?$', r'\s+CORP\.?$', r'\s+LLC\.?$', r'\s+LP\.?$',
        r'\s+CO\.?$', r'\s+COS\.?$', r'\s+HOLDINGS?$',
        r'\s+ENTERPRISES?$', r'\s+COMPANIES$', r'\s+SERVICES?$',
        r'\s+CONSTRUCTORS?$', r'\s+BUILDERS?$',
        r'\s+CONTRACTORS?$', r'\s+& SONS?$', r'\s+& ASSOCIATES?$',
        r'\s+OF COS\.?$', r'\s+& CO\.?$'
    ]

    for suffix in suffixes:
        cleaned = re.sub(suffix, '', cleaned, flags=re.IGNORECASE)

    # Handle GROUP: only remove if result would have 2+ words
    group_match = re.search(r'\s+GROUP$', cleaned, flags=re.IGNORECASE)
    if group_match:
        without_group = cleaned[:group_match.start()].strip()
        # Count words (split by whitespace)
        if len(without_group.split()) >= 2:
            cleaned = without_group
        # else keep GROUP

    # Remove trailing punctuation
    cleaned = cleaned.rstrip('.,;:').strip()

    return cleaned


# Allowed suffixes that don't disqualify a match
ALLOWED_SUFFIXES = [
    'inc', 'inc.', 'incorporated',
    'corp', 'corp.', 'corporation',
    'llc', 'llc.', 'l.l.c.',
    'lp', 'lp.', 'l.p.',
    'llp', 'llp.', 'l.l.p.',
    'co', 'co.', 'company', 'companies',
    'construction', 'constructors',
    'contractors', 'contractor', 'contracting',
    'builders', 'builder', 'building',
    'group', 'holdings', 'holding',
    'enterprises', 'enterprise',
    'services', 'service',
    'industries', 'industrial',
    'pc', 'p.c.',
    'na', 'n.a.',
    'usa', 'us',
    'of', 'the', '&', 'and',
]


def normalize_name(name: str) -> str:
    """Normalize a company name for comparison."""
    normalized = name.lower().strip()
    # Remove "the " prefix
    normalized = re.sub(r'^the\s+', '', normalized)
    # Remove trailing punctuation
    normalized = normalized.rstrip('.,;:')
    return normalized


def is_match(search_term: str, result_name: str) -> bool:
    """
    Check if a search result matches the search term.

    Match criteria:
    1. Exact match (case-insensitive, ignoring "The" prefix)
    2. Result starts with search term and only has allowed suffixes after
    """
    search_norm = normalize_name(search_term)
    result_norm = normalize_name(result_name)

    # Exact match
    if search_norm == result_norm:
        return True

    # Check if result starts with search term
    if not result_norm.startswith(search_norm):
        return False

    # Get the remainder after the search term
    remainder = result_norm[len(search_norm):].strip()

    # If nothing remains, it's a match
    if not remainder:
        return True

    # Check if remainder contains only allowed suffixes
    # Split remainder into words
    remainder_words = remainder.replace(',', ' ').replace('.', ' ').split()

    for word in remainder_words:
        word_clean = word.strip('.,;:').lower()
        if word_clean and word_clean not in ALLOWED_SUFFIXES:
            return False

    return True


async def search_contractor(page, company_name: str, cleaned_name: str) -> dict:
    """Search for a contractor on Procore network and return match info."""
    result = {
        "search_term": cleaned_name,
        "exact_match": False,
        "match_count": 0,
        "top_matches": []
    }

    try:
        # Navigate to search with the company name as query
        search_url = f"{BASE_URL}?q={cleaned_name.replace(' ', '+')}"
        await page.goto(search_url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
        await asyncio.sleep(3)

        # Get page content
        content = await page.content()

        # Extract the count from JSON
        count_match = re.search(r'"count"\s*:\s*(\d+)', content)
        if count_match:
            result["match_count"] = int(count_match.group(1))

        # Extract company names from JSON - they appear as "name": "Company Name"
        all_names = re.findall(r'"name"\s*:\s*"([^"]+)"', content)

        # Filter out generic/non-company names and deduplicate
        skip_names = {'main office', 'headquarters', 'true', 'false', 'null', ''}
        company_names = []
        seen = set()
        for n in all_names:
            n_lower = n.lower()
            if (len(n) > 2 and
                n_lower not in skip_names and
                n_lower not in seen and
                not n.startswith('http') and
                not n.isdigit()):
                company_names.append(n)
                seen.add(n_lower)

        if result["match_count"] > 0 and company_names:
            # Check each result for a match
            for found_name in company_names[:20]:
                if is_match(cleaned_name, found_name):
                    result["exact_match"] = True
                    break

            # Store top matches (company names only)
            result["top_matches"] = company_names[:5]

    except Exception as e:
        print(f"    Error searching: {e}")

    return result


async def scrape_enr_contractors() -> list[dict]:
    """Main scraping function for ENR contractors."""
    print("Extracting contractors from PDF...")
    contractors = extract_contractors_from_pdf(PDF_FILE)
    print(f"Found {len(contractors)} contractors")

    if not contractors:
        print("ERROR: No contractors extracted from PDF")
        return []

    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = await context.new_page()

        for i, contractor in enumerate(contractors):
            rank = contractor["rank"]
            original_name = contractor["original_name"]
            cleaned_name = clean_company_name(original_name, rank)

            print(f"[{i+1}/{len(contractors)}] Rank {rank}: {original_name}")
            print(f"    Searching: {cleaned_name}")

            search_result = await search_contractor(page, original_name, cleaned_name)

            result = {
                "rank": rank,
                "original_name": original_name,
                "search_term": cleaned_name,
                "exact_match": search_result["exact_match"],
                "match_count": search_result["match_count"],
                "top_matches": "; ".join(search_result["top_matches"][:3])
            }
            results.append(result)

            status = "EXACT MATCH" if search_result["exact_match"] else "no exact match"
            print(f"    -> {search_result['match_count']} results ({status})")

            # Small delay to be respectful
            await asyncio.sleep(1)

        await browser.close()

    return results


def save_to_csv(results: list[dict]) -> None:
    """Save results to CSV file."""
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    fieldnames = ["timestamp", "rank", "original_name", "search_term",
                  "exact_match", "match_count", "top_matches"]

    # Write fresh file (not append) since this is a complete scan
    with open(DATA_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            result["timestamp"] = timestamp
            writer.writerow(result)

    print(f"\nResults saved to {DATA_FILE}")


def update_summary_csv(results: list[dict]) -> None:
    """Update the summary CSV with today's results.

    Format: contractor names in first column, dates as subsequent columns,
    values are 1 (match found) or 0 (no match).
    """
    SUMMARY_FILE.parent.mkdir(parents=True, exist_ok=True)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Build a dict of rank -> match result (1 or 0) for today
    today_results = {}
    for r in results:
        today_results[r["rank"]] = 1 if r["exact_match"] else 0

    # Read existing summary if it exists
    existing_data = {}  # rank -> {date: value, ...}
    existing_dates = []

    if SUMMARY_FILE.exists():
        with open(SUMMARY_FILE, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames:
                # First column is 'rank', second is 'contractor', rest are dates
                existing_dates = [col for col in reader.fieldnames if col not in ('rank', 'contractor')]

                for row in reader:
                    rank = int(row['rank'])
                    existing_data[rank] = {date: row[date] for date in existing_dates}

    # Add today's date if not already present
    if today not in existing_dates:
        existing_dates.append(today)

    # Merge today's results
    for rank, match_value in today_results.items():
        if rank not in existing_data:
            existing_data[rank] = {}
        existing_data[rank][today] = match_value

    # Get contractor names from results
    rank_to_name = {r["rank"]: r["search_term"] for r in results}

    # Write updated summary
    fieldnames = ['rank', 'contractor'] + existing_dates

    with open(SUMMARY_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        # Write rows sorted by rank
        for rank in sorted(existing_data.keys()):
            row = {
                'rank': rank,
                'contractor': rank_to_name.get(rank, f"Rank {rank}")
            }
            for date in existing_dates:
                row[date] = existing_data[rank].get(date, '')
            writer.writerow(row)

    print(f"Summary updated: {SUMMARY_FILE}")


async def main():
    """Main entry point."""
    print("=" * 70)
    print("ENR Top 400 Contractors - Procore Network Search")
    print(f"Started: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 70 + "\n")

    if not PDF_FILE.exists():
        print(f"ERROR: PDF file not found: {PDF_FILE}")
        return

    results = await scrape_enr_contractors()

    if results:
        save_to_csv(results)
        update_summary_csv(results)

        # Summary
        exact_matches = sum(1 for r in results if r["exact_match"])
        with_results = sum(1 for r in results if r["match_count"] > 0)

        print("\n" + "=" * 70)
        print("Summary:")
        print("-" * 70)
        print(f"  Total contractors searched: {len(results)}")
        print(f"  With exact match: {exact_matches}")
        print(f"  With any results: {with_results}")
        print(f"  No results found: {len(results) - with_results}")
        print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
