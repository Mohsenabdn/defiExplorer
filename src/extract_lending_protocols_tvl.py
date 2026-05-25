#!/usr/bin/env python3
"""
Get TVL for lending protocols from a parquet file using defillama_sdk.
"""

import pandas as pd
from defillama_sdk import DefiLlama
import logging
import os
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_lending_protocols_tvl(input_parquet_path: str, output_parquet_path: str):
    """
    Read protocols from parquet, filter for lending category, fetch current TVL,
    and save results to a new parquet file.
    
    Args:
        input_parquet_path: Path to input parquet file with 'protocol' and 'category' columns
        output_parquet_path: Path where output parquet file will be saved
    
    Returns:
        DataFrame with protocol and tvl columns
    """
    
    # Step 1: Read the parquet file
    logger.info(f"Reading parquet file from {input_parquet_path}")
    df = pd.read_parquet(input_parquet_path)
    
    # Verify required columns exist
    required_columns = ['protocol', 'category']
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Input parquet file must contain '{col}' column. Found columns: {df.columns.tolist()}")
    
    # Step 2: Filter for lending protocols (case-insensitive)
    logger.info("Filtering for lending protocols...")
    lending_df = df[df['category'].str.lower() == 'lending'].copy()
    logger.info(f"Found {len(lending_df)} lending protocols out of {len(df)} total protocols")
    
    if len(lending_df) == 0:
        logger.warning("No lending protocols found in the input file")
        # Create empty output with protocol and tvl columns
        empty_result = pd.DataFrame(columns=['protocol', 'tvl'])
        empty_result.to_parquet(output_parquet_path, index=False)
        return empty_result
    
    # Step 3: Initialize DefiLlama SDK client
    logger.info("Initializing DeFiLlama SDK...")
    client = DefiLlama()
    
    # Get all protocols data from DeFiLlama API
    logger.info("Fetching all protocols data from DeFiLlama API...")
    try:
        all_protocols = client.tvl.getProtocols()
        logger.info(f"Successfully fetched {len(all_protocols)} protocols from API")
    except Exception as e:
        logger.error(f"Failed to fetch protocols from API: {e}")
        raise
    
    # Create a mapping from protocol name to TVL
    # Handle case-insensitive matching
    protocol_tvl_map = {}
    for protocol in all_protocols:
        protocol_name = protocol.get('name', '')
        tvl_value = protocol.get('tvl', 0)
        if protocol_name:
            protocol_tvl_map[protocol_name.lower()] = tvl_value
    
    # Step 4: Get TVL for each lending protocol
    logger.info("Retrieving TVL for each lending protocol...")
    tvl_results = []
    
    for _, row in lending_df.iterrows():
        protocol_name = row['protocol']
        protocol_key = protocol_name.lower()
        
        if protocol_key in protocol_tvl_map:
            tvl_value = protocol_tvl_map[protocol_key]
            tvl_results.append({
                'protocol': protocol_name,
                'tvl': tvl_value
            })
            logger.debug(f"Found TVL for {protocol_name}: ${tvl_value:,.2f}")
        else:
            # Try partial matching for protocols with different naming
            matched = False
            for api_name, tvl_val in protocol_tvl_map.items():
                # Check if protocol name is contained in API name or vice versa
                if protocol_key in api_name or api_name in protocol_key:
                    tvl_results.append({
                        'protocol': protocol_name,
                        'tvl': tvl_val
                    })
                    logger.info(f"Found partial match for '{protocol_name}' using '{api_name}'")
                    matched = True
                    break
            
            if not matched:
                logger.warning(f"No TVL data found for protocol: {protocol_name}")
                tvl_results.append({
                    'protocol': protocol_name,
                    'tvl': None
                })
    
    # Step 5: Create output DataFrame
    output_df = pd.DataFrame(tvl_results)
    matched_count = output_df['tvl'].notna().sum()
    logger.info(f"Retrieved TVL data for {matched_count} out of {len(output_df)} lending protocols")
    
    # Optional: Add TVL summary statistics for verification
    if output_df['tvl'].notna().any():
        avg_tvl = output_df['tvl'].mean()
        total_tvl = output_df['tvl'].sum()
        logger.info(f"Average TVL: ${avg_tvl:,.2f}")
        logger.info(f"Total TVL across all lending protocols: ${total_tvl:,.2f}")
    
    # Step 6: Save to parquet file
    logger.info(f"Saving results to {output_parquet_path}")
    
    # Create directory if it doesn't exist
    output_dir = os.path.dirname(output_parquet_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
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
        f"data/tvl/lending_protocols/partition_date={timestamp}"
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
        print(f"❓ Protocols without TVL data: {result_df['tvl'].isna().sum():,}")
        
        if result_df['tvl'].notna().any():
            print(f"\n💰 Top 5 lending protocols by TVL:")
            top_protocols = result_df.nlargest(5, 'tvl')
            for idx, row in top_protocols.iterrows():
                print(f"   {row['protocol']:<30} : ${row['tvl']:>15,.2f}")
        
        print(f"\n💾 Output saved to: {output}")
        
        # Show file size
        if os.path.exists(output):
            size_bytes = os.path.getsize(output)
            size_kb = size_bytes / 1024
            print(f"📁 File size: {size_kb:.2f} KB")
        
    except Exception as e:
        logger.error(f"Failed to process: {e}")
        raise


if __name__ == "__main__":
    main()
