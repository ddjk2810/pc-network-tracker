"""
Procore Construction Network Data Scraper

Collects contractor counts from https://network.procore.com/
by company type and appends to CSV file.
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

BASE_URL = "https://network.procore.com/search"
DATA_FILE = Path(__file__).parent / "data" / "procore_network_counts.csv"
TIMEOUT_MS = 60000


async def wait_for_count_change(page, previous_count: int | None, timeout: int = 10000) -> int | None:
    """Wait for the count to change from a previous value."""
    start_time = asyncio.get_event_loop().time()

    while (asyncio.get_event_loop().time() - start_time) * 1000 < timeout:
        content = await page.content()

        # Look for count in the visible results header (not in JSON data)
        # The displayed count should update when filters are applied
        try:
            # Try to find the results count in the page heading
            heading = await page.locator('h1, h2, [class*="result"]').first.inner_text()
            match = re.search(r'([\d,]+)\s*Results?', heading, re.IGNORECASE)
            if match:
                count = int(match.group(1).replace(",", ""))
                if previous_count is None or count != previous_count:
                    return count
        except Exception:
            pass

        # Fallback: check JSON data
        json_match = re.search(r'"count"\s*:\s*(\d+)', content)
        if json_match:
            count = int(json_match.group(1))
            if previous_count is None or count != previous_count:
                return count

        await asyncio.sleep(0.5)

    return None


async def get_initial_count(page) -> int | None:
    """Get the initial total count from the page."""
    await page.wait_for_load_state("domcontentloaded", timeout=TIMEOUT_MS)
    await asyncio.sleep(3)

    content = await page.content()
    json_match = re.search(r'"count"\s*:\s*(\d+)', content)
    if json_match:
        return int(json_match.group(1))
    return None


async def click_filter_and_get_count(page, filter_text: str, total_count: int) -> int | None:
    """Click on a company type filter and return the new count."""
    try:
        # First, find and expand the Company Types filter section if needed
        # Look for "Company Types" or similar header and expand it
        try:
            company_types_header = page.locator('button:has-text("Company Type"), [class*="filter"]:has-text("Company Type")')
            if await company_types_header.count() > 0:
                # Check if it's collapsed (aria-expanded="false")
                is_expanded = await company_types_header.first.get_attribute("aria-expanded")
                if is_expanded == "false":
                    await company_types_header.first.click()
                    await asyncio.sleep(1)
        except Exception:
            pass

        # Find and click the specific filter checkbox/label
        # Try multiple selectors
        clicked = False

        # Method 1: Look for label with exact text
        try:
            label = page.locator(f'label:has-text("{filter_text}")')
            if await label.count() > 0:
                await label.first.click()
                clicked = True
        except Exception:
            pass

        # Method 2: Look for checkbox input near the text
        if not clicked:
            try:
                checkbox = page.locator(f'input[type="checkbox"]').filter(has_text=filter_text)
                if await checkbox.count() > 0:
                    await checkbox.first.click()
                    clicked = True
            except Exception:
                pass

        # Method 3: Look for any clickable element with the filter text within a filter section
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

        # Wait for the count to update (should be different from total)
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
    """Scrape contractor counts for all company types."""
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

        # Now get filtered counts
        for company_type in COMPANY_TYPES[1:]:  # Skip "Total"
            name = company_type["name"]
            filter_text = company_type["filter_text"]

            print(f"Fetching: {name}...")

            # Reload page fresh for each filter to avoid stacking filters
            await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
            await asyncio.sleep(3)

            count = await click_filter_and_get_count(page, filter_text, total_count)
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

    fieldnames = ["timestamp"] + [ct["name"] for ct in COMPANY_TYPES]
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
    for name, count in results.items():
        if count:
            print(f"  {name}: {count:,}")
        else:
            print(f"  {name}: N/A")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
