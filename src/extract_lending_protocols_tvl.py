#!/usr/bin/env python3
"""
Get TVL for lending protocols from a parquet file using defillama_sdk.
"""

import pandas as pd
from defillama_sdk import DefiLlama
import logging
import os
from datetime import datetime
from src.catalog import Catalog

# Set up logging
logging.basicConfig(
    level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_lending_protocols_tvl(
        input_parquet_path: str, output_parquet_path: str
):
    """
    Read protocols from parquet, filter for lending category,
    fetch current TVL, and save results to a new parquet file.

    Args:
        input_parquet_path: Path to input parquet file with 'protocol'
        and 'category' columns
        output_parquet_path: Path where output parquet file will be saved

    Returns:
        DataFrame with protocol, url, and tvl columns
    """

    # Step 1: Read the parquet file
    logger.info(f"Reading parquet file from {input_parquet_path}")
    df = pd.read_parquet(input_parquet_path)

    # Verify required columns exist
    required_columns = ['protocol', 'category', 'url', 'parent_protocol']
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(
                f"Input parquet file must contain '{col}' column.\
Found columns: {df.columns.tolist()}"
            )

    # Step 2: Filter for lending protocols (case-insensitive)
    logger.info("Filtering for lending protocols...")
    lending_df = df[df['category'].str.lower() == 'lending'].copy()
    logger.info(
        f"Found {len(lending_df)} lending protocols out of {len(df)}\
total protocols"
    )

    if len(lending_df) == 0:
        logger.warning("No lending protocols found in the input file")
        # Create empty output with protocol and tvl columns
        empty_result = pd.DataFrame(columns=['protocol', 'url', 'tvl'])
        empty_result.to_parquet(output_parquet_path, index=False)
        return empty_result

    # Step 3: Initialize DefiLlama SDK client
    logger.info("Initializing DeFiLlama SDK...")
    client = DefiLlama()

    # Step 4: Get TVL for each lending protocol
    logger.info("Retrieving TVL for each lending protocol...")
    tvl_results = []
    parent_as_protocol_counter = 0
    api_error_tvl_counter = 0
    api_error_protocol_counter = 0

    for _, row in lending_df.iterrows():
        if pd.isna(row['parent_protocol']):
            protocol_name = row['protocol']
        else:
            protocol_name = row['parent_protocol']
            parent_as_protocol_counter += 1

        # Try to get TVL with error handling
        try:
            tvl_value = client.tvl.getTvl(protocol_name)
        except Exception as e:
            # Check if it's an ApiError (or any other exception)
            if (
                'ApiError' in str(type(e))
                or 'API' in str(e)
                or 'api' in str(e).lower()
            ):
                api_error_tvl_counter += 1
                logger.warning(
                    f"ApiError for protocol '{protocol_name}': {e}.\
Trying another appraoch."
                )
            else:
                logger.warning(
                    f"Unexpected error for protocol '{protocol_name}':\
{e}. Setting TVL to None."
                )
            try:
                protocol = client.tvl.getProtocol(protocol_name)
                tvl_value = protocol['tvl'][-1]['totalLiquidityUSD']
            except Exception as e:
                # Check if it's an ApiError (or any other exception)
                if (
                    'ApiError' in str(type(e))
                    or 'API' in str(e)
                    or 'api' in str(e).lower()
                ):
                    api_error_protocol_counter += 1
                    logger.warning(
                        f"ApiError for protocol '{protocol_name}':\
{e}. Setting TVL to None."
                    )
                else:
                    logger.warning(
                        f"Unexpected error for protocol '{protocol_name}':\
{e}. Setting TVL to None."
                    )
            tvl_value = None

        tvl_results.append(
            {
                'protocol': protocol_name,
                'url': row['url'],
                'tvl': tvl_value
            }
        )

    # Step 5: Create output DataFrame
    output_df = pd.DataFrame(tvl_results).drop_duplicates()
    logger.info(
        f"Used parent_protocol for {parent_as_protocol_counter}\
out of {len(lending_df)} lending protocols to retrieve TVL"
    )
    if api_error_tvl_counter > 0:
        logger.warning(
            f"Encountered {api_error_tvl_counter}\
API errors while fetching TVL data"
        )
    if api_error_protocol_counter > 0:
        logger.warning(
            f"Encountered {api_error_protocol_counter}\
API errors while fetching TVL data by second approach"
        )

    # Step 6: Save to parquet file
    logger.info(f"Saving results to {output_parquet_path}")

    output_df.to_parquet(output_parquet_path, index=False)
    logger.info("Process completed successfully!")

    return output_df


def main():
    """
    Main execution function.
    """
    # Input path
    input_prefix = "data/tvl/protocols"
    timestamp = datetime.now().strftime("%Y%m%d")
    input = f"{input_prefix}/partition_date={timestamp}/"

    # Output path
    output_prefix_with_partition =\
        f"data/tvl/lending_protocols_tvl/partition_date={timestamp}"
    os.makedirs(output_prefix_with_partition, exist_ok=True)
    output = f"{output_prefix_with_partition}/defillama_lending_tvl.parquet"

    logger.info("🚀 Starting lending protocols TVL extraction")

    try:
        result_df = get_lending_protocols_tvl(input, output)

        # Display results summary
        print("\n" + "="*60)
        print("📊 LENDING PROTOCOLS TVL SUMMARY")
        print("="*60)

        print(f"\n📈 Total lending protocols: {len(result_df):,}")
        print(f"💵 Protocols with TVL data: {result_df['tvl'].notna().sum():,}")
        print(
            f"❓ Protocols without TVL data: {result_df['tvl'].isna().sum():,}"
        )

        if result_df['tvl'].notna().any():
            print("\n💰 Top 5 lending protocols by TVL:")
            top_protocols = result_df.nlargest(5, 'tvl')
            for idx, row in top_protocols.iterrows():
                print(f"   {row['protocol']:<30} : ${row['tvl']:>15,.2f}")

        print(f"\n💾 Output saved to: {output}")

        # Show file size
        if os.path.exists(output):
            size_bytes = os.path.getsize(output)
            size_kb = size_bytes / 1024
            print(f"📁 File size: {size_kb:.2f} KB")

        # Creating latest schema
        schemaname = f"schemas/\
{"/".join(output_prefix_with_partition.split("/")[-3:-1])}.json"
        os.makedirs("/".join(schemaname.split("/")[:-1]), exist_ok=True)
        catalog = Catalog()
        catalog.generate_schema_from_parquet(output, schemaname)

    except Exception as e:
        logger.error(f"Failed to process: {e}")
        raise


if __name__ == "__main__":
    main()
