import pandas as pd
import os
from unittest.mock import Mock, patch
import tempfile
import shutil

# Import the module to test
from extract_protocols import (
    extract_protocols_with_categories,
    save_to_parquet,
    show_statistics
)


class TestExtractProtocols:
    """Tests for protocol extraction functionality."""

    @patch('extract_protocols.DefiLlama')
    def test_extract_protocols_with_categories_success(self, mock_defillama):
        """Test successful extraction of protocols with categories."""
        # Mock the API response
        mock_client = Mock()
        mock_client.tvl.getProtocols.return_value = [
            {
                'name': 'Uniswap', 'category': 'DEX',
                'url': 'https://uniswap.org'
            },
            {
                'name': 'Aave', 'category': 'Lending',
                'parentProtocolSlug': 'v3', 'url': 'https://aave.com'
            },
            {
                'name': '  Curve  ', 'category': '  DEX  ',
                'parentProtocolSlug': '', 'url': ''
            },
            {'name': None, 'category': None},
            {'name': '', 'category': '', 'parentProtocolSlug': '', 'url': ''},
        ]
        mock_defillama.return_value = mock_client

        # Execute
        df = extract_protocols_with_categories()

        # Assert
        assert len(df) == 5
        assert list(df.columns) == [
            'protocol', 'category', 'parent_protocol', 'url'
        ]

        # Check name cleaning
        assert df.iloc[0]['protocol'] == 'Uniswap'
        assert df.iloc[2]['protocol'] == 'Curve'
        assert df.iloc[3]['protocol'] == 'Unknown'
        assert df.iloc[4]['protocol'] == 'Unknown'

        # Check category cleaning
        assert df.iloc[0]['category'] == 'DEX'
        assert df.iloc[2]['category'] == 'DEX'
        assert df.iloc[3]['category'] == 'Uncategorized'

        # Check parent protocol handling
        assert pd.isna(df.iloc[0]['parent_protocol'])
        assert df.iloc[1]['parent_protocol'] == 'v3'
        assert pd.isna(df.iloc[2]['parent_protocol'])

        # Check URL handling
        assert df.iloc[0]['url'] == 'https://uniswap.org'
        assert df.iloc[1]['url'] == 'https://aave.com'
        assert pd.isna(df.iloc[2]['url'])

    @patch('extract_protocols.DefiLlama')
    def test_extract_protocols_with_categories_api_error(self, mock_defillama):
        """Test handling of API errors during protocol extraction."""
        mock_client = Mock()
        mock_client.tvl.getProtocols.side_effect = Exception(
            "API connection failed"
        )
        mock_defillama.return_value = mock_client

        df = extract_protocols_with_categories()

        assert df is None

    @patch('extract_protocols.DefiLlama')
    def test_extract_protocols_empty_response(self, mock_defillama):
        """Test handling of empty API response."""
        mock_client = Mock()
        mock_client.tvl.getProtocols.return_value = []
        mock_defillama.return_value = mock_client

        df = extract_protocols_with_categories()

        assert df is not None
        assert len(df) == 0
        assert len(df.columns) == 0 or list(df.columns) == []


class TestSaveToParquet:
    """Tests for parquet saving functionality."""

    def setup_method(self):
        """Set up temporary directory for each test."""
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Clean up temporary directory after each test."""
        shutil.rmtree(self.temp_dir)

    def test_save_to_parquet_success(self):
        """Test successful saving of DataFrame to parquet."""
        df = pd.DataFrame({
            'protocol': ['Uniswap', 'Aave'],
            'category': ['DEX', 'Lending'],
            'parent_protocol': [None, 'v3'],
            'url': ['https://uniswap.org', 'https://aave.com']
        })

        filename = save_to_parquet(
            df, self.temp_dir, f"{self.temp_dir}/test.parquet"
        )

        assert filename is not None
        assert os.path.exists(filename)

        # Verify the saved file
        saved_df = pd.read_parquet(filename)
        assert 'partition_date' in saved_df.columns
        assert len(saved_df) == 2
        assert saved_df['protocol'].iloc[0] == 'Uniswap'

        # Clean up
        os.remove(filename)

    def test_save_to_parquet_empty_dataframe(self):
        """Test saving an empty DataFrame."""
        df = pd.DataFrame(columns=['protocol', 'category'])

        filename = save_to_parquet(
            df, self.temp_dir, f"{self.temp_dir}/empty.parquet"
        )

        assert filename is not None
        assert os.path.exists(filename)

        saved_df = pd.read_parquet(filename)
        assert 'partition_date' in saved_df.columns
        assert len(saved_df) == 0


class TestShowStatistics:
    """Tests for statistics display functionality."""

    def test_show_statistics_with_data(self, capsys):
        """Test statistics display with valid data."""
        df = pd.DataFrame({
            'protocol': ['Uniswap', 'Aave', 'Curve', 'Compound', 'Maker'],
            'category': ['DEX', 'Lending', 'DEX', 'Lending', 'CDP']
        })

        show_statistics(df)

        captured = capsys.readouterr()
        assert "Total protocols: 5" in captured.out
        assert "Unique categories: 3" in captured.out
        assert "DEX" in captured.out
        assert "Lending" in captured.out
        assert "CDP" in captured.out

    def test_show_statistics_empty_dataframe(self, capsys):
        """Test statistics display with empty DataFrame."""
        df = pd.DataFrame(columns=['protocol', 'category'])

        show_statistics(df)

        captured = capsys.readouterr()
        assert "Total protocols: 0" in captured.out
        assert "Unique categories: 0" in captured.out
