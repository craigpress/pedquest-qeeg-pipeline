"""Tests for bin metadata correctness."""
import pandas as pd
import numpy as np
from qeeg.analysis.time_binning import aggregate_by_bins


def test_n_total_epochs_is_true_total_not_usable():
    """F5 regression: n_total_epochs must be the total row count in the bin,
    not the usable count. These must be separate fields."""
    n = 7200  # 2 hours
    df = pd.DataFrame({"var1": np.random.rand(n)})
    hours = pd.Series(np.linspace(0, 2, n))

    # 50% artifact in first hour
    usable = pd.Series(True, index=range(n))
    usable.iloc[0:1800] = False  # first 1800 of 3600 in 0-1h bin

    result = aggregate_by_bins(
        df, hours, variables=["var1"],
        edges=[0, 1, 2], usable_mask=usable,
    )

    bin_0_1 = result[result["bin_label"] == "0-1h"].iloc[0]

    # Total epochs should be ~3600 (all rows in 0-1h), NOT 1800
    assert bin_0_1["n_total_epochs"] >= 3500, (
        f"n_total_epochs should be ~3600 (all rows), got {bin_0_1['n_total_epochs']}"
    )
    # Usable should be ~1800
    assert 1700 <= bin_0_1.get("n_usable_epochs", 0) <= 1900, (
        f"n_usable_epochs should be ~1800, got {bin_0_1.get('n_usable_epochs')}"
    )
