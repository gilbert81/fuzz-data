#!/usr/bin/env python3
"""
Creates a batch of dummy paid orders on your Shopify dev store, spread
across the last ~90 days, so the semantic layer has enough volume to
compute meaningful metrics (repeat rate, AOV variance, LTV, etc).

Usage:
    SHOPIFY_SHOP=pedal-mania-qeci6wdh.myshopify.com \
    SHOPIFY_ACCESS_TOKEN=shpat_xxx \
    python seed_orders.py --count 40

Requires the app's access token to have write_orders scope.
Orders are created with "test": true so they're clearly marked as
test data (visible in the admin, excluded from real reporting if
this were ever a live store).
"""

import argparse
import os
import random
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

API_VERSION = "2025-10"


def get_env(name):
    val = os.environ.get(name)
    if not val:
        sys.exit(f"Missing required env var: {name}")
    return val


def fetch_products(shop, headers):
    url = f"https://{shop}/admin/api/{API_VERSION}/products.json?limit=50"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    products = resp.json().get("products", [])
    if not products:
        sys.exit("No products found on the store. Seed products first.")
    variants = []
    for p in products:
        for v in p.get("variants", []):
            variants.append(
                {
                    "variant_id": v["id"],
                    "title": p["title"],
                    "price": v["price"],
                }
            )
    return variants


def random_customer(i):
    return {
        "first_name": f"Test{i}",
        "last_name": "Buyer",
        "email": f"test.buyer.{i}@example.com",
    }


def random_date_within(days_back):
    delta_days = random.uniform(0, days_back)
    dt = datetime.now(timezone.utc) - timedelta(days=delta_days)
    return dt.isoformat()


def build_order_payload(variants, customer, created_at):
    n_items = random.randint(1, 3)
    line_items = []
    for _ in range(n_items):
        v = random.choice(variants)
        line_items.append(
            {
                "variant_id": v["variant_id"],
                "quantity": random.randint(1, 2),
            }
        )

    return {
        "order": {
            "line_items": line_items,
            "customer": customer,
            "email": customer["email"],
            "financial_status": "paid",
            "created_at": created_at,
            "processed_at": created_at,  # Shopify records historical/backdated timestamps here
            "test": True,
            "send_receipt": False,
            "send_fulfillment_receipt": False,
        }
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=40, help="Number of orders to create")
    parser.add_argument("--customers", type=int, default=15, help="Number of distinct customers")
    parser.add_argument("--days-back", type=int, default=90, help="Spread orders over this many days")
    args = parser.parse_args()

    shop = get_env("SHOPIFY_SHOP")
    token = get_env("SHOPIFY_ACCESS_TOKEN")

    headers = {
        "X-Shopify-Access-Token": token,
        "Content-Type": "application/json",
    }

    print("Fetching existing products/variants ...")
    variants = fetch_products(shop, headers)
    print(f"Found {len(variants)} variants across your product catalog.")

    # Reuse the same customer across multiple orders sometimes, to get
    # repeat-purchase signal for LTV / repeat-rate metrics.
    customers = [random_customer(i) for i in range(args.customers)]

    created = 0
    for i in range(args.count):
        customer = random.choice(customers)
        created_at = random_date_within(args.days_back)
        payload = build_order_payload(variants, customer, created_at)

        url = f"https://{shop}/admin/api/{API_VERSION}/orders.json"

        max_retries = 6
        for attempt in range(max_retries):
            resp = requests.post(url, headers=headers, json=payload)

            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", 5))
                wait = retry_after + 1  # small buffer on top of what Shopify tells us
                print(f"[{i}] Rate limited, waiting {wait:.1f}s (attempt {attempt + 1}/{max_retries}) ...")
                time.sleep(wait)
                continue

            if resp.status_code >= 300:
                print(f"[{i}] Failed ({resp.status_code}): {resp.text[:300]}")
            else:
                order_id = resp.json()["order"]["id"]
                created += 1
                print(f"[{i}] Created order {order_id} for {customer['email']} @ {created_at[:10]}")
            break
        else:
            print(f"[{i}] Gave up after {max_retries} retries.")

        # Order creation has its own, stricter rate limit than general REST
        # calls — pace well below it to avoid tripping 429s repeatedly.
        time.sleep(3)

    print(f"\nDone. {created}/{args.count} orders created successfully.")


if __name__ == "__main__":
    main()