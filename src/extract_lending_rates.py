#!/usr/bin/env python3
"""
Fetch lending rates for all lending protocols from DeFiLlama.
Reads protocol list from Parquet file and retrieves current rates.
"""

import pandas as pd
import requests
import logging
from datetime import datetime
from typing import Dict, List, Optional
import time
from tqdm import tqdm
import json

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LendingRateFetcher:
    """Fetch lending rates from DeFiLlama for specified protocols"""

    def __init__(self, protocols_parquet: str = "defillama_protocols.parquet"):
        """Initialize with the protocols parquet file"""
        self.protocols_df = pd.read_parquet(protocols_parquet)
        self.lending_protocols = self.protocols_df[
            self.protocols_df['category'].str.lower() == 'lending'
        ].copy()
        
        logger.info(f"Loaded {len(self.lending_protocols)} lending protocols")
        
        # API endpoints
        self.base_url = "https://api.llama.fi"
        self.rate_limit_delay = 0.1  # 100ms between requests to be safe
        
    def fetch_protocol_rates(self, protocol_name: str) -> Optional[Dict]:
        """
        Fetch rates for a specific protocol using DeFiLlama API.
        Returns dictionary with rate information.
        """
        try:
            # Method 1: Try to get protocol details (includes TVL, but not always APY)
            # Using the documented endpoint: /protocol/{protocol}
            response = requests.get(
                f"{self.base_url}/protocol/{protocol_name.lower()}",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Look for rate-related fields in the response
                rates = {
                    'protocol': protocol_name,
                    'timestamp': datetime.now().isoformat(),
                    'tvl_usd': data.get('tvl', 0),
                    'chains': data.get('chains', []),
                    # These fields might not exist - we'll search for them
                    'supply_apy': None,
                    'borrow_apy': None,
                    'reward_apy': None,
                }
                
                # Search for APY fields in the response
                if 'currentChainTvls' in data:
                    # Calculate total TVL across chains
                    total_tvl = sum(data['currentChainTvls'].values())
                    rates['tvl_usd'] = total_tvl
                
                # Look for any yield/rate fields recursively
                rates.update(self._extract_rate_fields(data))
                
                return rates
            else:
                logger.debug(f"Protocol {protocol_name} returned status {response.status_code}")
                return None
                
        except requests.RequestException as e:
            logger.debug(f"Error fetching {protocol_name}: {e}")
            return None
    
    def _extract_rate_fields(self, data: Dict, prefix: str = "") -> Dict:
        """
        Recursively search for rate-related fields in API response.
        """
        rate_fields = {}
        rate_keywords = ['apy', 'apr', 'yield', 'rate', 'interest', 'reward']
        
        if isinstance(data, dict):
            for key, value in data.items():
                key_lower = key.lower()
                
                # Check if this key looks like a rate field
                if any(keyword in key_lower for keyword in rate_keywords):
                    if isinstance(value, (int, float)):
                        rate_fields[f'{prefix}{key}'] = value
                    elif isinstance(value, dict):
                        # Recursively search nested dicts
                        nested = self._extract_rate_fields(value, f"{key}.")
                        rate_fields.update(nested)
                elif isinstance(value, dict):
                    # Always search nested dicts for potential rate fields
                    nested = self._extract_rate_fields(value, f"{prefix}{key}.")
                    rate_fields.update(nested)
        
        return rate_fields
    
    def fetch_all_rates(self, max_protocols: Optional[int] = None) -> pd.DataFrame:
        """
        Fetch rates for all lending protocols.
        Returns DataFrame with rate information.
        """
        all_rates = []
        
        # Limit for testing if specified
        protocols_to_fetch = self.lending_protocols
        if max_protocols:
            protocols_to_fetch = protocols_to_fetch.head(max_protocols)
            logger.info(f"Limiting to first {max_protocols} protocols for testing")
        
        # Use tqdm for progress bar
        for idx, row in tqdm(
            protocols_to_fetch.iterrows(), 
            total=len(protocols_to_fetch),
            desc="Fetching lending rates"
        ):
            protocol_name = row['protocol']
            rates = self.fetch_protocol_rates(protocol_name)
            
            if rates:
                rates['protocol_id'] = row['protocol_id']
                all_rates.append(rates)
            
            # Respect rate limits
            time.sleep(self.rate_limit_delay)
        
        # Convert to DataFrame
        rates_df = pd.DataFrame(all_rates)
        
        logger.info(f"Successfully fetched rates for {len(rates_df)} out of {len(protocols_to_fetch)} protocols")
        
        return rates_df
    
    def save_rates(self, rates_df: pd.DataFrame, filename: Optional[str] = None):
        """Save rates DataFrame to Parquet and CSV"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"lending_rates_{timestamp}"
        
        # Save as Parquet
        parquet_file = f"{filename}.parquet"
        rates_df.to_parquet(parquet_file, index=False)
        logger.info(f"Saved rates to {parquet_file}")
        
        # Save as CSV for easy viewing
        csv_file = f"{filename}.csv"
        rates_df.to_csv(csv_file, index=False)
        logger.info(f"Saved rates to {csv_file}")
        
        return parquet_file, csv_file

def main():
    """Main execution function"""
    logger.info("🚀 Starting lending rates fetch")
    
    # Initialize fetcher
    timestamp = datetime.now().strftime("%Y%m%d")
    prefix = f"data/tvl/protocols/partition_date={timestamp}/"
    fetcher = LendingRateFetcher(
        prefix + "defillama_protocols.parquet"
    )
    
    # Fetch all rates (remove max_protocols to fetch all 612)
    # For testing, start with a small number:
    rates_df = fetcher.fetch_all_rates(max_protocols=50)  # Test with 50 first
    
    if not rates_df.empty:
        # Show summary statistics
        print("\n" + "="*60)
        print("📊 RATES FETCH SUMMARY")
        print("="*60)
        
        print(f"\n✅ Successfully fetched: {len(rates_df)} protocols")
        print(f"📈 Protocols with TVL data: {rates_df['tvl_usd'].notna().sum()}")
        
        # Display rate fields found
        rate_columns = [col for col in rates_df.columns if any(kw in col.lower() for kw in ['apy', 'apr', 'yield', 'rate'])]
        if rate_columns:
            print(f"\n💰 Rate fields found: {', '.join(rate_columns)}")
            
            # Show top protocols by TVL
            print("\n🏦 Top 10 Lending Protocols by TVL:")
            top_by_tvl = rates_df.nlargest(10, 'tvl_usd')[['protocol', 'tvl_usd'] + rate_columns[:2] if rate_columns else ['protocol']]
            print(top_by_tvl.to_string(index=False))
        else:
            print("\n⚠️ No explicit rate fields found in API responses")
            print("   This suggests rates might be in a different endpoint or require Pro API")
        
        # Save results
        parquet_file, csv_file = fetcher.save_rates(rates_df)
        
        print(f"\n💾 Data saved to:")
        print(f"   {parquet_file}")
        print(f"   {csv_file}")
    else:
        logger.error("No rates data retrieved")

if __name__ == "__main__":
    main()
