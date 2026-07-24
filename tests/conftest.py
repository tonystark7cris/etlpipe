"""Shared pytest fixtures for etlpipe tests."""

from __future__ import annotations

import pandas as pd
import pytest


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """A basic DataFrame for general-purpose testing."""
    return pd.DataFrame(
        {
            "ID": [1, 2, 3, 4, 5],
            "Name": ["Alice", "Bob", "Charlie", "Diana", "Eve"],
            "Age": [30, 25, 35, 28, 32],
            "City": ["New York", "Boston", "Chicago", "Boston", "New York"],
            "Salary": [70000, 55000, 85000, 62000, 78000],
        }
    )


@pytest.fixture
def sample_df_with_nulls() -> pd.DataFrame:
    """A DataFrame with some null values."""
    return pd.DataFrame(
        {
            "ID": [1, 2, 3, 4, 5],
            "Name": ["Alice", None, "Charlie", "Diana", None],
            "Age": [30, 25, None, 28, 32],
            "Score": [95.5, None, 88.0, None, 72.5],
        }
    )


@pytest.fixture
def sample_dates_df() -> pd.DataFrame:
    """A DataFrame with date-like strings."""
    return pd.DataFrame(
        {
            "ID": [1, 2, 3],
            "DateStr": ["01/15/2023", "02/20/2023", "03/25/2023"],
        }
    )


@pytest.fixture
def sample_text_df() -> pd.DataFrame:
    """A DataFrame with various text data."""
    return pd.DataFrame(
        {
            "ID": [1, 2, 3],
            "Email": ["alice@example.com", "bob@test.org", "invalid-email"],
            "Tags": ["python,data,ml", "sql,etl", "java,spring,boot,api"],
            "FullName": ["Alice Smith", "Bob Jones", "Charlie Brown"],
        }
    )


@pytest.fixture
def left_df() -> pd.DataFrame:
    """Left DataFrame for join tests."""
    return pd.DataFrame(
        {
            "CustomerID": [1, 2, 3, 4],
            "Name": ["Alice", "Bob", "Charlie", "Diana"],
        }
    )


@pytest.fixture
def right_df() -> pd.DataFrame:
    """Right DataFrame for join tests."""
    return pd.DataFrame(
        {
            "CustomerID": [2, 3, 5],
            "OrderTotal": [150.00, 200.00, 95.00],
        }
    )


@pytest.fixture
def sales_df() -> pd.DataFrame:
    """Sales DataFrame for transform tests."""
    return pd.DataFrame(
        {
            "Region": ["East", "East", "West", "West", "East"],
            "Quarter": ["Q1", "Q2", "Q1", "Q2", "Q1"],
            "Revenue": [100, 200, 150, 250, 300],
            "Quantity": [10, 20, 15, 25, 30],
        }
    )
