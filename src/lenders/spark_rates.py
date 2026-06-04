import asyncio
import logging
import os
import pandas as pd
from datetime import datetime

# Wayfinder SDK imports
from wayfinder_paths.mcp.scripting import get_adapter
from wayfinder_paths.adapters.sparklend_adapter.adapter import SparkLendAdapter
from wayfinder_paths.core.constants.chains import CHAIN_ID_ETHEREUM

# Set up logging
logging.basicConfig(
    level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def to_float(value, default=0.0):
    """Convert string or number to float safely."""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


async def fetch_sparklend_rates():
    """
    Fetches lending rates from SparkLend via Wayfinder SDK
    and writes them to a Parquet file, matching the Aave extractor structure.
    """
    # Connect to SparkLend adapter
    adapter = await get_adapter(SparkLendAdapter)
    logger.info("Connected to SparkLend adapter")

    # Fetch all markets with caps included
    try:
        markets = await adapter.get_all_markets(
            chain_id=CHAIN_ID_ETHEREUM,
            include_caps=True,
        )
        if not markets:
            logger.warning("No markets data returned from SparkLend.")
            return
    except Exception as e:
        logger.error(f"Failed to fetch markets: {e}")
        return

    records = []
    timestamp = datetime.now().strftime("%Y%m%d")

    for market in markets[1]:
        symbol = market.get("symbol", "Unknown")
        name = market.get("name", "")
        decimals = market.get("decimals", 18)

        # APY values are already in decimal form (e.g., 0.05 = 5%)
        supply_apy_raw = market.get("supply_apy", 0.0)
        borrow_apy_raw = market.get("variable_borrow_apy", 0.0)

        # Convert to percentage (multiply by 100) for consistency with Aave script
        supply_apy = to_float(supply_apy_raw) * 100
        borrow_apy = to_float(borrow_apy_raw) * 100

        # Caps are returned in native token units (wei)
        supply_cap_raw = market.get("supply_cap", 0)
        borrow_cap_raw = market.get("borrow_cap", 0)
        supply_cap = to_float(supply_cap_raw)
        borrow_cap = to_float(borrow_cap_raw)

        # Note: Wayfinder SDK does not directly provide total supply/borrow amounts.
        # These are set to 0.0; if needed, they can be fetched via get_pos().
        total_supply_native = 0.0
        total_supply_usd = 0.0
        total_borrow_native = 0.0
        total_borrow_usd = 0.0
        utilization_rate = 0.0

        # Status flags
        is_frozen = market.get("is_frozen", False)
        is_paused = market.get("is_paused", False)
        is_active = market.get("is_active", True)
        can_supply = market.get("can_supply", True)
        can_borrow = market.get("can_borrow", True)
        can_use_as_collateral = market.get("can_use_as_collateral", False)

        record = {
            "symbol": symbol,
            "name": name,
            "decimals": decimals,
            "supply_apy_percent": supply_apy,
            "borrow_apy_percent": borrow_apy,
            "total_supply_native": total_supply_native,
            "total_supply_usd": total_supply_usd,
            "total_borrow_native": total_borrow_native,
            "total_borrow_usd": total_borrow_usd,
            "utilization_rate_percent": utilization_rate,
            "supply_cap_native": supply_cap,
            "borrow_cap_native": borrow_cap,
            "is_frozen": is_frozen,
            "is_paused": is_paused,
            "is_active": is_active,
            "can_supply": can_supply,
            "can_borrow": can_borrow,
            "can_use_as_collateral": can_use_as_collateral,
            "partition_date": int(timestamp)
        }
        records.append(record)

    if not records:
        logger.warning("No market records found.")
        return

    # Create DataFrame and write to Parquet
    df = pd.DataFrame(records)

    output_dir = f"data/lenders/sparklend_rates/partition_date={timestamp}"
    os.makedirs(output_dir, exist_ok=True)
    output_file = f"{output_dir}/sparklend_rates.parquet"

    try:
        df.to_parquet(output_file, index=False, engine='pyarrow')
        logger.info(f"✅ Successfully saved to {output_file}")
        logger.info(f"Total reserves saved: {len(records)}")
    except Exception as e:
        logger.error(f"Failed to save Parquet file: {e}")


def main():
    """Entry point to run the async function."""
    asyncio.run(fetch_sparklend_rates())


if __name__ == "__main__":
    main()
