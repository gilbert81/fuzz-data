import ibis
from boring_semantic_layer import to_semantic_table


def get_ga4_connection(read_only: bool = True):
    # Confirmed from dlt pipeline dashboard: pipeline name ga4_public_pipeline,
    # schema ga4_public. Adjust the filename below if `ls *.duckdb` shows a
    # different file was created for this pipeline.
    return ibis.duckdb.connect("ga4_public_pipeline.duckdb", read_only=read_only)


def build_ga4_model():
    con = get_ga4_connection()
    events_tbl = con.table("ga4_events", database="ga4_sample")

    ga4_events = (
        to_semantic_table(events_tbl, name="ga4_events")
        .with_dimensions(
            event_date=lambda t: t.event_date,  # now a real DATE, parsed in BigQuery
            event_name=lambda t: t.event_name,
            country=lambda t: t.country,
            device_category=lambda t: t.device_category,
            traffic_medium=lambda t: t.traffic_medium,
            traffic_source=lambda t: t.traffic_source,
        )
        .with_measures(
            event_count=lambda t: t.count(),
            unique_users=lambda t: t.user_pseudo_id.nunique(),
            unique_sessions=lambda t: t.session_id.nunique(),
            purchase_count=lambda t: (t.event_name == "purchase").sum(),
            # purchase_revenue_usd is null on all non-purchase event rows,
            # so summing it directly gives total revenue with no extra filter needed
            revenue=lambda t: t.purchase_revenue_usd.sum(),
            items_sold=lambda t: t.item_quantity.sum(),
        )
    )

    return {"ga4_events": ga4_events}


if __name__ == "__main__":
    models = build_ga4_model()
    for name, model in models.items():
        print(f"--- {name} ---")
        print("dimensions:", list(model.dimensions))
        print("measures:", list(model.measures))