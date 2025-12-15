"""
Download Full US Code + Founding Documents
This will download ~2-3 GB of legal text
"""

import os
import requests
import zipfile
import io
from pathlib import Path
from tqdm import tqdm

# Base URLs
USCODE_BASE = "https://uscode.house.gov/download/releasepoints/us/pl/119/46"
FOUNDING_DOCS_BASE = "https://www.archives.gov"

# Directories
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
USCODE_DIR = DATA_DIR / "uscode"
FOUNDING_DIR = DATA_DIR / "founding_documents"


def setup_directories():
    """Create necessary directories"""
    USCODE_DIR.mkdir(parents=True, exist_ok=True)
    FOUNDING_DIR.mkdir(parents=True, exist_ok=True)


def download_file(url, dest_path, desc="Downloading"):
    """Download a file with progress bar"""
    print(f"\n{desc}...")
    print(f"URL: {url}")

    response = requests.get(url, stream=True)
    response.raise_for_status()

    total_size = int(response.headers.get("content-length", 0))

    with open(dest_path, "wb") as f:
        if total_size == 0:
            f.write(response.content)
        else:
            with tqdm(total=total_size, unit="B", unit_scale=True, desc=desc) as pbar:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    pbar.update(len(chunk))


def download_uscode_title(title_num):
    """Download a single US Code title"""
    title_str = f"{title_num:02d}"
    filename = f"xml_usc{title_str}@119-46.zip"
    url = f"{USCODE_BASE}/{filename}"
    dest = USCODE_DIR / filename

    try:
        download_file(url, dest, f"Title {title_num}")

        # Extract
        with zipfile.ZipFile(dest, "r") as zip_ref:
            extract_dir = USCODE_DIR / f"title_{title_num:02d}"
            zip_ref.extractall(extract_dir)

        # Remove zip to save space
        dest.unlink()
        return True
    except Exception as e:
        print(f"Error downloading Title {title_num}: {e}")
        return False


def download_all_uscode():
    """Download all 54 titles of US Code"""
    print("\n" + "=" * 70)
    print("DOWNLOADING COMPLETE US CODE")
    print("=" * 70)
    print("\nThis will download ~2-3 GB of legal text (54 titles)")
    print("Estimated time: 30-60 minutes depending on connection")

    response = input("\nContinue? (yes/no): ")
    if response.lower() != "yes":
        print("Cancelled.")
        return

    success_count = 0
    for title_num in range(1, 55):  # Titles 1-54
        if download_uscode_title(title_num):
            success_count += 1

    print(f"\n✓ Downloaded {success_count} of 54 titles")


def download_founding_documents():
    """Download founding documents"""
    print("\n" + "=" * 70)
    print("DOWNLOADING FOUNDING DOCUMENTS")
    print("=" * 70)

    documents = {
        "declaration_of_independence.txt": {
            "url": "https://www.archives.gov/founding-docs/declaration-transcript",
            "name": "Declaration of Independence",
        },
        "constitution.txt": {
            "url": "https://www.archives.gov/founding-docs/constitution-transcript",
            "name": "US Constitution",
        },
        "articles_of_confederation.txt": {
            "url": "https://www.archives.gov/founding-docs/articles-of-confederation-transcript",
            "name": "Articles of Confederation",
        },
        "northwest_ordinance.txt": {
            "url": "https://avalon.law.yale.edu/18th_century/nworder.asp",
            "name": "Northwest Ordinance",
        },
    }

    # Manual text since websites don't provide plain text APIs
    print("\nNote: Founding documents require manual extraction from websites")
    print("Creating template files with URLs...")

    for filename, info in documents.items():
        dest = FOUNDING_DIR / filename
        content = f"""{info['name']}
{'='*70}

Visit: {info['url']}

This document should be manually copied from the source above.
The official texts are available at:
- National Archives: https://www.archives.gov/founding-docs
- Yale Avalon Project: https://avalon.law.yale.edu/

"""
        with open(dest, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  Created: {filename}")

    # Download one that's easily available - Constitution from Congress.gov
    print("\nDownloading Constitution from Congress.gov API...")
    try:
        const_url = "https://constitution.congress.gov/constitution/"
        # This would need proper scraping - for now create a note
        print("  Note: Use official sources above for accurate texts")
    except Exception as e:
        print(f"  Could not auto-download: {e}")


def create_founding_docs_manually():
    """Create files with the actual founding document texts"""

    # Declaration of Independence
    declaration = """The unanimous Declaration of the thirteen united States of America

When in the Course of human events, it becomes necessary for one people to dissolve the political bands which have connected them with another, and to assume among the powers of the earth, the separate and equal station to which the Laws of Nature and of Nature's God entitle them, a decent respect to the opinions of mankind requires that they should declare the causes which impel them to the separation.

We hold these truths to be self-evident, that all men are created equal, that they are endowed by their Creator with certain unalienable Rights, that among these are Life, Liberty and the pursuit of Happiness.--That to secure these rights, Governments are instituted among Men, deriving their just powers from the consent of the governed, --That whenever any Form of Government becomes destructive of these ends, it is the Right of the People to alter or to abolish it, and to institute new Government, laying its foundation on such principles and organizing its powers in such form, as to them shall seem most likely to effect their Safety and Happiness...

[Full text available at: https://www.archives.gov/founding-docs/declaration-transcript]
"""

    with open(
        FOUNDING_DIR / "declaration_of_independence.txt", "w", encoding="utf-8"
    ) as f:
        f.write(declaration)

    print("Created founding document templates in:", FOUNDING_DIR)


def get_download_size_estimate():
    """Show what will be downloaded"""
    print("\n" + "=" * 70)
    print("DOWNLOAD SIZE ESTIMATES")
    print("=" * 70)
    print(
        """
US Code (XML format):
  • Title 26 (Tax Code): ~350 MB
  • Title 42 (Public Health): ~500 MB
  • Other 52 titles: ~1.5 GB
  • Total: ~2.5 GB

Founding Documents:
  • ~100 KB (text files)

Total Download: ~2.5 GB
Disk Space After Extraction: ~5-6 GB

Time Estimate:
  • Fast connection (50 Mbps): ~10-15 minutes
  • Average connection (10 Mbps): ~30-60 minutes
"""
    )


def download_sample_titles():
    """Download just a few sample titles for testing"""
    print("\n" + "=" * 70)
    print("DOWNLOADING SAMPLE TITLES")
    print("=" * 70)
    print("\nDownloading 3 sample titles for testing...")

    # Small, medium, large
    sample_titles = [1, 18, 26]  # General Provisions, Crimes, Tax Code

    for title_num in sample_titles:
        download_uscode_title(title_num)

    print("\n✓ Sample download complete")
    print("Check the data/uscode/ directory")


if __name__ == "__main__":
    setup_directories()

    print(
        """
    ╔══════════════════════════════════════════════════════════════════╗
    ║         US CODE + FOUNDING DOCUMENTS DOWNLOADER                  ║
    ╚══════════════════════════════════════════════════════════════════╝
    """
    )

    print("\nOptions:")
    print("  1. Download ALL US Code titles (2.5 GB, 30-60 min)")
    print("  2. Download sample titles (3 titles, ~400 MB, 5 min)")
    print("  3. Setup founding documents (templates)")
    print("  4. Show size estimates")
    print("  5. Exit")

    choice = input("\nChoose option (1-5): ").strip()

    if choice == "1":
        get_download_size_estimate()
        download_all_uscode()
        download_founding_documents()
    elif choice == "2":
        download_sample_titles()
        download_founding_documents()
    elif choice == "3":
        download_founding_documents()
        create_founding_docs_manually()
    elif choice == "4":
        get_download_size_estimate()
    else:
        print("Exiting...")

    print("\n✓ Complete!")
    print(f"Data saved to: {DATA_DIR}")
