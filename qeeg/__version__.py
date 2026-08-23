"""Pipeline version — the single source of truth.

Consumed by:
  - cache keys (auto-invalidates cached results when this changes)
  - pyproject.toml (read dynamically at build via tool.setuptools.dynamic)
  - the FastAPI app version (api/main.py imports this)

Bump this on any change that alters pipeline output so stale caches are dropped.
"""
__version__ = "4.0.0"

# Version of the exported column vocabulary — the `common_name` identifiers.
#
# Tracked separately from __version__ because it answers a different question:
# not "which code produced this dataset" but "which column names does it speak".
# Two datasets can share a pipeline version and disagree on column names, and an
# analysis script cares only about the latter.
#
#   1  identifiers as of commit bf4f732, frozen in
#      tests/fixtures/column_identity_v1.json
#   2  after the column-resolution remediation: columns resolve by panel ordinal
#      rather than trend-name lookup, absolute I-numbers are no longer baked into
#      identifiers, and mislabels are corrected (rda_left x3 -> left/right/
#      generalized; spike_threshold_per_10s x2 -> left/right; sleep stages split;
#      band-over-broadband ratios reclassified to relative_power).
#   3  rhythmicity FreqPow relabelled: its 16 sub-columns are 4 bands x 4
#      values (PersystTrendCSV_Format_Reference.md 3.27), not spectrogram bins,
#      so all 64 columns per Research export had read as sub-2.7 Hz delta.
#   4  Coherence_Avg named by its 0-32 Hz range instead of a bin-centre
#      frequency. It is a single broadband average, so `coherence_c3p3_0.00hz`
#      asserted a DC bin it does not have and collided with the spectrogram's
#      real first bin.
#   5  code-review fixes. Three identifiers were wrong: a bilateral spike
#      detector named left (the ' AND ' split made the bilateral branch
#      unreachable), a 2-minute running MAX of the detections channel taking
#      the bare seizure_probability_p14 name that v1 used for the continuous
#      score, and two 30-minute averages named _avg64s because the window was
#      read from Persyst's stale display label instead of the MMX. Also removed
#      the last two absolute-I-number hardcodes (_d{i_group}, heart_rate_{n}),
#      stopped the uniqueness backstop displacing naturally-occurring _N names,
#      and narrowed ratio routing so a band ratio in a non-power label can no
#      longer pull that trend into relative_power.
#   6  SeizureEventsP14's two sub-columns reach their schema again. Once the V7
#      I-group table stopped firing, nothing named sub-column 2 and the pair
#      fell to the uniqueness backstop as seizure_detection /
#      seizure_detection__dup2 -- which reads as a second detection column when
#      it is the notification channel. Now seizure_detection_event and
#      seizure_notification_event.
#   7  whole-brain FFT columns carry a channel token. The All 10-20 columns
#      were bare fft_delta / fft_theta / fft_alpha / fft_beta, which read as
#      family names rather than columns; now fft_delta_all etc. Also stops the
#      rhythmic-delta rule falling through to a keyword scan that labelled any
#      unresolved channel 'left', and confines FreqPow band names to the
#      documented 16-sub-column layout.
#
#   8  the uniqueness backstop no longer ships. Three seizure_detection
#      instruments collapsed onto seizure_detection_event / __dup2 / __dup3 --
#      the SeizureEventsP14 overlay pair, the SeizureProbabilityP14 Detections
#      channel, and a 2-minute running MAX of that channel. They are now
#      seizure_detection_event / seizure_notification_event /
#      seizure_detection_p14 / seizure_detection_p14_max120s. The template's
#      second heart-rate instrument likewise took heart_rate__dup2; it is now
#      heart_rate_2, from its CSV header ordinal rather than an I-number.
#      A __dupN name is unusable as an identifier -- it says only "some other
#      column" -- so any occurrence is a naming bug, not an acceptable output.
#
# Bump when any common_name changes, and regenerate the identity fixture.
# No dataset was ever produced under an earlier vocabulary, so the stamp
# exists to let a downstream script assert which names it is reading -- not
# to migrate old data. See docs/COLUMN_NAMING.md.
COLUMN_SCHEMA_VERSION = 8
