

"""
Pulls a richer slice of the GA4 obfuscated sample e-commerce dataset from
BigQuery: a 14-day range, proper date typing, purchase revenue, and a
couple of useful nested event params flattened out.
"""

import dlt
from google.cloud import bigquery


@dlt.resource(name="ga4_events", write_disposition="replace")
def ga4_sample_events():
    # Pass your active GCP project ID here (used for billing the query, not
    # for owning the public dataset itself).
    client = bigquery.Client()

    query = """
        SELECT
            PARSE_DATE('%Y%m%d', event_date) AS event_date,
            event_name,
            user_pseudo_id,
            geo.country AS country,
            device.category AS device_category,
            traffic_source.medium AS traffic_medium,
            traffic_source.source AS traffic_source,
            ecommerce.purchase_revenue_in_usd AS purchase_revenue_usd,
            ecommerce.total_item_quantity AS item_quantity,
            (
                SELECT ep.value.int_value
                FROM UNNEST(event_params) AS ep
                WHERE ep.key = 'ga_session_id'
            ) AS session_id,
            (
                SELECT ep.value.string_value
                FROM UNNEST(event_params) AS ep
                WHERE ep.key = 'page_location'
            ) AS page_location
        FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
        WHERE _TABLE_SUFFIX BETWEEN '20210101' AND '20210114'
    """

    query_job = client.query(query)
    results = query_job.result()

    for row in results:
        yield dict(row)


def run():
    pipeline = dlt.pipeline(
        pipeline_name="ga4_public_pipeline",
        destination="duckdb",
        dataset_name="ga4_sample",
    )
    info = pipeline.run(ga4_sample_events())
    print(info)
    return info


if __name__ == "__main__":
    run()