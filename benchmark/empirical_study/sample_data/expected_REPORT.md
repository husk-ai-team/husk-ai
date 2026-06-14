# Empirical study — analysis report

- Engineers: **12**
- Total timing rows: 48

## Headline (T_total)

- Paired T-test: t = 12.6661, df = 3, p = 0.00106
- Mean diff (baseline − husk): 20.708 min (95 % CI [15.506, 25.911])
- Cohen's d: 6.333
- **Publishable: True**

## Per-segment breakdown

### t_identify_min

- baseline: mean=14.333 stdev=2.2 n=24
- husk:     mean=2.708 stdev=0.624 n=24
- paired diff mean = 11.625 (p = 0.00219)

### t_edit_min

- baseline: mean=5.25 stdev=0.676 n=24
- husk:     mean=3.208 stdev=0.588 n=24
- paired diff mean = 2.042 (p = 0.00792)

### t_verify_min

- baseline: mean=8.042 stdev=0.859 n=24
- husk:     mean=1.0 stdev=0.0 n=24
- paired diff mean = 7.042 (p = 0.00024)

### t_total_min

- baseline: mean=27.625 stdev=2.81 n=24
- husk:     mean=6.917 stdev=0.83 n=24
- paired diff mean = 20.708 (p = 0.00106)
