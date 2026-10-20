# RAG Insight Agent

Phase 3A deliverable: A cited explanation system for Environmental Protection Officers.

## Overview

The RAG (Retrieval-Augmented Generation) Insight Agent provides answers about air quality and PM2.5 forecasting by:

1. **Retrieving context** from trusted document sources (WHO, Pakistan EPA, etc.)
2. **Querying data** from the DuckDB warehouse when relevant
3. **Generating cited answers** with source attribution and row IDs

## Key Features

✅ **Trusted Sources**: Corpus built from 4 authoritative PDF documents  
✅ **Data Integration**: Queries the gold forecast features table for real measurements  
✅ **Citation Tracking**: Every claim cites its source (document + page number)  
✅ **Row ID Traceability**: All data-backed numbers include warehouse row IDs  
✅ **Honest Uncertainty**: Returns "I don't know" for unknown questions

## Setup

### 1. Install Dependencies

```bash
pip install chromadb sentence-transformers pdfplumber
```

### 2. Build the Corpus

```bash
python -m src.rag.corpus_builder
```

This will:
- Process all PDFs in `corpus/`
- Chunk documents into ~500 character segments
- Generate embeddings using sentence-transformers
- Store in ChromaDB at `corpus/chroma_db/`

**Expected output:**
```
Found 4 PDF files
Processing who_air_quality_guidelines.pdf...
  Created 45 chunks from who_air_quality_guidelines.pdf
...
✓ Corpus built successfully!
  Total documents in collection: 178
```

### 3. Verify Warehouse Exists

The agent needs the processed data warehouse:

```bash
# Should exist from Phase 2A
ls data/processed/warehouse.duckdb
```

If not, run: `make data` or `python -m src.process.build_processed`

## Usage

### Interactive Mode

```bash
python -m src.rag.query_agent
```

Ask questions like:
- "What PM2.5 level is unhealthy?"
- "What's the current PM2.5 in Lahore?"
- "What are WHO air quality guidelines?"

### Single Question Mode

```bash
python -m src.rag.query_agent --question "What causes high PM2.5 in Lahore?"
```

### Programmatic Usage

```python
from src.rag.query_agent import InsightAgent

agent = InsightAgent()
response = agent.generate_answer("What is PM2.5?")

print(response['answer'])
print(f"Citations: {response['citations']}")
print(f"Row IDs: {response['row_ids']}")
```

## Testing

Run the test suite to verify all Phase 3A requirements:

```bash
python -m src.rag.test_agent
```

**Tests:**
1. ✅ Citation Test - Cites WHO and trusted sources
2. ✅ Row ID Test - Returns warehouse row IDs for data claims
3. ✅ Unknown Query Test - Admits "I don't know" appropriately
4. ✅ Additional Scenarios - Multi-city, health impacts, guidelines

## Demo

See the agent in action:

```bash
python -m src.rag.demo
```

Shows 5 example questions with full responses, citations, and row IDs.

## Architecture

### Components

```
src/rag/
├── corpus_builder.py   # PDF processing & vector DB creation
├── query_agent.py      # Main agent with RAG logic
├── test_agent.py       # Test suite
├── demo.py            # Example usage
└── README.md          # This file
```

### Data Flow

```
User Question
    ↓
[Retrieve Context]  ← ChromaDB (embedded documents)
    ↓
[Check for Data Need]
    ↓
[Query Warehouse]   ← DuckDB (gold_forecast_features)
    ↓
[Generate Answer]
    ↓
Response with:
  - answer (text)
  - citations (source + page)
  - row_ids (warehouse traceability)
  - data_points (count)
```

### Decision Logic

| Question Type | Action | Output |
|--------------|--------|--------|
| Data query (PM2.5 levels) | Query warehouse + retrieve docs | Numbers with row IDs + health context |
| General knowledge (guidelines) | Retrieve docs only | Answer from documents with citations |
| Unknown topic | Return "I don't know" | Honest admission |

## Example Responses

### Data-Backed Query

**Q:** "What's the PM2.5 level in Lahore?"

**A:** 
```
Based on sensor data (row IDs: [45231, 45232, 45233, ...]), 
PM2.5 levels in Lahore averaged 87.3 μg/m³ (range: 65.2 - 112.8 μg/m³).

According to who_air_quality_guidelines.pdf (p.3): 
"Levels above 55 μg/m³ are considered unhealthy for all population groups..."

📊 Data points: 24
🔗 Row IDs: [45231, 45232, 45233, 45234, 45235, ...]
📚 Sources:
   - who_air_quality_guidelines.pdf (page 3)
   - lahore_air_quality_report_2024.pdf (page 12)
```

### Document-Based Query

**Q:** "What are the health effects of PM2.5?"

**A:**
```
According to health_impacts_pm25.pdf (p.5): 
"Fine particulate matter (PM2.5) can penetrate deep into the lungs and 
bloodstream, causing cardiovascular and respiratory diseases, and premature 
mortality. Short-term exposure increases hospital admissions..."

📚 Sources:
   - health_impacts_pm25.pdf (page 5)
   - who_air_quality_guidelines.pdf (page 8)
```

### Unknown Query

**Q:** "What's the weather on Mars?"

**A:**
```
I don't know. I don't have information about that in my trusted sources 
or data warehouse.
```

## Success Criteria (Phase 3A)

| Criterion | Status |
|----------|--------|
| Corpus has ≥3 trusted documents | ✅ 4 documents |
| Every number comes with row IDs | ✅ Implemented |
| Unknown questions return "I don't know" | ✅ Implemented |
| All claims cite sources | ✅ Source + page number |

## Troubleshooting

### "ChromaDB not found"
Run `python -m src.rag.corpus_builder` first.

### "Warehouse not found"
Run `make data` or `python -m src.process.build_processed`.

### "No data for that date"
The warehouse contains historical data. Queries for future dates will return "I don't know".

### Empty responses
Check that PDFs are in `corpus/` and contain extractable text.

## Configuration

### Chunk Size
Edit `corpus_builder.py`:
```python
chunk_size=500  # characters per chunk
overlap=50      # overlap between chunks
```

### Retrieval Count
Edit `query_agent.py`:
```python
n_results=3  # number of document chunks to retrieve
```

### Embedding Model
Default: `all-MiniLM-L6-v2` (fast, lightweight)

For better accuracy, use: `all-mpnet-base-v2` (slower, larger)

## Performance

- **Corpus build time**: ~30 seconds for 4 PDFs
- **Query latency**: ~200ms per question
- **Storage**: ~5MB for ChromaDB index
- **Memory**: ~300MB for model + embeddings

## Next Steps (Phase 3B-3D)

- [ ] **Phase 3B**: Integrate into Prefect pipeline for automated insights
- [ ] **Phase 3C**: Add FastAPI endpoint `/api/agent/ask`
- [ ] **Phase 3D**: Add to React dashboard as chat interface

## References

- ChromaDB: https://www.trychroma.com/
- Sentence Transformers: https://www.sbert.net/
- PDFPlumber: https://github.com/jsvine/pdfplumber
