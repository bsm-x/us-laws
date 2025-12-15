# Setting up OpenAI Embeddings

## Step 1: Add Your API Key

Create a `.env` file in the project root:

```bash
# In: C:\Users\blake\OneDrive\Projects\us-laws\.env
OPENAI_API_KEY=sk-proj-your-actual-key-here
```

**Important**: Don't commit this file to git. It's already in .gitignore.

## Step 2: Stop Current Embedding Process

If you have the default embedding running, stop it (Ctrl+C) and delete the old database:

```bash
# Delete the old database (it used the wrong embedding model)
rm -rf data/vector_db
```

Or in PowerShell:

```powershell
Remove-Item -Recurse -Force data\vector_db
```

## Step 3: Run with OpenAI Embeddings

```bash
python scripts/processing/create_vector_db.py
```

## What Changed:

### Before (Free Model):

- Model: all-MiniLM-L6-v2
- Dimensions: 384
- Cost: $0
- Quality: Good
- Time: 10-30 minutes
- Hardware: Uses your CPU/GPU

### After (OpenAI):

- Model: text-embedding-3-large
- Dimensions: 3072 (8x more dimensions!)
- Cost: ~$3-5 for entire US Code
- Quality: Excellent (best available)
- Time: 15-30 minutes
- Hardware: Uses OpenAI's servers

## Cost Breakdown:

For ~60,000 sections, ~30M tokens total:

- **text-embedding-3-large**: $0.13 per 1M tokens
- **Total**: 30M × $0.00013 = **~$3.90**

This is a one-time cost. Searches are free after that.

## Benefits:

1. **Better accuracy** - Understands nuanced legal queries
2. **Better recall** - Finds relevant sections you might miss with keywords
3. **Legal understanding** - Pre-trained on diverse text including legal documents
4. **Dimensionality** - 3072 dimensions capture more semantic nuances

## Verify It's Working:

After creation completes, test it:

```bash
python scripts/processing/search_code.py "copyright protection duration"
```

The results should be highly relevant to copyright law even if the exact phrase isn't used.

## Troubleshooting:

**"OPENAI_API_KEY not found"**

- Make sure .env file exists in project root
- Check that it contains: `OPENAI_API_KEY=sk-...`
- No quotes needed around the key

**"Rate limit exceeded"**

- OpenAI has rate limits on API calls
- The script automatically batches requests
- If it fails, just run it again - it will resume

**"Insufficient credits"**

- Add credits to your OpenAI account
- Visit: https://platform.openai.com/account/billing

## Using the Database:

Once created, everything else works the same:

**Command line:**

```bash
python scripts/processing/search_code.py "your query"
```

**Web interface:**

```bash
python -m app.main
# Visit http://localhost:8000/search
```

The vector database stores the embedding model info, so searches will automatically use the same OpenAI model.
