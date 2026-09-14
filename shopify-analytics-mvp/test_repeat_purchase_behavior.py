"""
Verification test for JTBD 1: Repeat Rate & Time-to-Second-Order (Shopify).
Validates semantic layer outputs against ground-truth manual DuckDB SQL queries.
"""

import duckdb
import ibis
from semantic_model import build_models


def test_ground_truth_vs_semantic_layer():
    print("Connecting to DuckDB directly for ground-truth SQL...")
    raw_con = duckdb.connect("shopify.duckdb", read_only=True)
    sql = """
    WITH ranked_orders AS (
        SELECT
            customer__id AS customer_id,
            id AS order_id,
            COALESCE(processed_at, created_at) AS order_timestamp,
            ROW_NUMBER() OVER (PARTITION BY customer__id ORDER BY COALESCE(processed_at, created_at)) AS order_num
        FROM shopify_data.orders
        WHERE customer__id IS NOT NULL
    ),
    customer_orders AS (
        SELECT
            customer_id,
            MAX(CASE WHEN order_num = 1 THEN order_timestamp END) AS first_order_at,
            MAX(CASE WHEN order_num = 2 THEN order_timestamp END) AS second_order_at,
            MAX(order_num) AS total_orders
        FROM ranked_orders
        GROUP BY customer_id
    ),
    customer_metrics AS (
        SELECT
            customer_id,
            total_orders,
            first_order_at,
            second_order_at,
            CASE WHEN second_order_at IS NOT NULL THEN 1 ELSE 0 END AS has_second_order,
            epoch(second_order_at - first_order_at) / 86400.0 AS days_to_second_order
        FROM customer_orders
    )
    SELECT
        COUNT(*) AS total_customers,
        SUM(has_second_order) AS repeat_customers,
        SUM(has_second_order)::DOUBLE / COUNT(*) AS repeat_rate,
        MEDIAN(days_to_second_order) AS median_days_to_second_order,
        QUANTILE_CONT(days_to_second_order, 0.75) AS p75_days_to_second_order
    FROM customer_metrics;
    """
    ground_truth = raw_con.sql(sql).df().iloc[0].to_dict()
    print("Ground Truth SQL Results:")
    for k, v in ground_truth.items():
        print(f"  {k}: {v}")

    print("\nQuerying BSL repeat_purchase_behavior semantic model...")
    models = build_models()
    assert "repeat_purchase_behavior" in models, "repeat_purchase_behavior not in models"
    model = models["repeat_purchase_behavior"]

    measures = [
        "total_customers",
        "repeat_customers",
        "repeat_rate",
        "median_days_to_second_order",
        "p75_days_to_second_order",
    ]
    result = model.query(measures=measures).execute().iloc[0].to_dict()
    print("Semantic Model Results:")
    for k, v in result.items():
        print(f"  {k}: {v}")

    # Assertions
    assert int(result["total_customers"]) == int(ground_truth["total_customers"]), "total_customers mismatch"
    assert int(result["repeat_customers"]) == int(ground_truth["repeat_customers"]), "repeat_customers mismatch"
    assert abs(result["repeat_rate"] - ground_truth["repeat_rate"]) < 1e-6, "repeat_rate mismatch"
    assert abs(result["median_days_to_second_order"] - ground_truth["median_days_to_second_order"]) < 1e-6, "median_days mismatch"
    assert abs(result["p75_days_to_second_order"] - ground_truth["p75_days_to_second_order"]) < 1e-6, "p75_days mismatch"

    # Sanity checks on plausibility
    assert result["repeat_rate"] > 0, "repeat_rate must be positive"
    assert result["median_days_to_second_order"] > 0, "median_days_to_second_order must be positive"
    assert result["p75_days_to_second_order"] >= result["median_days_to_second_order"], "p75 must be >= median"

    print("\nChecking metadata descriptions on all dimensions and measures...")
    dims = model.get_dimensions()
    for dname, dim in dims.items():
        assert dim.description, f"Dimension {dname} missing description!"
        print(f"  [dim] {dname}: {dim.description}")

    meas = model.get_measures()
    for mname, m in meas.items():
        assert m.description, f"Measure {mname} missing description!"
        print(f"  [measure] {mname}: {m.description}")

    print("\nRegression check on existing models...")
    assert "orders" in models
    assert "customers" in models
    assert "customer_ltv" in models
    ltv_res = models["customer_ltv"].query(measures=["repeat_customers", "avg_ltv", "total_customer_count"]).execute()
    assert len(ltv_res) == 1
    print("  customer_ltv query succeeded:", ltv_res.iloc[0].to_dict())

    print("\nALL VERIFICATIONS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    test_ground_truth_vs_semantic_layer()
