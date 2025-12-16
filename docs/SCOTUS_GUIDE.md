# Supreme Court Opinions Guide

This document describes how to download, search, and browse Supreme Court opinions in the US Laws application.

## Overview

The Supreme Court integration provides:

- **Download Script** - Fetches opinions from CourtListener's free API
- **Vector Search** - Semantic search across opinion text
- **Web Browser** - Browse and view opinions by year/case
- **RAG Integration** - AI answers now include relevant SCOTUS opinions

## Data Source: CourtListener

[CourtListener](https://www.courtlistener.com/) is a free, open database of court opinions maintained by the Free Law Project. Their REST API provides access to:

- All Supreme Court opinions (majority, concurrence, dissent, etc.)
- Case metadata (names, dates, citations, docket numbers)
- Full opinion text (plain text format)

**API Information:**

- Base URL: `https://www.courtlistener.com/api/rest/v4/`
- Rate Limit: 5,000 requests/hour
- **Authentication Required**: Free API token needed
- Documentation: [courtlistener.com/api](https://www.courtlistener.com/api/)

## Quick Start

### 0. Get CourtListener API Token (Required)

CourtListener requires authentication to access their API:

1. Create a free account at [courtlistener.com/sign-in](https://www.courtlistener.com/sign-in/)
2. Get your API token from [API Help](https://www.courtlistener.com/help/api/rest/#authentication)
3. Add to your `.env` file:

```bash
COURTLISTENER_API_KEY=your_token_here
```

### 1. Download SCOTUS Opinions

```bash
# Download all available opinions (may take several hours)
python scripts/download/download_scotus_opinions.py

# Or download a limited number for testing
python scripts/download/download_scotus_opinions.py --limit 500

# Filter by year
python scripts/download/download_scotus_opinions.py --year 2020
```

This creates:

- `data/scotus/scotus_opinions.db` - SQLite database with cases and opinions

### 2. Add to Vector Database

```bash
python scripts/processing/add_scotus_to_vector_db.py
```

This adds opinions to LanceDB for semantic search alongside US Code.

### 3. Run the Application

```bash
python -m app.main
```

Visit [http://localhost:8000/scotus](http://localhost:8000/scotus) to browse opinions.

## Database Schema

The SQLite database (`data/scotus/scotus_opinions.db`) has two tables:

### `cases` Table

| Column             | Type    | Description                              |
| ------------------ | ------- | ---------------------------------------- |
| id                 | INTEGER | Primary key                              |
| cluster_id         | INTEGER | CourtListener cluster ID (unique)        |
| case_name          | TEXT    | Full case name                           |
| case_name_short    | TEXT    | Short case name for display              |
| date_filed         | TEXT    | Decision date (YYYY-MM-DD)               |
| citation           | TEXT    | Official citation (e.g., "347 U.S. 483") |
| docket_number      | TEXT    | Supreme Court docket number              |
| judges             | TEXT    | List of justices                         |
| syllabus           | TEXT    | Case syllabus (if available)             |
| procedural_history | TEXT    | Procedural history                       |
| attorneys          | TEXT    | Attorneys of record                      |

### `opinions` Table

| Column     | Type    | Description              |
| ---------- | ------- | ------------------------ |
| id         | INTEGER | Primary key              |
| case_id    | INTEGER | Foreign key to cases.id  |
| opinion_id | INTEGER | CourtListener opinion ID |
| type       | TEXT    | Opinion type (see below) |
| author     | TEXT    | Author justice name      |
| plain_text | TEXT    | Full text of the opinion |
| word_count | INTEGER | Word count               |

### Opinion Types

| Code                 | Label                |
| -------------------- | -------------------- |
| 010combined          | Opinion of the Court |
| 015unanimous         | Unanimous Opinion    |
| 020lead              | Lead Opinion         |
| 025plurality         | Plurality Opinion    |
| 030concurrence       | Concurring Opinion   |
| 035concurrenceinpart | Concurring in Part   |
| 040dissent           | Dissenting Opinion   |
| 045dissentinpart     | Dissenting in Part   |
| 050addendum          | Addendum             |
| 060rehearing         | Rehearing            |

## Web Interface

### Browse Cases

Navigate to `/scotus` to browse all cases with:

- Search by case name
- Filter by year
- Pagination

### View Case Details

Click on any case to see:

- Full case metadata
- Syllabus (if available)
- All opinions (majority, concurrence, dissent)
- Expandable full opinion text
- Link to CourtListener for more details

## RAG Integration

When you ask a question on the AI Search page, the system now searches both:

1. **US Code** - Federal statutes
2. **SCOTUS Opinions** - Supreme Court case law

Results are ranked by relevance and combined. The AI will cite both statutes and case law in its answers.

### Example Query

**Question:** "What are the constitutional limits on police searches?"

The AI might cite:

- **US Code** sections on search and seizure rules
- **SCOTUS** cases like _Mapp v. Ohio_, _Terry v. Ohio_

## Citation Popups

When viewing AI answers:

- Click on `[1]`, `[2]` citation markers to see source text
- US Code sources link to uscode.house.gov
- SCOTUS sources link to CourtListener

## Files Created

```
us-laws/
├── scripts/
│   ├── download/
│   │   └── download_scotus_opinions.py   # Download script
│   └── processing/
│       └── add_scotus_to_vector_db.py    # Vector DB script
├── data/
│   └── scotus/
│       └── scotus_opinions.db            # SQLite database
├── app/
│   └── routers/
│       └── scotus.py                     # Web router
└── docs/
    └── SCOTUS_GUIDE.md                   # This file
```

## API Endpoints

| Endpoint               | Method | Description              |
| ---------------------- | ------ | ------------------------ |
| `/scotus`              | GET    | Browse cases (paginated) |
| `/scotus?year=2020`    | GET    | Filter by year           |
| `/scotus?search=Brown` | GET    | Search by case name      |
| `/scotus/case/{id}`    | GET    | View specific case       |

## Limitations

- **Text Only**: Some opinions may lack full text
- **Historical Coverage**: Older cases may have incomplete metadata
- **No PDF**: Only plain text is stored (no original documents)
- **Rate Limits**: CourtListener has request limits

## Troubleshooting

### "Database Not Found"

Run the download script first:

```bash
python scripts/download/download_scotus_opinions.py --limit 100
```

### "No SCOTUS results in RAG"

Add opinions to the vector database:

```bash
python scripts/processing/add_scotus_to_vector_db.py
```

### Slow Downloads

The API has rate limits. The script includes delays to avoid hitting them. For faster downloads, consider using their bulk data exports instead.

## Future Enhancements

- [ ] Extract case citations to other cases
- [ ] Link citations to US Code sections
- [ ] Add opinion-to-statute citation graph
- [ ] Support for other federal courts
