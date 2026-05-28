#!/usr/bin/env python3
"""
Extract all DeFiLlama protocols with their categories and save to Parquet.
Generates unique integer IDs for each protocol.
"""

import pandas as pd
from defillama_sdk import DefiLlama
from datetime import datetime
import logging
import os
from src.catalog import Catalog

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def extract_protocols_with_categories():
    """
    Extract all protocols from DeFiLlama with their categories.
    Returns a DataFrame with protocol_id, protocol, and category columns.
    """
    logger.info("Initializing DeFiLlama SDK...")
    client = DefiLlama()

    logger.info("Fetching all protocols...")
    try:
        protocols_data = client.tvl.getProtocols()
        logger.info(f"Successfully fetched {len(protocols_data)} protocols")
    except Exception as e:
        logger.error(f"Failed to fetch protocols: {e}")
        return None

    # Prepare data for DataFrame
    protocols_list = []

    for protocol in protocols_data:
        # Extract protocol name - handle None and whitespace values
        name = protocol.get('name', 'Unknown')
        # Convert to string, strip whitespace, and check if empty
        if name is None or str(name).strip() == '':
            name = 'Unknown'
        else:
            name = str(name).strip()  # Clean up any extra whitespace

        # Extract category - handle None and whitespace values
        category = protocol.get('category', 'Uncategorized')
        if category is None or str(category).strip() == '':
            category = 'Uncategorized'
        else:
            category = str(category).strip()  # Clean up any extra whitespace

        # Extract parent protocol slug if exists otherwise none
        parentProtocol = protocol.get('parentProtocolSlug', None)
        if isinstance(parentProtocol, str):
            if parentProtocol.strip() == '':
                parentProtocol = None
            else:
                parentProtocol = parentProtocol.strip()

        # Extract URL if exists otherwise none
        url = protocol.get('url', None)
        if isinstance(url, str):
            if url.strip() == '':
                url = None
            else:
                url = url.strip()

        protocols_list.append({
            'protocol': name,
            'category': category,
            'parent_protocol': parentProtocol,
            'url': url
        })

    # Create DataFrame
    df = pd.DataFrame(protocols_list)

    # Convert any remaining NaN values (just in case)
    df = df.fillna({'protocol': 'Unknown', 'category': 'Uncategorized'})

    logger.info(f"Created DataFrame with {len(df)} rows and {len(df.columns)} columns")

    return df


def save_to_parquet(df, prefix, filename=None):
    """
    Save DataFrame to Parquet file.
    """
    timestamp = datetime.now().strftime("%Y%m%d")

    # Create partition_date directory
    prefix_with_partition = f"{prefix}/partition_date={timestamp}"
    os.makedirs(prefix_with_partition, exist_ok=True)

    if filename is None:
        filename = f"{prefix_with_partition}/defillama_protocols.parquet"

    # Add timestamp column to DataFrame
    df_with_timestamp = df.copy()  # Create a copy to avoid modifying original
    df_with_timestamp['partition_date'] = int(timestamp)

    logger.info(f"Saving data to {filename}...")

    try:
        df_with_timestamp.to_parquet(filename, index=False, engine='pyarrow')
        logger.info(f"✅ Successfully saved to {filename}")

        return filename
    except Exception as e:
        logger.error(f"Failed to save Parquet file: {e}")
        return None


def show_statistics(df):
    """
    Display basic statistics about the extracted data.
    """
    print("\n" + "="*60)
    print("📊 PROTOCOL EXTRACTION STATISTICS")
    print("="*60)

    print(f"\n📈 Total protocols: {len(df):,}")
    print(f"🏷️  Unique categories: {df['category'].nunique()}")

    print("\n📂 Top 10 Categories by Protocol Count:")
    category_counts = df['category'].value_counts().head(10)
    for category, count in category_counts.items():
        print(f"   {category:<20} : {count:>5} protocols")

    print("\n🔝 Top 10 Protocols (by ID order):")
    print(df.head(10).to_string(index=False))

    print("\n📋 Sample of unique categories:")
    categories = sorted(df['category'].unique())[:20]
    for cat in categories:
        count = len(df[df['category'] == cat])
        print(f"   {cat:<30} : {count:>4} protocols")


def main():
    """
    Main execution function.
    """
    logger.info("🚀 Starting DeFiLlama protocol extraction")

    # Extract data
    df = extract_protocols_with_categories()

    if df is None:
        logger.error("Extraction failed. Exiting.")
        return

    # Show statistics
    show_statistics(df)

    # Save to file
    dataPrefix = "data/tvl/protocols"
    filename = save_to_parquet(df, dataPrefix)

    if filename:
        print("\n💾 Data saved successfully!")
        print(f"   File: {filename}")
        print(f"   Total protocols: {len(df):,}")
        print("   File size: ", end="")

        import os
        size_bytes = os.path.getsize(filename)
        size_mb = size_bytes / (1024 * 1024)
        print(f"{size_mb:.2f} MB")

    logger.info("🎉 Extraction completed successfully!")

    # Creating latest schema
    schemaname = f"schemas/{"/".join(dataPrefix.split("/")[-2:])}.json"
    os.makedirs("/".join(schemaname.split("/")[:-1]), exist_ok=True)
    catalog = Catalog()
    catalog.generate_schema_from_parquet(filename, schemaname)


if __name__ == "__main__":
    main()
