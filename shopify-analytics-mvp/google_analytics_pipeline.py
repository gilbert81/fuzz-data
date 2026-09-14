""" Loads the pipeline for Google Analytics V4. """

import time
from typing import Any
import json

import dlt
from dlt.sources.credentials import GcpServiceAccountCredentials

from google_analytics import google_analytics

# Explicit service account credentials — bypasses dlt's Union[OAuth, ServiceAccount]
# auto-resolution, which was falling through to GeneralOAuthFlow instead of using
# the service account block already correctly defined in secrets.toml.
credentials = GcpServiceAccountCredentials()
credentials.parse_native_representation(
    json.dumps(
        {
            "type": "service_account",
            "project_id": dlt.secrets["sources.google_analytics.credentials.project_id"],
            "private_key": dlt.secrets["sources.google_analytics.credentials.private_key"],
            "client_email": dlt.secrets["sources.google_analytics.credentials.client_email"],
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    )
)

# From GA Admin > Property Settings > Property ID (numeric). NOT the GCP project ID.
# Confirm this isn't still the template placeholder (213025502) unless that
# genuinely is your connected demo property's real ID.
PROPERTY_ID = "213025502"

QUERIES = [
    {
        "resource_name": "sample_analytics_data1",
        "dimensions": ["browser", "city"],
        "metrics": ["totalUsers", "transactions"],
    },
    {
        "resource_name": "sample_analytics_data2",
        "dimensions": ["browser", "city", "dateHour"],
        "metrics": ["totalUsers"],
    },
]


def simple_load() -> Any:
    """
    Loads GA4 report data into duckdb using explicit service account credentials.
    Incremental loading is on; subsequent runs pick up from the last loaded date.

    Returns:
        Load info on the pipeline that has been run.
    """
    pipeline = dlt.pipeline(
        pipeline_name="dlt_google_analytics_pipeline",
        destination="duckdb",
        dev_mode=False,
        dataset_name="sample_analytics_data",
    )

    data_analytics = google_analytics(
        credentials=credentials,
        property_id=PROPERTY_ID,
        queries=QUERIES,
    )
    info = pipeline.run(data=data_analytics)
    print(info)
    return info


if __name__ == "__main__":
    start_time = time.time()
    simple_load()
    end_time = time.time()
    print(f"Time taken: {end_time - start_time}")

def simple_load_config() -> Any:
    """
    Just loads the data normally. QUERIES are taken from config. Incremental loading for this pipeline is on,
    the last load time is saved in dlt_state, and the next load of the pipeline will have the last load as a starting date.

    Returns:
        Load info on the pipeline that has been run.
    """
    # FULL PIPELINE RUN
    pipeline = dlt.pipeline(
        pipeline_name="dlt_google_analytics_pipeline",
        destination='duckdb',
        dev_mode=False,
        dataset_name="sample_analytics_data",
    )
    # Google Analytics source function - taking data from QUERIES defined locally instead of config
    data_analytics = google_analytics()
    info = pipeline.run(data=data_analytics)
    print(info)
    return info


def chose_date_first_load(start_date: str = "2000-01-01") -> Any:
    """
    Chooses the starting date for the first pipeline load. Subsequent loads of the pipeline will be from the last loaded date.

    Args:
        start_date: The string version of the date in the format yyyy-mm-dd and some other values.
            More info: https://developers.google.com/analytics/devguides/reporting/data/v1/rest/v1beta/DateRange

    Returns:
        Load info on the pipeline that has been run.
    """
    # FULL PIPELINE RUN
    pipeline = dlt.pipeline(
        pipeline_name="dlt_google_analytics_pipeline",
        destination='duckdb',
        dev_mode=False,
        dataset_name="sample_analytics_data",
    )
    # Google Analytics source function
    data_analytics = google_analytics(start_date=start_date)
    info = pipeline.run(data=data_analytics)
    print(info)
    return info


if __name__ == "__main__":
    start_time = time.time()
    simple_load()
    end_time = time.time()
    print(f"Time taken: {end_time-start_time}")
