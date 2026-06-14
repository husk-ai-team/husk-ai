# Sample data — fixtures for pipeline testing only

The files in this folder are **synthetic fixtures**, not real measurements.
They exist so contributors can verify the analysis pipeline (`analysis.py`)
works end-to-end before recruiting real engineers.

| File | What it is |
|---|---|
| `sample_raw_timings.csv` | Fabricated timing rows for 12 fake engineers across 4 tasks in a within-subjects crossover design. Numbers are calibrated to look plausible (baseline ~25-30 min, Husk ~6-8 min) so the analysis produces a "publishable" verdict end-to-end. |
| `expected_analysis.json` | The output `analysis.py` should produce when fed the sample CSV. Used as a regression check. |
| `expected_REPORT.md` | The narrative report the sample input should yield. |

To verify your local pipeline:

```bash
cp benchmark/empirical_study/sample_data/sample_raw_timings.csv \
   benchmark/empirical_study/results/raw_timings.csv

uv run python benchmark/empirical_study/analysis.py
diff benchmark/empirical_study/results/analysis.json \
     benchmark/empirical_study/sample_data/expected_analysis.json
```

When you run the real empirical study with actual engineers:

1. Delete or move the sample data out of `results/`.
2. Place real participant CSVs into `results/raw_timings.csv`.
3. Run `analysis.py` against the real data.

**Do not** publish or cite the fixture numbers anywhere. They are not real
measurements.
