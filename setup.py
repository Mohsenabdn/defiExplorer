# setup.py
from setuptools import setup, find_packages

setup(
    # Basic information
    name="defiExplorer",           # Name of your package
    version="0.1",               # Version number
    description="DefiLlama protocol extractor with schema catalog",
    author="Mohsen Abedini",

    # Package discovery
    packages=find_packages(),    # Automatically finds src/ directory

    # Python version requirement
    python_requires=">=3.14",
)
