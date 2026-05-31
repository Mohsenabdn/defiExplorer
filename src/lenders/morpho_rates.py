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

# Official Morpho API endpoint
MORPHO_API_URL = "https://api.morpho.org/graphql"


def to_float(value, default=0.0):
    """Convert a value to float safely."""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def fetch_morpho_lending_rates():
    """
    Fetches lending rates from the official Morpho API (Ethereum mainnet) and writes them to a Parquet file.
    """
    # Query specifically for Ethereum mainnet (chainId: 1) and markets with supply assets greater than $1M
    query = """
    {
      markets(
        first: 1000
        where: {
          chainId_in: [1]
          supplyAssetsUsd_gte: 1000000
        }
        orderBy: SupplyAssetsUsd
        orderDirection: Desc
      ) {
        items {
          marketId
          loanAsset {
            address
            name
            symbol
            decimals
          }
          collateralAsset {
            address
            name
            symbol
            decimals
          }
          state {
            supplyApy
            borrowApy
            utilization
            supplyAssets
            supplyAssetsUsd
            borrowAssets
            borrowAssetsUsd
          }
          lltv
          oracle {
            address
          }
          irmAddress
        }
        pageInfo {
          countTotal
        }
      }
    }
    """

    response = requests.post(MORPHO_API_URL, json={"query": query})
    if response.status_code != 200:
        logger.error(f"API request failed with status {response.status_code}: {response.text}")
        return

    data = response.json()
    if "errors" in data:
        logger.error(f"GraphQL errors: {data['errors']}")
        return

    markets = data.get("data", {}).get("markets", {}).get("items", [])
    if not markets:
        logger.warning("No markets data returned.")
        logger.info(f"Full response: {data}")
        return

    # Prepare records for DataFrame
    records = []
    timestamp = datetime.now().strftime("%Y%m%d")

    for market in markets:
        loan_asset = market.get("loanAsset") or {}
        collat_asset = market.get("collateralAsset") or {}
        state = market.get("state") or {}

        symbol = loan_asset.get("symbol", "Unknown")
        name = loan_asset.get("name", "")
        decimals = loan_asset.get("decimals", 0)

        # Values are already in standard format (e.g., 0.05 for 5%)
        supply_apy_percent = to_float(state.get("supplyApy", 0)) * 100
        borrow_apy_percent = to_float(state.get("borrowApy", 0)) * 100
        utilization = to_float(state.get("utilization", 0)) * 100

        total_supply_native = to_float(state.get("supplyAssets", 0))
        total_supply_usd = to_float(state.get("supplyAssetsUsd", 0))
        total_borrow_native = to_float(state.get("borrowAssets", 0))
        total_borrow_usd = to_float(state.get("borrowAssetsUsd", 0))

        # LLTV is already a decimal percentage (e.g., 0.86 for 86%)
        lltv_percent = to_float(market.get("lltv", 0)) * 100

        record = {
            "market_id": market.get("uniqueKey", ""),
            "symbol": symbol,
            "name": name,
            "decimals": decimals,
            "collateral_symbol": collat_asset.get("symbol", ""),
            "collateral_name": collat_asset.get("name", ""),
            "supply_apy_percent": supply_apy_percent,
            "borrow_apy_percent": borrow_apy_percent,
            "total_supply_native": total_supply_native,
            "total_supply_usd": total_supply_usd,
            "total_borrow_native": total_borrow_native,
            "total_borrow_usd": total_borrow_usd,
            "utilization_rate_percent": utilization,
            "lltv_percent": lltv_percent,
            "oracle_address": market.get("oracleAddress", ""),
            "irm_address": market.get("irmAddress", ""),
            "partition_date": int(timestamp)
        }
        records.append(record)

    # Create DataFrame
    df = pd.DataFrame(records)

    # Write to partitioned Parquet
    prefix_with_partition = f"data/lenders/morpho_rates/partition_date={timestamp}"
    os.makedirs(prefix_with_partition, exist_ok=True)
    output_file = f"{prefix_with_partition}/morpho_rates.parquet"

    try:
        df.to_parquet(output_file, index=False, engine='pyarrow')
        logger.info(f"✅ Successfully saved to {output_file}")
        logger.info(f"Total markets saved: {len(records)}")
    except Exception as e:
        logger.error(f"Failed to save Parquet file: {e}")

    # Generate schema
    schema_path = f"schemas/{'/'.join(prefix_with_partition.split('/')[-3:-1])}.json"
    os.makedirs("/".join(schema_path.split("/")[:-1]), exist_ok=True)
    catalog = Catalog()
    catalog.generate_schema_from_parquet(output_file, schema_path)


if __name__ == "__main__":
    fetch_morpho_lending_rates()
