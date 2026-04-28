import streamlit as st
import pandas as pd
import plotly.express as px
import os

# ================= CONFIG =================
st.set_page_config(page_title="Smart Dashboard", layout="wide")

# ================= DARK UI =================
st.markdown("""
<style>
.stApp { background-color: #0b1220; color: white; }

section[data-testid="stSidebar"] {
    background-color: #111827;
}

.kpi {
    background: #111827;
    padding: 15px;
    border-radius: 10px;
    text-align: center;
}

.back-btn {
    position: fixed;
    top: 15px;
    right: 20px;
    background-color: #2563eb;
    color: white;
    padding: 10px 16px;
    border-radius: 8px;
    text-decoration: none;
    font-weight: bold;
}
</style>
""", unsafe_allow_html=True)

# ================= PATH =================
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_FILE = os.path.join(BASE_DIR, "current_dataset.txt")

# ================= GET DATASET =================
dataset_path = None

# ✅ 1. Query param (priority)
query_params = st.query_params
if "dataset" in query_params:
    dataset_path = query_params["dataset"]

# ✅ 2. From file
if not dataset_path and os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        dataset_path = f.read().strip()

# ❌ REMOVE THIS (causing mismatch)
# uploads fallback REMOVED intentionally

# ================= VALIDATION =================
if not dataset_path:
    st.error("❌ No dataset available")
    st.stop()

if not os.path.exists(dataset_path):
    st.error("❌ Dataset file not found (deleted or moved)")
    st.stop()

# ================= LOAD =================
try:
    if dataset_path.endswith(".csv"):
        df = pd.read_csv(dataset_path)
    else:
        df = pd.read_excel(dataset_path)
except Exception as e:
    st.error(f"❌ Error loading dataset: {e}")
    st.stop()

filename = os.path.basename(dataset_path)

# ================= AI MODE BUTTON =================
col_btn1, col_btn2 = st.columns([9, 1])

with col_btn2:
    if st.button("⬅ AI Mode"):
        st.markdown(
            """<meta http-equiv="refresh" content="0; url=http://127.0.0.1:5000/ai">""",
            unsafe_allow_html=True
        )

# ================= SIDEBAR FILTERS =================
st.sidebar.title("📊 Filters")

df_filtered = df.copy()

cat_cols = df.select_dtypes(include="object").columns
for col in cat_cols:
    selected = st.sidebar.multiselect(col, df[col].dropna().unique())
    if selected:
        df_filtered = df_filtered[df_filtered[col].isin(selected)]

num_cols = df.select_dtypes(include="number").columns
for col in num_cols:
    min_val = float(df[col].min())
    max_val = float(df[col].max())

    selected = st.sidebar.slider(col, min_val, max_val, (min_val, max_val))

    df_filtered = df_filtered[
        (df_filtered[col] >= selected[0]) &
        (df_filtered[col] <= selected[1])
    ]

# ================= MAIN =================
st.title("🚀 Smart Analytics Dashboard")
st.caption(f"Dataset: {filename}")

num_cols = df_filtered.select_dtypes(include="number").columns
cat_cols = df_filtered.select_dtypes(include="object").columns

# ================= KPI =================
st.markdown("### 📌 Key Insights")

if len(num_cols) > 0:
    cols = st.columns(min(4, len(num_cols)))

    for i in range(min(4, len(num_cols))):
        col = num_cols[i]

        if df_filtered[col].dropna().empty:
            val = "N/A"
        else:
            val = round(df_filtered[col].mean(), 2)

        cols[i].markdown(
            f"<div class='kpi'><h4>{col}</h4><h2>{val}</h2></div>",
            unsafe_allow_html=True
        )

# ================= CHARTS =================
st.markdown("### 📊 Visual Analysis")

col1, col2 = st.columns(2)

if len(cat_cols) > 0 and len(num_cols) > 0:
    grouped = df_filtered.groupby(cat_cols[0])[num_cols[0]].mean().reset_index()

    fig1 = px.bar(grouped, x=cat_cols[0], y=num_cols[0], color=num_cols[0])
    fig1.update_layout(plot_bgcolor="#0b1220", paper_bgcolor="#0b1220", font_color="white")

    col1.plotly_chart(fig1, use_container_width=True)

if len(num_cols) > 0:
    fig2 = px.histogram(df_filtered, x=num_cols[0], marginal="box")
    fig2.update_layout(plot_bgcolor="#0b1220", paper_bgcolor="#0b1220", font_color="white")

    col2.plotly_chart(fig2, use_container_width=True)

col3, col4 = st.columns(2)

if len(num_cols) >= 2:
    corr = df_filtered[num_cols].corr()

    fig3 = px.imshow(corr, text_auto=True, color_continuous_scale="RdBu")
    fig3.update_layout(plot_bgcolor="#0b1220", paper_bgcolor="#0b1220", font_color="white")

    col3.plotly_chart(fig3, use_container_width=True)

    fig4 = px.scatter(df_filtered, x=num_cols[0], y=num_cols[1])
    fig4.update_layout(plot_bgcolor="#0b1220", paper_bgcolor="#0b1220", font_color="white")

    col4.plotly_chart(fig4, use_container_width=True)

# ================= INSIGHTS =================
st.markdown("### 🧠 Insights")

if len(num_cols) > 0:
    col = num_cols[0]

    if not df_filtered.empty and df_filtered[col].dropna().shape[0] > 0:
        st.success(f"Average {col}: {round(df_filtered[col].mean(), 2)}")
    else:
        st.warning(f"No valid data for {col}")

if len(cat_cols) > 0:
    col = cat_cols[0]

    if not df_filtered.empty:
        vc = df_filtered[col].dropna().value_counts()

        if not vc.empty:
            st.success(f"Top {col}: {vc.idxmax()}")
        else:
            st.warning(f"No valid category data for {col}")
    else:
        st.warning("No data after applying filters")