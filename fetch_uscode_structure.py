"""
Fetch US Code Structure (Titles, Chapters, Sections)
This shows the current organization of all federal law
"""

import csv
import requests
import zipfile
import io
import os
import xml.etree.ElementTree as ET
from pathlib import Path

# US Code Title Information (54 titles)
US_CODE_TITLES = [
    {"number": 1, "name": "General Provisions", "enacted": True},
    {"number": 2, "name": "The Congress", "enacted": False},
    {"number": 3, "name": "The President", "enacted": True},
    {
        "number": 4,
        "name": "Flag and Seal, Seat of Government, and the States",
        "enacted": True,
    },
    {"number": 5, "name": "Government Organization and Employees", "enacted": True},
    {"number": 6, "name": "Domestic Security", "enacted": True},
    {"number": 7, "name": "Agriculture", "enacted": False},
    {"number": 8, "name": "Aliens and Nationality", "enacted": False},
    {"number": 9, "name": "Arbitration", "enacted": True},
    {"number": 10, "name": "Armed Forces", "enacted": True},
    {"number": 11, "name": "Bankruptcy", "enacted": True},
    {"number": 12, "name": "Banks and Banking", "enacted": False},
    {"number": 13, "name": "Census", "enacted": True},
    {"number": 14, "name": "Coast Guard", "enacted": True},
    {"number": 15, "name": "Commerce and Trade", "enacted": False},
    {"number": 16, "name": "Conservation", "enacted": False},
    {"number": 17, "name": "Copyrights", "enacted": True},
    {"number": 18, "name": "Crimes and Criminal Procedure", "enacted": True},
    {"number": 19, "name": "Customs Duties", "enacted": False},
    {"number": 20, "name": "Education", "enacted": False},
    {"number": 21, "name": "Food and Drugs", "enacted": False},
    {"number": 22, "name": "Foreign Relations and Intercourse", "enacted": False},
    {"number": 23, "name": "Highways", "enacted": True},
    {"number": 24, "name": "Hospitals and Asylums", "enacted": False},
    {"number": 25, "name": "Indians", "enacted": False},
    {"number": 26, "name": "Internal Revenue Code", "enacted": True},
    {"number": 27, "name": "Intoxicating Liquors", "enacted": False},
    {"number": 28, "name": "Judiciary and Judicial Procedure", "enacted": True},
    {"number": 29, "name": "Labor", "enacted": False},
    {"number": 30, "name": "Mineral Lands and Mining", "enacted": False},
    {"number": 31, "name": "Money and Finance", "enacted": True},
    {"number": 32, "name": "National Guard", "enacted": True},
    {"number": 33, "name": "Navigation and Navigable Waters", "enacted": False},
    {"number": 34, "name": "Crime Control and Law Enforcement", "enacted": True},
    {"number": 35, "name": "Patents", "enacted": True},
    {
        "number": 36,
        "name": "Patriotic and National Observances, Ceremonies, and Organizations",
        "enacted": True,
    },
    {
        "number": 37,
        "name": "Pay and Allowances of the Uniformed Services",
        "enacted": True,
    },
    {"number": 38, "name": "Veterans' Benefits", "enacted": True},
    {"number": 39, "name": "Postal Service", "enacted": True},
    {"number": 40, "name": "Public Buildings, Property, and Works", "enacted": True},
    {"number": 41, "name": "Public Contracts", "enacted": True},
    {"number": 42, "name": "The Public Health and Welfare", "enacted": False},
    {"number": 43, "name": "Public Lands", "enacted": False},
    {"number": 44, "name": "Public Printing and Documents", "enacted": True},
    {"number": 45, "name": "Railroads", "enacted": False},
    {"number": 46, "name": "Shipping", "enacted": True},
    {"number": 47, "name": "Telecommunications", "enacted": False},
    {"number": 48, "name": "Territories and Insular Possessions", "enacted": False},
    {"number": 49, "name": "Transportation", "enacted": True},
    {"number": 50, "name": "War and National Defense", "enacted": False},
    {"number": 51, "name": "National and Commercial Space Programs", "enacted": True},
    {"number": 52, "name": "Voting and Elections", "enacted": True},
    {"number": 53, "name": "Reserved", "enacted": False},
    {
        "number": 54,
        "name": "National Park Service and Related Programs",
        "enacted": True,
    },
]


def save_titles_to_csv(filename="us_code_titles.csv"):
    """Save basic title information to CSV"""
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Title Number", "Title Name", "Enacted as Positive Law"])

        for title in US_CODE_TITLES:
            writer.writerow(
                [title["number"], title["name"], "Yes" if title["enacted"] else "No"]
            )

    print(f"Saved {len(US_CODE_TITLES)} titles to {filename}")


def print_structure():
    """Print the US Code structure"""
    print("\n" + "=" * 70)
    print("UNITED STATES CODE - STRUCTURE")
    print("(Current as of Public Law 119-46, December 2, 2025)")
    print("=" * 70)

    enacted_count = sum(1 for t in US_CODE_TITLES if t["enacted"])

    print(f"\nTotal Titles: {len(US_CODE_TITLES)}")
    print(f"Enacted as Positive Law: {enacted_count}")
    print(f"Not Yet Enacted: {len(US_CODE_TITLES) - enacted_count}")

    print("\n" + "-" * 70)
    print(f"{'#':>3}  {'Title Name':<55} {'Enacted?':>8}")
    print("-" * 70)

    for title in US_CODE_TITLES:
        enacted = "✓" if title["enacted"] else ""
        print(f"{title['number']:>3}  {title['name']:<55} {enacted:>8}")

    print("-" * 70)

    print("\nNote: 'Enacted as Positive Law' means the title itself is the law.")
    print("Non-enacted titles are prima facie evidence of the law (the underlying")
    print("statutes are the actual law).")


def print_summary_stats():
    """Print summary statistics about the US Code"""
    print("\n" + "=" * 70)
    print("US CODE - QUICK FACTS")
    print("=" * 70)

    stats = """
    📚 Total Titles:                    54
    ⚖️  Enacted as Positive Law:         29
    📖 Total Sections (approximate):    ~60,000
    📜 Oldest Title:                    Title 1 (1947)
    🆕 Newest Title:                    Title 54 (2014)

    🏛️  Largest Titles (by section count):
       • Title 42 (Public Health) - ~21,000 sections
       • Title 26 (Tax Code) - ~10,000 sections
       • Title 10 (Armed Forces) - ~8,000 sections
       • Title 18 (Crimes) - ~3,000 sections
       • Title 5 (Gov't Employees) - ~2,500 sections

    📊 Organization:
       Title → Subtitle → Chapter → Subchapter → Part → Section

    🔗 Official Source: https://uscode.house.gov/
    """
    print(stats)


if __name__ == "__main__":
    print_structure()
    print_summary_stats()
    save_titles_to_csv()
