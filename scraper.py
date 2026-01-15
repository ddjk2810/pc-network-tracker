"""
Procore Construction Network Data Scraper

Collects contractor counts from https://network.procore.com/
by company type and market sector, appends to CSV file.
"""

import asyncio
import csv
import re
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# Company type filters to track
COMPANY_TYPES = [
    {"name": "Total", "filter_text": None},
    {"name": "General Contractors", "filter_text": "General Contractor"},
    {"name": "Owners", "filter_text": "Owner"},
    {"name": "Specialty Contractors", "filter_text": "Specialty Contractor"},
    {"name": "Architects", "filter_text": "Architect"},
    {"name": "Engineers", "filter_text": "Engineer"},
    {"name": "Consultants", "filter_text": "Consultant"},
    {"name": "Suppliers", "filter_text": "Supplier"},
]

# Market sector filters to track
MARKET_SECTORS = [
    {"name": "Commercial", "filter_text": "Commercial"},
    {"name": "Healthcare", "filter_text": "Healthcare"},
    {"name": "Industrial and Energy", "filter_text": "Industrial and Energy"},
    {"name": "Infrastructure", "filter_text": "Infrastructure"},
    {"name": "Institutional", "filter_text": "Institutional"},
    {"name": "Residential", "filter_text": "Residential"},
]

BASE_URL = "https://network.procore.com/search"
DATA_FILE = Path(__file__).parent / "data" / "procore_network_counts.csv"
TIMEOUT_MS = 60000


async def get_initial_count(page) -> int | None:
    """Get the initial total count from the page."""
    await page.wait_for_load_state("domcontentloaded", timeout=TIMEOUT_MS)
    await asyncio.sleep(3)

    content = await page.content()
    json_match = re.search(r'"count"\s*:\s*(\d+)', content)
    if json_match:
        return int(json_match.group(1))
    return None


async def click_filter_and_get_count(page, filter_text: str, total_count: int, filter_section: str = None) -> int | None:
    """Click on a filter and return the new count."""
    try:
        # Try to expand the filter section if specified
        if filter_section:
            try:
                section_header = page.locator(f'button:has-text("{filter_section}"), [class*="filter"]:has-text("{filter_section}")')
                if await section_header.count() > 0:
                    is_expanded = await section_header.first.get_attribute("aria-expanded")
                    if is_expanded == "false":
                        await section_header.first.click()
                        await asyncio.sleep(1)
            except Exception:
                pass

        # Find and click the specific filter
        clicked = False

        # Method 1: Look for label with the text
        try:
            label = page.locator(f'label:has-text("{filter_text}")')
            if await label.count() > 0:
                await label.first.click()
                clicked = True
        except Exception:
            pass

        # Method 2: Look for checkbox input
        if not clicked:
            try:
                checkbox = page.locator(f'input[type="checkbox"]').filter(has_text=filter_text)
                if await checkbox.count() > 0:
                    await checkbox.first.click()
                    clicked = True
            except Exception:
                pass

        # Method 3: Look for clickable element in filter section
        if not clicked:
            try:
                filter_item = page.locator(f'[class*="filter"] >> text="{filter_text}"')
                if await filter_item.count() > 0:
                    await filter_item.first.click()
                    clicked = True
            except Exception:
                pass

        # Method 4: Generic text search
        if not clicked:
            try:
                element = page.get_by_text(filter_text, exact=True)
                if await element.count() > 0:
                    await element.first.click()
                    clicked = True
            except Exception:
                pass

        if not clicked:
            print(f"    Could not find filter: {filter_text}")
            return None

        # Wait for the count to update
        await asyncio.sleep(3)

        # Get the new count
        content = await page.content()

        # Try to find a count that's different from total
        all_counts = re.findall(r'"count"\s*:\s*(\d+)', content)
        for count_str in all_counts:
            count = int(count_str)
            if count != total_count and count > 0:
                return count

        # If we couldn't find a different count, try the visible text
        try:
            text = await page.inner_text("body")
            match = re.search(r'([\d,]+)\s*Results?', text, re.IGNORECASE)
            if match:
                return int(match.group(1).replace(",", ""))
        except Exception:
            pass

        return None

    except Exception as e:
        print(f"    Error clicking filter: {e}")
        return None


async def scrape_counts() -> dict[str, int | None]:
    """Scrape contractor counts for all company types and market sectors."""
    results = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # Navigate to search page
        print("Loading search page...")
        await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
        await asyncio.sleep(4)

        # Get total count first
        total_count = await get_initial_count(page)
        results["Total"] = total_count
        print(f"Fetching: Total...")
        print(f"  -> {total_count:,}" if total_count else "  -> N/A")

        # Get company type counts
        print("\n--- Company Types ---")
        for company_type in COMPANY_TYPES[1:]:  # Skip "Total"
            name = company_type["name"]
            filter_text = company_type["filter_text"]

            print(f"Fetching: {name}...")

            # Reload page fresh for each filter
            await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
            await asyncio.sleep(3)

            count = await click_filter_and_get_count(page, filter_text, total_count, "Company Type")
            results[name] = count

            if count:
                print(f"  -> {count:,}")
            else:
                print(f"  -> Unable to fetch")

        # Get market sector counts
        print("\n--- Market Sectors ---")
        for sector in MARKET_SECTORS:
            name = sector["name"]
            filter_text = sector["filter_text"]

            print(f"Fetching: {name}...")

            # Reload page fresh for each filter
            await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
            await asyncio.sleep(3)

            count = await click_filter_and_get_count(page, filter_text, total_count, "Market Sector")
            results[name] = count

            if count:
                print(f"  -> {count:,}")
            else:
                print(f"  -> Unable to fetch")

        await browser.close()

    return results


def save_to_csv(results: dict[str, int | None]) -> None:
    """Append results to CSV file with timestamp."""
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    file_exists = DATA_FILE.exists()

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Build fieldnames: timestamp, company types, then market sectors
    fieldnames = ["timestamp"]
    fieldnames += [ct["name"] for ct in COMPANY_TYPES]
    fieldnames += [ms["name"] for ms in MARKET_SECTORS]

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
    print("Procore Construction Network Data Scraper")
    print(f"Started: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 60 + "\n")

    results = await scrape_counts()
    save_to_csv(results)

    print("\n" + "=" * 60)
    print("Summary:")
    print("-" * 60)
    print("Company Types:")
    for ct in COMPANY_TYPES:
        name = ct["name"]
        count = results.get(name)
        if count:
            print(f"  {name}: {count:,}")
        else:
            print(f"  {name}: N/A")

    print("\nMarket Sectors:")
    for ms in MARKET_SECTORS:
        name = ms["name"]
        count = results.get(name)
        if count:
            print(f"  {name}: {count:,}")
        else:
            print(f"  {name}: N/A")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
