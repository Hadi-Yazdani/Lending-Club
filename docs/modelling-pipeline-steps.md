# Modelling pipeline — the thirteen steps, in order

Onboarding companion to [data-profiling-findings.md](data-profiling-findings.md).
Every number below is measured on this dataset, not illustrative.

The order matters more than any individual step. Most credit-modelling failures are
ordering failures: profiling before filtering, imputing before splitting, screening
features on data the model shouldn't have seen yet.

One distinction runs through the whole list: **does this step touch the label?**
Anything that does must wait until after the split (Step 6). Anything that doesn't
can run on the full population. Steps 4 and 7 are the same activity — measuring
columns — separated for exactly that reason.

---

## 1. Scope & Population Definition

Decide which rows are in the modelling population, before looking at anything else.
Filters are business decisions with consequences you must be able to defend: a date
floor, a term, a product. This comes first because every statistic downstream —
null rates, distributions, base rates — is a property of *this population*, not of
the file. Profile before you filter and you will measure the wrong thing.

The population also defines what your model's output *means*: here,
`P(default | 36-month loan, issued 2012–2015, accepted by LC)`. That last clause
never goes away — see §6 of the findings doc.

**Example:** 2,260,701 raw rows → issued 2012-01..2015-12 → `term == 36 months` →
resolved status = **589,488 loans**. The term filter isn't cosmetic: a 60-month loan
issued in 2015 matures in 2020, past the 2018Q4 snapshot, so the date window is only
valid for 36-month loans.

---

## 2. Label Definition

Define the target variable: what counts as the bad outcome, and over what horizon.
Binary here — `Charged Off` + `Default` → 1, `Fully Paid` → 0. The positive class
must be the event you're predicting, or every metric reads backwards.

Loans still in flight (`Current`, `Late (31-120)`) get **excluded, not coded 0**.
Their outcome is genuinely unknown — this is censoring: the value isn't missing,
the *ending* is. There is no middle grade for "late"; a late loan is an absent
observation, not a partial one.

**Example:** base default rate = **14.03%**. `Default` contributes 0 rows — only 40
exist in the whole file and none survive the filters.

---

## 3. Column Triage & Leakage Screening

Two passes, bundled because they share a precondition — neither needs the label,
neither needs distributions — and a consequence: profiling 151 columns when 80 are
already dead is wasted work. Only the second requires judgment, which is why the step
is usually named after it. Both drop whole columns; neither drops a row.

### 3a. Mechanical triage — no judgment required

Free deletions, found with `nunique()` and a null count. Nothing here is a risk
decision; it is bookkeeping that stops 151 columns from looking like 151 questions.

Four families: **100% null in this population** (15 columns — `member_id`,
`next_pymnt_d`, `revol_bal_joint`, every `sec_app_*`; that block was added in 2017),
**zero variance** (11 — `policy_code`, `pymnt_plan`, `hardship_flag`,
`disbursement_method`), **identifiers** (`id`, `url` — which contains the loan id),
and **free text** (`emp_title`, `title`, `desc`).

`nunique()` alone finds only the first two. It **drops NaN by default**, so a column
that is 99.96% null with one surviving value reads as "constant" and a column at
97.5% null reads as perfectly healthy. Null *rate* and *distinct count* are two
different measurements and you need both side by side — 37 further columns sit in the
≥97%-null band and no `nunique()` test will surface them.

Measure on the **population, not the file**. `term` is constant only because Step 1
filtered to 36 months, and `out_prncp` is 0.0 only because Step 2 kept resolved loans
— both are artefacts of upstream decisions, not properties of the column.

Free text and `zip_code` are *legitimately* knowable at origination. They leave for
cardinality, PII, and fair-lending reasons — record which, because "dropped as
leakage" is the wrong reason and someone will read it.

### 3b. Leakage screening — the time-machine test

For every surviving column ask: **was this value knowable at the moment of the
decision?** Not "is it about the borrower" — timing, not subject matter. `loan_amnt`
and `purpose` are loan attributes and perfectly legal; `last_fico_range_low` is a
borrower attribute and lethal.

Column names do not announce their timing, so sort by clock:

| Clock | Meaning | Verdict |
|---|---|---|
| Application | stated by the borrower when applying | legal |
| Bureau pull | the credit report LC pulled at underwriting | legal |
| Servicing | written after the money moved | **banned** |

Use a **whitelist, not a blacklist**. With 151 columns a blacklist will miss one,
and the one it misses will be the one that wrecks the model. A whitelist fails
closed — including against schema drift, where a column added in a later export is
silently ignored rather than silently admitted. Do this *before* any correlation
ranking, or leakage columns will sit at the top looking like a discovery.

One empirical check belongs here, run as a one-off audit and never as a selector,
because it touches the label: **null rate by `loan_status`**. A column populated only
for terminal loans is on the servicing clock, and its *presence* leaks even when its
value looks innocuous — which is why dropping the column is not enough, and a
`was_missing` flag derived from it re-imports what you just removed.

**Example:** `settlement_amount` is **100.00%** null on Fully Paid and 88.61% on
Charged Off. `recoveries > 0` covers 77.8% of Charged Off and **0.0%** of Fully Paid
— a non-zero value identifies the bad class perfectly, because you only recover money
on loans that defaulted.

**Example:** at origination, Fully Paid and Charged Off borrowers differ by 10.5
FICO points. At last credit pull they differ by **182**. `last_fico < 500` is 74.6%
charged off — the column is a readout of the outcome, because defaulting is what
destroyed the score.

### The output is a spec, not a dataframe

Not a list of the ~70 survivors — a verdict plus a reason for all 151 columns. The
reasons are what anyone asks about six months later, and a keep-list cannot hold one.
They are not interchangeable: **leakage**, **structurally empty**, **zero variance**,
**identifier / PII**, and **policy** — `issue_d` is knowable at origination and banned
anyway, because it is the split key and a model that learns "2015 defaults less" has
learned a calendar.

Assert `set(spec) == set(df.columns)`. Schema drifts, and a loud failure beats a
quietly shorter feature matrix.

The spec is amended, not frozen: redundant pairs surface in Step 4, vintage-correlated
nullity is handled in Step 8, weak predictors go in Step 7. Stamp each entry with the
step that justified it.

---

## 4. Data Profiling — target-free

Describe what each surviving column contains: null rate, distinct values,
distribution, and — critically — how those vary **across time**. Descriptive, not
exploratory: profiling asks "what is in here," EDA asks "what's interesting."
It is **read-only**. It changes no data; its output is a document. Fixing happens
in Steps 5 and 8, and profiling is what tells you which fixes are warranted.

**Nothing here touches the label.** Anything that relates a column to the target is
Step 7, after the split. Missingness in this dataset is almost never damage: it is
structural, and means "product didn't exist yet," "event never happened," or
"genuinely unknown" — three meanings, three handlings.

**Example:** `mo_sin_old_rev_tl_op` is 51.9% null in 2012 and 0.0% from 2013 on —
LC phased the field in. Since the split trains on 2012-01..2014-06, a `was_missing`
flag would become a proxy for "issued in 2012," which does not generalise forward.

---

## 5. Outlier & Data-Quality Screening

Outliers live in the **inputs**, never in the **target**. The test is *impossible*,
not *rare*. A grade-A borrower who defaulted is not an outlier — it is the
phenomenon being measured, and deleting it teaches the model that grade A never
defaults.

Prefer **capping to deleting**: winsorising neutralises the distortion while keeping
the row's label. Decide the rule before looking at outcomes, and learn the actual
thresholds on train only.

**Example:** `dti = 999` (1 row) is LC's sentinel for undefined — an error. But
`annual_inc > $1M` (103 rows) is rare, not impossible: income here is self-reported
and only sometimes verified. Cap it, don't drop it.

---

## 6. Temporal Split

Split into train / validation / test **before** anything that learns a value from
data — imputation, scaling, encoding, binning, outlier thresholds, feature screens.
Any of those fitted on the full dataset leaks test information into model design,
even though no test row ever reaches `fit()`.

The split is **temporal**, not random. A random split puts a 2015 loan in train and
a 2014 loan in test — the future teaching the past. Deployment always scores
forward in time, so the test must too.

**Example:** train 2012-01..2014-06, then validation, then test on the most recent
vintages. Everything from here down sees the training window and nothing else.

---

## 7. Univariate Screening (WOE / IV) — target-aware

Now measure how each feature relates to the target: bin the feature, compute the
default rate per bin, and rank features by predictive strength. In credit scoring
the standard metrics are **WOE** (weight of evidence, per bin) and **IV**
(information value, per feature).

This is Step 4's activity with the label added, which is exactly why it waits until
after the split. Run it over all 589,488 rows and test outcomes shape which features
you keep — leakage through model design rather than through `fit()`. It also acts as
a **second leakage net**: an implausibly high IV usually means a surviving
post-origination column, not a brilliant feature. Re-run after Step 9.

**Example:** default rate by grade runs 5.60% (A) → 25.60% (F). By contrast,
`last_fico_range_low` would show near-perfect separation — the signature of leakage,
not signal.

---

## 8. Imputation & Missing-Value Handling

Decide the fill strategy per column *family* — fitted on train, applied to
validation and test. The right strategy depends on what the blank means, which is
why this comes after profiling.

"Never happened" is not "unknown." A borrower with no delinquency has no
months-since-last-delinquency; imputing the median invents a delinquency that never
occurred. Use a sentinel plus an explicit indicator flag.

**Example:** `mths_since_last_delinq` → sentinel + indicator. But
`mo_sin_old_rev_tl_op` → drop it, or raise the population floor to 2013-01, because
its nullity encodes vintage rather than credit behaviour.

---

## 9. Feature Engineering

Build derived features from origination-time inputs: ratios, durations,
normalisations. Less mysterious than it sounds — mostly arithmetic that makes an
existing relationship visible to the model.

One rule governs everything: **an engineered feature inherits the leakage status of
its worst input.** `total_pymnt / loan_amnt` is an elegant feature and completely
poisoned. Send anything new back through Step 7 before keeping it.

**Example:** `installment ÷ monthly income` (payment burden);
`loan_amnt ÷ annual_inc`; `issue_d − earliest_cr_line` (credit history length).

---

## 10. Baseline / Benchmark

Establish what performance is already available for free, before claiming your model
adds value. Without a baseline an AUC is an uninterpretable number.

LC's own `grade` already predicts default well. This drives the Model A / Model B
split: Model A uses raw borrower attributes only, Model B is allowed LC's scorecard
(`grade`, `sub_grade`, `int_rate`). The interesting question is whether A can stand
on its own.

**Example:** grade alone separates 5.60% (A) from 25.60% (F). Any model that can't
beat that has learned nothing LC didn't already know.

---

## 11. Model Training

Fit the model on the training split. The least interesting step, and the one most
people start with. By this point every consequential decision — population, label,
feature set, split — has already been made, and they determine the outcome far more
than the algorithm choice does.

Model family matters mainly for how much Step 5 and Step 8 work you need: trees
tolerate extreme values and route NaN natively, logistic regression does neither.

**Example:** logistic regression for an interpretable, coefficient-legible baseline;
gradient boosting for performance. Report both.

---

## 12. Calibration

Check that predicted probabilities are **numerically** correct, not merely correctly
ranked. A model that ranks perfectly but predicts 3% where the truth is 14% will
score a great AUC and lose money on every loan it approves.

Ranking metrics (AUC, Gini) are blind to this. You need a calibration curve, plus
Brier score or log loss. Any expected-return calculation consumes the probability
directly, so an uncalibrated PD makes the entire business layer meaningless.

**Example:** bucket the test set by predicted PD and plot predicted vs realised
default rate. In the 10–12% predicted bucket, the realised rate should be 10–12%.

---

## 13. Threshold Selection & Business Policy

Convert probabilities into a decision. The cutoff comes from the business objective,
**not from 0.5** — that default assumes a balanced problem and symmetric costs, and
this problem has neither.

Here the objective is expected return, which means the threshold depends on interest
earned versus loss given default. Note the standing assumption: `Fully Paid` includes
early prepayment, so assuming full interest overstates revenue on prepayers.

**Example:** sweep the cutoff, plot approval rate against realised default rate and
expected return, then report the resulting policy — "approve the top 60%, default
rate falls from 14.03% to X%."

---

## Ordering traps

| Trap | Why it's wrong |
|---|---|
| Profile before filtering | Null rates are properties of the population, not the file |
| Score in-flight loans as 0 | Censoring — the ending is unknown, not good |
| Drop rows whose outcome surprises you | Filtering on the target; destroys calibration |
| Split after imputing | Fill values learned from test data |
| Random split | Future informs past; deployment never works that way |
| Run WOE/IV on the full population | Test outcomes shape which features you keep |
| Rank correlations before leakage screening | `recoveries` tops the list and looks like a discovery |
| Treat Step 3 as leakage only | `id`, `url` and `policy_code` all pass the time-machine test |
| Flag `was_missing` on a dropped leaky column | Re-imports the leakage you just removed |

## The one-line test

Before running any step, ask **"does this touch the label?"**
If yes, it belongs after Step 6. That single question separates Step 4 from Step 7,
and catches most of the traps above before you fall into them.
