import plotly.graph_objects as go
import pandas as pd
from typing import List, Dict, Tuple, Any, Optional

def _safe_col(df: pd.DataFrame, col: str):
    if col not in df.columns:
        raise ValueError(f"Column {col} not found in DataFrame")
    return df[col]

def generate_plotly_divs(df: pd.DataFrame, profile: Dict[str, Any], max_charts: int = 4) -> List[Dict[str, Any]]:
    charts = []
    suggestions = profile.get("suggestions", [])[:max_charts]
    for s in suggestions:
        try:
            div, title = generate_single_plot_div(df, chart_type=s.get("suggested_chart"), xcol=s.get("x"), ycol=s.get("y"))
            charts.append({"title": title, "div": div, "suggestion": s})
        except Exception:
            continue
    return charts

def generate_single_plot_div(df: pd.DataFrame, chart_type: Optional[str] = None, xcol: Optional[str] = None, ycol: Optional[str] = None) -> Tuple[str, str]:
    """
    Build a Plotly figure and return (div_html, title).
    Supported chart_type: bar, line, scatter, pie, heatmap, histogram, box
    """
    if chart_type is None:
        chart_type = "bar"

    # BAR
    if chart_type == "bar":
        if xcol is None or ycol is None:
            raise ValueError("Bar chart requires xcol and ycol")
        agg = df.groupby(xcol)[ycol].sum().reset_index().sort_values(by=ycol, ascending=False)
        fig = go.Figure(data=[go.Bar(x=agg[xcol].astype(str), y=agg[ycol])])
        fig.update_layout(title=f"Bar: {xcol} vs {ycol}", xaxis_title=xcol, yaxis_title=ycol)

    # LINE
    elif chart_type == "line":
        if xcol is None or ycol is None:
            raise ValueError("Line chart requires xcol and ycol")
        xseries = pd.to_datetime(df[xcol], errors="coerce")
        yseries = pd.to_numeric(df[ycol], errors="coerce")
        tmp = pd.DataFrame({xcol: xseries, ycol: yseries}).dropna().sort_values(by=xcol)
        fig = go.Figure(data=[go.Scatter(x=tmp[xcol], y=tmp[ycol], mode="lines+markers")])
        fig.update_layout(title=f"Line: {ycol} over {xcol}", xaxis_title=xcol, yaxis_title=ycol)

    # SCATTER
    elif chart_type == "scatter":
        if xcol is None or ycol is None:
            raise ValueError("Scatter requires xcol and ycol")
        fig = go.Figure(data=[go.Scatter(x=df[xcol], y=df[ycol], mode="markers", marker=dict(size=7, opacity=0.7))])
        fig.update_layout(title=f"Scatter: {xcol} vs {ycol}", xaxis_title=xcol, yaxis_title=ycol)

    # PIE
    elif chart_type == "pie":
        if xcol is None:
            raise ValueError("Pie requires xcol")
        counts = df[xcol].astype(str).value_counts().reset_index()
        counts.columns = [xcol, "count"]
        fig = go.Figure(data=[go.Pie(labels=counts[xcol], values=counts["count"], hole=0.0)])
        fig.update_layout(title=f"Pie: distribution of {xcol}")

    # HEATMAP
    elif chart_type == "heatmap":
        numeric = df.select_dtypes(include=["number"])
        if numeric.shape[1] < 2:
            raise ValueError("Heatmap requires at least two numeric columns")
        corr = numeric.corr()
        fig = go.Figure(data=go.Heatmap(z=corr.values, x=corr.columns, y=corr.index, colorscale="Viridis"))
        fig.update_layout(title="Correlation Heatmap")

    # HISTOGRAM
    elif chart_type == "histogram":
        if ycol is None:
            raise ValueError("Histogram requires ycol (numeric column)")
        fig = go.Figure(data=[go.Histogram(x=df[ycol], nbinsx=30)])
        fig.update_layout(title=f"Histogram: {ycol}", xaxis_title=ycol)

    # BOX
    elif chart_type == "box":
        if ycol is None:
            raise ValueError("Box plot requires at least ycol")
        fig = go.Figure()
        if xcol:
            fig.add_trace(go.Box(x=df[xcol].astype(str), y=df[ycol], name=f"{ycol} by {xcol}"))
            fig.update_layout(title=f"Box: {ycol} by {xcol}")
        else:
            fig.add_trace(go.Box(y=df[ycol], name=ycol))
            fig.update_layout(title=f"Box: {ycol}")

    else:
        raise ValueError(f"Unsupported chart type: {chart_type}")

    div = fig.to_html(full_html=False, include_plotlyjs="cdn")
    title = fig.layout.title.text if fig.layout.title else "Chart"
    return div, title
