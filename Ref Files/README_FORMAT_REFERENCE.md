# Two format-reference documents — which to trust

There are two copies of the Persyst trend-CSV format reference here. They have
diverged, so cite the right one.

| File | Role |
|---|---|
| `PersystTrendCSV_Format_Reference.md` | The citation of record. Retargeted to the shipped template; extend this one. |
| `PersystTrendCSV_Format_Reference_ORIGINAL_2026-05-15.md` | **Frozen original**, dated 2026-05-15 against a superseded template. Do not edit. Kept in the development repository as provenance; **not shipped in the release**, because its prose describes a template this pipeline can no longer read. |

Neither is raw vendor prose: both carry a **"Confirmed?"** column, i.e. they
record what has been *verified against exports*, including what remains unknown.
That honesty is the point — §3.27 explicitly marks FreqPow sub-column positions 2
and 4 as unconfirmed, which is why the mapper labels them `_v2`/`_v4` instead of
inventing names.

For vendor statements, go to `Persyst-15-Help/`.

## Where they conflict, and why the code follows the vendor

§3.27 glosses the FreqPow bands as Delta/Theta/Alpha/Beta with **"Approx. range"**
`~1-4 / ~4-8 / ~8-13 / ~13-25 Hz`. Persyst's own help page
(`Persyst-15-Help/03-Trending/Trend Types Rhythmicity.md`) states rhythmicity is
computed in

> four bands: 1-4 Hz, 4-9 Hz, 9-16 Hz and 16-25 Hz.

The exported data settles it. Observed maxima of the position-1 (peak-frequency)
sub-columns across the real subject-1 Research export:

```
band 1   3.96 Hz      band 2   8.59 Hz      band 3  13.89 Hz      band 4  22.90 Hz
```

8.59 does not fit "~4-8" and 13.89 does not fit "~8-13", so the clinical-band
gloss would be contradicted by the values it labels. The vendor ranges contain
all four. `_RHYTHMICITY_FREQPOW_BANDS` in `qeeg/ingestion/column_mapper.py`
therefore uses `1_4hz / 4_9hz / 9_16hz / 16_25hz`. §3.27's own "Approx." marking
means the two sources do not actually disagree — one is a loose gloss.
