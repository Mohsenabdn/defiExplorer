# test_morpho_rates.py
from unittest.mock import Mock, patch
from freezegun import freeze_time

# Import the module to test
from lenders.morpho_rates import fetch_morpho_lending_rates, to_float


# Helper: sample GraphQL response with two markets (one with high supply, one with low)
def sample_graphql_response():
    return {
        "data": {
            "markets": {
                "items": [
                    {
                        "marketId": "0xabc123...",
                        "loanAsset": {
                            "address": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
                            "name": "USD Coin",
                            "symbol": "USDC",
                            "decimals": 6
                        },
                        "collateralAsset": {
                            "address": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
                            "name": "Wrapped Ether",
                            "symbol": "WETH",
                            "decimals": 18
                        },
                        "state": {
                            "supplyApy": 0.035,
                            "borrowApy": 0.052,
                            "utilization": 0.67,
                            "supplyAssets": 5000000,
                            "supplyAssetsUsd": 5000000,
                            "borrowAssets": 3350000,
                            "borrowAssetsUsd": 3350000
                        },
                        "lltv": 860000000000000000,
                        "oracle": {"address": "0x5f4ec3df9cbd43714fe2740f5e3616155c5b8419"},
                        "irmAddress": "0x464a159d4eebc4f8e2b827f45c5e1d4d8b9b1b9a"
                    },
                    {
                        "marketId": "0xdef456...",
                        "loanAsset": {
                            "address": "0xdac17f958d2ee523a2206206994597c13d831ec7",
                            "name": "Tether USD",
                            "symbol": "USDT",
                            "decimals": 6
                        },
                        "collateralAsset": {
                            "address": "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599",
                            "name": "Wrapped Bitcoin",
                            "symbol": "WBTC",
                            "decimals": 8
                        },
                        "state": {
                            "supplyApy": 0.021,
                            "borrowApy": 0.038,
                            "utilization": 0.55,
                            "supplyAssets": 2000000,
                            "supplyAssetsUsd": 2000000,
                            "borrowAssets": 1100000,
                            "borrowAssetsUsd": 1100000
                        },
                        "lltv": 750000000000000000,
                        "oracle": {"address": "0xacd0d1a0c8a3a4b5c6d7e8f9a0b1c2d3e4f5a6b7"},
                        "irmAddress": "0x1111111111111111111111111111111111111111"
                    }
                ],
                "pageInfo": {"countTotal": 2}
            }
        }
    }


# ----------------------
# Tests for to_float helper
# ----------------------
def test_to_float_with_none():
    assert to_float(None) == 0.0


def test_to_float_with_string_number():
    assert to_float("123.45") == 123.45


def test_to_float_with_invalid_string():
    assert to_float("abc", default=5.0) == 5.0


def test_to_float_with_int():
    assert to_float(42) == 42.0


# ----------------------
# Tests for fetch_morpho_lending_rates (with mocking)
# ----------------------
@freeze_time("2025-06-30 14:30:00")
@patch("lenders.morpho_rates.Catalog")
@patch("lenders.morpho_rates.pd.DataFrame.to_parquet")
@patch("lenders.morpho_rates.os.makedirs")
@patch("lenders.morpho_rates.requests.post")
def test_successful_fetch_and_save(mock_post, mock_makedirs, mock_to_parquet, MockCatalog):
    # Mock API response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = sample_graphql_response()
    mock_post.return_value = mock_response

    # Mock Catalog instance
    mock_catalog_instance = MockCatalog.return_value

    # Run function
    fetch_morpho_lending_rates()

    # Assert API called once (check URL)
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert kwargs["json"]["query"] is not None  # query string present
    assert args[0] == "https://api.morpho.org/graphql"

    # Assert directories created
    mock_makedirs.assert_any_call("data/lenders/morpho_rates/partition_date=20250630", exist_ok=True)
    # The schema directory creation may be called once or twice; we check at least the required one
    mock_makedirs.assert_any_call("schemas/lenders", exist_ok=True)

    # Assert to_parquet called with correct path
    expected_output = "data/lenders/morpho_rates/partition_date=20250630/morpho_rates.parquet"
    mock_to_parquet.assert_called_once_with(expected_output, index=False, engine='pyarrow')

    # Assert Catalog.generate_schema_from_parquet called
    expected_schema_path = "schemas/lenders/morpho_rates.json"
    mock_catalog_instance.generate_schema_from_parquet.assert_called_once_with(
        expected_output, expected_schema_path
    )


@patch("lenders.morpho_rates.logger")
@patch("lenders.morpho_rates.requests.post")
def test_api_request_failure(mock_post, mock_logger):
    mock_response = Mock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    mock_post.return_value = mock_response

    fetch_morpho_lending_rates()

    mock_logger.error.assert_called_with(
        "API request failed with status 500: Internal Server Error"
    )


@patch("lenders.morpho_rates.logger")
@patch("lenders.morpho_rates.requests.post")
def test_graphql_errors_in_response(mock_post, mock_logger):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"errors": [{"message": "Something went wrong"}]}
    mock_post.return_value = mock_response

    fetch_morpho_lending_rates()

    mock_logger.error.assert_called_with(
        "GraphQL errors: [{'message': 'Something went wrong'}]"
    )


@patch("lenders.morpho_rates.logger")
@patch("lenders.morpho_rates.requests.post")
def test_empty_markets_response(mock_post, mock_logger):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": {"markets": {"items": []}}}
    mock_post.return_value = mock_response

    fetch_morpho_lending_rates()

    mock_logger.warning.assert_called_with("No markets data returned.")


@freeze_time("2025-06-30 14:30:00")
@patch("lenders.morpho_rates.Catalog")
@patch("lenders.morpho_rates.pd.DataFrame.to_parquet")
@patch("lenders.morpho_rates.os.makedirs")
@patch("lenders.morpho_rates.requests.post")
def test_partition_date_correct(mock_post, mock_makedirs, mock_to_parquet, MockCatalog):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = sample_graphql_response()
    mock_post.return_value = mock_response

    # Run function
    fetch_morpho_lending_rates()

    # Verify output path contains the correct partition date
    expected_path = "data/lenders/morpho_rates/partition_date=20250630/morpho_rates.parquet"
    mock_to_parquet.assert_called_once_with(expected_path, index=False, engine='pyarrow')


@patch("lenders.morpho_rates.Catalog")
@patch("lenders.morpho_rates.pd.DataFrame.to_parquet")
@patch("lenders.morpho_rates.os.makedirs")
@patch("lenders.morpho_rates.requests.post")
def test_schema_path_calculation(mock_post, mock_makedirs, mock_to_parquet, MockCatalog):
    """Verify schema path is built correctly from partition path."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = sample_graphql_response()
    mock_post.return_value = mock_response

    mock_catalog_instance = MockCatalog.return_value

    fetch_morpho_lending_rates()

    expected_schema_path = "schemas/lenders/morpho_rates.json"
    mock_catalog_instance.generate_schema_from_parquet.assert_called_once()
    actual_args = mock_catalog_instance.generate_schema_from_parquet.call_args[0]
    assert actual_args[1] == expected_schema_path
