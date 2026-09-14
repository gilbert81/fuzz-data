# Product Dev Brief: Curated Business-Pattern Library
**Project:** Multi-source semantic layer (Shopify + GA4) — Phase 3
**Status:** Draft for review
**Owner:** Gill

---

## 1. Context

The recipe (dlt → duckdb → BSL semantic layer → MCP) is proven end-to-end across two structurally
different sources. The next gap isn't ingestion or grounding — it's **metric coverage**. Right now
the semantic layer answers simple aggregates well (revenue, AOV, LTV) but has no support for the
handful of *pattern-shaped* questions that make up most of what a real business stakeholder actually
asks (retention, funnels, segmentation, etc).

A prior draft proposed a generic, parameterized "rolling metric, any grain, any partition" tool. That
was the wrong shape: it re-opens the exact governance risk the semantic layer exists to close down —
an agent with a flexible-enough tool is functionally back to writing its own SQL.

**Revised direction:** implement a small, named, curated library of well-understood business patterns
(per the "E-Commerce SQL Cookbook" reference), each exposed as its own governed semantic model — same
discipline as `customer_ltv`, not a general-purpose calculator.

---

## 2. Goal

Prove the semantic layer can correctly answer the small set of patterns that cover most real
stakeholder questions, without sacrificing governance (named, described, engine-computed — no agent-side
arithmetic on raw rows).

**Non-goals for this phase:**
- No generic/parameterized rolling-window tool (rejected — see above).
- No new data sources.
- No UI/front-door work (still MCP-only, per the existing distribution decision).

---

## 3. Pattern Inventory & Fit Assessment

| Pattern | Data availability | Decision |
|---|---|---|
| Repeat Rate & Time-to-2nd-Order | Shopify orders — data already in hand | **Build now** |
| Conversion Funnel | GA4 events — needs event_name check | **Build now, pending check** |
| Cohort Retention | Shopify orders + customers | Backlog |
| RFM Segmentation | Shopify orders | Backlog |
| Growth Accounting | Shopify orders | Backlog (overlaps with repeat-rate for demo purposes) |
| Sessionization | GA4 events | **Already solved** — `session_id` pulled directly from BigQuery, no build needed |
| Pareto / ABC Analysis | Needs SKU/line-item data | Not available — Shopify line items not currently ingested |
| Inventory Aging | Needs inventory + unit cost | Not available — outside current API scope |

This phase scopes to the two "Build now" rows only.

---

## 4. Jobs To Be Done

### JTBD 1 — Repeat Rate & Time-to-Second-Order (Shopify)

**Job:** *When a stakeholder asks "do customers come back, and how soon," the agent should return an
exact repeat-purchase rate and a median/percentile time-to-second-order, grounded in real order data —
not an approximation from `customer_ltv`'s existing repeat-customer count.*

**Tasks:**
- [x] Extend the existing order-level customer aggregation (already built for `customer_ltv`) to rank
      orders per customer using `ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY created_at)`.
- [x] Derive `repeat_rate` = customers with a 2nd order divided by customers with a 1st order.
- [x] Derive `days_to_second_order` per customer (2nd order timestamp minus 1st order timestamp).
- [x] Expose `median_days_to_second_order` and `p75_days_to_second_order` as measures (mirrors the
      cookbook's intervention-trigger logic — p75 is the operationally useful number, not just median).
- [x] Wrap as a new semantic model (`repeat_purchase_behavior` or similar), each dimension/measure with
      a `description=`, same as all other current models.
- [x] Verify against a manual query on the current seeded dataset before trusting it.

**Definition of Done:**
- `repeat_rate` matches a hand-computed value on the current seeded dataset.
- `median_days_to_second_order` returns a plausible number (not null, not negative, not absurdly large
  given the 90-day seed window).
- Agent, asked "how many customers come back and how long does it take," returns these numbers with no
  visible arithmetic reasoning in its own response — the engine computed them, not the model.

---

### JTBD 2 — Conversion Funnel (GA4)

**Job:** *When a stakeholder asks "where do we lose people between browsing and buying," the agent
should return funnel counts and stage-to-stage conversion percentages, computed once by the engine —
not reconstructed by the agent skimming raw event rows.*

**Tasks:**
- [ ] **Pre-check (blocking):** confirm `add_to_cart`, `begin_checkout`, and `purchase` all exist as
      distinct `event_name` values in the current GA4 dataset:
      ```sql
      SELECT DISTINCT event_name FROM ga4_sample.ga4_events ORDER BY 1;
      ```
      If any stage is missing, the funnel is not buildable against this dataset as-is — fall back to
      whichever stages are actually present, or flag as blocked.
- [ ] Build the per-user stage-flag aggregation (`MAX(CASE WHEN event_name = 'view_item' THEN 1 ELSE 0
      END)` pattern, per user) as the base ibis expression.
- [ ] Derive stage counts (`viewed`, `carted`, `checkout`, `purchased`) as measures.
- [ ] Derive stage-to-stage conversion percentages (`view_to_cart`, `cart_to_checkout`,
      `checkout_to_purchase`) using safe division (guard divide-by-zero — ibis equivalent of
      `SAFE_DIVIDE`).
- [ ] Wrap as a new semantic model (`conversion_funnel`), with descriptions on every measure explaining
      exactly what "conversion" means at each stage (per the grounding discipline already applied
      elsewhere — no ambiguous measure names this time; learn from the GA4 `unique_users` lesson).
- [ ] Verify against a manual query.

**Definition of Done:**
- Stage counts are monotonically decreasing (viewed ≥ carted ≥ checkout ≥ purchased) — a basic sanity
  check that catches an obviously broken join/filter.
- Conversion percentages match a hand-computed check on the current dataset.
- Agent, asked "where do we lose people in the funnel," returns stage percentages without needing a
  follow-up clarifying query — i.e. the model's dimensions/measures are self-explanatory enough that
  no `search_dimension_values`-style discovery round-trip is needed first.

---

## 5. Sequencing

1. Run the GA4 event_name pre-check first — it's blocking for JTBD 2 and takes seconds.
2. Build JTBD 1 (Repeat Rate) — lowest risk, builds directly on `customer_ltv`'s existing pattern.
3. Build JTBD 2 (Conversion Funnel) — pending pre-check passing.
4. Re-run the Antigravity/Claude test prompts against both new models, same grounding discipline as
   every prior model: compare agent output against a manual query before trusting it.
5. Add both to the combined `mcp_server.py` models dict.

**Explicitly deferred, revisit only if a real demo need arises:**
- Cohort Retention, RFM Segmentation, Growth Accounting (backlog, same "build patterns as named
  models" discipline applies whenever picked up).
- Pareto/ABC and Inventory Aging — blocked on data availability, would require expanding Shopify Admin
  API scope (line items, inventory) before any build work is possible.
- Generic parameterized rolling-window tool — rejected as a direction; if a genuine need for arbitrary
  grain/partition combinations emerges later, revisit as its own governed, validated tool rather than
  open-ended SQL access.

---

## 6. Governance Principle (carried forward, restated for this phase)

Every new pattern is:
- **Named** — a specific semantic model, not a parameter to a generic tool.
- **Described** — every dimension/measure has a `description=` explaining exactly what it computes and
  any known caveats (mirroring the fix already applied after the GA4 ambiguity incident).
- **Verified** — checked against a manual query before being trusted or demoed.
- **Bounded** — the agent can query it flexibly (any grouping, any filter BSL supports) but cannot
  invent a new calculation shape the pattern wasn't built for.