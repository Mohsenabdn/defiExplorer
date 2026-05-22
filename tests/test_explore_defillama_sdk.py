"""
Unit tests for explore_defillama_sdk.py
Tests the DefiLlama SDK Explorer functionality
"""

import pytest
from unittest.mock import Mock, patch
import json
from pathlib import Path

# Import the module to test
import explore_defillama_sdk as explorer


class TestExploreClientMethods:
    """Test the explore_client_methods function"""

    def test_explore_client_methods_with_mock_client(self):
        """Test exploring methods on a mock client"""
        # Create a mock client with some attributes
        mock_client = Mock()
        mock_client.method1 = lambda: None
        mock_client.method2 = lambda x: x
        mock_client.attribute1 = "test"
        mock_client._private_method = lambda: None  # Should be filtered out

        # Call the function
        result = explorer.explore_client_methods(mock_client)

        # Verify results
        assert isinstance(result, list)
        assert "method1" in result
        assert "method2" in result
        assert "attribute1" in result
        assert "_private_method" not in result

    def test_explore_client_methods_empty_client(self):
        """Test exploring methods on a client with no public methods"""
        mock_client = Mock()
        # Remove all public methods by creating a client with only private ones
        mock_client._private = lambda: None

        with patch('builtins.print') as mock_print:
            result = explorer.explore_client_methods(mock_client)
            assert isinstance(result, list)
            # Verify print was called with header
            mock_print.assert_any_call("=" * 60)
            mock_print.assert_any_call("🔍 EXPLORING DEFILLAMA SDK CLIENT")
            mock_print.assert_any_call("=" * 60)

    def test_explore_client_methods_error_handling(self):
        """Test error handling when accessing attributes fails"""
        class ProblematicClient:
            def __getattribute__(self, name):
                if name == 'problem_attr':
                    raise AttributeError("Access denied")
                return super().__getattribute__(name)

        client = ProblematicClient()
        # Add a normal attribute
        client.normal_attr = "works"

        # Should not raise exception
        result = explorer.explore_client_methods(client)
        assert "normal_attr" in result


class TestExploreSubmodules:
    """Test the explore_submodules function"""

    def test_explore_submodules_with_mock_submodule(self):
        """Test exploring a submodule with methods"""
        mock_client = Mock()

        # Create a mock submodule with methods
        mock_submodule = Mock()
        mock_submodule.method1 = lambda x: x
        mock_submodule.method2 = lambda: "test"

        # Add docstrings
        mock_submodule.method1.__doc__ = "Method 1 docstring"
        mock_submodule.method2.__doc__ = "Method 2 docstring"

        # Attach submodule to client
        mock_client.test_submodule = mock_submodule

        # Call the function
        result = explorer.explore_submodules(mock_client, "test_submodule")

        # Verify results
        assert result is not None
        assert "method1" in result
        assert "method2" in result
        assert result["method1"]["docstring"] == "Method 1 docstring"
        assert "signature" in result["method1"]

    def test_explore_submodules_not_found(self):
        """Test exploring a non-existent submodule"""
        mock_client = Mock()
        # Ensure submodule doesn't exist
        del mock_client.nonexistent

        result = explorer.explore_submodules(mock_client, "nonexistent")
        assert result is None

    def test_explore_submodules_with_attributes(self):
        """Test submodule with both methods and attributes"""
        mock_client = Mock()
        mock_submodule = Mock()
        mock_submodule.method = lambda: None
        mock_submodule.attribute = "some value"
        mock_client.test_submodule = mock_submodule

        with patch('builtins.print') as mock_print:
            result = explorer.explore_submodules(mock_client, "test_submodule")
            assert result is not None
            # Verify both method and attribute were printed
            assert mock_print.call_count > 0


class TestTestApiCall:
    """Test the test_api_call function"""

    def test_test_api_call_success(self):
        """Test successful API call"""
        mock_method = Mock(return_value={"data": "test"})
        result = explorer.test_api_call(mock_method, "arg1", key="value")

        assert result == {"data": "test"}
        mock_method.assert_called_once_with("arg1", key="value")

    def test_test_api_call_error(self):
        """Test API call that raises an exception"""
        mock_method = Mock(side_effect=Exception("API Error"))

        with patch('builtins.print') as mock_print:
            result = explorer.test_api_call(mock_method)
            assert result is None
            mock_print.assert_called_once()
            assert "Error: API Error" in mock_print.call_args[0][0]

    def test_test_api_call_no_args(self):
        """Test API call with no arguments"""
        mock_method = Mock(return_value="success")
        result = explorer.test_api_call(mock_method)

        assert result == "success"
        mock_method.assert_called_once_with()


class TestExploreDataStructure:
    """Test the explore_data_structure function"""

    def test_explore_data_structure_dict(self):
        """Test exploring a dictionary structure"""
        test_data = {
            "key1": "value1",
            "key2": 123,
            "key3": {"nested": "data"},
            "key4": [1, 2, 3],
            "key5": "another",
            "key6": "more data"
        }

        with patch('builtins.print') as mock_print:
            explorer.explore_data_structure(test_data, "TestDict", max_depth=1)

            # Verify print was called
            assert mock_print.call_count > 0
            # Check that we printed dictionary info
            print_calls = [str(call) for call in mock_print.call_args_list]
            assert any("dict with 6 keys" in str(call) for call in print_calls)

    def test_explore_data_structure_list(self):
        """Test exploring a list structure"""
        test_data = [{"item": 1}, {"item": 2}, {"item": 3}]

        with patch('builtins.print') as mock_print:
            explorer.explore_data_structure(test_data, "TestList", max_depth=1)

            # Verify list info was printed
            print_calls = [str(call) for call in mock_print.call_args_list]
            assert any(
                "list with 3 items" in str(call) for call in print_calls
            )

    def test_explore_data_structure_primitive(self):
        """Test exploring a primitive data type"""
        test_data = "simple string"

        with patch('builtins.print') as mock_print:
            explorer.explore_data_structure(test_data, "TestPrimitive")

            # Verify primitive was printed
            print_calls = [str(call) for call in mock_print.call_args_list]
            assert any(
                "TestPrimitive: str = simple string" in str(call)
                for call in print_calls
            )

    def test_explore_data_structure_max_depth(self):
        """Test that max depth parameter limits recursion"""
        test_data = {
            "level1": {
                "level2": {
                    "level3": "deep"
                }
            }
        }

        with patch('builtins.print') as mock_print:
            explorer.explore_data_structure(test_data, "TestDict", max_depth=2)

            # Should still work without recursion errors
            assert mock_print.call_count > 0

    def test_explore_data_structure_empty_dict(self):
        """Test exploring an empty dictionary"""
        test_data = {}

        with patch('builtins.print') as mock_print:
            explorer.explore_data_structure(test_data, "EmptyDict")

            print_calls = [str(call) for call in mock_print.call_args_list]
            assert any("dict with 0 keys" in str(call) for call in print_calls)


class TestMainFunction:
    """Test the main function"""

    @patch('explore_defillama_sdk.DefiLlama')
    @patch('builtins.print')
    def test_main_basic_execution(self, mock_print, mock_defillama_class):
        """Test main function executes without errors"""
        # Mock the DefiLlama client
        mock_client = Mock()
        mock_defillama_class.return_value = mock_client

        # Mock submodules
        mock_client.tvl = Mock()
        mock_client.fees = Mock()

        # Mock protocol data - return a LIST, not a Mock
        mock_protocols = [
            {"name": "Aave", "category": "Lending", "id": "aave"},
            {"name": "Compound", "category": "Lending", "id": "compound"},
            {"name": "Uniswap", "category": "Dex", "id": "uniswap"}
        ]
        mock_client.tvl.getProtocols.return_value = mock_protocols

        # Mock Aave details
        mock_aave_details = {
            "name": "Aave",
            "category": "Lending",
            "apy": 0.05,
            "supplyRate": 0.03,
            "borrowRate": 0.07
        }
        mock_client.tvl.getProtocol.return_value = mock_aave_details

        # Run main function
        explorer.main()

        # Verify client was initialized
        mock_defillama_class.assert_called_once()

        # Verify API calls were made
        mock_client.tvl.getProtocols.assert_called_once()
        mock_client.tvl.getProtocol.assert_called_with('aave')

        # Verify file was saved
        assert Path('sdk_exploration_results.json').exists()

        # Clean up
        Path('sdk_exploration_results.json').unlink()

    @patch('explore_defillama_sdk.DefiLlama')
    def test_main_with_no_submodules(self, mock_defillama_class):
        """Test main function when no submodules are available"""
        mock_client = Mock()

        # Create proper mock submodules that return empty lists
        mock_tvl = Mock()
        mock_tvl.getProtocols.return_value = []  # Empty list, not Mock
        mock_client.tvl = mock_tvl

        mock_fees = Mock()
        mock_fees.getFees.return_value = []  # Empty list, not Mock
        mock_client.fees = mock_fees

        mock_defillama_class.return_value = mock_client

        with patch('builtins.print') as mock_print:
            explorer.main()

            # Should still complete without errors
            assert mock_print.call_count > 0
            # Verify we tried to get protocols
            mock_client.tvl.getProtocols.assert_called_once()

        # Clean up
        if Path('sdk_exploration_results.json').exists():
            Path('sdk_exploration_results.json').unlink()

    @patch('explore_defillama_sdk.DefiLlama')
    def test_main_with_api_error(self, mock_defillama_class):
        """Test main function handling API errors"""
        mock_client = Mock()
        mock_defillama_class.return_value = mock_client

        # Mock API error - getProtocols raises exception
        mock_tvl = Mock()
        mock_tvl.getProtocols.side_effect = Exception("API Connection Error")
        # Make getProtocol return None to simulate failure
        # Important: return None, not a Mock
        mock_tvl.getProtocol.return_value = None
        mock_client.tvl = mock_tvl

        # Ensure fees submodule exists with proper return values
        mock_fees = Mock()
        # Empty list to avoid iteration issues
        mock_fees.getFees.return_value = []
        mock_client.fees = mock_fees

        # Should not crash
        explorer.main()

        # Clean up
        if Path('sdk_exploration_results.json').exists():
            Path('sdk_exploration_results.json').unlink()

    @patch('explore_defillama_sdk.DefiLlama')
    def test_main_file_save_on_error(self, mock_defillama_class):
        """Test that file is saved even if there are errors"""
        mock_client = Mock()
        mock_defillama_class.return_value = mock_client

        # Mock partial failure - getProtocols fails
        mock_tvl = Mock()
        mock_tvl.getProtocols.side_effect = Exception("API Error")
        # Make getProtocol return None to simulate failure
        # Important: return None, not a Mock
        mock_tvl.getProtocol.return_value = None
        mock_client.tvl = mock_tvl

        # Ensure fees submodule exists with proper return values
        mock_fees = Mock()
        # Empty list to avoid iteration issues
        mock_fees.getFees.return_value = []
        mock_client.fees = mock_fees

        explorer.main()

        # File should still be created
        assert Path('sdk_exploration_results.json').exists()

        # Verify file contains valid JSON
        with open('sdk_exploration_results.json', 'r') as f:
            data = json.load(f)
            assert 'available_submodules' in data

        # Clean up
        Path('sdk_exploration_results.json').unlink()


class TestIntegrationWithRealSDK:
    """Integration tests (these should be run with actual SDK if available)"""

    @pytest.mark.integration
    def test_real_defillama_sdk_import(self):
        """Test that we can actually import the SDK"""
        try:
            from defillama_sdk import DefiLlama
            client = DefiLlama()
            assert client is not None
        except ImportError:
            pytest.skip("defillama_sdk not installed")

    @pytest.mark.integration
    def test_real_client_methods(self):
        """Test with real SDK client (if available)"""
        try:
            from defillama_sdk import DefiLlama
            client = DefiLlama()

            # Should not raise errors
            methods = explorer.explore_client_methods(client)
            assert isinstance(methods, list)
        except ImportError:
            pytest.skip("defillama_sdk not installed")


class TestEdgeCases:
    """Test edge cases and error conditions"""

    def test_explore_submodules_with_none_client(self):
        """Test exploring submodules with None as client"""
        result = explorer.explore_submodules(None, "test")
        assert result is None  # Returns None instead of raising exception

    def test_test_api_call_with_none_method(self):
        """Test test_api_call with None as method"""
        result = explorer.test_api_call(None)
        assert result is None

    def test_explore_data_structure_recursive_list(self):
        """Test exploring a recursive data structure"""
        recursive_list = [1, 2, 3]
        recursive_list.append(recursive_list)  # Create self-reference

        # Should handle without infinite recursion
        with patch('builtins.print') as mock_print:
            explorer.explore_data_structure(
                recursive_list, "RecursiveList", max_depth=3
            )
            assert mock_print.call_count > 0

    def test_explore_data_structure_large_dict(self):
        """Test exploring a very large dictionary"""
        large_dict = {f"key_{i}": f"value_{i}" for i in range(1000)}

        with patch('builtins.print') as mock_print:
            explorer.explore_data_structure(
                large_dict, "LargeDict", max_depth=1
            )
            # Should only print first 5 keys
            print_output = str(mock_print.call_args_list)
            assert "... and 995 more keys" in print_output\
                or "more keys" in print_output


class TestFileOperations:
    """Test file operation functionality"""

    @patch('explore_defillama_sdk.DefiLlama')
    def test_results_file_content(self, mock_defillama_class):
        """Test that the results file contains expected data"""
        mock_client = Mock()
        mock_defillama_class.return_value = mock_client

        # Mock protocol data - return a proper list
        mock_protocols = [
            {"name": "TestProtocol", "category": "Lending", "id": "test"}
        ]

        # Set up tvl submodule properly
        mock_tvl = Mock()
        mock_tvl.getProtocols.return_value = mock_protocols
        # Return proper dict for getProtocol
        mock_tvl.getProtocol.return_value = {
            "name": "TestProtocol",
            "category": "Lending",
            "id": "test"
        }
        mock_client.tvl = mock_tvl

        # Set up fees submodule
        mock_fees = Mock()
        mock_fees.getFees.return_value = []
        mock_client.fees = mock_fees

        # Run main function
        explorer.main()

        # Read and verify file
        with open('sdk_exploration_results.json', 'r') as f:
            data = json.load(f)
            assert 'available_submodules' in data
            assert 'protocols_count' in data
            assert data['protocols_count'] == 1  # Should be 1, not 0
            assert 'sample_protocol' in data

        # Clean up
        Path('sdk_exploration_results.json').unlink()

    @patch('explore_defillama_sdk.DefiLlama')
    def test_file_overwrite(self, mock_defillama_class):
        """Test that the file is overwritten on subsequent runs"""
        mock_client = Mock()
        mock_defillama_class.return_value = mock_client

        # Set up tvl submodule properly
        mock_tvl = Mock()
        mock_tvl.getProtocols.return_value = []
        mock_tvl.getProtocol.return_value = None
        mock_client.tvl = mock_tvl

        # Set up fees submodule
        mock_fees = Mock()
        mock_fees.getFees.return_value = []
        mock_client.fees = mock_fees

        # First run
        explorer.main()

        # Modify the file
        with open('sdk_exploration_results.json', 'w') as f:
            json.dump({"modified": True}, f)

        # Second run
        explorer.main()

        # File should be overwritten
        with open('sdk_exploration_results.json', 'r') as f:
            data = json.load(f)
            assert "modified" not in data
            assert 'available_submodules' in data

        # Clean up
        Path('sdk_exploration_results.json').unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
