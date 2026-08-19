# Lending Club Credit Risk Model — Task Definition

## 1. Business framing

You are a risk analyst at a marketplace lender. The credit committee funds loans at
a fixed interest rate determined by an internal grading model. They want an
independent probability-of-default (PD) estimate at the moment of the funding
decision, so they can (a) sanity-check the incumbent grading model and (b) set an
approval cutoff that maximises expected return per dollar lent.

**Stakeholder:** Head of Credit Risk.
**Decision the model supports:** fund / decline, and at what expected loss.

---

## 2. The prediction task, stated precisely

- **Unit of observation:** one approved loan application.
- **Prediction time:** the instant before funding. Anything recorded after this
  moment is banned as a feature (see §4).
- **Output:** a calibrated probability that the loan will default over its full term.
- **Task type:** binary classification, with calibration treated as a first-class
  requirement rather than an afterthought.

---

## 3. Target definition (write this down before touching a model)

**Population — v1 scope:**

- 36-month term loans only.
- Issued between 2012-01-01 and 2015-12-31.

Rationale: the data runs through 2018Q4, so a 36-month loan issued by 2015Q4 has
fully matured and its outcome is observed. Loans issued after that are censored —
their outcome is unknown, not negative. Pre-2012 volume is small and underwriting
policy differed materially.

**Label:**

| `loan_status` | label |
|---|---|
| Fully Paid | 0 |
| Charged Off | 1 |
| Default | 1 |
| Current, Late (16-30), Late (31-120), In Grace Period | **excluded** |

Excluding in-flight loans is not optional. Coding them as 0 would silently label
future defaults as good loans.

**Report in the README:** the number of rows dropped at each step and the resulting
base default rate. Compute it — do not assume it.

**Stretch version (only if v1 finishes early):** switch to a fixed 24-month
performance window (`defaulted within 24 months of origination`). This is closer to
industry practice and lets you use more recent vintages, but requires deriving a
default date from payment history.

---

## 4. Feature scope — the core discipline of this project

### Banned (post-origination — these are the leakage traps)

```
total_pymnt              total_pymnt_inv        total_rec_prncp
total_rec_int            total_rec_late_fee     recoveries
collection_recovery_fee  last_pymnt_d           last_pymnt_amnt
next_pymnt_d             out_prncp              out_prncp_inv
last_credit_pull_d       last_fico_range_low    last_fico_range_high
debt_settlement_flag     settlement_*           hardship_*
```

Any of these will give you a model that looks extraordinary and is worthless.
`recoveries` alone is close to a perfect predictor, because you only recover money
on loans that defaulted.

### Allowed (known at origination)

Loan terms (`loan_amnt`, `term`, `installment`), borrower attributes (`emp_length`,
`home_ownership`, `annual_inc`, `verification_status`, `purpose`, `addr_state`),
and credit bureau fields at pull time (`dti`, `delinq_2yrs`, `earliest_cr_line`,
`inq_last_6mths`, `open_acc`, `pub_rec`, `revol_bal`, `revol_util`, `total_acc`,
`fico_range_low`, `fico_range_high`).

`issue_d` is used for splitting only, never as a feature.

### The interesting case: `grade`, `sub_grade`, `int_rate`

These are Lending Club's own risk assessment. They are known at origination, so
they are **not** leakage — but a model containing them is largely learning to
imitate the incumbent scorecard.

**Build both:**

- **Model A** — without grade/sub_grade/int_rate. Question: can raw borrower
  attributes support a risk model on their own?
- **Model B** — with them. Question: is there signal the incumbent scorecard misses?

The delta between A and B is a more interesting finding than either model's AUC.

### Implementation requirement

The whitelist lives in a version-controlled config file (YAML or a Python
constant), with a one-line justification for every exclusion. Not a comment in a
notebook.

---

## 5. Splits

Temporal, on `issue_d`. Never random.

| Split | Issuance window |
|---|---|
| Train | 2012-01-01 – 2014-06-30 |
| Validation | 2014-07-01 – 2015-03-31 |
| Test | 2015-04-01 – 2015-12-31 |

Touch the test set once, at the end. Tune on validation only.

---

## 6. Metrics

**Technical**

- PR-AUC (primary ranking metric)
- Brier score and a calibration curve (primary calibration metric)
- ROC-AUC reported for comparability, not used for decisions

Calibration outranks ranking here. You price off the probability, so a model that
ranks well but is systematically overconfident is unusable.

**Business — this is the headline**

Approve if expected return is positive:

```
E[return] = (1 - PD) x expected_interest - PD x expected_loss_given_default
```

Use `int_rate` and `loan_amnt` for the revenue side. Assume a fixed LGD (state your
assumption, e.g. 60%) unless you derive one.

Then plot **expected portfolio return against approval rate**, and compare your
policy against Lending Club's actual grade-based cutoffs on the same test vintages.

---

## 7. Deliverables

### Code

1. **Cleaning pipeline** — versioned, importable, unit-tested. Handles dtype
   coercion, percent-sign stripping, sparse joint-applicant columns, and drops rows
   per the §3 population rules. Deterministic and re-runnable.
2. **Feature whitelist config** with per-column justification.
3. **Training script** producing Model A and Model B, plus a baseline
   (logistic regression on 5 features) that everything must beat.
4. **Scoring interface** — a CLI or small API taking an application record and
   returning PD plus an approve/decline under the chosen cutoff. This is the "model
   gets used" component.

### Charts

1. **Vintage curves** — cumulative default rate by months-on-book, one line per
   origination quarter. Industry-standard; signals domain awareness immediately.
2. Calibration plot, Model A vs Model B vs baseline.
3. Decile lift table — predicted decile against realised default rate.
4. Expected return vs approval-rate cutoff, yours vs Lending Club's.
5. Partial dependence for the top three features.

### Writing

- **Model card:** intended use, population, features, metrics, known limitations.
- **README leading with the leakage story** (see §9).

---

## 8. Explicitly out of scope

- Reject inference on the rejected-loans file — mention as future work only.
- Survival analysis / time-to-default modelling.
- 60-month loans.
- Deep learning. Gradient boosting and logistic regression are the correct tools.

---

## 9. Day-one exercise

Before building anything properly: train a model on **all** columns including the
banned list. Record the AUC. It will be near-perfect.

Then throw it away and rebuild under the whitelist.

Lead the README with both numbers and the explanation. "My first model scored 0.99
and here is why I deleted it" demonstrates more judgment than any metric you could
report, because it is the exact mistake that gets made in production.

---

## 10. Definition of done

- [ ] Cleaning pipeline runs end-to-end from raw CSV with a single command
- [ ] Population and label rules documented, with row counts at each filter
- [ ] Feature whitelist config committed, every exclusion justified
- [ ] Models A and B beat the baseline on the validation set
- [ ] Calibration curve within acceptable deviation on the test set
- [ ] Approval-policy comparison chart produced against Lending Club's own cutoffs
- [ ] Scoring interface returns a decision for a single application
- [ ] Model card written
- [ ] README opens with the leakage narrative

---

## 11. Suggested schedule (3 weeks)

**Week 1** — Day-one leakage exercise. Population filters, label construction,
cleaning pipeline, whitelist config, baseline model.

**Week 2** — Models A and B, temporal CV, hyperparameter tuning on validation,
calibration. Test set stays sealed.

**Week 3** — Test set evaluation, business-metric policy comparison, all charts,
scoring interface, model card and README.

If you fall behind, cut in this order: the scoring interface, then Model B, then
partial dependence plots. Never cut the calibration work or the vintage curves —
those are what make it look like credit risk rather than a Kaggle notebook.
