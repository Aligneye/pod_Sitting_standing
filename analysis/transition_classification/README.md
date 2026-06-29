# Transition Classification Baseline

This directory contains a separate machine-learning benchmark for posture transitions.

## Goal

Build a simple classical ML baseline to understand dataset separability before any deep learning work.

## Scope

- Logistic Regression
- Random Forest
- SVM with RBF kernel
- 5-fold cross validation
- Transition-level samples only
- No neural networks

## Folder Structure

```text
analysis/transition_classification/
  README.md
  baseline_classifier.py
  dataset_builder.py
  feature_experiments.py
  utils.py
  reports/
  plots/
  models/
  dataset/
```

## Dataset Building

Each transition becomes one sample:

- transition ID
- class label
- duration
- normalized acceleration sequence

The default normalization uses 100 samples per transition and flattens `acc_x`, `acc_y`, and `acc_z` into a 300-dimensional vector.

## How to Run

Build dataset:

```bash
python analysis/transition_classification/dataset_builder.py
```

Run baseline benchmark:

```bash
python analysis/transition_classification/baseline_classifier.py
```

Run feature experiments:

```bash
python analysis/transition_classification/feature_experiments.py
```

Optional arguments:

- `--participant harshit`
- `--session 1`
- `--file path/to/session.csv`
- `--samples 100`

## Outputs

- `reports/classification_report.md`
- `reports/results.csv`
- `reports/predictions.csv`
- `reports/feature_comparison.csv`
- `plots/*confusion_matrix.png`

## Why classical ML first

We want a lightweight baseline that tells us whether the transition data is already separable with simple models before investing in more complex architectures.

## Current Limitations

- Small dataset size
- Potential participant-specific bias
- Cross-validation may still be optimistic if sessions are not diverse enough
- This is only a baseline, not the final posture detection system
