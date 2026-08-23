# test_data

`clinical_data.csv` and `eeg_date_correction.csv` are the small alignment
fixtures the suite reads directly.

The stress-test cohort (5 synthetic patients x 48 h, ~600 MB) is **not**
shipped. Generate it locally:

```bash
python tests/generate_stress_data.py
```

It writes to `test_data/stress_test/`. Everything in it is synthetic --
no patient data is distributed with this release.
