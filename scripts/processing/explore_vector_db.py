"""
Explore and visualize the LanceDB vector database
Run with: python scripts/processing/explore_vector_db.py
"""

import sys
from pathlib import Path
from collections import Counter

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import lancedb
import pandas as pd

try:
    from app.config import get_settings

    settings = get_settings()
    VECTOR_DB_DIR = settings.vector_db_dir
except ImportError:
    VECTOR_DB_DIR = PROJECT_ROOT / "data" / "vector_db"


def explore_database():
    print("=" * 70)
    print("LANCEDB VECTOR DATABASE EXPLORER")
    print("=" * 70)

    # Connect to database
    print(f"\nDatabase location: {VECTOR_DB_DIR}")
    db = lancedb.connect(str(VECTOR_DB_DIR))

    # List all tables
    tables = db.table_names()
    print(f"\nTables in database: {tables}")

    # Open the main table
    table = db.open_table("uscode")
    row_count = table.count_rows()
    print(f"\nTotal rows in 'uscode' table: {row_count:,}")

    # Get schema
    print("\n" + "-" * 70)
    print("TABLE SCHEMA:")
    print("-" * 70)
    schema = table.schema
    for field in schema:
        print(f"  {field.name}: {field.type}")

    # Sample some data (without the huge vector column)
    print("\n" + "-" * 70)
    print("SAMPLE RECORDS (first 5):")
    print("-" * 70)

    # Convert to pandas for easy viewing
    df = table.to_pandas()

    # Show sample without vector column
    sample = df[["identifier", "heading", "title", "text_length"]].head(5)
    print(sample.to_string(index=False))

    # Distribution by title
    print("\n" + "-" * 70)
    print("DOCUMENTS BY TITLE (top 15):")
    print("-" * 70)

    title_counts = df["title"].value_counts().head(15)
    for title, count in title_counts.items():
        bar = "█" * min(50, count // 100)
        print(f"  Title {title:>20}: {count:>5,} {bar}")

    # Founding Documents
    print("\n" + "-" * 70)
    print("FOUNDING DOCUMENTS:")
    print("-" * 70)

    founding = df[df["title"] == "Founding Documents"]
    if len(founding) > 0:
        for _, row in founding.iterrows():
            print(f"  • {row['identifier'][:60]}")
            print(f"    Heading: {row['heading'][:50]}")
            print(f"    Text length: {row['text_length']:,} chars")
            print()
    else:
        print("  No founding documents found in database.")

    # Text length statistics
    print("-" * 70)
    print("TEXT LENGTH STATISTICS:")
    print("-" * 70)
    print(f"  Min:    {df['text_length'].min():,} chars")
    print(f"  Max:    {df['text_length'].max():,} chars")
    print(f"  Mean:   {df['text_length'].mean():,.0f} chars")
    print(f"  Median: {df['text_length'].median():,.0f} chars")

    # Vector dimensions
    print("\n" + "-" * 70)
    print("VECTOR INFORMATION:")
    print("-" * 70)
    sample_vector = df["vector"].iloc[0]
    print(f"  Dimensions: {len(sample_vector)}")
    print(
        f"  Sample values: [{sample_vector[0]:.4f}, {sample_vector[1]:.4f}, {sample_vector[2]:.4f}, ...]"
    )

    # Storage size
    print("\n" + "-" * 70)
    print("STORAGE:")
    print("-" * 70)
    lance_dir = VECTOR_DB_DIR / "uscode.lance"
    if lance_dir.exists():
        total_size = sum(f.stat().st_size for f in lance_dir.rglob("*") if f.is_file())
        print(f"  Database size: {total_size / (1024*1024):.1f} MB")

    print("\n" + "=" * 70)
    print("EXPLORATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    explore_database()
