"""A column that never varies carries no information — say so before modelling.

Two vendor behaviours motivated this, both faithfully transported and neither a
pipeline defect:

  * Persyst's `Status Epilepticus Advanced/Combined (Percent)` sit at a
    **non-zero floor of 0.050331** when nothing is detected. They never reach 0,
    so `> 0` is true on every epoch of every recording, and a reported mean of
    "0.05%" is the floor rather than a finding.
  * Those two trends are **byte-identical on every row** in every export
    examined. Entering both in a model is perfect collinearity.

The survey reports; it never repairs.
"""
import numpy as np
import pandas as pd
import pytest

from qeeg.quality.constant_columns import find_constant_columns


def _df(**cols) -> pd.DataFrame:
    return pd.DataFrame(cols)


class TestConstantDetection:
    def test_a_non_zero_floor_is_reported(self):
        """The ESE case: constant, non-zero, and therefore not a measurement."""
        rep = _find(_df(ese=[0.050331] * 100, real=np.arange(100.0)))
        assert rep.constant == {"ese": pytest.approx(0.050331)}
        assert "real" not in rep.constant
        assert any("floor, not a measurement" in w for w in rep.warnings())

    def test_an_all_zero_column_is_reported_separately(self):
        """Zero-constant is worth knowing but reads differently from a floor."""
        rep = _find(_df(never_fired=[0.0] * 50, real=np.arange(50.0)))
        assert rep.constant == {"never_fired": 0.0}
        warns = " ".join(rep.warnings())
        assert "zero for the whole recording" in warns
        assert "floor, not a measurement" not in warns

    def test_nan_is_missing_not_a_value(self):
        """A column nulled in places is still constant where it was measured."""
        col = [5.0] * 40 + [np.nan] * 10
        rep = _find(_df(partly_nulled=col, real=np.arange(50.0)))
        assert rep.constant["partly_nulled"] == pytest.approx(5.0)
        assert not rep.all_null

    def test_an_entirely_missing_column_is_not_called_constant(self):
        rep = _find(_df(gone=[np.nan] * 30, real=np.arange(30.0)))
        assert rep.all_null == ["gone"]
        assert "gone" not in rep.constant

    def test_a_varying_column_is_left_alone(self):
        rep = _find(_df(real=np.arange(100.0)))
        assert not rep.constant and not rep.duplicate_groups


class TestDuplicateDetection:
    def test_identical_columns_are_grouped(self):
        """The advanced/combined case, on a recording where they vary."""
        v = np.sin(np.arange(200.0))
        rep = _find(_df(advanced_percent=v, combined_percent=v.copy(),
                        other=np.cos(np.arange(200.0))))
        assert rep.duplicate_groups == [["advanced_percent", "combined_percent"]]
        assert rep.n_duplicated == 1
        assert any("do not model them as separate variables" in w
                   for w in rep.warnings())

    def test_near_identical_columns_are_not_grouped(self):
        """One differing row is enough — this must not be a tolerance test."""
        a = np.sin(np.arange(200.0))
        b = a.copy()
        b[137] += 1e-6
        rep = _find(_df(a=a, b=b))
        assert not rep.duplicate_groups

    def test_constants_are_not_reported_as_duplicates_of_each_other(self):
        """Otherwise every all-zero column forms one huge useless group."""
        rep = _find(_df(z1=[0.0] * 50, z2=[0.0] * 50, z3=[0.0] * 50))
        assert not rep.duplicate_groups
        assert set(rep.constant) == {"z1", "z2", "z3"}


class TestScope:
    def test_internal_and_identifier_columns_are_skipped(self):
        rep = _find(_df(_usable=[1.0] * 20, patient_id=[1.0] * 20,
                        real=np.arange(20.0)))
        assert not rep.constant
        assert rep.n_checked == 1

    def test_non_numeric_columns_are_skipped(self):
        df = _df(real=np.arange(20.0))
        df["label"] = ["x"] * 20
        rep = _find(df)
        assert rep.n_checked == 1

    def test_a_short_frame_is_not_surveyed(self):
        """One row is trivially constant everywhere; that is not a finding."""
        rep = _find(_df(a=[1.0]))
        assert not rep.constant


def _find(df):
    return find_constant_columns(df)
