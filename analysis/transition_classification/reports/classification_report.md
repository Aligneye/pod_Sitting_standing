# Baseline Transition Classification Report

This benchmark uses classical machine learning only.

## Model Results

| Model | Accuracy | Precision | Recall | F1 | CV Mean | CV Std |
|---|---:|---:|---:|---:|---:|---:|
| Logistic Regression | 0.981 | 0.963 | 1.000 | 0.981 | 0.980 | 0.040 |
| Random Forest | 0.962 | 0.929 | 1.000 | 0.963 | 0.960 | 0.049 |
| SVM (RBF) | 0.981 | 0.963 | 1.000 | 0.981 | 0.980 | 0.040 |

## Notes

- Predictions preserve transition IDs so failures can be traced back to individual transitions.
- Cross validation uses 5 stratified folds.
- This is a baseline only, not the final deployment model.