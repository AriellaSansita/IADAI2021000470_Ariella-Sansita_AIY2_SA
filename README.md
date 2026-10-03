# IADAI2021000470_Ariella-Sansita_AIY2_SA

**Hospital Inpatient Discharges Dashboard** - Artificial Intelligence, Mathematics for AI-II (Summative Assessment)

**Live app:** https://YOUR-APP-NAME.streamlit.app  <!-- paste your Streamlit Cloud link here -->

## Project overview
MediScope Health Analytics works with hospitals to improve patient care and reduce costs. This dashboard
analyses inpatient discharge records so administrators, clinicians and operations managers can see
which diagnoses, demographics and facilities drive longer stays and higher charges.

### Research questions
1. Which diagnoses are linked to long stays?
2. Which age groups incur the highest charges?
3. How does patient severity affect total cost?
4. Are there counties with longer average stays?
5. How do payment types affect the final billing?
6. Which facilities have the highest utilisation?

*(Add 2-3 sentences of external research here, with links, on how hospitals use discharge data for
planning and cost control.)*

## Key features
- Sidebar filters: county, severity, age group, gender, payment type
- KPI cards: discharges, average stay, average and total charges
- Five interactive Plotly charts: bar (stay per diagnosis), box plot (charges by severity),
  heatmap (stay by facility and county), pie chart (payment types), histogram (length of stay)
- EDA tab with groupby / pivot_table summaries and auto-generated insights
- Data tab with CSV download of the filtered data

## Data preprocessing
- Renamed columns to readable names
- Removed invalid records (stay <= 0, non-positive charges) and extreme charge outliers (> 99.5th percentile)
- Converted `Total Charges` / `Total Costs` from currency strings to float
- Standardised age group, gender, race, severity, county and payment type
- Mapped diagnosis codes to readable descriptions
- Dropped null-heavy columns (e.g. birth weight)
- Engineered `Charge per Day` and `Stay Category`

## Integration details
Python 3, pandas and NumPy (cleaning/analysis), Plotly Express (charts), Streamlit (UI), GitHub +
Streamlit Community Cloud (hosting).

## Repository structure
```
├── app.py
├── requirements.txt
├── README.md
├── data/hospital_discharges.csv
└── screenshots/
```

## Deployment instructions
1. Push `app.py`, `requirements.txt`, `README.md` and `data/` to this GitHub repo.
2. Go to https://share.streamlit.io and sign in with GitHub.
3. Click **Deploy an app**, select this repo, branch `main`, main file `app.py`.
4. Click **Deploy** and paste the live URL at the top of this README.

Run locally:
```
pip install -r requirements.txt
streamlit run app.py
```

## Screenshots
![Overview](screenshots/overview.png)
![Charts](screenshots/charts.png)
