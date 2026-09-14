"""
Semantic model definitions for the pedal-mania Shopify data.
Adjust column names below to match your actual `DESCRIBE` output.
"""

import ibis
from boring_semantic_layer import Dimension, Measure, to_semantic_table


def get_connection(read_only: bool = True):
    return ibis.duckdb.connect("shopify.duckdb", read_only=read_only)


def build_models():
    con = get_connection()

    orders_tbl = con.table("orders", database="shopify_data")
    customers_tbl = con.table("customers", database="shopify_data")

    # --- Orders: revenue, AOV, refund rate ---
    orders = (
        to_semantic_table(orders_tbl, name="orders")
        .with_dimensions(
            order_id=lambda t: t.id,
            customer_id=lambda t: t.customer__id,   # confirmed: BIGINT, dlt-flattened
            created_at=lambda t: t.created_at,
            processed_at=lambda t: t.processed_at, # business order timestamp (preserves historical/backdated dates)
            financial_status=lambda t: t.financial_status,
        )
        .with_measures(
            order_count=lambda t: t.count(),
            # total_price comes back as VARCHAR from Shopify's API — cast before aggregating
            revenue=lambda t: t.total_price.cast("double").sum(),
            aov=lambda t: t.total_price.cast("double").mean(),
            refunded_orders=lambda t: t.financial_status.isin(
                ["refunded", "partially_refunded"]
            ).sum(),
        )
    )

    # --- Customer purchase behavior, derived from orders directly ---
    # NOTE: deliberately NOT using customers.orders_count / customers.total_spent —
    # those are Shopify-precomputed rollups that silently exclude test orders
    # (and possibly other edge cases). Deriving from the orders table itself
    # is the source-of-truth approach and matches what we verified manually.
    #
    # TIMESTAMP NOTE: In Shopify's Orders API, custom timestamps provided during
    # order creation/import are recorded in `processed_at`. Shopify's internal server
    # clock always overwrites `created_at` with the actual API insertion time.
    # Thus `processed_at` is the authoritative business transaction date (spanning
    # the 90-day window), whereas `created_at` clusters around the script runtime.
    orders_base = orders_tbl.filter(orders_tbl.customer__id.notnull()).select(
        "id", "customer__id", "created_at", "processed_at", "total_price"
    )
    orders_with_ts = orders_base.mutate(
        order_timestamp=ibis.coalesce(orders_base.processed_at, orders_base.created_at)
    )
    w = ibis.window(group_by="customer__id", order_by="order_timestamp")
    ranked_orders = orders_with_ts.mutate(order_num=ibis.row_number().over(w) + 1)

    customer_orders = (
        ranked_orders.group_by("customer__id")
        .aggregate(
            order_count=lambda t: t.count(),
            total_spent=lambda t: t.total_price.cast("double").sum(),
            first_order_at=lambda t: ibis.ifelse(
                t.order_num == 1, t.order_timestamp, None
            ).max(),
            second_order_at=lambda t: ibis.ifelse(
                t.order_num == 2, t.order_timestamp, None
            ).max(),
        )
    )

    days_to_second = (
        customer_orders.second_order_at.epoch_seconds()
        - customer_orders.first_order_at.epoch_seconds()
    ) / 86400.0

    customer_behavior = customer_orders.mutate(
        days_to_second_order=days_to_second,
        has_second_order=ibis.ifelse(customer_orders.second_order_at.notnull(), 1, 0),
    )

    customer_ltv = (
        to_semantic_table(customer_behavior, name="customer_ltv")
        .with_dimensions(
            customer_id=lambda t: t.customer__id,
            order_count=lambda t: t.order_count,
        )
        .with_measures(
            repeat_customers=lambda t: (t.order_count > 1).sum(),
            avg_ltv=lambda t: t.total_spent.mean(),
            total_customer_count=lambda t: t.count(),
        )
    )

    # --- Repeat Purchase Behavior & Time-to-Second-Order ---
    repeat_purchase_behavior = (
        to_semantic_table(
            customer_behavior,
            name="repeat_purchase_behavior",
            description=(
                "Customer repeat purchase rate and time-to-second-order behavior derived from order history. "
                "Uses Shopify's processed_at business timestamps (which preserve historical/backdated order dates) "
                "to calculate true elapsed calendar days."
            ),
        )
        .with_dimensions(
            customer_id=Dimension(
                expr=lambda t: t.customer__id,
                description="Shopify customer ID",
            ),
            order_count=Dimension(
                expr=lambda t: t.order_count,
                description="Total number of orders placed by the customer",
            ),
            has_second_order=Dimension(
                expr=lambda t: t.has_second_order,
                description="Flag indicating whether customer placed a second order (1 if repeat customer, 0 if one-time buyer)",
            ),
            days_to_second_order=Dimension(
                expr=lambda t: t.days_to_second_order,
                description="Days elapsed between customer's first and second order (null for one-time buyers)",
            ),
            first_order_at=Dimension(
                expr=lambda t: t.first_order_at,
                description="Timestamp of customer's first order (based on processed_at business date)",
                is_time_dimension=True,
            ),
        )
        .with_measures(
            total_customers=Measure(
                expr=lambda t: t.count(),
                description="Total count of distinct customers who placed at least one order",
            ),
            repeat_customers=Measure(
                expr=lambda t: t.has_second_order.sum(),
                description="Count of customers who have returned to place a second order (2 or more lifetime orders)",
            ),
            repeat_rate=Measure(
                expr=lambda t: t.has_second_order.sum().cast("double") / t.count(),
                description="Repeat purchase rate: proportion of customers with a second order (repeat_customers / total_customers)",
            ),
            median_days_to_second_order=Measure(
                expr=lambda t: t.days_to_second_order.median(),
                description=(
                    "Median days elapsed between first order and second order among repeat customers "
                    "(grounded in Shopify processed_at business dates)"
                ),
            ),
            p75_days_to_second_order=Measure(
                expr=lambda t: t.days_to_second_order.quantile(0.75),
                description=(
                    "75th percentile of days elapsed between first order and second order among repeat customers "
                    "(intervention threshold, grounded in Shopify processed_at business dates)"
                ),
            ),
        )
    )

    # --- Customers: basic profile info only (do NOT trust orders_count/total_spent here) ---
    customers = (
        to_semantic_table(customers_tbl, name="customers")
        .with_dimensions(
            customer_id=lambda t: t.id,
            created_at=lambda t: t.created_at,
        )
        .with_measures(
            customer_count=lambda t: t.count(),
        )
    )

    return {
        "orders": orders,
        "customers": customers,
        "customer_ltv": customer_ltv,
        "repeat_purchase_behavior": repeat_purchase_behavior,
    }


if __name__ == "__main__":
    # quick sanity check when run directly
    models = build_models()
    for name, model in models.items():
        print(f"--- {name} ---")
        print("dimensions:", list(model.dimensions))
        print("measures:", list(model.measures))