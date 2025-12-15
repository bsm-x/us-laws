"""
Compact and clean up the LanceDB vector database
Removes old versions and reclaims disk space

Run with: python scripts/processing/compact_vector_db.py
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import lancedb

try:
    from app.config import get_settings

    settings = get_settings()
    VECTOR_DB_DIR = settings.vector_db_dir
except ImportError:
    VECTOR_DB_DIR = PROJECT_ROOT / "data" / "vector_db"


def get_dir_size(path: Path) -> int:
    """Get total size of directory in bytes"""
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def compact_database():
    print("=" * 60)
    print("LANCEDB COMPACTION & CLEANUP")
    print("=" * 60)

    lance_dir = VECTOR_DB_DIR / "uscode.lance"

    if not lance_dir.exists():
        print(f"ERROR: Database not found at {lance_dir}")
        return

    # Get size before
    size_before = get_dir_size(lance_dir)
    print(f"\nDatabase location: {VECTOR_DB_DIR}")
    print(f"Size before: {size_before / (1024*1024):.1f} MB")

    # Connect and open table
    print("\nConnecting to database...")
    db = lancedb.connect(str(VECTOR_DB_DIR))
    table = db.open_table("uscode")

    row_count = table.count_rows()
    print(f"Current row count: {row_count:,}")

    # Compact files (merge small fragments) using the optimize API
    print("\nCompacting files...")
    try:
        # Convert to lance table for optimization
        lance_table = table.to_lance()
        stats = lance_table.optimize.compact_files()
        print(f"  Fragments removed: {stats.fragments_removed}")
        print(f"  Fragments added: {stats.fragments_added}")
    except (AttributeError, ImportError) as e:
        print(f"  Skipping compaction: {e}")

    # Clean up old versions
    print("\nCleaning up old versions...")
    try:
        lance_table = table.to_lance()
        lance_table.cleanup_old_versions()
        print("  Old versions removed.")
    except (AttributeError, ImportError) as e:
        print(f"  Skipping version cleanup: {e}")

    # Get size after
    size_after = get_dir_size(lance_dir)
    saved = size_before - size_after

    print("\n" + "-" * 60)
    print("RESULTS:")
    print("-" * 60)
    print(f"  Size before:  {size_before / (1024*1024):.1f} MB")
    print(f"  Size after:   {size_after / (1024*1024):.1f} MB")
    print(
        f"  Space saved:  {saved / (1024*1024):.1f} MB ({100*saved/size_before:.1f}%)"
    )
    print(f"  Row count:    {table.count_rows():,} (unchanged)")

    print("\n" + "=" * 60)
    print("COMPACTION COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    compact_database()
