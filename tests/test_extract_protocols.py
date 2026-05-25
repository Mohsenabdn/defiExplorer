#!/usr/bin/env python3
"""
Unit tests for extract_protocols.py
"""

import pytest
import pandas as pd
import tempfile
import os
from datetime import datetime
from unittest.mock import Mock, patch
from extract_protocols import (
    extract_protocols_with_categories,
    save_to_parquet,
    show_statistics
)


class MockProtocol:
    """Mock protocol data structure"""
    def __init__(self, name, category):
        self.name = name
        self.category = category
        self.get = Mock(return_value=name)

    def __getitem__(self, key):
        if key == 'name':
            return self.name
        elif key == 'category':
            return self.category
        return None

    def get(self, key, default=None):
        if key == 'name':
            return self.name
        elif key == 'category':
            return self.category
        return default


class TestExtractProtocols:
    """Test cases for extract_protocols_with_categories function"""

    @patch('extract_protocols.DefiLlama')
    def test_extract_protocols_with_missing_fields(self, mock_defillama):
        """Test extraction when protocols have missing fields"""
        mock_client = Mock()
        mock_defillama.return_value = mock_client

        # Mock protocol data with missing fields
        mock_protocols_data = [
            {'name': 'Uniswap', 'category': 'Dexes'},
            {'name': None, 'category': 'Lending'},  # Explicit None name
            {'name': 'Compound', 'category': None},  # Explicit None category
            {'name': 'MakerDAO'},  # Missing category entirely
            {},  # Empty dict - missing both
            {'name': '', 'category': ''},  # Empty strings
        ]
        mock_client.tvl.getProtocols.return_value = mock_protocols_data

        df = extract_protocols_with_categories()

        # Assertions - now matching actual behavior after fix
        assert df is not None
        assert len(df) == 6

        # Check protocol names
        assert df['protocol'].tolist() == [
            'Uniswap',      # Normal
            'Unknown',      # None becomes Unknown
            'Compound',     # Normal
            'MakerDAO',     # Normal (category missing but name present)
            'Unknown',      # Empty dict - both become Unknown
            'Unknown'       # Empty string becomes Unknown
        ]

        # Check categories
        assert df['category'].tolist() == [
            'Dexes',           # Normal
            'Lending',         # Normal (name was None, but category is fine)
            'Uncategorized',   # None category becomes Uncategorized
            'Uncategorized',   # Missing category becomes Uncategorized
            'Uncategorized',   # Empty dict - both become defaults
            'Uncategorized'    # Empty string becomes Uncategorized
        ]

    @patch('extract_protocols.DefiLlama')
    def test_extract_protocols_with_none_values(self, mock_defillama):
        """Test extraction when protocol has None values"""
        mock_client = Mock()
        mock_defillama.return_value = mock_client

        mock_protocols_data = [
            {'name': None, 'category': None},
            {'name': 'ValidName', 'category': None},
            {'name': None, 'category': 'ValidCategory'},
        ]
        mock_client.tvl.getProtocols.return_value = mock_protocols_data

        df = extract_protocols_with_categories()

        assert df is not None
        assert len(df) == 3

        # First protocol: both None
        assert df.iloc[0]['protocol'] == 'Unknown'
        assert df.iloc[0]['category'] == 'Uncategorized'

        # Second protocol: valid name, None category
        assert df.iloc[1]['protocol'] == 'ValidName'
        assert df.iloc[1]['category'] == 'Uncategorized'

        # Third protocol: None name, valid category
        assert df.iloc[2]['protocol'] == 'Unknown'
        assert df.iloc[2]['category'] == 'ValidCategory'

    @patch('extract_protocols.DefiLlama')
    def test_extract_protocols_with_empty_strings(self, mock_defillama):
        """Test extraction when protocol has empty strings"""
        mock_client = Mock()
        mock_defillama.return_value = mock_client

        mock_protocols_data = [
            {'name': '', 'category': ''},
            {'name': '   ', 'category': '   '},  # This was causing the error
        ]
        mock_client.tvl.getProtocols.return_value = mock_protocols_data

        df = extract_protocols_with_categories()

        assert df is not None
        assert len(df) == 2

        # Both should be 'Unknown' after stripping
        assert df.iloc[0]['protocol'] == 'Unknown'
        assert df.iloc[0]['category'] == 'Uncategorized'

        # The whitespace-only string should become 'Unknown'
        assert df.iloc[1]['protocol'] == 'Unknown'
        assert df.iloc[1]['category'] == 'Uncategorized'

        # Verify no whitespace strings remain
        assert not df['protocol'].str.contains(r'^\s+$', na=False).any()
        assert not df['category'].str.contains(r'^\s+$', na=False).any()

    @patch('extract_protocols.DefiLlama')
    def test_extract_protocols_with_mixed_valid_invalid(self, mock_defillama):
        """Test extraction with mix of valid and invalid data"""
        mock_client = Mock()
        mock_defillama.return_value = mock_client

        mock_protocols_data = [
            {'name': 'Uniswap', 'category': 'Dexes'},
            {'name': None, 'category': 'Dexes'},  # Name missing
            {'name': 'Aave', 'category': None},   # Category missing
            {'name': 'Compound'},                  # Category missing
        ]
        mock_client.tvl.getProtocols.return_value = mock_protocols_data

        df = extract_protocols_with_categories()

        # Verify no NaN values in DataFrame
        assert not df['protocol'].isna().any()
        assert not df['category'].isna().any()

        # Verify specific values
        assert df[df['protocol'] == 'Uniswap']['category'].iloc[0] == 'Dexes'
        assert df[df['protocol'] == 'Unknown']['category'].iloc[0] == 'Dexes'
        assert df[df['protocol'] == 'Aave']['category'].iloc[0] ==\
            'Uncategorized'
        assert df[df['protocol'] == 'Compound']['category'].iloc[0] ==\
            'Uncategorized'


class TestSaveToParquet:
    """Test cases for save_to_parquet function"""

    @pytest.fixture
    def sample_dataframe(self):
        """Create a sample DataFrame for testing"""
        return pd.DataFrame({
            'protocol': ['Uniswap', 'Aave', 'Compound'],
            'category': ['Dexes', 'Lending', 'Lending']
        })

    def test_save_to_parquet_with_default_name(self, sample_dataframe):
        """Test saving with default filename"""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                # Create data directory structure
                os.makedirs("data/tvl/protocols", exist_ok=True)

                filename = save_to_parquet(sample_dataframe)

                assert filename is not None
                assert "partition_date=" in filename
                assert filename.endswith(".parquet")
                assert os.path.exists(filename)

                # Verify the saved data
                df_loaded = pd.read_parquet(filename)
                assert len(df_loaded) == 3
                assert 'partition_date' in df_loaded.columns
                assert df_loaded['protocol'].tolist() == [
                    'Uniswap', 'Aave', 'Compound'
                ]
            finally:
                os.chdir(original_cwd)

    def test_save_to_parquet_with_custom_name(self, sample_dataframe):
        """Test saving with custom filename"""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                os.makedirs("data/tvl/protocols", exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d")
                custom_filename = f"data/tvl/protocols/\
partition_date={timestamp}/custom_protocols.parquet"

                filename = save_to_parquet(sample_dataframe, custom_filename)

                assert filename == custom_filename
                assert os.path.exists(custom_filename)
            finally:
                os.chdir(original_cwd)

    def test_save_to_parquet_adds_timestamp_column(self, sample_dataframe):
        """Test that timestamp column is added correctly"""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                os.makedirs("data/tvl/protocols", exist_ok=True)

                filename = save_to_parquet(sample_dataframe)
                df_loaded = pd.read_parquet(filename)

                assert 'partition_date' in df_loaded.columns
                assert df_loaded['partition_date'].dtype == int
                current_date = int(datetime.now().strftime("%Y%m%d"))
                assert (df_loaded['partition_date'] == current_date).all()
            finally:
                os.chdir(original_cwd)

    def test_save_to_parquet_creates_directory(self, sample_dataframe):
        """Test that directory is created if it doesn't exist"""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                # Ensure directory doesn't exist initially
                assert not os.path.exists("data/tvl/protocols")

                filename = save_to_parquet(sample_dataframe)

                assert os.path.exists(os.path.dirname(filename))
                assert os.path.exists(filename)
            finally:
                os.chdir(original_cwd)

    def test_save_to_parquet_original_df_unchanged(self, sample_dataframe):
        """Test that original DataFrame is not modified"""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                os.makedirs("data/tvl/protocols", exist_ok=True)
                original_columns = sample_dataframe.columns.tolist()

                save_to_parquet(sample_dataframe)

                # Original DataFrame should not have partition_date column
                assert sample_dataframe.columns.tolist() == original_columns
                assert 'partition_date' not in sample_dataframe.columns
            finally:
                os.chdir(original_cwd)

    @patch('extract_protocols.pd.DataFrame.to_parquet')
    def test_save_to_parquet_handles_exception(
        self, mock_to_parquet, sample_dataframe
    ):
        """Test handling of exception during save"""
        mock_to_parquet.side_effect = Exception("Disk full")

        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                os.makedirs("data/tvl/protocols", exist_ok=True)

                filename = save_to_parquet(sample_dataframe)

                assert filename is None
            finally:
                os.chdir(original_cwd)

    def test_save_to_parquet_multiple_calls_different_dates(
            self, sample_dataframe
    ):
        """Test saving multiple times with different dates"""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                os.makedirs("data/tvl/protocols", exist_ok=True)

                # First save
                filename1 = save_to_parquet(sample_dataframe)

                # Simulate a different date by patching datetime
                with patch('extract_protocols.datetime') as mock_datetime:
                    mock_datetime.now.return_value.strftime.return_value =\
                        "20231225"
                    mock_datetime.now.return_value = datetime(2023, 12, 25)
                    filename2 = save_to_parquet(sample_dataframe)

                assert filename1 != filename2
                assert os.path.exists(filename1)
                assert os.path.exists(filename2)
                assert "20231225" in filename2
            finally:
                os.chdir(original_cwd)


class TestShowStatistics:
    """Test cases for show_statistics function"""

    @pytest.fixture
    def sample_dataframe(self):
        """Create a sample DataFrame for testing"""
        return pd.DataFrame({
            'protocol': [
                'Uniswap', 'Aave', 'Compound', 'MakerDAO', 'Curve',
                'Balancer', 'SushiSwap', 'PancakeSwap', 'Yearn', '1inch'
            ],
            'category': [
                'Dexes', 'Lending', 'Lending', 'CDP', 'Dexes',
                'Dexes', 'Dexes', 'Dexes', 'Yield', 'Aggregator'
            ]
        })

    def test_show_statistics_runs_successfully(self, sample_dataframe, capsys):
        """Test that show_statistics runs without errors"""
        show_statistics(sample_dataframe)
        captured = capsys.readouterr()

        assert "PROTOCOL EXTRACTION STATISTICS" in captured.out
        assert "Total protocols: 10" in captured.out
        assert "Unique categories:" in captured.out
        assert "Top 10 Categories by Protocol Count" in captured.out

    def test_show_statistics_empty_dataframe(self, capsys):
        """Test show_statistics with empty DataFrame"""
        empty_df = pd.DataFrame(columns=['protocol', 'category'])

        show_statistics(empty_df)
        captured = capsys.readouterr()

        assert "Total protocols: 0" in captured.out
        assert "Unique categories: 0" in captured.out

    def test_show_statistics_with_uncategorized(self, capsys):
        """Test show_statistics with Uncategorized category"""
        df = pd.DataFrame({
            'protocol': ['Proto1', 'Proto2', 'Proto3'],
            'category': ['Uncategorized', 'Dexes', 'Uncategorized']
        })

        show_statistics(df)
        captured = capsys.readouterr()

        assert "Uncategorized" in captured.out
        assert "Unique categories: 2" in captured.out

    def test_show_statistics_category_counts(self, sample_dataframe, capsys):
        """Test that category counts are displayed correctly"""
        show_statistics(sample_dataframe)
        captured = capsys.readouterr()

        # Check that Dexes appears with count 5
        assert "Dexes" in captured.out
        assert "5" in captured.out


class TestIntegration:
    """Integration tests for the complete workflow"""

    @patch('extract_protocols.DefiLlama')
    def test_end_to_end_workflow(self, mock_defillama):
        """Test the complete extraction and saving workflow"""
        # Setup mock
        mock_client = Mock()
        mock_defillama.return_value = mock_client
        mock_protocols_data = [
            {'name': 'Uniswap', 'category': 'Dexes'},
            {'name': 'Aave', 'category': 'Lending'},
            {'name': 'Compound', 'category': 'Lending'},
        ]
        mock_client.tvl.getProtocols.return_value = mock_protocols_data

        # Extract
        df = extract_protocols_with_categories()
        assert len(df) == 3

        # Save - use a temporary directory
        with tempfile.TemporaryDirectory() as tmpdir:
            original_dir = os.getcwd()
            os.chdir(tmpdir)
            try:
                filename = save_to_parquet(df)
                assert filename is not None
                assert os.path.exists(filename)

                # Verify saved data
                df_loaded = pd.read_parquet(filename)
                assert len(df_loaded) == 3
                assert 'partition_date' in df_loaded.columns
                assert 'protocol' in df_loaded.columns
                assert 'category' in df_loaded.columns
            finally:
                os.chdir(original_dir)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
