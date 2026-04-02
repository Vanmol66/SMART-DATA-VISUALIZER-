# backend/utils/data_analyzer.py
import math
from collections import Counter
from typing import Dict, Any

import numpy as np
import pandas as pd


def safe_mode(series: pd.Series):
    vals = series.dropna().astype(str).values
    if len(vals) == 0:
        return None, 0
    c = Counter(vals)
    mode_val, mode_count = c.most_common(1)[0]
    return mode_val, int(mode_count)


def detect_column_type(series: pd.Series) -> str:
    """
    Decide whether a column should be treated as 'categorical', 'numerical', or 'datetime'.
    """
    if pd.api.types.is_datetime64_any_dtype(series) or pd.api.types.is_datetime64_ns_dtype(series):
        return "datetime"
    if pd.api.types.is_numeric_dtype(series):
        return "numerical"
    # Try parse to datetime strings
    try:
        parsed = pd.to_datetime(series.dropna(), errors="coerce")
        if parsed.notna().sum() / max(1, len(series.dropna())) > 0.6:
            return "datetime"
    except Exception:
        pass
    n_unique = series.nunique(dropna=True)
    n = len(series.dropna())
    if n == 0:
        return "unknown"
    unique_ratio = n_unique / n
    if unique_ratio < 0.05 or n_unique < 30:
        return "categorical"
    return "categorical"


# ---------------------------
# Scoring helper functions
# ---------------------------
def _normalized(v, vmin, vmax):
    if vmax <= vmin:
        return 0.0
    return max(0.0, min(1.0, (v - vmin) / (vmax - vmin)))


def _readability_for_category(n_unique, n_rows):
    # Favor small cardinality for category readability
    if n_rows <= 0:
        return 0.5
    # ideal <= 8, degrade gradually up to 50
    return max(0.0, 1.0 - min(1.0, (n_unique - 1) / 50.0))


def _between_group_signal(df: pd.DataFrame, cat_col: str, num_col: str):
    try:
        grp = df.groupby(cat_col)[num_col].mean()
        if grp.size <= 1:
            return 0.0
        # between-group variance normalized by overall variance
        between_var = grp.var()
        overall_var = df[num_col].var()
        if overall_var is None or math.isnan(overall_var) or overall_var <= 0:
            return 0.0
        return _normalized(abs(between_var), 0.0, overall_var)
    except Exception:
        return 0.0


def _corr_signal(df: pd.DataFrame, xcol: str, ycol: str):
    try:
        sub = df[[xcol, ycol]].dropna()
        if sub.shape[0] < 3:
            return 0.0
        corr = sub[xcol].corr(sub[ycol])
        if corr is None or math.isnan(corr):
            return 0.0
        return min(1.0, abs(corr))
    except Exception:
        return 0.0


def _trend_signal(df: pd.DataFrame, dt_col: str, num_col: str):
    try:
        tmp = df[[dt_col, num_col]].dropna()
        tmp[dt_col] = pd.to_datetime(tmp[dt_col], errors="coerce")
        tmp = tmp.dropna().sort_values(dt_col)
        if tmp.shape[0] < 3:
            return 0.0
        X = (tmp[dt_col] - tmp[dt_col].min()).dt.total_seconds().astype(float).values
        y = tmp[num_col].astype(float).values
        coeffs = np.polyfit(X, y, 1)
        y_pred = np.polyval(coeffs, X)
        ss_res = ((y - y_pred) ** 2).sum()
        ss_tot = ((y - y.mean()) ** 2).sum()
        r2 = 1 - ss_res / (ss_tot + 1e-9)
        r2 = max(0.0, min(1.0, r2))
        return r2
    except Exception:
        return 0.0


# ---------------------------
# Main analyzer
# ---------------------------
def analyze_dataframe(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Build a profile with types, basic stats, mean/median/mode, and suggestions.
    Each suggestion contains: suggested_chart, reason, score (0..100), explain_score.
    """
    profile: Dict[str, Any] = {}
    profile["n_rows"], profile["n_cols"] = df.shape
    profile["columns"] = []

    for col in df.columns:
        ser = df[col]
        col_info = {
            "name": col,
            "dtype": str(ser.dtype),
            "type": detect_column_type(ser),
            "n_unique": int(ser.nunique(dropna=True)),
            "n_missing": int(ser.isna().sum()),
            "sample_values": list(ser.dropna().astype(str).unique()[:5])
        }

        if pd.api.types.is_numeric_dtype(ser):
            clean = ser.dropna().astype(float)
            col_info["count"] = int(clean.size)
            col_info["mean"] = None if clean.size == 0 else float(clean.mean())
            col_info["median"] = None if clean.size == 0 else float(clean.median())
            mode_val, mode_count = safe_mode(clean)
            try:
                mode_val_num = float(mode_val) if mode_val is not None and str(mode_val).replace('.', '', 1).isdigit() else mode_val
            except Exception:
                mode_val_num = mode_val
            col_info["mode"] = mode_val_num
            col_info["mode_count"] = mode_count
            col_info["std"] = None if clean.size == 0 else float(clean.std())
            col_info["min"] = None if clean.size == 0 else float(clean.min())
            col_info["max"] = None if clean.size == 0 else float(clean.max())
            try:
                col_info["skew"] = float(clean.skew())
            except Exception:
                col_info["skew"] = None
        else:
            mode_val, mode_count = safe_mode(ser)
            col_info["mode"] = mode_val
            col_info["mode_count"] = mode_count

        profile["columns"].append(col_info)

    numeric_df = df.select_dtypes(include=[np.number])
    profile["numeric_columns"] = list(numeric_df.columns)
    if not numeric_df.empty and numeric_df.shape[1] > 1:
        profile["correlation"] = numeric_df.corr().round(4).to_dict()
    else:
        profile["correlation"] = {}

    # Suggestions heuristics with simple suitability scores (no sklearn).
    suggestions = []
    categorical_cols = [c["name"] for c in profile["columns"] if c["type"] == "categorical"]
    numerical_cols = profile["numeric_columns"]
    datetime_cols = [c["name"] for c in profile["columns"] if c["type"] == "datetime"]

    # category -> numeric (bar + box)
    for cat in categorical_cols:
        cat_info = next((c for c in profile["columns"] if c["name"] == cat), None)
        nuniq = cat_info["n_unique"] if cat_info else 0
        for num in numerical_cols:
            info_signal = _between_group_signal(df, cat, num)
            readability = _readability_for_category(nuniq, profile["n_rows"])
            score_val = 0.65 * info_signal + 0.35 * readability
            score_pct = round(100 * max(0.0, min(1.0, score_val)), 1)

            suggestions.append({
                "type": "category_quantity",
                "x": cat,
                "y": num,
                "suggested_chart": "bar",
                "reason": "Categorical X vs Numerical Y — bar for group aggregates.",
                "score": score_pct,
                "explain_score": f"between_var_signal={info_signal:.2f},readability={readability:.2f}"
            })

            # box distribution
            score_box = 0.6 * readability + 0.4 * min(1.0, 0.5 + info_signal / 2.0)
            suggestions.append({
                "type": "category_distribution",
                "x": cat,
                "y": num,
                "suggested_chart": "box",
                "reason": "Box plot shows distributions and outliers by category.",
                "score": round(100 * max(0.0, min(1.0, score_box)), 1),
                "explain_score": f"readability={readability:.2f}"
            })

    # pie suggestions (small-cardinality)
    for cat in categorical_cols:
        cat_info = next((c for c in profile["columns"] if c["name"] == cat), None)
        if cat_info and cat_info["n_unique"] <= 8:
            try:
                counts = df[cat].value_counts(normalize=True)
                entropy = -(counts * np.log2(counts + 1e-9)).sum()
                entropy_norm = entropy / math.log2(max(cat_info["n_unique"], 2))
                uniform_penalty = entropy_norm
            except Exception:
                uniform_penalty = 0.5
            score_pie = 0.7 * (1 - uniform_penalty) + 0.3 * 0.8
            suggestions.append({
                "type": "category_percentage",
                "x": cat,
                "suggested_chart": "pie",
                "reason": "Small-cardinality categorical distribution — pie shows percentage share.",
                "score": round(100 * max(0.0, min(1.0, score_pie)), 1),
                "explain_score": f"cardinality={cat_info['n_unique']},entropy_penalty={uniform_penalty:.2f}"
            })

    # time series suggestions
    for dt in datetime_cols:
        for num in numerical_cols:
            trend = _trend_signal(df, dt, num)
            score_line = 0.75 * trend + 0.25 * 0.6
            suggestions.append({
                "type": "timeseries",
                "x": dt,
                "y": num,
                "suggested_chart": "line",
                "reason": "Time series data — line chart shows trends.",
                "score": round(100 * max(0.0, min(1.0, score_line)), 1),
                "explain_score": f"trend_r2={trend:.2f}"
            })

    # numeric vs numeric (scatter)
    if len(numerical_cols) >= 2:
        for i in range(len(numerical_cols)):
            for j in range(i + 1, len(numerical_cols)):
                xcol = numerical_cols[i]
                ycol = numerical_cols[j]
                corr_sig = _corr_signal(df, xcol, ycol)
                score_scatter = 0.65 * corr_sig + 0.35 * 0.6
                suggestions.append({
                    "type": "numeric_numeric",
                    "x": xcol,
                    "y": ycol,
                    "suggested_chart": "scatter",
                    "reason": "Two numeric variables — scatter to inspect correlation.",
                    "score": round(100 * max(0.0, min(1.0, score_scatter)), 1),
                    "explain_score": f"corr_abs={corr_sig:.2f}"
                })

    # correlation heatmap global (fixed-good default)
    if len(numerical_cols) >= 2:
        suggestions.append({
            "type": "correlation",
            "suggested_chart": "heatmap",
            "reason": "Correlation matrix heatmap for numeric variables.",
            "score": 80.0,
            "explain_score": "global-correlation"
        })

    # sort suggestions by score descending for convenience
    profile["suggestions"] = sorted(suggestions, key=lambda s: s.get("score", 0), reverse=True)

    return profile
