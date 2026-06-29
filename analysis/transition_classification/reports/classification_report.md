# Baseline Transition Classification Report

This benchmark uses classical machine learning only.

## Model Results

| Model | Accuracy | Precision | Recall | F1 | CV Mean | CV Std |
|---|---:|---:|---:|---:|---:|---:|
| Logistic Regression | 0.920 | 0.932 | 0.907 | 0.919 | 0.920 | 0.050 |
| Random Forest | 0.933 | 0.922 | 0.947 | 0.934 | 0.933 | 0.042 |
| SVM (RBF) | 0.973 | 0.961 | 0.987 | 0.974 | 0.973 | 0.039 |

## Notes

- Predictions preserve transition IDs so failures can be traced back to individual transitions.
- Cross validation uses 5 stratified folds.
- This is a baseline only, not the final deployment model.