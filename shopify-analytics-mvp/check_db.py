import duckdb

# Connect to the DuckDB database
conn = duckdb.connect("shopify.duckdb")

print("--- TABLES IN 'shopify_data' SCHEMA ---")
# Query information_schema directly to find all tables created by dlt
tables = conn.sql(
    "SELECT table_name FROM information_schema.tables WHERE table_schema = 'shopify_data';"
).fetchall()

if tables:
    for (table_name,) in tables:
        # Exclude dlt internal state tables from the row count summary
        if not table_name.startswith("_dlt"):
            count = conn.sql(f"SELECT COUNT(*) FROM shopify_data.\"{table_name}\";").fetchone()[0]
            print(f"shopify_data.{table_name}: {count} rows")
else:
    print("No tables found in 'shopify_data' schema.")