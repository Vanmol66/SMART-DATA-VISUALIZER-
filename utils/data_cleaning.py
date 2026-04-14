import pandas as pd
import numpy as np

def analyze_cleanliness(df):

    total_cells = df.shape[0] * df.shape[1]

    missing = df.isnull().sum().sum()
    duplicates = df.duplicated().sum()

    missing_pct = (missing / total_cells) * 100 if total_cells else 0
    duplicate_pct = (duplicates / len(df)) * 100 if len(df) else 0

    # ✅ OUTLIERS DETECTION
    outliers = 0
    for col in df.select_dtypes(include=["number"]).columns:
        q1 = df[col].quantile(0.25)
        q3 = df[col].quantile(0.75)
        iqr = q3 - q1
        outliers += ((df[col] < (q1 - 1.5 * iqr)) | (df[col] > (q3 + 1.5 * iqr))).sum()

    # ✅ FINAL SCORE
    score = 100 - (missing_pct * 0.5 + duplicate_pct * 0.2 + (outliers/total_cells)*100 * 0.3)
    score = max(0, round(score, 2))

    # CATEGORY
    if score > 80:
        category = "Well Cleaned"
    elif score > 50:
        category = "Average"
    else:
        category = "Messy"

    issues = []
    suggestions = []
    column_issues = []

    # ✅ MISSING
    if missing > 0:
        issues.append(f"{missing} missing values")
        suggestions.append("Fill missing values using mean/median")

    # ✅ DUPLICATES
    if duplicates > 0:
        issues.append(f"{duplicates} duplicate rows")
        suggestions.append("Remove duplicate rows")

    # ✅ OUTLIERS
    if outliers > 0:
        issues.append(f"{outliers} outliers detected")
        suggestions.append("Handle outliers using IQR or clipping")

    # ✅ COLUMN LEVEL
    for col in df.columns:
        col_missing = df[col].isnull().sum()

        if col_missing > 0:
            column_issues.append(f"{col}: {col_missing} missing")

        # skew detection
        if df[col].dtype != "object":
            skew = df[col].skew()
            if abs(skew) > 1:
                column_issues.append(f"{col}: highly skewed")

    return {
        "score": score,
        "category": category,
        "missing": missing,
        "duplicates": duplicates,
        "outliers": int(outliers),
        "issues": issues,
        "suggestions": suggestions,
        "column_issues": column_issues
    }