# Data profiling findings — accepted loans

Companion to [lending-club-task-definition.md](lending-club-task-definition.md).
Everything below was computed from
`src/data/datasets/versions/3/accepted_2007_to_2018q4.csv/accepted_2007_to_2018Q4.csv`
(2,260,701 rows × 151 columns), not assumed.

Purpose: record what the raw file actually contains so column decisions get made
once, deliberately, instead of being re-argued per notebook cell.

---

## 1. Population funnel (v1 scope)

| Step | Rows | Dropped |
|---|---:|---:|
| Raw file | 2,260,701 | — |
| Issued 2012-01-01 .. 2015-12-31 | 844,905 | 1,415,796 |
| + `term == " 36 months"` | 589,635 | 255,270 |
| + resolved `loan_status` | **589,488** | 147 |

**Modelling population: 589,488 loans.**

### Label mix

| `loan_status` | label | Rows | Share |
|---|---|---:|---:|
| Fully Paid | 0 | 506,760 | 85.97% |
| Charged Off | 1 | 82,728 | 14.03% |
| Default | 1 | 0 | 0.00% |

> ### Base default rate = **14.03%**
>
> Materially lower than the ~18.6% you get from the same date window *without* the
> 36-month filter. 60-month loans default at a much higher rate, and mixing them in
> inflates the base rate. The v1 scope is 36-month only, so 14.03% is the number to
> design around and to quote in the README.

`Default` contributes **zero** rows here. Only 40 exist in the whole 2.26M-row file
and none survive the v1 filter. Keep it in the label map for correctness, but expect
it to change nothing.

---

## 2. `loan_status` vocabulary

The delinquency ladder, in the order a loan travels it. Counts are whole-file.

| Status | Days past due | Rows | Terminal? |
|---|---|---:|---|
| Issued | funded, no payment due yet | 0 | no |
| Current | 0 | 878,317 | no |
| In Grace Period | 1–15 | 8,436 | no |
| Late (16–30 days) | 16–30 | 4,349 | no |
| Late (31–120 days) | 31–120 | 21,467 | no |
| Default | 121+ | 40 | yes |
| Charged Off | written off as a loss | 268,559 | yes |
| Fully Paid | repaid in full | 1,076,751 | yes |

- **In Grace Period** — no late fee charged; usually an autopay timing miss. Weak signal.
- **Late (16–30)** — late fee applies, collections outreach begins. Still very curable.
- **Late (31–120)** — cure rates fall sharply; realistically headed for write-off.
- **Default** — LC's formal 121+ dpd state. Transitional; LC charges off almost immediately.
- **Charged Off** — an accounting action, not a borrower action. Does **not** mean zero
  recovery: collections continue afterward, which is exactly why `recoveries` is such
  lethal leakage — a non-zero value there means the loan charged off, full stop.
- **Fully Paid** — includes **early prepayment**. A loan repaid in month 6 of 36 looks
  identical to one that ran full term but earned a fraction of the interest. The
  `E[return]` formula in §7 of the task definition assumes full interest and therefore
  overstates revenue on prepayers. State this as an explicit assumption.

### Why in-flight loans are excluded, not coded 0

A `Late (31–120 days)` loan has a genuinely unknown outcome. Some cure and repay in
full; most don't. Label them 1 and every cure is mislabelled; label them 0 — the
tempting default, since "not charged off yet" — and every eventual write-off is
mislabelled as a good loan. This is **censoring**: the value isn't missing, the
*ending* is.

### The "Does not meet the credit policy" rows

```
Does not meet the credit policy. Status:Fully Paid    1,988
Does not meet the credit policy. Status:Charged Off     761
```

Legacy loans originated under underwriting LC later retired. **All 2,749 fall between
June 2007 and December 2010**, so the 2012-01-01 population floor removes every one.
No special handling needed — just don't let a naive `.str.contains("Fully Paid")`
sweep them back in.

---

## 3. Column triage — 151 collapses fast

Null rates below are measured **on the 589,488-row v1 population**, not the raw file.
That distinction matters: several columns are well-populated overall but empty in this
window.

| Stage | Cut | Remaining |
|---|---:|---:|
| Raw | — | 151 |
| 100% null in this window | −18 | 133 |
| ≥97% null in this window | −34 | 99 |
| Post-origination (banned by §4) | ~−20 | ~79 |
| IDs / free text / constants | ~−10 | ~69 |

The business-analysis job is ~40 columns, not 151. The rest is mechanical triage.

### 3.1 100% null in this population (18) — free deletion

```
member_id, next_pymnt_d, dti_joint, annual_inc_joint,
verification_status_joint, revol_bal_joint,
sec_app_num_rev_accts, sec_app_open_act_il, sec_app_inq_last_6mths,
sec_app_earliest_cr_line, sec_app_fico_range_high, sec_app_fico_range_low,
sec_app_revol_util, sec_app_open_acc, sec_app_mort_acc,
sec_app_mths_since_last_major_derog, sec_app_collections_12_mths_ex_med,
sec_app_chargeoff_within_12_mths
```

LC launched joint applications in 2017 — two years after this window closes.
`member_id` is redacted throughout the public file. Zero information content.

### 3.2 ≥97% null in this population (34) — two families

**Credit-bureau fields LC added around Dec 2015** (97.5–97.8% null here):

```
open_acc_6m, open_act_il, open_il_12m, open_il_24m, mths_since_rcnt_il,
total_bal_il, il_util, open_rv_12m, open_rv_24m, max_bal_bc, all_util,
inq_fi, total_cu_tl, inq_last_12m
```

**Post-origination hardship / settlement** (98.4–99.8% null, banned regardless):

```
hardship_* (14 columns), settlement_* (5), debt_settlement_flag_date,
payment_plan_start_date, deferral_term, orig_projected_additional_accrued_interest
```

### 3.3 Constant / near-constant — zero variance

`nunique()` finds these faster than any correlation screen. All show 0.0% null,
which is how they hide:

| Column | Values present |
|---|---|
| `policy_code` | `1.0` |
| `pymnt_plan` | `n` |
| `hardship_flag` | `N` |
| `disbursement_method` | `Cash` |
| `out_prncp`, `out_prncp_inv` | `0.0` (always, for resolved loans) |
| `term` | `36 months` (constant by construction after filtering) |
| `application_type` | `Individual` / `Joint App` — but every joint field is 100% null |

### 3.4 Identifiers and free text

`id`, `url` (contains the loan id), `zip_code` (3-digit, high cardinality),
`emp_title` (6.7% null, very high cardinality), `title`, `desc` (87.3% null,
borrower-written).

`emp_title` and `desc` are legitimately known at origination — they're a
text-modelling project, not a leakage problem. Out of scope for v1; note them as
future work rather than silently dropping.

### 3.5 Redundant pairs — collinearity, not leakage

- `loan_amnt` / `funded_amnt` / `funded_amnt_inv` — near-identical; keep one.
- `fico_range_low` / `fico_range_high` — differ by a constant 4. Use the midpoint.
- `grade` / `sub_grade` / `int_rate` — monotone transforms of each other. This is the
  Model A / Model B split in §4, not a drop decision.

---

## 4. Opportunity: ~40 usable bureau fields beyond the §4 starter list

The allowed list in §4 of the task definition names ~20 fields. Profiling found
roughly 40 more that pass the time-machine test — bureau attributes at pull time, same
category as `revol_util` — and are well-populated in this window:

| Null rate | Columns |
|---:|---|
| 1.0% | `mort_acc`, `total_bal_ex_mort`, `total_bc_limit`, `acc_open_past_24mths` |
| ~2% | `num_sats`, `num_bc_sats`, `bc_util`, `bc_open_to_buy`, `percent_bc_gt_75`, `mths_since_recent_bc` |
| 3.8% | `num_actv_bc_tl`, `num_actv_rev_tl`, `num_rev_accts`, `num_il_tl`, `num_bc_tl`, `num_op_rev_tl`, `num_rev_tl_bal_gt_0`, `num_tl_op_past_12m`, `num_tl_30dpd`, `num_tl_90g_dpd_24m`, `num_accts_ever_120_pd`, `pct_tl_nvr_dlq`, `tot_cur_bal`, `avg_cur_bal`, `tot_hi_cred_lim`, `tot_coll_amt`, `total_rev_hi_lim`, `total_il_high_credit_limit`, `mo_sin_old_rev_tl_op`, `mo_sin_old_il_acct`, `mo_sin_rcnt_tl`, `mo_sin_rcnt_rev_tl_op` |

Model A asks whether raw borrower attributes can support a risk model without leaning
on LC's scorecard. These are exactly where that signal would live. Including them is
defensible — but make the call **explicitly in the feature config with a written
justification**, not by accident. Read §5 first.

---

## 5. ⚠️ Vintage-correlated nullity — interacts badly with the temporal split

The uniform-looking 3.8% null rate above is **not** uniform across time. Null rate by
issue year, within the v1 population:

| Column | 2012 | 2013 | 2014 | 2015 |
|---|---:|---:|---:|---:|
| `mo_sin_old_rev_tl_op` | **51.9%** | 0.0% | 0.0% | 0.0% |
| `num_sats` | **29.9%** | 0.0% | 0.0% | 0.0% |
| `mort_acc` | **13.9%** | 0.0% | 0.0% | 0.0% |
| `mths_since_recent_inq` | 25.1% | 11.2% | 9.5% | 11.0% |
| `emp_length` | 4.0% | 5.0% | 5.9% | 6.7% |
| `revol_util` | 0.1% | 0.1% | 0.0% | 0.0% |

These fields were phased in during 2012–2013. The split in §5 of the task definition is
**train 2012-01 .. 2014-06**, so training data is disproportionately affected while
validation and test are clean.

**Consequences to handle deliberately:**

1. A median/mean imputer fitted on train learns a fill value driven by 2012 rows, then
   applies it to test data that never needs it.
2. A `was_missing` indicator flag becomes a proxy for "issued in 2012" — the model can
   learn vintage, which does not generalise forward.
3. Tree models that route NaN to a default branch will split partly on origination era
   rather than on credit risk.

**Recommended handling:** either raise the population floor to 2013-01-01 (costs volume,
buys a clean feature matrix), or keep 2012 and drop the worst offenders
(`mo_sin_old_rev_tl_op`, `num_sats`). Whichever you pick, record the decision and the
volume cost in the feature config.

`mths_since_recent_inq` and the `mths_since_last_*` family have a different, legitimate
reason for nullity: **"never happened" is not the same as "unknown."** A borrower with
no delinquency has no months-since-last-delinquency. Impute with a sentinel plus an
explicit indicator, never with the median.

---

## 6. Rejected dataset — out of scope, and why

Nine columns, no outcome:

```
Amount Requested, Application Date, Loan Title, Risk_Score,
Debt-To-Income Ratio, Zip Code, State, Employment Length, Policy Code
```

- **No `loan_status`.** These loans were never funded, so no repayment behaviour
  exists. There is no ground truth to train against or validate on — ever.
- **Features barely overlap** with the accepted file, and the shared ones are formatted
  differently: `Debt-To-Income Ratio` is a string (`"10%"`), `Risk_Score` is not on the
  same scale as `fico_range_low`. Scoring rejected applicants with the v1 model isn't
  runnable; it would require a separate, crippled model trained on the ~5-column
  intersection, which tells you about *that* model rather than about yours.

Consistent with §9 of the task definition, which lists reject inference as future work
only.

**What it is worth:** one honest paragraph in the writeup. The model estimates
**P(default | accepted)**, not **P(default | applied)**. It has only ever seen
borrowers who cleared LC's existing filter. Naming that selection bias explicitly is
worth more than any modelling these nine columns could support.

---

## 7. Working notes

**Filter first, then profile.** Profiling 2.26M rows you are about to drop is wasted
work — the population is 589,488, a quarter of the file.

**Cache the filtered population.** A chunked pass over the raw CSV takes minutes and
you will restart the kernel often:

```python
df = build_population(raw)              # 589,488 × ~70
df.to_pickle("data/interim/v1_population.pkl")
```

`to_pickle` works with the currently installed packages. `pip install pyarrow` if you
want `.to_parquet()` for something portable and compressed.

**Bureau column naming.** The fields are systematically named; learning the morphemes
decodes ~60 columns at once:

| Fragment | Meaning |
|---|---|
| `tl` | trade line (a credit account) |
| `bc` | bankcard |
| `il` | installment loan |
| `rev` / `rv` | revolving |
| `sats` | satisfactory accounts |
| `mo_sin_` / `mths_since_` | months since… |
| `dpd` | days past due |
| `_12m` / `_24m` | lookback window |
| `derog` | derogatory mark |

So `num_actv_bc_tl` = number of active bankcard trade lines; `pct_tl_nvr_dlq` = percent
of trade lines never delinquent. The authoritative reference is
`LCDataDictionary.xlsx` from the Kaggle dataset page — it is not in `versions/3`.

**Screen features on train only.** Selecting features using statistics computed over the
full dataset leaks test information into model design, even though no test row ever
reaches `fit()`. Compute screens inside 2012-01 .. 2014-06 and nowhere else.

**Business triage before statistical screening.** A correlation-with-target ranking run
across all 151 columns puts `recoveries`, `total_rec_prncp`, `last_fico_range_low`, and
`total_pymnt` at the top, where they look like a spectacular discovery. Remove leakage
first, then rank.

**Whitelist, not blacklist.** With 151 columns a blacklist will miss one, and the one it
misses will be the one that wrecks the model. A whitelist fails closed: a column nobody
thought about is simply absent.

---

## 8. Open decisions

- [ ] Include the ~40 extra bureau fields from §4 above? (Recommended: yes, with §5 handled.)
- [ ] Population floor 2012-01 or 2013-01? (Trades volume against vintage-nullity.)
- [ ] Imputation strategy per column family — sentinel + indicator for `mths_since_*`,
      something else for the vintage-affected fields.
- [ ] Prepayment treatment in the `E[return]` calculation — assume full interest, or
      derive realised interest from matured loans?
