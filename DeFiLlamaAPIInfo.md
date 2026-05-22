Here's a concise summary of the DeFiLlama API and how to get started with it for your lending rate aggregator.

## 🎯 What DeFiLlama API Offers

DeFiLlama provides a comprehensive REST API that aggregates DeFi data across 100+ protocols and multiple chains. For a lending rate aggregator, you'll primarily use the **yields endpoint**, which returns standardized APY data for lending pools, liquidity pools, and other yield-generating opportunities.

### Core Endpoints You'll Use

| Endpoint | Description | For Your App |
|----------|-------------|---------------|
| `GET /yields` | Lists all pools with their current APYs | **Primary endpoint** — Get lending rates across protocols |
| `GET /yields?token=USDC` | Filter pools by specific token | Find best USDC lending rates |
| `GET /protocols` | List all tracked protocols with TVL | Get protocol slugs for filtering |
| `GET /chains` | Chain information | Filter by blockchain (Arbitrum, Base, etc.) |

### What the Yields Data Looks Like

Each pool returned by the `/yields` endpoint follows this structure:

```json
{
  "pool": "0x3ed3b47dd13ec9a98b44e6204a523e766b225811-ethereum",
  "chain": "Ethereum",
  "project": "aave",
  "symbol": "USDC",
  "tvlUsd": 1000450000,
  "apyBase": 3.25,           // Base APY from lending fees
  "apyReward": 1.10,         // Bonus APY from reward tokens
  "apy": 4.35,               // Total APY (base + reward)
  "rewardTokens": ["0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9"],
  "underlyingTokens": ["0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"],
  "poolMeta": "v3 market",
  "url": "https://app.aave.com/reserve-overview/USDC"
}
```

For lending protocols like Aave, you also get borrowing-specific fields:
- `apyBaseBorrow` — Interest rate for borrowers
- `apyRewardBorrow` — Bonus rewards for borrowing
- `totalSupplyUsd` — Total deposits in the pool
- `totalBorrowUsd` — Total loans outstanding
- `ltv` — Loan-to-value ratio (max borrowing power)

### Pricing Tiers

| Tier | Cost | Rate Limit | Best For |
|------|------|------------|----------|
| **Free (Open)** | $0 | Standard limits | Development and MVPs |
| **API Pro** | $300/month or $3,000/year | 1,000 requests/min, 1M calls/month | Production apps |

**Start with the free tier.** You can build and test your entire MVP without paying anything. Upgrade only when you hit limits or need premium endpoints like historical token prices and token unlock schedules.

## 🚀 Quick Start: Fetch Lending Rates

Here's a minimal example to get all lending opportunities:

```javascript
// Fetch all yield pools
const response = await fetch('https://api.llama.fi/yields');
const pools = await response.json();

// Filter for lending pools with USDC
const lendingPools = pools.filter(pool => 
  pool.symbol === 'USDC' && 
  pool.tvlUsd > 1000000  // >$1M TVL for reliability
);

// Sort by total APY
const bestRates = lendingPools.sort((a, b) => b.apy - a.apy);
console.log(bestRates.map(p => ({
  protocol: p.project,
  chain: p.chain,
  apy: p.apy,
  tvlUsd: p.tvlUsd
})));
```

## 💡 Key Things to Know

### Data Freshness
- Pool data (APY, TVL) is updated **every hour**
- TVL and borrow data updates **every 30 minutes**
- Sufficient for a lending rate aggregator since rates change slowly based on pool utilization

### Standardized Data Quality
DeFiLlama normalizes data across protocols using consistent methodology:
- **Conservative APY calculation** — omits pre-mined rewards and uses unboosted values
- **Minimum TVL filter** — pools below $10k TVL are excluded from API
- **Stablecoin filter** — pools need >$1M TVL and audited protocols for stablecoin dashboards

### What You Won't Get on Free Tier
The free API gives you everything needed for MVP. Paid tier adds:
- Historical token prices
- Token unlock schedules
- Active user metrics
- Higher rate limits

## 📝 Your First Step

1. **Test the endpoint in your browser** — visit `https://api.llama.fi/yields`
2. **Filter manually** — look for USDC pools on Arbitrum or Base
3. **Build a simple dashboard** — display top 10 lending rates with protocol names and chains

You can build a completely functional rate aggregator with just the free API. DeFiLlama has already done the hard work of integrating 100+ protocols — your job is to present that data in a way that helps users make faster, smarter decisions.

Ready to try a specific API call, or want to see how to filter for just Arbitrum lending pools?