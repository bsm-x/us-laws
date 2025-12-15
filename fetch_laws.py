"""
Fetch all US Public Laws metadata from Congress.gov API
Creates a simple CSV with law titles and enactment dates
"""

import os
import requests
import csv
import time
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

API_KEY = os.getenv("CONGRESS_API_KEY")
BASE_URL = "https://api.congress.gov/v3"


def fetch_laws_for_congress(congress_number: int) -> list:
    """Fetch all public laws for a specific Congress (2-year session)"""
    laws = []
    offset = 0
    limit = 250  # Max allowed by API

    while True:
        # Must specify law type: 'pub' for public laws, 'priv' for private laws
        url = f"{BASE_URL}/law/{congress_number}/pub"
        params = {
            "api_key": API_KEY,
            "offset": offset,
            "limit": limit,
            "format": "json",
        }

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            # API returns 'bills' not 'laws'
            batch = data.get("bills", [])
            if not batch:
                break

            laws.extend(batch)
            print(f"  Congress {congress_number}: fetched {len(laws)} laws...")

            # Check if there are more
            if len(batch) < limit:
                break

            offset += limit
            time.sleep(0.5)  # Rate limiting

        except requests.exceptions.RequestException as e:
            print(f"  Error fetching Congress {congress_number}: {e}")
            break

    return laws


def fetch_all_laws(start_congress: int = 82, end_congress: int = 118) -> list:
    """
    Fetch laws from Congress 82 (1951) to current.
    Congress 82+ have digital records in the API.
    Each Congress = 2 years (e.g., 118th = 2023-2024)
    """
    all_laws = []

    for congress in range(start_congress, end_congress + 1):
        year_start = 1789 + (congress - 1) * 2
        print(f"Fetching Congress {congress} ({year_start}-{year_start + 1})...")
        laws = fetch_laws_for_congress(congress)
        all_laws.extend(laws)
        time.sleep(1)  # Be nice to the API

    return all_laws


def save_to_csv(laws: list, filename: str = "us_public_laws.csv"):
    """Save laws to CSV file"""
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Congress",
                "Bill Number",
                "Public Law",
                "Title",
                "Origin Chamber",
                "Latest Action Date",
                "Latest Action",
            ]
        )

        for bill in laws:
            # Extract the public law number from the 'laws' array
            law_info = bill.get("laws", [{}])[0] if bill.get("laws") else {}
            public_law = law_info.get("number", "")
            latest_action = bill.get("latestAction") or {}

            writer.writerow(
                [
                    bill.get("congress", ""),
                    bill.get("number", ""),
                    f"P.L. {public_law}" if public_law else "",
                    bill.get("title", ""),
                    bill.get("originChamber", ""),
                    latest_action.get("actionDate", ""),
                    latest_action.get("text", ""),
                ]
            )

    print(f"\nSaved {len(laws)} laws to {filename}")


def print_summary(laws: list):
    """Print summary statistics"""
    print("\n" + "=" * 60)
    print("US PUBLIC LAWS SUMMARY")
    print("=" * 60)

    # Count by Congress
    by_congress = {}
    for law in laws:
        c = law.get("congress", "Unknown")
        by_congress[c] = by_congress.get(c, 0) + 1

    print(f"\nTotal Laws: {len(laws)}")
    print(f"Congresses covered: {min(by_congress.keys())} - {max(by_congress.keys())}")
    print(f"\nLaws per Congress:")

    for congress in sorted(by_congress.keys()):
        year = 1789 + (congress - 1) * 2
        bar = "█" * (by_congress[congress] // 20)
        print(f"  {congress:3d} ({year}): {by_congress[congress]:4d} {bar}")


if __name__ == "__main__":
    print("US Public Laws Fetcher")
    print("=" * 40)

    if not API_KEY:
        print("\n⚠️  You need a Congress.gov API key!")
        print("   Get one free at: https://api.congress.gov/sign-up/")
        print("   Then add it to .env file: CONGRESS_API_KEY=your_key_here")
    else:
        # Fetch laws (Congress 82-118 = 1951-2024)
        laws = fetch_all_laws(start_congress=82, end_congress=118)

        # Save and summarize
        save_to_csv(laws)
        print_summary(laws)
