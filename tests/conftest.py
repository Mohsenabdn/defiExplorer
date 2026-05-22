# tests/conftest.py
import sys
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent.parent / "src"
print(src_path)
sys.path.insert(0, str(src_path))

import pytest

def pytest_configure(config):
    """Configure pytest markers"""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (requires real SDK)"
    )

@pytest.fixture(autouse=True)
def cleanup_files():
    """Automatically cleanup test files after each test"""
    yield
    # Clean up any test files
    test_files = ['sdk_exploration_results.json']
    for file in test_files:
        path = Path(file)
        if path.exists():
            path.unlink()
