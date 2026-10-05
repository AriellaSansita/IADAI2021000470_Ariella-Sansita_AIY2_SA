"""
Hospital Inpatient Discharges Dashboard
MediScope Health Analytics - Streamlit app
Run locally:  streamlit run app.py

The CSV is read automatically from the repository (same folder as app.py, or ./data/).
"""
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Hospital Inpatient Discharges", page_icon="🏥", layout="wide")

BASE_DIR = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# 1. DATA LOCATION - auto-detect the CSV that lives in the repo
# ---------------------------------------------------------------------------
def find_repo_csv() -> Path | None:
    """Look for the dataset in the repo: preferred names first, then any CSV."""
    preferred = [
        BASE_DIR / "data" / "hospital_discharges_final.csv",
        BASE_DIR / "hospital_discharges_final.csv",
    ]
    for p in preferred:
        if p.exists():
            return p
    # Fallback: any csv in repo root or data/ (largest one is most likely the dataset)
    found = list(BASE_DIR.glob("*.csv")) + list((BASE_DIR / "data").glob("*.csv"))
    found = [f for f in found if f.name.lower() != "requirements.csv"]
    return max(found, key=lambda f: f.stat().st_size) if found else None


# ---------------------------------------------------------------------------
# 2. DATA LOADING & CLEANING
# ---------------------------------------------------------------------------
# Readable name -> possible raw column names (lower-case, exact match)
COLUMN_MAP = {
    "County": ["hospital county", "county", "hospital service area"],
    "Facility": ["facility name", "facility", "hospital name"],
    "Age Group": ["age group", "age_group"],
    "Gender": ["gender", "sex"],
    "Race": ["race"],
    "Length of Stay": ["length of stay", "length_of_stay", "los"],
    "Diagnosis Code": ["ccs diagnosis code", "diagnosis code", "diagnosis_code", "apr drg code"],
    "Diagnosis": ["ccs diagnosis description", "diagnosis description", "diagnosis",
                  "apr drg description", "apr mdc description", "primary diagnosis"],
    "Severity": ["apr severity of illness description", "severity", "severity of illness",
                 "severity of illness description"],
    "Admission Type": ["type of admission", "admission type"],
    "Payment Type": ["payment typology 1", "payment type", "payment typology", "payment_type"],
    "Total Charges": ["total charges", "charges", "total_charges"],
    "Total Costs": ["total costs", "costs", "total_costs"],
    "Birth Weight": ["birth weight", "birth_weight"],
}

# Last-resort keyword match for the diagnosis column (any column name containing these)
DIAG_KEYWORDS = ["diagnos", "drg", "ccs", "condition", "disease", "procedure"]


def rename_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename raw columns to clear, readable names (exact match, then keyword fallback)."""
    lookup = {c.strip().lower(): c for c in df.columns}
    rename = {}
    for new, options in COLUMN_MAP.items():
        for opt in options:
            if opt in lookup and lookup[opt] not in rename:
                rename[lookup[opt]] = new
                break

    # Fallback: fuzzy-find a diagnosis column if exact names failed
    if "Diagnosis" not in rename.values():
        for raw_col in df.columns:
            if raw_col in rename:
                continue
            if any(k in raw_col.lower() for k in DIAG_KEYWORDS):
                rename[raw_col] = "Diagnosis"
                break
    return df.rename(columns=rename)


def money_to_float(series: pd.Series) -> pd.Series:
    """Convert strings like '$1,234.50' to float."""
    return pd.to_numeric(
        series.astype(str).str.replace(r"[$,\s]", "", regex=True), errors="coerce"
    )


@st.cache_data(show_spinner="Cleaning data...")
def clean_data(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Full preprocessing pipeline. Returns cleaned data + a log of what changed."""
    log = {"raw_rows": len(df)}
    df = rename_columns(df.copy())

    # Length of stay: handle '120 +' style values, then drop invalid (<=0 / NaN)
    if "Length of Stay" in df:
        df["Length of Stay"] = pd.to_numeric(
            df["Length of Stay"].astype(str).str.replace(r"[^\d.\-]", "", regex=True),
            errors="coerce",
        )
        before = len(df)
        df = df[df["Length of Stay"] > 0]
        log["invalid_stay_removed"] = before - len(df)

    # Money columns: string -> float
    for col in ["Total Charges", "Total Costs"]:
        if col in df:
            df[col] = money_to_float(df[col])
    if "Total Charges" in df:
        before = len(df)
        df = df[df["Total Charges"] > 0]
        # Remove extreme outliers (above the 99.5th percentile) so charts stay readable
        cap = df["Total Charges"].quantile(0.995)
        df = df[df["Total Charges"] <= cap]
        log["charge_outliers_removed"] = before - len(df)

    # Standardise categorical fields
    for col in ["Age Group", "Gender", "Race", "Severity", "County", "Facility",
                "Payment Type", "Admission Type", "Diagnosis"]:
        if col in df:
            df[col] = df[col].astype(str).str.strip().str.title().replace({"Nan": np.nan})
    if "Gender" in df:
        df["Gender"] = df["Gender"].replace({"M": "Male", "F": "Female", "U": "Unknown"})
    if "Severity" in df:
        order = ["Minor", "Moderate", "Major", "Extreme"]
        df["Severity"] = pd.Categorical(df["Severity"], categories=order, ordered=True)
    if "Age Group" in df:
        df["Age Group"] = df["Age Group"].astype("category")

    # Diagnosis code -> readable category (the description column already maps it)
    if "Diagnosis" not in df and "Diagnosis Code" in df:
        df["Diagnosis"] = "Code " + df["Diagnosis Code"].astype(str)

    # Birth weight: 0 means "not applicable" -> treat as missing
    if "Birth Weight" in df:
        df["Birth Weight"] = pd.to_numeric(df["Birth Weight"], errors="coerce").replace(0, np.nan)

    # Drop null-heavy columns (>60% missing), e.g. birth weight
    null_share = df.isna().mean()
    dropped = null_share[null_share > 0.6].index.tolist()
    df = df.drop(columns=dropped)
    log["dropped_columns"] = dropped

    # Feature engineering
    if {"Total Charges", "Length of Stay"} <= set(df.columns):
        df["Charge per Day"] = df["Total Charges"] / df["Length of Stay"]
    if "Length of Stay" in df:
        df["Stay Category"] = pd.cut(
            df["Length of Stay"], bins=[0, 3, 7, 14, np.inf],
            labels=["Short (1-3d)", "Medium (4-7d)", "Long (8-14d)", "Very long (15d+)"],
        )

    log["clean_rows"] = len(df)
    return df.reset_index(drop=True), log


@st.cache_data(show_spinner="Loading data...")
def load_csv(path_or_file) -> pd.DataFrame:
    return pd.read_csv(path_or_file, low_memory=False)


# ---------------------------------------------------------------------------
# 3. LOAD DATA (repo file by default, optional upload override)
# ---------------------------------------------------------------------------
st.title("🏥 Hospital Inpatient Discharges Dashboard")
st.caption("MediScope Health Analytics | Length of stay, charges, severity and utilisation insights")

with st.sidebar.expander("Data source", expanded=False):
    uploaded = st.file_uploader("Override with another CSV (optional)", type="csv")

repo_csv = find_repo_csv()
if uploaded:
    raw = load_csv(uploaded)
    st.sidebar.caption("Using uploaded file")
elif repo_csv:
    raw = load_csv(repo_csv)
    st.sidebar.caption(f"Loaded from repo: `{repo_csv.relative_to(BASE_DIR)}`")
else:
    st.error("No CSV found in the repository. Add your dataset to the repo root or a `data/` folder "
             "(e.g. `data/hospital_discharges_final.csv`), or upload one from the sidebar.")
    st.stop()

# If no diagnosis-like column exists in the file, let the user pick one instead of crashing
if "Diagnosis" not in rename_columns(raw).columns:
    text_cols = [c for c in raw.columns if raw[c].dtype == "object"]
    choice = st.sidebar.selectbox(
        "No diagnosis column detected - choose the column to use as 'Diagnosis'",
        ["(none)"] + list(raw.columns),
    )
    if choice != "(none)":
        raw = raw.rename(columns={choice: "Diagnosis"})

df, log = clean_data(raw)

REQUIRED = ["Length of Stay", "Total Charges", "Severity", "Payment Type"]
missing = [c for c in REQUIRED if c not in df.columns]
if missing:
    st.error(f"Could not find these columns: {missing}. Check the original column names below "
             "or update `COLUMN_MAP` in app.py.")
    st.write("Original CSV columns:", list(raw.columns))
    st.write("Columns after cleaning:", list(df.columns))
    st.stop()

# ---------------------------------------------------------------------------
# 4. SIDEBAR FILTERS
# ---------------------------------------------------------------------------
st.sidebar.header("Filters")


def multiselect_filter(label, col):
    if col in df.columns:
        opts = sorted(df[col].dropna().astype(str).unique())
        return st.sidebar.multiselect(label, opts, default=[])
    return []


filters = {
    "County": multiselect_filter("County", "County"),
    "Severity": multiselect_filter("Severity", "Severity"),
    "Age Group": multiselect_filter("Age Group", "Age Group"),
    "Gender": multiselect_filter("Gender", "Gender"),
    "Payment Type": multiselect_filter("Payment type", "Payment Type"),
}
fdf = df.copy()
for col, chosen in filters.items():
    if chosen:
        fdf = fdf[fdf[col].astype(str).isin(chosen)]

if fdf.empty:
    st.warning("No records match the selected filters.")
    st.stop()

with st.sidebar.expander("Data cleaning log"):
    st.write(log)

# ---------------------------------------------------------------------------
# 5. KPIs
# ---------------------------------------------------------------------------
k1, k2, k3, k4 = st.columns(4)
k1.metric("Discharges", f"{len(fdf):,}")
k2.metric("Avg length of stay", f"{fdf['Length of Stay'].mean():.1f} days")
k3.metric("Avg charges", f"${fdf['Total Charges'].mean():,.0f}")
k4.metric("Total charges", f"${fdf['Total Charges'].sum() / 1e6:,.1f}M")

st.divider()

tab_viz, tab_eda, tab_data = st.tabs(["📊 Visualisations", "🔎 EDA & insights", "🗂 Data"])

# ---------------------------------------------------------------------------
# 6. VISUALISATIONS (5 required charts)
# ---------------------------------------------------------------------------
with tab_viz:
    # Chart 1: Bar - avg stay per diagnosis (falls back to another category if the file has no diagnosis column)
    if "Diagnosis" in fdf.columns:
        group_col, group_label = "Diagnosis", "diagnosis"
    else:
        st.warning("This dataset has no diagnosis column, so chart 1 groups by another category. "
                   "Use the original dataset (with a diagnosis / CCS description column) for diagnosis-level results.")
        options = [c for c in ["Admission Type", "Age Group", "Severity", "Payment Type", "County", "Facility"]
                   if c in fdf.columns]
        group_col = st.selectbox("Group average stay by", options)
        group_label = group_col.lower()

    st.subheader(f"1. Average hospital stay per {group_label}")
    top_n = st.slider("Number of groups", 3, 30, 15)
    min_cases = st.number_input("Minimum cases per group", 1, 1000, 30)
    diag = (fdf.groupby(group_col, observed=True)["Length of Stay"].agg(["mean", "count"])
            .query("count >= @min_cases").sort_values("mean", ascending=False).head(top_n)
            .reset_index().rename(columns={group_col: "Group"}))
    if diag.empty:
        st.info("No group meets the minimum case count - lower the threshold.")
    else:
        diag["Group"] = diag["Group"].astype(str)
        fig1 = px.bar(diag.sort_values("mean"), x="mean", y="Group", orientation="h",
                      color="mean", color_continuous_scale="Reds", hover_data=["count"],
                      labels={"mean": "Avg stay (days)", "count": "Cases", "Group": group_col})
        fig1.update_layout(height=max(400, 28 * len(diag)), coloraxis_showscale=False)
        st.plotly_chart(fig1, use_container_width=True)

    c1, c2 = st.columns(2)
    # Chart 2: Box plot - charges by severity
    with c1:
        st.subheader("2. Total charges by severity")
        fig2 = px.box(fdf, x="Severity", y="Total Charges", color="Severity",
                      category_orders={"Severity": ["Minor", "Moderate", "Major", "Extreme"]})
        fig2.update_layout(showlegend=False)
        st.plotly_chart(fig2, use_container_width=True)

    # Chart 3: Pie - payment type
    with c2:
        st.subheader("3. Patients by payment type")
        pay = fdf["Payment Type"].value_counts().reset_index()
        pay.columns = ["Payment Type", "Patients"]
        fig4 = px.pie(pay, names="Payment Type", values="Patients", hole=0.35)
        st.plotly_chart(fig4, use_container_width=True)

    # Chart 4: Heatmap - avg stay by facility and county
    if {"Facility", "County"} <= set(fdf.columns):
        st.subheader("4. Average stay by facility and county")
        n_fac = st.slider("Top facilities (by discharges)", 5, 30, 15)
        top_fac = fdf["Facility"].value_counts().head(n_fac).index
        top_cty = fdf["County"].value_counts().head(12).index
        pv = fdf[fdf["Facility"].isin(top_fac) & fdf["County"].isin(top_cty)].pivot_table(
            index="Facility", columns="County", values="Length of Stay", aggfunc="mean")
        fig3 = px.imshow(pv, aspect="auto", color_continuous_scale="YlOrRd",
                         labels=dict(color="Avg stay (days)"))
        fig3.update_layout(height=max(400, 30 * len(pv)))
        st.plotly_chart(fig3, use_container_width=True)
        st.caption("Blank cells = facility has no discharges in that county (facilities sit in one county).")

    # Chart 5: Histogram - length of stay
    st.subheader("5. Distribution of length of stay")
    cap = max(int(fdf["Length of Stay"].quantile(0.99)), 1)
    fig5 = px.histogram(fdf[fdf["Length of Stay"] <= cap], x="Length of Stay", nbins=cap,
                        color_discrete_sequence=["#2a9d8f"], marginal="box")
    fig5.update_layout(bargap=0.05, xaxis_title="Length of stay (days, up to 99th percentile)")
    st.plotly_chart(fig5, use_container_width=True)

# ---------------------------------------------------------------------------
# 7. EDA & INSIGHTS
# ---------------------------------------------------------------------------
with tab_eda:
    st.subheader("Research questions")
    st.markdown("""
1. Which diagnoses are linked to long stays?
2. Which age groups incur the highest charges?
3. How does patient severity affect total cost?
4. Are there counties with longer average stays?
5. How do payment types affect the final billing?
6. Which facilities have the highest utilisation?
""")

    if "Age Group" in fdf:
        st.markdown("**Q2 - Charges by age group and gender**")
        age = fdf.groupby("Age Group", observed=True)["Total Charges"].agg(["mean", "sum", "count"]).reset_index()
        figa = px.bar(age, x="Age Group", y="mean", color="mean", color_continuous_scale="Blues",
                      labels={"mean": "Avg charges ($)"}, hover_data=["sum", "count"])
        st.plotly_chart(figa, use_container_width=True)
        if "Gender" in fdf:
            st.dataframe(fdf.pivot_table(index="Age Group", columns="Gender", values="Total Charges",
                                         aggfunc="mean", observed=True).round(0))

    st.markdown("**Q3 - Severity vs. stay and cost**")
    sev = fdf.groupby("Severity", observed=True).agg(
        avg_stay=("Length of Stay", "mean"), avg_charges=("Total Charges", "mean"),
        median_charges=("Total Charges", "median"), cases=("Length of Stay", "size")).round(1)
    st.dataframe(sev)

    if "County" in fdf:
        st.markdown("**Q4 - Counties with the longest average stay**")
        cty = (fdf.groupby("County")["Length of Stay"].agg(["mean", "count"])
               .query("count >= 50").sort_values("mean", ascending=False).head(10).round(2))
        st.dataframe(cty)

    st.markdown("**Q5 - Payment type vs. billing**")
    st.dataframe(fdf.groupby("Payment Type")["Total Charges"].agg(["mean", "median", "count"]).round(0)
                 .sort_values("mean", ascending=False))

    if "Facility" in fdf:
        st.markdown("**Q6 - Top high-utilisation facilities**")
        st.dataframe(fdf["Facility"].value_counts().head(10).rename("Discharges"))

    st.markdown("**Correlation (numeric fields)**")
    num = fdf.select_dtypes("number")
    st.plotly_chart(px.imshow(num.corr().round(2), text_auto=True, color_continuous_scale="RdBu_r",
                              zmin=-1, zmax=1), use_container_width=True)

    st.subheader("Key insights (update as filters change)")
    top_d = diag.iloc[0] if len(diag) else None
    if top_d is not None:
        st.info(f"Longest average stay by {group_label}: **{top_d['Group']}** at {top_d['mean']:.1f} days ({int(top_d['count'])} cases).")
    if len(sev):
        st.info(f"Average charges rise from ${sev['avg_charges'].iloc[0]:,.0f} ({sev.index[0]}) to "
                f"${sev['avg_charges'].iloc[-1]:,.0f} ({sev.index[-1]}) across severity levels.")

# ---------------------------------------------------------------------------
# 8. DATA
# ---------------------------------------------------------------------------
with tab_data:
    st.dataframe(fdf.head(1000))
    st.download_button("Download filtered data (CSV)", fdf.to_csv(index=False).encode(),
                       "filtered_discharges.csv", "text/csv")
