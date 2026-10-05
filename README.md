# IADAI2021000470_Ariella-Sansita_AIY2_SA

**Hospital Inpatient Discharges Dashboard**

**Live app:** https://idai2021000470ariella-sansitaaiy2sa-9w6gtexks3dpxkq44gq4ru.streamlit.app/

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

Hospital discharge data is widely used for health-system planning and cost analysis. New York's
SPARCS, the source of this dataset, is an all-payer system that has collected patient-level detail
on diagnoses, treatments, services and charges since 1979. The US federal HCUP databases are
built on similar discharge records and are used to study healthcare use, access, outcomes and costs,
which helps policymakers and hospital administrators plan services. Length of stay is a key
planning measure because shortening stays frees beds for new admissions, but commentary on a
Journal of the American College of Surgeons study notes that savings from cutting stays depend on
whether the hospital is capacity-constrained, since the final day of a stay accounts for only
about 2.4% of total costs. This is why the dashboard compares length of stay and charges across
diagnoses, severity levels, counties, facilities and payers.*

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
<img width="1468" height="729" alt="Screenshot 2026-10-05 at 3 31 48 PM" src="https://github.com/user-attachments/assets/add76546-2ecf-4159-9d15-79b9f694e7b5" />
<img width="1466" height="729" alt="Screenshot 2026-10-05 at 3 32 08 PM" src="https://github.com/user-attachments/assets/6bca8e62-26ea-4109-80f3-bf4f48ca9410" />
<img width="1393" height="619" alt="Screenshot 2026-10-05 at 3 32 35 PM" src="https://github.com/user-attachments/assets/1eca75a2-f31b-4618-8938-7fb482532a31" />

## References
1. https://healthweb-back.health.ny.gov/statistics/sparcs/
2. https://hcup-us.ahrq.gov/news/exhibit_booth/hcup_fact_sheet.jsp
3. https://reliasmedia.com/articles/68520-relevance-of-length-of-stay-reductions
