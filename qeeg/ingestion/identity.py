"""Single source of truth for deriving a patient ID from a file/recording stem.

Historically this rule was duplicated three divergent ways (parser, quick_scan,
upload) which collapsed or split patients inconsistently across studies. All call
sites now delegate here. The patient ID is the recording-identity token: the stem
up to the first underscore (the underscore separates segment/UUID/panel/eeg-number
suffixes), or the whole stem if there is none.

Verified against the real cohort conventions:

    '2046_1'          -> '2046'      (PedQuEST: studyID_eegNumber)
    '2046_1_2'        -> '2046'      (PedQuEST continuation segment)
    '01-001_UUID_2'   -> '01-001'    (POCCA: siteID-patientID_UUID_eegNumber)
    '01-001'          -> '01-001'    (first EEG, no underscore)
    'subject-10_rec' -> 'subject-10'   (Persyst .dat stem: patientID_hash)
    'subject-10'         -> 'subject-10'   (no hash)

Note 'subject-1' and 'subject-10' are DISTINCT patient IDs (see tests/test_cache.py) —
the hyphenated suffix is part of the identity, not a segment to be merged away.
"""
from __future__ import annotations


def derive_patient_id(stem: str) -> str:
    """Return the patient identity token from a filename/recording stem.

    Rule: everything before the first underscore, or the whole (stripped) stem
    if there is no underscore. Returns '' only for an empty/whitespace input.
    """
    if not stem:
        return ""
    stem = stem.strip()
    return stem.split("_", 1)[0] or stem
