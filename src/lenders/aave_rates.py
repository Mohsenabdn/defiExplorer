import requests
import logging
import os
import pandas as pd
from datetime import datetime
from src.catalog import Catalog

# Set up logging
logging.basicConfig(
    level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

URL = "https://api.v4.aave.com/graphql"


def to_float(value, default=0.0):
    """Convert string or number to float safely."""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def fetch_aave_lending_rates():
    """
    Fetches lending rates from Aave V4 and writes them to a Parquet file.
    """
    query = """
    {
      reserves(
        request: {
          query: { chainIds: [1] }
          filter: ALL
        }
      ) {
        id
        canSupply
        canBorrow
        canUseAsCollateral
        asset {
          underlying {
            info {
              symbol
              name
              decimals
            }
          }
          summary {
            utilizationRate {
              value
              normalized
            }
          }
        }
        summary {
          supplyApy { value normalized }
          borrowApy { value normalized }
          supplied {
            amount { value }
            exchange(currency: USD) { value }
          }
          borrowed {
            amount { value }
            exchange(currency: USD) { value }
          }
        }
        status {
          frozen
          paused
          active
        }
        settings {
          supplyCap { amount { value } }
          borrowCap { amount { value } }
        }
      }
    }
    """

    response = requests.post(URL, json={"query": query})
    if response.status_code != 200:
        logger.error(f"API request failed with status {response.status_code}: {response.text}")
        return

    data = response.json()
    if "errors" in data:
        logger.error(f"GraphQL errors: {data['errors']}")
        return

    reserves = data.get("data", {}).get("reserves", [])
    if not reserves:
        logger.warning("No reserves data returned.")
        logger.info("Full response:", data)
        return

    # Collect records for DataFrame
    records = []
    timestamp = datetime.now().strftime("%Y%m%d")

    for reserve in reserves:
        status = reserve.get("status", {})
        asset_info = reserve.get("asset", {}).get("underlying", {}).get("info", {})
        symbol = asset_info.get("symbol", "Unknown")
        name = asset_info.get("name", "")
        decimals = asset_info.get("decimals", 0)

        summary = reserve.get("summary", {})
        supply_apy_raw = summary.get("supplyApy", {}).get("value", "0")
        borrow_apy_raw = summary.get("borrowApy", {}).get("value", "0")
        supply_apy = to_float(supply_apy_raw) * 100   # as percentage
        borrow_apy = to_float(borrow_apy_raw) * 100

        supplied = summary.get("supplied", {})
        supplied_native_raw = supplied.get("amount", {}).get("value", "0")
        supplied_usd_raw = supplied.get("exchange", {}).get("value", "0")
        supplied_native = to_float(supplied_native_raw)
        supplied_usd = to_float(supplied_usd_raw)   # convert to float for DataFrame

        borrowed = summary.get("borrowed", {})
        borrowed_native_raw = borrowed.get("amount", {}).get("value", "0")
        borrowed_usd_raw = borrowed.get("exchange", {}).get("value", "0")
        borrowed_native = to_float(borrowed_native_raw)
        borrowed_usd = to_float(borrowed_usd_raw)

        util_rate_raw = reserve.get("asset", {}).get("summary", {}).get("utilizationRate", {}).get("value", "0")
        util_rate = to_float(util_rate_raw) * 100

        supply_cap_raw = reserve.get("settings", {}).get("supplyCap", {}).get("amount", {}).get("value", "0")
        borrow_cap_raw = reserve.get("settings", {}).get("borrowCap", {}).get("amount", {}).get("value", "0")
        supply_cap = to_float(supply_cap_raw)
        borrow_cap = to_float(borrow_cap_raw)

        record = {
            "symbol": symbol,
            "name": name,
            "decimals": decimals,
            "supply_apy_percent": supply_apy,
            "borrow_apy_percent": borrow_apy,
            "total_supply_native": supplied_native,
            "total_supply_usd": supplied_usd,
            "total_borrow_native": borrowed_native,
            "total_borrow_usd": borrowed_usd,
            "utilization_rate_percent": util_rate,
            "supply_cap_native": supply_cap,
            "borrow_cap_native": borrow_cap,
            "is_frozen": status.get("frozen", False),
            "is_paused": status.get("paused", False),
            "is_active": status.get("active", True),
            "can_supply": reserve.get("canSupply", False),
            "can_borrow": reserve.get("canBorrow", False),
            "can_use_as_collateral": reserve.get("canUseAsCollateral", False),
            "partition_date": int(timestamp)
        }
        records.append(record)

    # Create DataFrame and write to Parquet
    df = pd.DataFrame(records)

    # Create output file path
    prefix_with_partition = f"data/lenders/aave_rates/partition_date={timestamp}"
    os.makedirs(prefix_with_partition, exist_ok=True)
    output_file = f"{prefix_with_partition}/aave_rates.parquet"

    # Write dataframe to parquet file
    try:
        df.to_parquet(output_file, index=False, engine='pyarrow')
        logger.info(f"✅ Successfully saved to {output_file}")
        logger.info(f"Total reserves saved: {len(records)}")

    except Exception as e:
        logger.error(f"Failed to save Parquet file: {e}")

    # Generate schema
    schema_path = f"schemas/{"/".join(prefix_with_partition.split("/")[-3:-1])}.json"
    os.makedirs("/".join(schema_path.split("/")[:-1]), exist_ok=True)
    catalog = Catalog()
    catalog.generate_schema_from_parquet(output_file, schema_path)


if __name__ == "__main__":
    fetch_aave_lending_rates()
