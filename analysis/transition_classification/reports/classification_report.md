# Baseline Transition Classification Report

This benchmark uses classical machine learning only.

## Model Results

| Model | Accuracy | Precision | Recall | F1 | CV Mean | CV Std |
|---|---:|---:|---:|---:|---:|---:|
| Logistic Regression | 0.914 | 0.920 | 0.908 | 0.914 | 0.914 | 0.016 |
| Random Forest | 0.961 | 0.938 | 0.987 | 0.962 | 0.960 | 0.025 |
| SVM (RBF) | 0.974 | 0.962 | 0.987 | 0.974 | 0.974 | 0.013 |
| SVM (RBF Probability) | 0.974 | 0.962 | 0.987 | 0.974 | 0.974 | 0.013 |

## Notes

- Predictions preserve transition IDs so failures can be traced back to individual transitions.
- Cross validation uses 5 stratified folds.
- This is a baseline only, not the final deployment model.