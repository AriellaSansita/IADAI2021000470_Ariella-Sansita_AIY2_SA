"""
Hospital Inpatient Discharges Dashboard
MediScope Health Analytics - Streamlit app
Run locally:  streamlit run app.py
"""
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Hospital Inpatient Discharges", page_icon="🏥", layout="wide")

DATA_PATH = "data/hospital_discharges.csv"  # put your dataset here (or use the sidebar uploader)

# ---------------------------------------------------------------------------
# 1. DATA LOADING & CLEANING
# ---------------------------------------------------------------------------
# Readable name -> possible raw column names (lower-case). Adjust if your file differs.
COLUMN_MAP = {
    "County": ["hospital county", "county"],
    "Facility": ["facility name", "facility", "hospital name"],
    "Age Group": ["age group"],
    "Gender": ["gender", "sex"],
    "Race": ["race"],
    "Length of Stay": ["length of stay", "los"],
    "Diagnosis Code": ["ccs diagnosis code", "diagnosis code"],
    "Diagnosis": ["ccs diagnosis description", "diagnosis description", "diagnosis"],
    "Severity": ["apr severity of illness description", "severity", "severity of illness"],
    "Admission Type": ["type of admission", "admission type"],
    "Payment Type": ["payment typology 1", "payment type", "payment typology"],
    "Total Charges": ["total charges", "charges"],
    "Total Costs": ["total costs", "costs"],
    "Birth Weight": ["birth weight"],
}


def rename_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename raw columns to clear, readable names."""
    lookup = {c.strip().lower(): c for c in df.columns}
    rename = {}
    for new, options in COLUMN_MAP.items():
        for opt in options:
            if opt in lookup:
                rename[lookup[opt]] = new
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
        # sort age groups naturally: '0 To 17', '18 To 29', ... '70 Or Older'
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
# 2. SIDEBAR - load data + filters
# ---------------------------------------------------------------------------
st.title("🏥 Hospital Inpatient Discharges Dashboard")
st.caption("MediScope Health Analytics | Length of stay, charges, severity and utilisation insights")

uploaded = st.sidebar.file_uploader("Upload dataset (CSV)", type="csv")
try:
    raw = load_csv(uploaded) if uploaded else load_csv(DATA_PATH)
except FileNotFoundError:
    st.warning(f"Dataset not found at `{DATA_PATH}`. Upload the CSV in the sidebar to begin.")
    st.stop()

df, log = clean_data(raw)

REQUIRED = ["Length of Stay", "Total Charges", "Diagnosis", "Severity", "Payment Type"]
missing = [c for c in REQUIRED if c not in df.columns]
if missing:
    st.error(f"Could not find these columns: {missing}. Update `COLUMN_MAP` in app.py to match your file.")
    st.write("Columns found:", list(df.columns))
    st.stop()

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
# 3. KPIs
# ---------------------------------------------------------------------------
k1, k2, k3, k4 = st.columns(4)
k1.metric("Discharges", f"{len(fdf):,}")
k2.metric("Avg length of stay", f"{fdf['Length of Stay'].mean():.1f} days")
k3.metric("Avg charges", f"${fdf['Total Charges'].mean():,.0f}")
k4.metric("Total charges", f"${fdf['Total Charges'].sum() / 1e6:,.1f}M")

st.divider()

tab_viz, tab_eda, tab_data = st.tabs(["📊 Visualisations", "🔎 EDA & insights", "🗂 Data"])

# ---------------------------------------------------------------------------
# 4. VISUALISATIONS (5 required charts)
# ---------------------------------------------------------------------------
with tab_viz:
    # Chart 1: Bar - avg stay per diagnosis
    st.subheader("1. Average hospital stay per diagnosis")
    top_n = st.slider("Number of diagnoses", 5, 30, 15)
    min_cases = st.number_input("Minimum cases per diagnosis", 1, 1000, 30)
    diag = (fdf.groupby("Diagnosis")["Length of Stay"].agg(["mean", "count"])
            .query("count >= @min_cases").sort_values("mean", ascending=False).head(top_n)
            .reset_index())
    fig1 = px.bar(diag.sort_values("mean"), x="mean", y="Diagnosis", orientation="h",
                  color="mean", color_continuous_scale="Reds", hover_data=["count"],
                  labels={"mean": "Avg stay (days)", "count": "Cases"})
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

    # Chart 4: Pie - payment type
    with c2:
        st.subheader("3. Patients by payment type")
        pay = fdf["Payment Type"].value_counts().reset_index()
        pay.columns = ["Payment Type", "Patients"]
        fig4 = px.pie(pay, names="Payment Type", values="Patients", hole=0.35)
        st.plotly_chart(fig4, use_container_width=True)

    # Chart 3: Heatmap - avg stay by facility and county
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
    cap = int(fdf["Length of Stay"].quantile(0.99))
    fig5 = px.histogram(fdf[fdf["Length of Stay"] <= cap], x="Length of Stay", nbins=cap,
                        color_discrete_sequence=["#2a9d8f"], marginal="box")
    fig5.update_layout(bargap=0.05, xaxis_title="Length of stay (days, up to 99th percentile)")
    st.plotly_chart(fig5, use_container_width=True)

# ---------------------------------------------------------------------------
# 5. EDA & INSIGHTS (answers to the research questions)
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

    # Auto-generated headline insights
    st.subheader("Key insights (update as filters change)")
    top_d = diag.iloc[0] if len(diag) else None
    if top_d is not None:
        st.info(f"Longest average stay: **{top_d['Diagnosis']}** at {top_d['mean']:.1f} days ({int(top_d['count'])} cases).")
    st.info(f"Average charges rise from ${sev['avg_charges'].iloc[0]:,.0f} ({sev.index[0]}) to "
            f"${sev['avg_charges'].iloc[-1]:,.0f} ({sev.index[-1]}) across severity levels.")

# ---------------------------------------------------------------------------
# 6. DATA
# ---------------------------------------------------------------------------
with tab_data:
    st.dataframe(fdf.head(1000))
    st.download_button("Download filtered data (CSV)", fdf.to_csv(index=False).encode(),
                       "filtered_discharges.csv", "text/csv")
