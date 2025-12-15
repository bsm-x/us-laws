# Citation Graph

## Overview

The Citation Graph feature maps how US Code sections reference each other. This creates a network showing:
- Which sections are most frequently cited (authoritative)
- Which sections cite the most others (comprehensive)
- How different parts of federal law interconnect

## Statistics

- **187,395** total citations parsed
- **43,148** unique sections indexed
- Covers all 54 titles of the US Code

## Building the Citation Graph

```bash
python scripts/processing/build_citation_graph.py
```

This script:
1. Parses all US Code XML files
2. Extracts cross-references using regex patterns
3. Builds a SQLite database at `data/citations.db`
4. Takes 2-5 minutes to complete

## Database Schema

The citation graph uses SQLite with two tables:

### `citations` Table
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| source_section | TEXT | Section making the citation (e.g., "17 USC 101") |
| target_section | TEXT | Section being cited (e.g., "17 USC 102") |

### `sections` Table
| Column | Type | Description |
|--------|------|-------------|
| identifier | TEXT | Section identifier (primary key) |
| cited_by_count | INTEGER | How many times this section is cited |
| cites_count | INTEGER | How many sections this cites |

## Web Interface

Visit http://localhost:8000/citations

### Features

1. **Statistics Dashboard**
   - Total citations count
   - Total sections indexed

2. **Section Lookup**
   - Enter a section identifier (e.g., "17 USC 101")
   - See all sections that cite it
   - See all sections it cites

3. **Most Cited Sections**
   - Top 10 most-referenced sections
   - Shows citation count for each
   - Click to view the section

4. **Most Citing Sections**
   - Top 10 sections with most outgoing references
   - Useful for finding comprehensive overview sections

## API Endpoints

### Get Citation Graph Status
```bash
GET /citations/status
```
Returns total citations and sections count.

### Lookup Citations for a Section
```bash
GET /citations/lookup?section=17+USC+101
```
Returns sections that cite the given section and sections it cites.

### Get Most Cited Sections
```bash
GET /citations/most-cited?limit=10
```
Returns the most frequently cited sections.

### Get Most Citing Sections
```bash
GET /citations/most-citing?limit=10
```
Returns sections that cite the most other sections.

## Integration with AI Search

When viewing a US Code section page, the sidebar shows:
- **Cited By**: Sections that reference this one
- **Cites**: Sections this one references

This helps understand the legal context and related provisions.

## Citation Patterns Detected

The parser recognizes these reference formats:
- `section 101 of title 17`
- `17 U.S.C. 101`
- `title 17, United States Code`
- `section 101(a)(1)`
- Cross-title references

## Use Cases

1. **Legal Research**: Find authoritative sections frequently referenced
2. **Impact Analysis**: See what other laws depend on a section
3. **Navigation**: Discover related provisions through citations
4. **Understanding Structure**: See how different titles interconnect

## Technical Details

### Regex Patterns Used

```python
# Title and section pattern
r'(?:section|§)\s*(\d+[a-zA-Z0-9\-]*)\s+of\s+title\s+(\d+)'

# USC format
r'(\d+)\s*U\.?S\.?C\.?\s*(?:§\s*)?(\d+[a-zA-Z0-9\-]*)'
```

### Performance

- Initial build: 2-5 minutes
- Database size: ~15MB
- Query time: <10ms for most lookups

## Limitations

- Only captures explicit statutory citations
- Does not include regulatory references (CFR)
- Does not track case law citations
- Some complex citation formats may be missed
