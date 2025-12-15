# US Code Vector Database & Semantic Search

## Overview

This system creates a vector database of the entire US Code, enabling semantic search across all federal laws using natural language queries.

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Create Vector Database

```bash
python scripts/processing/create_vector_db.py
```

**What happens:**

- Parses all US Code XML files (~60,000 sections)
- Generates embeddings for each section
- Stores in local LanceDB database
- Takes 10-30 minutes depending on your computer
- Requires ~500MB disk space

### 3. Search Methods

#### Command Line Search

```bash
# Simple search
python scripts/processing/search_code.py "copyright protection duration"

# Get more results
python scripts/processing/search_code.py -n 20 "criminal penalties for fraud"

# Interactive mode
python scripts/processing/search_code.py
```

#### Web Interface

```bash
# Start web server
python -m app.main

# Visit http://localhost:8000/search
```

## How It Works

### Embeddings

- Uses OpenAI's text-embedding-3-small model
- Converts text into 1536-dimensional vectors
- Captures semantic meaning, not just keywords

### What Gets Embedded

Each section is embedded as:

```
{identifier}: {heading}

{full text of section}
```

Example:

```
17 USC 102: Subject matter of copyright: In general

Copyright protection subsists, in accordance with this title,
in original works of authorship fixed in any tangible medium...
```

### Search Process

1. Query is converted to embedding vector
2. LanceDB finds nearest neighbors (L2 distance)
3. Returns most semantically similar sections
4. Results sorted by relevance score

## Example Queries

### Business & Tax

- "tax deductions for home offices"
- "corporate tax rates and brackets"
- "depreciation rules for equipment"
- "business expense limitations"

### Criminal Law

- "penalties for insider trading"
- "wire fraud statutes and sentencing"
- "computer crime and hacking laws"
- "money laundering requirements"

### Intellectual Property

- "copyright protection duration"
- "patent infringement damages"
- "trademark registration process"
- "fair use doctrine"

### Employment & Labor

- "workplace discrimination laws"
- "minimum wage requirements"
- "overtime pay rules"
- "disability accommodation requirements"

### Immigration

- "visa requirements for employment"
- "asylum application process"
- "deportation proceedings"

### Healthcare

- "HIPAA privacy requirements"
- "Medicare coverage rules"
- "drug approval process"

## Database Structure

```
data/
  vector_db/
    uscode.lance/            # LanceDB table directory
      _versions/             # Version history
      _indices/              # Vector index files
      *.lance                # Data fragments (columnar format)
```

## Performance

- **Indexing time**: 10-30 minutes for all 54 titles
- **Search time**: <100ms per query
- **Accuracy**: High for semantic similarity
- **Memory**: ~2GB during indexing, ~500MB for database

## Advanced Usage

### Rebuild Database

```bash
# Delete old database
rm -rf data/vector_db

# Create new one
python scripts/processing/create_vector_db.py
```

### Custom Queries

```python
import lancedb
import openai

# Connect to database
db = lancedb.connect("data/vector_db")
table = db.open_table("uscode")

# Get embedding for query
client = openai.OpenAI()
response = client.embeddings.create(input=["your query"], model="text-embedding-3-small")
query_vector = response.data[0].embedding

# Search
results = table.search(query_vector).limit(10).to_list()

for r in results:
    print(f"{r['identifier']}: {r['heading']}")
```

### Filter by Metadata

```python
# Search only in specific title
results = table.search(query_vector).where("title = '17'").limit(10).to_list()
```

## Technical Details

### Embedding Model

- **Model**: OpenAI text-embedding-3-small
- **Dimensions**: 1536
- **Context window**: 8191 tokens
- **Language**: Multilingual
- **Speed**: ~100 sections/second (API limited)

### Vector Database

- **Engine**: LanceDB
- **Storage**: Columnar Lance format
- **Distance metric**: L2 (Euclidean)
- **Persistence**: Local filesystem

### Limitations

- Very long sections (>8000 chars) are truncated
- Embeddings are English-only
- No cross-title relationship understanding
- Relevance depends on query phrasing

## Troubleshooting

### "Vector database not found"

```bash
python scripts/processing/create_vector_db.py
```

### "No XML files found"

```bash
python scripts/download/download_full_code.py
# Choose option 1 to download all titles
```

### "Out of memory"

- Process titles one at a time
- Close other applications
- Reduce batch size in create_vector_db.py

### Poor search results

- Try rephrasing your query
- Use more specific legal terminology
- Try multiple related searches
- Check if the topic exists in federal law

## API Integration

### Use in Your Code

```python
from scripts.processing.search_code import search

# Get results as data
results = search("your query", n_results=5)

# Process results
for result in results:
    identifier = result['metadata']['identifier']
    heading = result['metadata']['heading']
    text = result['document']
    relevance = result['distance']
```

## Future Enhancements

- [x] Add founding documents to vector DB
- [x] GPT integration for Q&A
- [x] Claude integration for Q&A
- [ ] Multi-query search (combine multiple queries)
- [ ] Citation graph (link related sections)
- [ ] Historical version tracking
- [ ] Export results to PDF/Word
- [ ] Save favorite searches
- [ ] Highlight matching terms

## Resources

- [LanceDB Documentation](https://lancedb.github.io/lancedb/)
- [OpenAI Embeddings](https://platform.openai.com/docs/guides/embeddings)
- [US Code Website](https://uscode.house.gov/)
- [Congress.gov API](https://api.congress.gov/)
