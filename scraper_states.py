"""
Procore Construction Network State Data Scraper

Collects contractor counts by US state from https://network.procore.com/us
and appends to CSV file.
"""

import asyncio
import csv
import re
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

US_STATES = [
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado",
    "Connecticut", "Delaware", "District of Columbia", "Florida", "Georgia",
    "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky",
    "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota",
    "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire",
    "New Jersey", "New Mexico", "New York", "North Carolina", "North Dakota",
    "Ohio", "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island", "South Carolina",
    "South Dakota", "Tennessee", "Texas", "Utah", "Vermont", "Virginia",
    "Washington", "West Virginia", "Wisconsin", "Wyoming"
]

URL = "https://network.procore.com/us"
DATA_FILE = Path(__file__).parent / "data" / "procore_network_states.csv"
TIMEOUT_MS = 60000


async def scrape_state_counts() -> dict[str, int | None]:
    """Scrape contractor counts for all US states."""
    results = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        print("Loading US states page...")
        await page.goto(URL, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
        await asyncio.sleep(3)

        # Get page content
        content = await page.content()

        # Extract state counts using regex patterns
        # Pattern matches state name followed by count in various formats
        for state in US_STATES:
            # Try to find the state and its associated count
            # Pattern 1: State name followed by comma and number (e.g., "California, 43,427")
            pattern1 = rf'{re.escape(state)}[,\s]+(\d[\d,]+)'
            # Pattern 2: Look for state in link text with nearby count
            pattern2 = rf'{re.escape(state)}.*?(\d{{1,3}}(?:,\d{{3}})+|\d+)'

            count = None
            match = re.search(pattern1, content)
            if match:
                count_str = match.group(1).replace(",", "")
                count = int(count_str)
            else:
                match = re.search(pattern2, content, re.DOTALL)
                if match:
                    count_str = match.group(1).replace(",", "")
                    count = int(count_str)

            results[state] = count

        # Also try to get the total
        total_match = re.search(r'(\d{1,3}(?:,\d{3})+)\s*(?:contractors|construction professionals)', content, re.IGNORECASE)
        if total_match:
            results["US Total"] = int(total_match.group(1).replace(",", ""))

        await browser.close()

    return results


def save_to_csv(results: dict[str, int | None]) -> None:
    """Append results to CSV file with timestamp."""
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    file_exists = DATA_FILE.exists()

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    fieldnames = ["timestamp", "US Total"] + US_STATES
    row = {"timestamp": timestamp}
    row.update(results)

    with open(DATA_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

    print(f"\nData saved to {DATA_FILE}")


async def main():
    """Main entry point."""
    print("=" * 60)
    print("Procore Construction Network - US States Scraper")
    print(f"Started: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 60 + "\n")

    results = await scrape_state_counts()
    save_to_csv(results)

    # Count successful fetches
    fetched = sum(1 for v in results.values() if v is not None)
    total_states = len(US_STATES) + 1  # +1 for US Total

    print("\n" + "=" * 60)
    print(f"Summary: Fetched {fetched}/{total_states} values")
    print("-" * 60)

    # Show top 10 states by count
    state_counts = [(k, v) for k, v in results.items() if v is not None and k != "US Total"]
    state_counts.sort(key=lambda x: x[1], reverse=True)

    if "US Total" in results and results["US Total"]:
        print(f"  US Total: {results['US Total']:,}")
    print("\n  Top 10 States:")
    for state, count in state_counts[:10]:
        print(f"    {state}: {count:,}")

    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
