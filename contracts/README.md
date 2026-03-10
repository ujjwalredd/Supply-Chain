# Data Contracts (Soda Core)

Quality checks enforced at each medallion layer.

## Run locally
```bash
pip install soda-core soda-core-postgres
soda scan -d supply_chain_db -c contracts/soda_connection.yml contracts/orders.yml
```

## Files
- `orders.yml` - Production orders table: nulls, dupes, enum validity, freshness
- `silver_orders.yml` - Silver layer Parquet: structural integrity
- `soda_connection.yml` - DB connection config (reads env vars)
