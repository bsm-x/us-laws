# US Code Vector Database & Semantic Search

## Overview

This system creates a vector database of the entire US Code, enabling semantic search across all federal laws using natural language queries.

## Quick Start

### 1. Install ChromaDB

```bash
pip install chromadb
```

### 2. Create Vector Database

```bash
python create_vector_db.py
```

**What happens:**

- Parses all US Code XML files (~60,000 sections)
- Generates embeddings for each section
- Stores in local ChromaDB database
- Takes 10-30 minutes depending on your computer
- Requires ~500MB disk space

### 3. Search Methods

#### Command Line Search

```bash
# Simple search
python search_code.py "copyright protection duration"

# Get more results
python search_code.py -n 20 "criminal penalties for fraud"

# Interactive mode
python search_code.py
```

#### Web Interface

```bash
# Start web server
python app.py

# Visit http://localhost:8000/search
```

## How It Works

### Embeddings

- Uses ChromaDB's default embedding function (all-MiniLM-L6-v2)
- Converts text into 384-dimensional vectors
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
2. ChromaDB finds nearest neighbors (cosine similarity)
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
    chroma.sqlite3           # SQLite database
    [uuid]/                  # Embedding data
      data_level0.bin
      header.bin
      length.bin
      link_lists.bin
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
python create_vector_db.py
```

### Custom Queries

```python
import chromadb
from pathlib import Path

client = chromadb.PersistentClient(path="data/vector_db")
collection = client.get_collection("uscode")

results = collection.query(
    query_texts=["your query here"],
    n_results=10
)

for doc, meta in zip(results['documents'][0], results['metadatas'][0]):
    print(f"{meta['identifier']}: {meta['heading']}")
```

### Filter by Metadata

```python
# Search only in specific title
results = collection.query(
    query_texts=["copyright"],
    where={"identifier": {"$regex": "^17 USC"}}
)
```

## Technical Details

### Embedding Model

- **Model**: sentence-transformers/all-MiniLM-L6-v2
- **Dimensions**: 384
- **Context window**: 512 tokens
- **Language**: English
- **Speed**: ~1000 sections/minute

### Vector Database

- **Engine**: ChromaDB
- **Storage**: SQLite + HNSW index
- **Distance metric**: Cosine similarity
- **Persistence**: Local filesystem

### Limitations

- Very long sections (>8000 chars) are truncated
- Embeddings are English-only
- No cross-title relationship understanding
- Relevance depends on query phrasing

## Troubleshooting

### "Vector database not found"

```bash
python create_vector_db.py
```

### "No XML files found"

```bash
python download_full_code.py
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
from search_code import search

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

- [ ] Add founding documents to vector DB
- [ ] Multi-query search (combine multiple queries)
- [ ] Citation graph (link related sections)
- [ ] Historical version tracking
- [ ] GPT integration for Q&A
- [ ] Export results to PDF/Word
- [ ] Save favorite searches
- [ ] Highlight matching terms

## Resources

- [ChromaDB Documentation](https://docs.trychroma.com/)
- [Sentence Transformers](https://www.sbert.net/)
- [US Code Website](https://uscode.house.gov/)
- [Congress.gov API](https://api.congress.gov/)
