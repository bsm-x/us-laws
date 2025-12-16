"""
Download Supreme Court opinions from CourtListener API.

This script fetches Supreme Court cases and their full opinion text from the
CourtListener REST API (free, public domain data from Free Law Project).

IMPORTANT: CourtListener requires an API token for access.
Get your free token at: https://www.courtlistener.com/help/api/rest/#authentication
Then add it to your .env file as COURTLISTENER_API_KEY=your_token_here

Rate limits: https://www.courtlistener.com/help/api/rest/#rates

Features:
    - Automatic resume: skips already-downloaded cases
    - Parallel downloads: uses multiple threads for faster processing
    - Rate limiting: respects API limits (5 requests/second)

Usage:
    python scripts/download/download_scotus_opinions.py [--limit N] [--year YYYY] [--workers N]

Examples:
    # Download all available opinions (may take a while)
    python scripts/download/download_scotus_opinions.py

    # Download only 100 opinions for testing
    python scripts/download/download_scotus_opinions.py --limit 100

    # Download opinions from 2020 onward
    python scripts/download/download_scotus_opinions.py --year 2020

    # Use 8 parallel workers (default: 5)
    python scripts/download/download_scotus_opinions.py --workers 8
"""

import os
import json
import time
import argparse
import sqlite3
import threading
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue

import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# CourtListener API base URL and token
API_BASE = "https://www.courtlistener.com/api/rest/v4"
COURTLISTENER_API_KEY = os.getenv("COURTLISTENER_API_KEY")

# Output directory
DATA_DIR = Path(__file__).parent.parent.parent / "data" / "scotus"
DB_PATH = DATA_DIR / "scotus_opinions.db"


class RateLimiter:
    """Thread-safe rate limiter for API requests."""

    def __init__(self, requests_per_second: float = 5.0):
        self.min_interval = 1.0 / requests_per_second
        self.last_request_time = 0.0
        self.lock = threading.Lock()

    def wait(self):
        """Wait if necessary to respect rate limit."""
        with self.lock:
            now = time.time()
            elapsed = now - self.last_request_time
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self.last_request_time = time.time()


# Global rate limiter (5 requests/second to be safe with CourtListener)
rate_limiter = RateLimiter(requests_per_second=5.0)

# Thread-local storage for database connections
_thread_local = threading.local()


def get_thread_connection():
    """Get or create a thread-local database connection."""
    if not hasattr(_thread_local, "conn"):
        _thread_local.conn = sqlite3.connect(DB_PATH)
    return _thread_local.conn


def get_existing_cluster_ids(conn) -> set:
    """Get set of cluster_ids already in the database."""
    cursor = conn.cursor()
    cursor.execute("SELECT cluster_id FROM cases")
    return {row[0] for row in cursor.fetchall()}


def get_cases_without_opinions(conn) -> list:
    """Get cases from the database that have no opinions downloaded yet."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT c.cluster_id, c.case_name, c.case_name_short, c.date_filed,
               c.docket_number, c.citation, c.scdb_id, c.judges, c.syllabus,
               c.procedural_history, c.attorneys, c.source
        FROM cases c
        LEFT JOIN opinions o ON c.cluster_id = o.cluster_id
        WHERE o.id IS NULL
    """
    )
    rows = cursor.fetchall()
    # Convert to dict format matching API response
    return [
        {
            "id": row[0],
            "case_name": row[1],
            "case_name_short": row[2],
            "date_filed": row[3],
            "docket_number": row[4],
            "citation": [row[5]] if row[5] else [],
            "scdb_id": row[6],
            "judges": row[7],
            "syllabus": row[8],
            "procedural_history": row[9],
            "attorneys": row[10],
            "source": row[11],
        }
        for row in rows
    ]


def create_database():
    """Create SQLite database for storing opinions."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create tables
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS cases (
            id INTEGER PRIMARY KEY,
            cluster_id INTEGER UNIQUE,
            case_name TEXT,
            case_name_short TEXT,
            docket_number TEXT,
            date_filed TEXT,
            date_argued TEXT,
            citation TEXT,
            scdb_id TEXT,
            judges TEXT,
            syllabus TEXT,
            procedural_history TEXT,
            attorneys TEXT,
            source TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS opinions (
            id INTEGER PRIMARY KEY,
            opinion_id INTEGER UNIQUE,
            case_id INTEGER,
            cluster_id INTEGER,
            type TEXT,
            author TEXT,
            author_id INTEGER,
            joined_by TEXT,
            html_text TEXT,
            plain_text TEXT,
            word_count INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (case_id) REFERENCES cases(id)
        )
    """
    )

    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cases_date ON cases(date_filed)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cases_citation ON cases(citation)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_opinions_case ON opinions(case_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_opinions_type ON opinions(type)")

    conn.commit()
    return conn


def get_opinion_clusters(session, start_year=None, limit=None):
    """
    Fetch Supreme Court opinion clusters (cases) from CourtListener.
    Each cluster represents a case that may have multiple opinions.
    """
    url = f"{API_BASE}/clusters/"
    params = {
        "docket__court": "scotus",
        "order_by": "-date_filed",
        "fields": "id,case_name,case_name_short,docket,date_filed,judges,syllabus,procedural_history,attorneys,scdb_id,citation,source",
    }

    if start_year:
        params["date_filed__gte"] = f"{start_year}-01-01"

    clusters = []
    page = 1

    while True:
        params["page"] = page

        try:
            response = session.get(url, params=params)
            # Handle 404 as end of pagination (CourtListener limits to ~100 pages)
            if response.status_code == 404:
                print(f"  Reached pagination limit at page {page}")
                break
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                print(f"  Reached pagination limit at page {page}")
                break
            print(f"  Error fetching page {page}: {e}")
            time.sleep(5)
            continue
        except requests.exceptions.RequestException as e:
            print(f"  Error fetching page {page}: {e}")
            time.sleep(5)
            continue

        results = data.get("results", [])
        if not results:
            break

        clusters.extend(results)
        print(
            f"  Fetched page {page}: {len(results)} clusters (total: {len(clusters)})"
        )

        if limit and len(clusters) >= limit:
            clusters = clusters[:limit]
            break

        if not data.get("next"):
            break

        page += 1
        time.sleep(0.5)  # Rate limiting

    return clusters


def get_opinions_for_cluster(session, cluster_id):
    """Fetch all opinions for a given cluster (case)."""
    rate_limiter.wait()  # Respect rate limit

    url = f"{API_BASE}/opinions/"
    params = {
        "cluster": cluster_id,
        "fields": "id,type,author,author_id,joined_by,html,plain_text",
    }

    try:
        response = session.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("results", [])
    except requests.exceptions.RequestException as e:
        print(f"    Error fetching opinions for cluster {cluster_id}: {e}")
        return []


def get_docket_info(session, docket_url):
    """Fetch docket information for a case."""
    try:
        response = session.get(docket_url)
        response.raise_for_status()
        return response.json()
    except:
        return {}


def save_cluster_to_db(conn, cluster, opinions):
    """Save a cluster and its opinions to the database."""
    cursor = conn.cursor()

    # Extract citation string
    citations = cluster.get("citation", [])
    citation_str = citations[0] if citations else ""

    # Insert cluster (case)
    try:
        cursor.execute(
            """
            INSERT OR REPLACE INTO cases
            (cluster_id, case_name, case_name_short, docket_number, date_filed,
             citation, scdb_id, judges, syllabus, procedural_history, attorneys, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                cluster["id"],
                cluster.get("case_name", ""),
                cluster.get("case_name_short", ""),
                cluster.get("docket_number", ""),
                cluster.get("date_filed", ""),
                citation_str,
                cluster.get("scdb_id", ""),
                cluster.get("judges", ""),
                cluster.get("syllabus", ""),
                cluster.get("procedural_history", ""),
                cluster.get("attorneys", ""),
                cluster.get("source", ""),
            ),
        )
        case_id = cursor.lastrowid

        # Get case_id if it was a replace
        cursor.execute("SELECT id FROM cases WHERE cluster_id = ?", (cluster["id"],))
        row = cursor.fetchone()
        if row:
            case_id = row[0]

    except sqlite3.IntegrityError:
        # Case already exists, get its ID
        cursor.execute("SELECT id FROM cases WHERE cluster_id = ?", (cluster["id"],))
        row = cursor.fetchone()
        case_id = row[0] if row else None

    if not case_id:
        return

    # Insert opinions
    for opinion in opinions:
        plain_text = opinion.get("plain_text", "") or ""
        html_text = opinion.get("html", "") or ""

        # Calculate word count
        word_count = len(plain_text.split()) if plain_text else 0

        # Joined by is a list of judge URLs
        joined_by = opinion.get("joined_by", [])
        joined_by_str = ",".join(str(j) for j in joined_by) if joined_by else ""

        try:
            cursor.execute(
                """
                INSERT OR REPLACE INTO opinions
                (opinion_id, case_id, cluster_id, type, author, author_id,
                 joined_by, html_text, plain_text, word_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    opinion["id"],
                    case_id,
                    cluster["id"],
                    opinion.get("type", ""),
                    opinion.get("author", ""),
                    opinion.get("author_id"),
                    joined_by_str,
                    html_text,
                    plain_text,
                    word_count,
                ),
            )
        except sqlite3.IntegrityError:
            pass  # Opinion already exists

    conn.commit()


def download_opinions(start_year=None, limit=None, max_workers=5, resume_only=False):
    """Main function to download Supreme Court opinions."""
    print("=" * 60)
    print("Supreme Court Opinions Downloader")
    print("Data source: CourtListener (Free Law Project)")
    if resume_only:
        print("Mode: Resume only (using local database)")
    print("=" * 60)

    # Check for API key
    if not COURTLISTENER_API_KEY:
        print("\n❌ ERROR: COURTLISTENER_API_KEY not found!")
        print("\nCourtListener requires an API token for access.")
        print("1. Create a free account at: https://www.courtlistener.com/sign-in/")
        print(
            "2. Get your API token at: https://www.courtlistener.com/help/api/rest/#authentication"
        )
        print("3. Add to your .env file: COURTLISTENER_API_KEY=your_token_here")
        return

    # Create session with headers
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "US-Laws-Project/1.0 (Educational/Research)",
            "Accept": "application/json",
            "Authorization": f"Token {COURTLISTENER_API_KEY}",
        }
    )

    # Create database
    print("\nCreating database...")
    conn = create_database()

    # Get existing cluster IDs to skip
    existing_ids = get_existing_cluster_ids(conn)
    if existing_ids:
        print(f"Found {len(existing_ids):,} existing cases in database")

    # Resume mode: skip API, use local database
    if resume_only:
        print("\nChecking for cases without opinions...")
        new_clusters = get_cases_without_opinions(conn)
        if not new_clusters:
            print("\n✅ All cases have opinions downloaded!")
            conn.close()
            return
        print(f"Found {len(new_clusters)} cases needing opinions")
    else:
        # Fetch clusters (cases) from API
        print(f"\nFetching Supreme Court cases...")
        if start_year:
            print(f"  Filtering: cases from {start_year} onward")
        if limit:
            print(f"  Limit: {limit} cases")

        clusters = get_opinion_clusters(session, start_year, limit)
        print(f"\nFound {len(clusters)} cases from API")

        # Filter out already-downloaded cases
        new_clusters = [c for c in clusters if c["id"] not in existing_ids]
        skipped_count = len(clusters) - len(new_clusters)

        if skipped_count > 0:
            print(f"Skipping {skipped_count:,} already-downloaded cases")

        if not new_clusters:
            print("\n✅ All cases already downloaded!")
            conn.close()
            return

    print(f"Downloading {len(new_clusters)} new cases with {max_workers} workers...")

    # Thread-safe progress tracking
    db_lock = threading.Lock()
    progress_lock = threading.Lock()
    completed = [0]  # Use list for mutable counter in closure
    failed = [0]

    def process_cluster(cluster):
        """Download and save a single cluster (thread-safe)."""
        cluster_id = cluster["id"]
        case_name = cluster.get("case_name_short", "") or cluster.get(
            "case_name", "Unknown"
        )

        try:
            opinions = get_opinions_for_cluster(session, cluster_id)

            # Use thread-local connection for database writes
            thread_conn = get_thread_connection()
            with db_lock:
                if opinions:
                    save_cluster_to_db(thread_conn, cluster, opinions)
                else:
                    # Save case even without opinions
                    save_cluster_to_db(thread_conn, cluster, [])

            with progress_lock:
                completed[0] += 1
                # Print progress every 10 cases or for first few
                if completed[0] <= 5 or completed[0] % 10 == 0:
                    print(
                        f"  [{completed[0]}/{len(new_clusters)}] {case_name[:40]} - {len(opinions)} opinion(s)"
                    )

            return (cluster_id, len(opinions), None)

        except Exception as e:
            with progress_lock:
                failed[0] += 1
            return (cluster_id, 0, str(e))

    # Process clusters in parallel
    print("\nDownloading opinions...")
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_cluster, cluster): cluster
            for cluster in new_clusters
        }

        for future in as_completed(futures):
            cluster = futures[future]
            try:
                result = future.result()
                if result[2]:  # Error occurred
                    case_name = cluster.get("case_name_short", "Unknown")
                    print(f"  ❌ Failed: {case_name[:30]} - {result[2]}")
            except Exception as e:
                case_name = cluster.get("case_name_short", "Unknown")
                print(f"  ❌ Exception: {case_name[:30]} - {e}")

    elapsed = time.time() - start_time

    # Print summary
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM cases")
    case_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM opinions")
    opinion_count = cursor.fetchone()[0]
    cursor.execute("SELECT SUM(word_count) FROM opinions")
    total_words = cursor.fetchone()[0] or 0

    print("\n" + "=" * 60)
    print("Download Complete!")
    print(f"  New cases downloaded: {completed[0]:,}")
    if failed[0] > 0:
        print(f"  Failed: {failed[0]:,}")
    print(f"  Time: {elapsed:.1f}s ({completed[0] / elapsed:.1f} cases/sec)")
    print(f"  Total cases in DB: {case_count:,}")
    print(f"  Total opinions: {opinion_count:,}")
    print(f"  Total words: {total_words:,}")
    print(f"  Database: {DB_PATH}")
    print("=" * 60)

    conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Download Supreme Court opinions from CourtListener"
    )
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=None,
        help="Maximum number of cases to download",
    )
    parser.add_argument(
        "--year",
        "-y",
        type=int,
        default=None,
        help="Start year (download cases from this year onward)",
    )
    parser.add_argument(
        "--workers",
        "-w",
        type=int,
        default=5,
        help="Number of parallel workers (default: 5)",
    )
    parser.add_argument(
        "--resume",
        "-r",
        action="store_true",
        help="Skip API pagination, only download opinions for cases already in DB",
    )

    args = parser.parse_args()
    download_opinions(
        start_year=args.year,
        limit=args.limit,
        max_workers=args.workers,
        resume_only=args.resume,
    )


if __name__ == "__main__":
    main()
