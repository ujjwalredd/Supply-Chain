---
name: data-ingestion
description: Auto-ingest new customer CSV files — schema inference, loader generation, validation
---

## System Context

The DataIngestionAgent watches `/data/source/` every 60 seconds.
Known files tracked in Redis SET `ingestion:known_files`.
Generated loaders saved to `/data/source/_loaders/<table_name>.py`.

## Built-in Files (pre-registered, always skip)

orderlist.csv, freightrates.csv, whcapacities.csv, plantports.csv,
productsperplant.csv, supplifySupplychain.csv, vmicustomers.csv, whcosts.csv, manifest.txt

## Schema Inference Process

1. Read 10-row sample from the CSV
2. Call Claude `infer_csv_schema` tool_use → get table_name, columns[], loader_code
3. Run loader through CodeExecutor 5-gate validation:
   - Gate 1: Python syntax check
   - Gate 2: Subprocess execution on sample
   - Gate 3: Output key validation
   - Gate 4: Schema type check
   - Gate 5: Timeout kill (10s)
4. If validation fails → retry once with error context
5. If second attempt fails → alert MEDIUM, skip file

## Common CSV Loader Patterns

For standard CSVs:
```python
def load_csv(path: Path) -> Iterator[dict]:
    import csv
    with open(path, encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield {k: v.strip() if v else None for k, v in row.items()}
```

For CSVs with type coercion:
```python
def load_csv(path: Path) -> Iterator[dict]:
    import csv
    from datetime import datetime
    with open(path, encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield {
                'order_id': row.get('OrderID', '').strip() or None,
                'quantity': int(row['Quantity']) if row.get('Quantity', '').strip() else 0,
                'order_date': datetime.strptime(row['Date'], '%Y-%m-%d') if row.get('Date', '').strip() else None,
            }
```

## Validation Rules

- The loader MUST be named `load_csv`
- Return type must be Iterator[dict] (use `yield`)
- Must handle empty/null values without raising exceptions
- All imports must be from Python stdlib only (no pip packages)
- No print statements
- Max 50 lines of loader code

## After Successful Ingestion

1. Loader saved to `/data/source/_loaders/<table>.py`
2. Metadata saved to `/data/source/_loaders/<table>.json`
3. `medallion_full_pipeline` triggered in Dagster
4. Audit log entry: `NEW_FILE_INGESTED` with table name and columns

## Diagnosing Ingestion Failures

- `"Loader validation failed"` → Claude-generated code has bugs → retry with error context
- `"Empty file"` → CSV is empty or header-only → skip and alert
- `"Schema inference failed"` → LLM API error → check ANTHROPIC_API_KEY env var
- `"Pipeline trigger failed"` → Dagster webserver down → dagster_guardian will handle pipeline

## Critical Rules

- NEVER mark a file as known unless ingestion fully succeeded
- NEVER run loader code outside the CodeExecutor sandbox
- A file being skipped does NOT mean it was processed — it means it failed and will be retried
