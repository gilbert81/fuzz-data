Here's a phased build list, scoped to just your dev store — no multi-tenant, no OAuth complexity.

**Phase 1: dlt (extraction + load)**

- [ ] Create a custom app in your dev store's admin (owner-only path — this still works, it's only broken for collaborators) and grab the Admin API access token.
- [ ] Install `dlt` and scaffold a pipeline pointed at duckdb as the destination.
- [ ] Seed the dev store with realistic data — Shopify's dev tools can generate sample orders/products/customers, or write a quick script to create 100–200 orders across a handful of customers and products so your metrics have something to chew on.
- [ ] Pull the four core resources: orders, customers, products, refunds. (Skip everything else — inventory, discounts, fulfillment — for now.)
- [ ] Run the pipeline once manually and confirm tables land in duckdb with sane row counts.

*Definition of done:* Running `python pipeline.py` populates a local duckdb file with orders/customers/products/refunds tables that match what you see in the Shopify admin — no manual data massaging needed to trust the numbers.

**Phase 2: duckdb (modeling)**

- [ ] Inspect the raw dlt tables — check types, nulls, nested JSON fields (line items, addresses) that dlt may have flattened into child tables.
- [ ] Write staging views/tables that clean and rename fields into a consistent schema (this is where you'd lean on the dlt-dbt-shopify mart models as a template rather than designing from scratch).
- [ ] Build a small set of mart tables: `fct_orders`, `dim_customers`, `dim_products` — enough to support the 10–15 metrics from your wedge (revenue, AOV, refund rate, repeat customer rate, LTV).
- [ ] Add a basic dbt project (or plain SQL scripts if you want to skip dbt for now) so the transformation is repeatable, not one-off queries.
- [ ] Re-run the whole thing from scratch once (drop duckdb file, re-pipeline, re-transform) to confirm it's reproducible.

*Definition of done:* You can run one command (or a two-step `dlt run` → `dbt run`) from a clean state and get fully-populated mart tables in duckdb that a human could hand-query in SQL and get correct answers to "what was revenue last month" or "who are my top 10 customers by spend."

**Phase 3: Semantic layer (Cube on duckdb)**

- [ ] Install Cube Core and point it at your duckdb file.
- [ ] Define your first 3–5 metrics in Cube's schema (start narrow: revenue, order count, AOV, refund rate, repeat customer rate) mapped to the mart tables from Phase 2.
- [ ] Add the basic dimensions you'll need to slice by (date, customer, product, channel if you have it).
- [ ] Query Cube directly (via its playground UI or REST API) and manually verify a couple of numbers against what you'd get running raw SQL on the mart tables — this is your grounding-accuracy check.
- [ ] Turn on Cube's MCP endpoint and confirm you can hit it with an MCP client (even a basic test script) and get the same verified numbers back.

*Definition of done:* You can ask Cube (via MCP or its API) "what was total revenue last month" and get back a number that matches your manual SQL check exactly — proving the semantic layer is grounding correctly, not just returning plausible-looking output.

Once these three phases are done, you'll have the full recipe working end-to-end against real (if synthetic-ish) data — that's the point where it's worth wiring in the agent layer on top and starting to think about the first real design-partner conversation.