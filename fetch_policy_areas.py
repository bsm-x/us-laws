"""
Fetch US Public Laws with Policy Area (topic category)
This allows organizing laws by subject matter
"""

import os
import csv
import json
import requests
import time
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("CONGRESS_API_KEY")
BASE_URL = "https://api.congress.gov/v3"


# Load existing laws
def load_existing_laws(filename="us_public_laws.csv"):
    """Load laws from CSV to get bill numbers"""
    laws = []
    with open(filename, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            laws.append(row)
    return laws


def get_bill_type(origin_chamber):
    """Convert origin chamber to bill type"""
    return "hr" if origin_chamber == "House" else "s"


def fetch_policy_area(congress, bill_type, bill_number):
    """Fetch policy area for a specific bill"""
    url = f"{BASE_URL}/bill/{congress}/{bill_type}/{bill_number}"
    params = {"api_key": API_KEY, "format": "json"}

    try:
        resp = requests.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        bill = data.get("bill", {})
        policy = bill.get("policyArea", {})
        return policy.get("name", "")
    except Exception as e:
        return ""


def fetch_policy_areas_sample(sample_size=100):
    """Fetch policy areas for a sample of laws to see the categories"""
    laws = load_existing_laws()

    # Get unique policy areas from a sample
    policy_areas = set()

    print(f"Sampling {sample_size} laws to discover policy areas...")

    for i, law in enumerate(laws[:sample_size]):
        congress = law.get("Congress")
        bill_num = law.get("Bill Number")
        origin = law.get("Origin Chamber")

        if congress and bill_num and origin:
            bill_type = get_bill_type(origin)
            policy = fetch_policy_area(congress, bill_type, bill_num)
            if policy:
                policy_areas.add(policy)
                print(f"  [{i+1}/{sample_size}] Found: {policy}")

        time.sleep(0.3)  # Rate limiting

    return sorted(policy_areas)


def count_by_policy_area_quick():
    """
    Quick approach: Use the API's policy area filter to count laws by category
    """
    # Known policy areas (from Congress.gov)
    policy_areas = [
        "Agriculture and Food",
        "Animals",
        "Armed Forces and National Security",
        "Arts, Culture, Religion",
        "Civil Rights and Liberties, Minority Issues",
        "Commerce",
        "Congress",
        "Crime and Law Enforcement",
        "Economics and Public Finance",
        "Education",
        "Emergency Management",
        "Energy",
        "Environmental Protection",
        "Families",
        "Finance and Financial Sector",
        "Foreign Trade and International Finance",
        "Government Operations and Politics",
        "Health",
        "Housing and Community Development",
        "Immigration",
        "International Affairs",
        "Labor and Employment",
        "Law",
        "Native Americans",
        "Public Lands and Natural Resources",
        "Science, Technology, Communications",
        "Social Sciences and History",
        "Social Welfare",
        "Sports and Recreation",
        "Taxation",
        "Transportation and Public Works",
        "Water Resources Development",
    ]

    print("\nKnown Policy Areas (topic categories):")
    print("=" * 50)
    for area in policy_areas:
        print(f"  • {area}")

    return policy_areas


if __name__ == "__main__":
    print("US Law Policy Areas")
    print("=" * 40)

    if not API_KEY:
        print("\n⚠️  Need CONGRESS_API_KEY in .env file")
    else:
        # Show known categories
        areas = count_by_policy_area_quick()

        print(f"\nTotal policy areas: {len(areas)}")
        print("\nTo fetch policy areas for all 20,000+ laws would take ~2 hours")
        print("(API rate limits + 1 call per law)")

        # Ask to sample
        print("\nRun with --sample to fetch a sample and verify categories")
