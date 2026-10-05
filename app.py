"""
Hospital Inpatient Discharges Dashboard
MediScope Health Analytics - Streamlit app
Run locally:  streamlit run app.py

The CSV (hospital_discharges_final.csv) is read automatically from the repository:
same folder as app.py, or a ./data/ sub-folder.
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Hospital Inpatient Discharges", page_icon="🏥", layout="wide")

BASE_DIR = Path(__file__).resolve().parent
SEVERITY_ORDER = ["Minor", "Moderate", "Major", "Extreme"]
AGE_ORDER = ["0 To 17", "18 To 29", "30 To 49", "50 To 69", "70 Or Older"]
STAY_ORDER = ["Short (1-3d)", "Medium (4-7d)", "Long (8-14d)", "Very long (15d+)"]


# ---------------------------------------------------------------------------
# 1. DATA LOCATION
# ---------------------------------------------------------------------------
def find_repo_csv():
    """Locate the dataset inside the repo."""
    for p in [BASE_DIR / "data" / "hospital_discharges_final.csv",
              BASE_DIR / "hospital_discharges_final.csv"]:
        if p.exists():
            return p
    found = list(BASE_DIR.glob("*.csv")) + list((BASE_DIR / "data").glob("*.csv"))
    return max(found, key=lambda f: f.stat().st_size) if found else None


# ---------------------------------------------------------------------------
# 2. LOADING & CLEANING
# ---------------------------------------------------------------------------
# Readable name -> possible raw column names (lower-case). Works for the raw SPARCS
# file and for the already-cleaned file.
COLUMN_MAP = {
    "County": ["hospital county", "county", "hospital service area"],
    "Facility": ["facility name", "facility", "hospital name"],
    "Age Group": ["age group", "age_group"],
    "Gender": ["gender", "sex"],
    "Race": ["race"],
    "Length of Stay": ["length of stay", "length_of_stay", "los"],
    "Diagnosis Code": ["ccs diagnosis code", "diagnosis code", "diagnosis_code"],
    "Diagnosis": ["ccs diagnosis description", "diagnosis description", "diagnosis",
                  "apr drg description", "apr mdc description", "primary diagnosis"],
    "Severity": ["apr severity of illness description", "severity",
                 "severity of illness", "severity of illness description"],
    "Admission Type": ["type of admission", "admission type"],
    "Payment Type": ["payment typology 1", "payment type", "payment typology", "payment_type"],
    "Total Charges": ["total charges", "charges", "total_charges"],
    "Total Costs": ["total costs", "costs", "total_costs"],
    "Birth Weight": ["birth weight", "birth_weight"],
}
DIAG_KEYWORDS = ["diagnos", "drg", "ccs"]  # fuzzy fallback for a diagnosis column

# Acronyms that .title() would wrongly turn into "Nyu", "Suny", ...
ACRONYMS = {r"\bNyu\b": "NYU", r"\bSuny\b": "SUNY", r"\bVa\b": "VA", r"\bUcsf\b": "UCSF"}


def rename_columns(df):
    """Rename raw columns to clear, readable names (exact match, then keyword fallback)."""
    lookup = {c.strip().lower(): c for c in df.columns}
    rename = {}
    for new, options in COLUMN_MAP.items():
        for opt in options:
            if opt in lookup and lookup[opt] not in rename:
                rename[lookup[opt]] = new
                break
    if "Diagnosis" not in rename.values():
        for raw_col in df.columns:
            if raw_col not in rename and any(k in raw_col.lower() for k in DIAG_KEYWORDS):
                rename[raw_col] = "Diagnosis"
                break
    return df.rename(columns=rename)


def money_to_float(series):
    """'$1,234.50' -> 1234.5"""
    return pd.to_numeric(series.astype(str).str.replace(r"[$,\s]", "", regex=True), errors="coerce")


def tidy_text(series):
    """Strip, Title-Case, restore acronyms, turn 'Nan' into real missing values."""
    s = series.astype(str).str.strip().str.title().replace({"Nan": np.nan})
    for pattern, repl in ACRONYMS.items():
        s = s.str.replace(pattern, repl, regex=True)
    return s


@st.cache_data(show_spinner="Loading and cleaning data...")
def load_and_clean(path: str):
    """Load the CSV and run the full preprocessing pipeline. Returns (clean df, change log)."""
    df = rename_columns(pd.read_csv(path, low_memory=False))
    log = {"raw_rows": len(df)}

    # Length of stay: handle '120 +' style values; drop invalid (<=0 / missing)
    df["Length of Stay"] = pd.to_numeric(
        df["Length of Stay"].astype(str).str.replace(r"[^\d.\-]", "", regex=True), errors="coerce")
    before = len(df)
    df = df[df["Length of Stay"] > 0]
    log["invalid_stay_removed"] = before - len(df)

    # Money columns: string -> float; drop non-positive charges
    for col in ["Total Charges", "Total Costs"]:
        if col in df:
            df[col] = money_to_float(df[col])
    before = len(df)
    df = df[df["Total Charges"] > 0]
    log["invalid_charges_removed"] = before - len(df)

    # Outliers: trim above the 99.5th percentile ONLY if the file still has extreme values
    # (the supplied "final" file was already trimmed, so trimming again would lose good rows)
    cap = df["Total Charges"].quantile(0.995)
    if df["Total Charges"].max() > 2 * cap:
        before = len(df)
        df = df[df["Total Charges"] <= cap]
        log["charge_outliers_removed"] = before - len(df)
    else:
        log["charge_outliers_removed"] = "skipped (already trimmed)"

    # Standardise categorical fields
    for col in ["Age Group", "Gender", "Race", "Severity", "County", "Facility",
                "Payment Type", "Admission Type", "Diagnosis"]:
        if col in df:
            df[col] = tidy_text(df[col])
    df["Gender"] = df["Gender"].replace({"M": "Male", "F": "Female", "U": "Unknown"})
    if "Admission Type" in df:  # "Not Available" is not a real admission type -> treat as missing
        df["Admission Type"] = df["Admission Type"].replace({"Not Available": np.nan})

    before = len(df)
    df = df.dropna(subset=["Severity"])  # severity is central to the analysis
    log["missing_severity_removed"] = before - len(df)
    df["Severity"] = pd.Categorical(df["Severity"], categories=SEVERITY_ORDER, ordered=True)
    if set(df["Age Group"].dropna().unique()) <= set(AGE_ORDER):
        df["Age Group"] = pd.Categorical(df["Age Group"], categories=AGE_ORDER, ordered=True)
    else:
        df["Age Group"] = df["Age Group"].astype("category")

    # Diagnosis code -> readable label (only if the file has codes but no description)
    if "Diagnosis" not in df and "Diagnosis Code" in df:
        df["Diagnosis"] = "Code " + df["Diagnosis Code"].astype(str)

    # Birth weight: 0 = not applicable -> missing
    if "Birth Weight" in df:
        df["Birth Weight"] = pd.to_numeric(df["Birth Weight"], errors="coerce").replace(0, np.nan)

    # Drop null-heavy columns (>60% missing), e.g. birth weight
    null_share = df.isna().mean()
    dropped = null_share[null_share > 0.6].index.tolist()
    df = df.drop(columns=dropped)
    log["dropped_columns"] = dropped

    # Feature engineering
    df["Charge per Day"] = df["Total Charges"] / df["Length of Stay"]
    df["Stay Category"] = pd.cut(df["Length of Stay"], bins=[0, 3, 7, 14, np.inf], labels=STAY_ORDER)
    if "Total Costs" in df:
        df["Cost-to-Charge Ratio"] = (df["Total Costs"] / df["Total Charges"]).clip(upper=1.5)

    log["clean_rows"] = len(df)
    return df.reset_index(drop=True), log


# ---------------------------------------------------------------------------
# 3. LOAD DATA
# ---------------------------------------------------------------------------
st.title("🏥 Hospital Inpatient Discharges Dashboard")
st.caption("MediScope Health Analytics | Length of stay, charges, severity and utilisation insights")

csv_path = find_repo_csv()
if csv_path is None:
    st.error("No CSV found in the repository. Add `hospital_discharges_final.csv` to the repo root "
             "or a `data/` folder and redeploy.")
    st.stop()

df, log = load_and_clean(str(csv_path))

REQUIRED = ["Length of Stay", "Total Charges", "Severity", "Payment Type", "Age Group"]
missing = [c for c in REQUIRED if c not in df.columns]
if missing:
    st.error(f"Could not find these columns: {missing}. Update `COLUMN_MAP` in app.py.")
    st.write("Columns found:", list(df.columns))
    st.stop()

HAS_DIAG = "Diagnosis" in df.columns

# ---------------------------------------------------------------------------
# 4. SIDEBAR FILTERS
# ---------------------------------------------------------------------------
st.sidebar.header("Filters")


def multiselect_filter(label, col):
    if col in df.columns:
        opts = [str(o) for o in (df[col].cat.categories if hasattr(df[col], "cat") else sorted(df[col].dropna().unique()))]
        return st.sidebar.multiselect(label, opts, default=[])
    return []


filters = {
    "County": multiselect_filter("County", "County"),
    "Severity": multiselect_filter("Severity", "Severity"),
    "Age Group": multiselect_filter("Age group", "Age Group"),
    "Gender": multiselect_filter("Gender", "Gender"),
    "Admission Type": multiselect_filter("Admission type", "Admission Type"),
    "Payment Type": multiselect_filter("Payment type", "Payment Type"),
}
fdf = df
for col, chosen in filters.items():
    if chosen:
        fdf = fdf[fdf[col].astype(str).isin(chosen)]

if fdf.empty:
    st.warning("No records match the selected filters.")
    st.stop()

st.sidebar.caption(f"Showing {len(fdf):,} of {len(df):,} discharges")

# ---------------------------------------------------------------------------
# 5. KPIs
# ---------------------------------------------------------------------------
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Discharges", f"{len(fdf):,}")
k2.metric("Avg length of stay", f"{fdf['Length of Stay'].mean():.1f} days")
k3.metric("Avg charges", f"${fdf['Total Charges'].mean():,.0f}")
k4.metric("Avg costs", f"${fdf['Total Costs'].mean():,.0f}" if "Total Costs" in fdf else "n/a")
total = fdf["Total Charges"].sum()
k5.metric("Total charges", f"${total / 1e9:,.2f}B" if total >= 1e9 else f"${total / 1e6:,.1f}M")

st.divider()
tab_viz, tab_eda, tab_data = st.tabs(["📊 Visualisations", "🔎 EDA & insights", "🗂 Data"])

# ---------------------------------------------------------------------------
# 6. VISUALISATIONS (5 required charts)
# ---------------------------------------------------------------------------
with tab_viz:
    # Chart 1: Bar - avg stay per diagnosis (or another category if the file has no diagnosis)
    if HAS_DIAG:
        group_col = "Diagnosis"
    else:
        st.info("This dataset has no diagnosis column, so chart 1 groups average stay by a "
                "different category. Pick one below.")
        opts = [c for c in ["Admission Type", "Age Group", "Severity", "Payment Type", "County", "Facility"]
                if c in fdf.columns]
        group_col = st.selectbox("Group average stay by", opts)
    st.subheader(f"1. Average hospital stay per {group_col.lower()}")
    a, b = st.columns(2)
    top_n = a.slider("Number of groups to show", 3, 30, 10)
    min_cases = b.number_input("Minimum cases per group", 1, 1000, 30)
    g1 = (fdf.groupby(group_col, observed=True)["Length of Stay"].agg(["mean", "count"])
          .query("count >= @min_cases").sort_values("mean", ascending=False).head(top_n).reset_index())
    g1[group_col] = g1[group_col].astype(str)
    if g1.empty:
        st.info("No group meets the minimum case count - lower the threshold.")
    else:
        fig1 = px.bar(g1.sort_values("mean"), x="mean", y=group_col, orientation="h",
                      color="mean", color_continuous_scale="Reds", hover_data={"count": ":,"},
                      labels={"mean": "Avg stay (days)", "count": "Cases"})
        fig1.update_layout(height=max(350, 40 * len(g1)), coloraxis_showscale=False)
        st.plotly_chart(fig1, width="stretch")

    c1, c2 = st.columns(2)
    # Chart 2: Box plot - charges by severity (sampled so the browser stays fast)
    with c1:
        st.subheader("2. Total charges by severity")
        box_df = fdf if len(fdf) <= 30000 else fdf.sample(30000, random_state=42)
        log_y = st.checkbox("Log scale (easier to compare the boxes)", value=False)
        fig2 = px.box(box_df, x="Severity", y="Total Charges", color="Severity",
                      category_orders={"Severity": SEVERITY_ORDER}, points="outliers")
        fig2.update_layout(showlegend=False, yaxis_tickprefix="$")
        if log_y:
            fig2.update_yaxes(type="log")
        st.plotly_chart(fig2, width="stretch")
        if len(fdf) > 30000:
            st.caption("Box plot drawn from a random sample of 30,000 discharges for speed.")

    # Chart 3: Pie - payment type
    with c2:
        st.subheader("3. Patients by payment type")
        pay = fdf["Payment Type"].value_counts().reset_index()
        pay.columns = ["Payment Type", "Patients"]
        fig3 = px.pie(pay, names="Payment Type", values="Patients", hole=0.35)
        fig3.update_traces(textposition="inside", textinfo="percent")
        fig3.update_layout(legend=dict(font=dict(size=10)), uniformtext_minsize=11, uniformtext_mode="hide")
        st.plotly_chart(fig3, width="stretch")

    # Chart 4: Heatmap - avg stay by facility and county
    if {"Facility", "County"} <= set(fdf.columns):
        st.subheader("4. Average stay by facility and county")
        st.caption("Facilities sit in a single county, so rows are labelled **County · Facility** (sorted by "
                   "longest average stay) and the columns show how stay changes across another dimension. "
                   "Cells with fewer than 20 discharges are left blank because their averages are unreliable.")
        h1, h2 = st.columns(2)
        n_fac = h1.slider("Top facilities (by discharges)", 5, 40, 20)
        col_dim = h2.selectbox("Columns", [c for c in ["Severity", "Admission Type", "Age Group", "Payment Type"]
                                           if c in fdf.columns])
        top_fac = fdf["Facility"].value_counts().head(n_fac).index
        hm = fdf[fdf["Facility"].isin(top_fac)].copy()
        hm["County · Facility"] = hm["County"].astype(str) + " · " + hm["Facility"].astype(str)
        pv = hm.pivot_table(index="County · Facility", columns=col_dim, values="Length of Stay",
                            aggfunc="mean", observed=True)
        n_cases = hm.pivot_table(index="County · Facility", columns=col_dim, values="Length of Stay",
                                 aggfunc="size", observed=True)
        pv = pv.where(n_cases >= 20)  # hide unreliable small-sample cells
        pv = pv.loc[pv.mean(axis=1).sort_values(ascending=False).index]
        fig4 = px.imshow(pv.round(1), aspect="auto", color_continuous_scale="YlOrRd", text_auto=".1f",
                         labels=dict(color="Avg stay (days)"))
        fig4.update_layout(height=max(400, 28 * len(pv)))
        st.plotly_chart(fig4, width="stretch")

    # Chart 5: Histogram - length of stay (pre-binned = fast)
    st.subheader("5. Distribution of length of stay")
    cap = max(int(fdf["Length of Stay"].quantile(0.99)), 1)
    counts = (fdf.loc[fdf["Length of Stay"] <= cap, "Length of Stay"].astype(int)
              .value_counts().sort_index().reset_index())
    counts.columns = ["Length of Stay", "Discharges"]
    fig5 = px.bar(counts, x="Length of Stay", y="Discharges", color_discrete_sequence=["#2a9d8f"])
    fig5.add_vline(x=fdf["Length of Stay"].mean(), line_dash="dash", line_color="#ef476f", line_width=2,
                   annotation_text=f"Mean {fdf['Length of Stay'].mean():.1f}", annotation_position="top right",
                   annotation_font_color="#ef476f")
    fig5.add_vline(x=fdf["Length of Stay"].median(), line_dash="dot", line_color="#ffb703", line_width=2,
                   annotation_text=f"Median {fdf['Length of Stay'].median():.0f}", annotation_position="top left",
                   annotation_font_color="#ffb703")
    fig5.update_layout(bargap=0.05, xaxis_title="Length of stay (days, up to 99th percentile)")
    st.plotly_chart(fig5, width="stretch")

# ---------------------------------------------------------------------------
# 7. EDA & INSIGHTS
# ---------------------------------------------------------------------------
with tab_eda:
    st.subheader("Research questions")
    st.markdown("""
1. Which categories (diagnosis / admission type) are linked to long stays?
2. Which age groups incur the highest charges?
3. How does patient severity affect total cost and stay?
4. Are there counties with longer average stays?
5. How do payment types affect the final billing?
6. Which facilities have the highest utilisation?
7. How much of the billed amount is actual cost (cost-to-charge ratio)?
""")

    with st.expander("Background & sources"):
        st.markdown("""
**Dataset.** Hospital inpatient discharge records (county, facility, demographics, severity, stay,
charges and costs). The counties and facilities are New York State, in the style of the state's SPARCS
discharge data.

**Why these measures matter to administrators.**
- *Length of stay* drives bed capacity and staffing; long stays are the main lever for efficiency.
- *Charges vs. costs* differ: charges are the billed amount, costs are what the hospital spends, so the
  **cost-to-charge ratio** shows how much of a bill reflects real resource use.
- *Severity of illness* (Minor to Extreme) explains much of the variation in stay and cost, so it is
  used to compare like with like.
- *Payer mix* (Medicare, Medicaid, private) shapes revenue and billing patterns.

**Engineered fields.** `Charge per Day` = charges / stay, `Stay Category` = stay bands,
`Cost-to-Charge Ratio` = costs / charges.

**References.** Streamlit, *Improving healthcare management with Streamlit*
(blog.streamlit.io/improving-healthcare-management-with-streamlit) and the Plotly Express documentation
(plotly.com/python/plotly-express).
""")

    # Q1
    st.markdown(f"**Q1 - Stay by {group_col.lower()} and severity (pivot table)**")
    if g1 is not None and len(g1):
        pv1 = fdf.pivot_table(index=group_col, columns="Severity", values="Length of Stay",
                              aggfunc="mean", observed=True).round(1)
        pv1["Overall"] = fdf.groupby(group_col, observed=True)["Length of Stay"].mean().round(1)
        st.dataframe(pv1.sort_values("Overall", ascending=False).head(15).style.format("{:.1f}", na_rep="-"),
                     width="stretch")

    # Q2
    st.markdown("**Q2 - Charges by age group and gender**")
    age = fdf.groupby("Age Group", observed=True)["Total Charges"].agg(["mean", "sum", "count"]).reset_index()
    figa = px.bar(age, x="Age Group", y="mean", color="mean", color_continuous_scale="Blues",
                  labels={"mean": "Avg charges ($)"}, hover_data={"sum": ":,.0f", "count": ":,"})
    figa.update_layout(coloraxis_showscale=False)
    st.plotly_chart(figa, width="stretch")
    if "Gender" in fdf:
        n_unk = int((fdf["Gender"] == "Unknown").sum())
        if n_unk:
            st.caption(f"Average charges by age group and gender. The {n_unk} records with unknown gender are "
                       "excluded because they are too few to give a meaningful average.")
        known = fdf[fdf["Gender"].isin(["Female", "Male"])]
        st.dataframe(known.pivot_table(index="Age Group", columns="Gender", values="Total Charges",
                                       aggfunc="mean", observed=True).style.format("${:,.0f}", na_rep="-"),
                     width="stretch")

    # Q3
    st.markdown("**Q3 - Severity vs. stay and cost**")
    sev = fdf.groupby("Severity", observed=True).agg(
        avg_stay=("Length of Stay", "mean"), avg_charges=("Total Charges", "mean"),
        median_charges=("Total Charges", "median"), cases=("Length of Stay", "size")).round(1)
    st.dataframe(
        sev.rename(columns={"avg_stay": "Avg stay (days)", "avg_charges": "Avg charges",
                            "median_charges": "Median charges", "cases": "Discharges"})
        .style.format({"Avg stay (days)": "{:.1f}", "Avg charges": "${:,.0f}",
                       "Median charges": "${:,.0f}", "Discharges": "{:,.0f}"}),
        width="stretch")

    # Q4
    if "County" in fdf:
        st.markdown("**Q4 - Counties with the longest average stay (min. 50 cases)**")
        cty = (fdf.groupby("County")["Length of Stay"].agg(["mean", "count"])
               .query("count >= 50").sort_values("mean", ascending=False).head(10).round(2))
        st.dataframe(cty.rename(columns={"mean": "Avg stay (days)", "count": "Discharges"})
                     .style.format({"Avg stay (days)": "{:.2f}", "Discharges": "{:,.0f}"}), width="stretch")

    # Q5
    st.markdown("**Q5 - Payment type vs. billing**")
    pay_tbl = fdf.groupby("Payment Type")["Total Charges"].agg(["mean", "median", "count"]).round(0) \
        .sort_values("mean", ascending=False)
    st.dataframe(pay_tbl.rename(columns={"mean": "Avg charges", "median": "Median charges", "count": "Discharges"})
                 .style.format({"Avg charges": "${:,.0f}", "Median charges": "${:,.0f}", "Discharges": "{:,.0f}"}),
                 width="stretch")
    if "County" in fdf:
        st.markdown("Average charges by county and payment type (pivot table, top 15 counties)")
        top_c = fdf["County"].value_counts().head(15).index
        sub = fdf[fdf["County"].isin(top_c)]
        pv5 = sub.pivot_table(index="County", columns="Payment Type", values="Total Charges", aggfunc="mean")
        n5 = sub.pivot_table(index="County", columns="Payment Type", values="Total Charges", aggfunc="size")
        pv5 = (pv5.where(n5 >= 20) / 1000).round(0)  # blank out cells with <20 discharges
        fig_pc = px.imshow(pv5, aspect="auto", color_continuous_scale="Blues", text_auto=".0f",
                           labels=dict(color="Avg charges ($k)"))
        fig_pc.update_layout(plot_bgcolor="#7a7f87", height=520)
        st.plotly_chart(fig_pc, width="stretch")
        st.caption("Values in thousands of dollars. Grey cells have fewer than 20 discharges, so no average is shown.")

    # Q6
    if "Facility" in fdf:
        st.markdown("**Q6 - Top 10 high-utilisation facilities**")
        fac = fdf["Facility"].value_counts().head(10).rename("Discharges").reset_index()
        figf = px.bar(fac.sort_values("Discharges"), x="Discharges", y="Facility", orientation="h",
                      color_discrete_sequence=["#4cc9f0"])
        figf.update_layout(height=420)
        st.plotly_chart(figf, width="stretch")

    # Q7
    if "Cost-to-Charge Ratio" in fdf:
        st.markdown("**Q7 - Cost-to-charge ratio by payment type**")
        ratio = fdf.groupby("Payment Type")["Cost-to-Charge Ratio"].median().round(3) \
            .sort_values().rename("Median cost / charge").reset_index()
        st.plotly_chart(px.bar(ratio, x="Payment Type", y="Median cost / charge", text_auto=".2f",
                               color_discrete_sequence=["#e76f51"]), width="stretch")

    st.markdown("**Correlation (numeric fields)**")
    num = fdf.select_dtypes("number")
    st.plotly_chart(px.imshow(num.corr().round(2), text_auto=True, color_continuous_scale="RdBu_r",
                              zmin=-1, zmax=1), width="stretch")
    cm = num.corr()
    st.caption(f"Longer stays go with higher charges (r = {cm.loc['Length of Stay', 'Total Charges']:.2f}) and "
               f"higher costs (r = {cm.loc['Length of Stay', 'Total Costs']:.2f}); charges and costs move closely "
               f"together (r = {cm.loc['Total Charges', 'Total Costs']:.2f}).")

    # Auto-generated insights (update with the filters)
    st.subheader("Key insights (update as filters change)")
    if len(g1):
        t = g1.iloc[0]
        st.info(f"Longest average stay by {group_col.lower()}: **{t[group_col]}** at "
                f"{t['mean']:.1f} days ({int(t['count']):,} cases).")
    top_age = age.sort_values("mean", ascending=False).iloc[0]
    st.info(f"Highest average charges by age group: **{top_age['Age Group']}** at \\${top_age['mean']:,.0f}.")
    if len(sev) > 1:
        lo, hi = sev["avg_charges"].iloc[0], sev["avg_charges"].iloc[-1]
        st.info(f"Average charges rise from \\${lo:,.0f} ({sev.index[0]}) to \\${hi:,.0f} ({sev.index[-1]}) "
                f"across severity levels - about {hi / lo:.1f}x.")
    top_pay = pay_tbl.index[0]
    st.info(f"Payment type with the highest average charges: **{top_pay}** (\\${pay_tbl['mean'].iloc[0]:,.0f}).")

# ---------------------------------------------------------------------------
# 8. DATA
# ---------------------------------------------------------------------------
with tab_data:
    st.dataframe(fdf.head(1000), width="stretch")
    st.download_button("Download filtered data (CSV)", fdf.to_csv(index=False).encode(),
                       "filtered_discharges.csv", "text/csv")
