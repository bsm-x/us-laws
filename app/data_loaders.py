"""
Data loading utilities with caching
Handles loading CSV data and caching parsed XML
"""

import csv
from pathlib import Path
from typing import List, Dict, Any, Optional

from app.config import get_settings

# Get settings
settings = get_settings()

# Cache for loaded data
_titles_cache: Optional[List[Dict[str, Any]]] = None
_uscode_cache: Dict[str, Any] = {}


def load_titles() -> List[Dict[str, Any]]:
    """Load US Code titles from CSV with caching"""
    global _titles_cache
    if _titles_cache is not None:
        return _titles_cache

    titles = []
    csv_path = settings.data_dir / "us_code_titles.csv" if settings.data_dir else None
    if csv_path and csv_path.exists():
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                titles.append(row)
    _titles_cache = titles
    return titles


def get_cached_uscode(title_num: int) -> Optional[Any]:
    """Get cached US Code data for a title"""
    return _uscode_cache.get(title_num)


def set_cached_uscode(title_num: int, data: Any) -> None:
    """Cache US Code data for a title"""
    _uscode_cache[title_num] = data


def clear_cache() -> None:
    """Clear all cached data"""
    global _titles_cache, _uscode_cache
    _titles_cache = None
    _uscode_cache = {}
