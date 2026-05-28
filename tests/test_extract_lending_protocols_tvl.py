import pytest
import pandas as pd
import numpy as np
import os
from unittest.mock import Mock, patch
import tempfile
import shutil

from extract_lending_protocols_tvl import get_lending_protocols_tvl


class TestGetLendingProtocolsTVL:
    """Tests for lending protocols TVL extraction functionality."""

    def setup_method(self):
        """Set up temporary directory and test data for each test."""
        self.temp_dir = tempfile.mkdtemp()

        # Create sample protocol data
        self.sample_protocols = pd.DataFrame({
            'protocol': ['Aave', 'Compound', 'Maker', 'Uniswap', 'Curve'],
            'category': ['Lending', 'lending', 'CDP', 'DEX', 'Lending'],
            'url': [
                'https://aave.com', 'https://compound.finance',
                'https://makerdao.com', 'https://uniswap.org',
                'https://curve.fi'
            ],
            'parent_protocol': [np.nan, np.nan, 'maker', np.nan, np.nan]
        })

        # Create sample protocol with parent protocol
        self.sample_with_parent = pd.DataFrame({
            'protocol': ['Aave V3', 'Compound V2'],
            'category': ['Lending', 'lending'],
            'url': ['https://aave.com', 'https://compound.finance'],
            'parent_protocol': ['aave', 'compound']
        })

    def teardown_method(self):
        """Clean up temporary directory after each test."""
        shutil.rmtree(self.temp_dir)

    def create_input_parquet(self, df):
        """Helper to create input parquet file."""
        input_path = os.path.join(self.temp_dir, 'input.parquet')
        df.to_parquet(input_path, index=False)
        return input_path

    def test_successful_tvl_extraction(self):
        """Test successful extraction of TVL for lending protocols."""
        # Create input file
        input_path = self.create_input_parquet(self.sample_protocols)
        output_path = os.path.join(self.temp_dir, 'output.parquet')

        # Mock the DeFiLlama SDK
        with patch('extract_lending_protocols_tvl.DefiLlama') as MockDefiLlama:
            mock_client = Mock()
            mock_client.tvl.getTvl.side_effect = [
                1000000000, 500000000, 750000000
            ]
            mock_client.tvl.getProtocol.return_value = {
                'tvl': [{'totalLiquidityUSD': 800000000}]
            }
            MockDefiLlama.return_value = mock_client

            # Execute
            result = get_lending_protocols_tvl(input_path, output_path)

            # Assert
            assert len(result) == 3  # Only lending protocols
            assert list(result.columns) == ['protocol', 'url', 'tvl']
            assert result['tvl'].notna().sum() == 3
            assert os.path.exists(output_path)

            # Verify the protocols extracted
            protocols = result['protocol'].tolist()
            assert 'Aave' in protocols
            assert 'Compound' in protocols
            assert 'Curve' in protocols

    def test_no_lending_protocols(self):
        """Test when no lending protocols are found."""
        # Create input with no lending protocols
        no_lending_df = pd.DataFrame({
            'protocol': ['Uniswap', 'Curve'],
            'category': ['DEX', 'DEX'],
            'url': ['https://uniswap.org', 'https://curve.fi'],
            'parent_protocol': [np.nan, np.nan]
        })

        input_path = self.create_input_parquet(no_lending_df)
        output_path = os.path.join(self.temp_dir, 'output.parquet')

        # Execute
        result = get_lending_protocols_tvl(input_path, output_path)

        # Assert
        assert len(result) == 0
        assert list(result.columns) == ['protocol', 'url', 'tvl']
        assert os.path.exists(output_path)

        # Verify file is saved
        saved_df = pd.read_parquet(output_path)
        assert len(saved_df) == 0

    def test_missing_required_columns(self):
        """Test error when required columns are missing."""
        # Create DataFrame missing required columns
        invalid_df = pd.DataFrame({
            'protocol': ['Aave'],
            'category': ['Lending']
            # Missing 'url' and 'parent_protocol'
        })

        input_path = self.create_input_parquet(invalid_df)
        output_path = os.path.join(self.temp_dir, 'output.parquet')

        # Execute and assert error
        with pytest.raises(ValueError) as exc_info:
            get_lending_protocols_tvl(input_path, output_path)

        assert "must contain 'url' column" in str(exc_info.value)

    def test_parent_protocol_usage(self):
        """Test that parent_protocol is used when available."""
        input_path = self.create_input_parquet(self.sample_with_parent)
        output_path = os.path.join(self.temp_dir, 'output.parquet')

        with patch('extract_lending_protocols_tvl.DefiLlama') as MockDefiLlama:
            mock_client = Mock()
            mock_client.tvl.getTvl.side_effect = [2000000000, 1000000000]
            MockDefiLlama.return_value = mock_client

            result = get_lending_protocols_tvl(input_path, output_path)

            # Verify getTvl was called with parent_protocol names
            calls = mock_client.tvl.getTvl.call_args_list
            assert calls[0][0][0] == 'aave'  # First call used parent_protocol
            # Second call used parent_protocol
            assert calls[1][0][0] == 'compound'

            # Result should show original protocol names
            assert result['protocol'].iloc[0] == 'aave'
            assert result['protocol'].iloc[1] == 'compound'

    def test_api_error_fallback_to_get_protocol(self):
        """Test fallback to getProtocol when getTvl fails."""
        input_path = self.create_input_parquet(self.sample_protocols.head(1))
        output_path = os.path.join(self.temp_dir, 'output.parquet')

        with patch('extract_lending_protocols_tvl.DefiLlama') as MockDefiLlama:
            mock_client = Mock()
            # Make getTvl fail with API error
            mock_client.tvl.getTvl.side_effect = Exception(
                "ApiError: rate limit"
            )
            # Make getProtocol succeed
            mock_client.tvl.getProtocol.return_value = {
                'tvl': [{'totalLiquidityUSD': 1500000000}]
            }
            MockDefiLlama.return_value = mock_client

            result = get_lending_protocols_tvl(input_path, output_path)

            # Should have tried getTvl, then fallback to getProtocol
            assert mock_client.tvl.getTvl.called
            assert mock_client.tvl.getProtocol.called
            assert result['tvl'].iloc[0] == 1500000000

    def test_api_error_both_methods_fail(self):
        """Test when both TVL retrieval methods fail."""
        input_path = self.create_input_parquet(self.sample_protocols.head(1))
        output_path = os.path.join(self.temp_dir, 'output.parquet')

        with patch('extract_lending_protocols_tvl.DefiLlama') as MockDefiLlama:
            mock_client = Mock()
            # Both methods fail
            mock_client.tvl.getTvl.side_effect = Exception(
                "ApiError: not found"
            )
            mock_client.tvl.getProtocol.side_effect = Exception(
                "ApiError: not found"
            )
            MockDefiLlama.return_value = mock_client

            result = get_lending_protocols_tvl(input_path, output_path)

            # TVL should be None
            assert pd.isna(result['tvl'].iloc[0])

            # Both methods should have been called
            assert mock_client.tvl.getTvl.called
            assert mock_client.tvl.getProtocol.called

    def test_case_insensitive_category_filtering(self):
        """Test that category filtering is case-insensitive."""
        # Create protocols with various case formats
        mixed_case_df = pd.DataFrame({
            'protocol': ['Aave', 'Compound', 'Maker'],
            'category': ['LENDING', 'lEnDiNg', 'Lending'],
            'url': [
                'https://aave.com', 'https://compound.finance',
                'https://makerdao.com'
            ],
            'parent_protocol': [np.nan, np.nan, np.nan]
        })

        input_path = self.create_input_parquet(mixed_case_df)
        output_path = os.path.join(self.temp_dir, 'output.parquet')

        with patch('extract_lending_protocols_tvl.DefiLlama') as MockDefiLlama:
            mock_client = Mock()
            mock_client.tvl.getTvl.return_value = 1000000000
            MockDefiLlama.return_value = mock_client

            result = get_lending_protocols_tvl(input_path, output_path)

            # All three should be caught by case-insensitive filter
            assert len(result) == 3

    def test_empty_input_file(self):
        """Test handling of empty input parquet file."""
        empty_df = pd.DataFrame(
            columns=['protocol', 'category', 'url', 'parent_protocol']
        )
        input_path = self.create_input_parquet(empty_df)
        output_path = os.path.join(self.temp_dir, 'output.parquet')

        result = get_lending_protocols_tvl(input_path, output_path)

        assert len(result) == 0
        assert list(result.columns) == ['protocol', 'url', 'tvl']
        assert os.path.exists(output_path)

    def test_duplicate_protocols_removed(self):
        """Test that duplicate protocols are removed from output."""
        # Create input with duplicate lending protocols
        duplicate_df = pd.DataFrame({
            'protocol': ['Aave', 'Aave', 'Compound'],
            'category': ['Lending', 'Lending', 'Lending'],
            'url': [
                'https://aave.com', 'https://aave.com',
                'https://compound.finance'
            ],
            'parent_protocol': [np.nan, np.nan, np.nan]
        })

        input_path = self.create_input_parquet(duplicate_df)
        output_path = os.path.join(self.temp_dir, 'output.parquet')

        with patch('extract_lending_protocols_tvl.DefiLlama') as MockDefiLlama:
            mock_client = Mock()
            mock_client.tvl.getTvl.return_value = 1000000000
            MockDefiLlama.return_value = mock_client

            result = get_lending_protocols_tvl(input_path, output_path)

            # Should have removed duplicate 'Aave'
            assert len(result) == 2
            assert result['protocol'].tolist() == ['Aave', 'Compound']

    def test_non_api_exception_handling(self):
        """Test handling of non-API exceptions."""
        input_path = self.create_input_parquet(self.sample_protocols.head(1))
        output_path = os.path.join(self.temp_dir, 'output.parquet')

        with patch('extract_lending_protocols_tvl.DefiLlama') as MockDefiLlama:
            mock_client = Mock()
            # Non-API exception
            mock_client.tvl.getTvl.side_effect = ValueError(
                "Invalid parameter"
            )
            MockDefiLlama.return_value = mock_client

            result = get_lending_protocols_tvl(input_path, output_path)

            # TVL should be None after non-API exception
            assert pd.isna(result['tvl'].iloc[0])
