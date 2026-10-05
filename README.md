# Candidate Name - Ariella Sansita M

# Candidate Registration Number - 1000470

# CRS Name: Artificial Intelligence

# Course Name - Machine Learning & Deep Learning

# School name - Birla Open Minds International School, Kollur

# Summative Assessment

# Hospital Inpatient Discharges Dashboard

## Project overview
MediScope Health Analytics works with hospitals to improve patient care and reduce costs. This dashboard
analyses inpatient discharge records so administrators, clinicians and operations managers can see
which diagnoses, demographics and facilities drive longer stays and higher charges.

## Research questions
1. Which categories (diagnosis / admission type) are linked to long stays?
2. Which age groups incur the highest charges?
3. How does patient severity affect total cost and stay?
4. Are there counties with longer average stays?
5. How do payment types affect the final billing?
6. Which facilities have the highest utilisation?
7. How much of the billed amount is actual cost (cost-to-charge ratio)?

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

## Key findings
- **Overall:** the average stay is 5.5 days (median 3), and the average charge is about $66,400 against an
  average cost of about $20,200.
- **Q1, long stays:** schizophrenia spectrum disorders have the longest stays among common diagnoses
  (16.6 days on average, 2,413 cases), followed by multiple myeloma (14.1 days) and sequela of cerebral
  infarction (14.0 days). By admission type, trauma (6.4 days), emergency (6.1) and urgent (6.0) admissions
  stay longest, while elective (4.4) and newborn (3.1) stays are shorter.
- **Q2, age:** average charges rise from about $35,000 for ages 0 to 17 to about $82,400 for ages 70 and
  over.
- **Q3, severity:** average stay grows from 2.9 days (Minor) to 12.8 days (Extreme), and average charges
  from about $36,600 to about $161,900, roughly 4.4 times higher.
- **Q4, counties:** Columbia County has the longest average stay (8.2 days, 235 cases), ahead of Niagara and
  Clinton (6.6 days each).
- **Q5, payers:** Miscellaneous/Other (about $88,800) and Medicare (about $81,700) have the highest average
  charges; Federal/State/Local/VA has the lowest (about $41,300).
- **Q6, facilities:** North Shore University Hospital (3,233 discharges in the sample), Mount Sinai Hospital
  (3,043) and Strong Memorial Hospital (2,628) are the busiest.
- **Q7, cost-to-charge:** the median cost is about 27% to 37% of the amount billed, depending on payer.
- **Correlation:** length of stay and total charges are positively correlated (r = 0.65). This shows an
  association, not that longer stays cause higher charges.

These figures come from a sample, so rarer diagnoses and small counties should be read with caution; the
dashboard's minimum-cases setting helps filter out very small groups.

## Repository structure
```
├── app.py
├── requirements.txt
├── README.md
├── data/hospital_discharges_final.csv
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
**Live app:** https://idai2021000470ariella-sansitaaiy2sa-9w6gtexks3dpxkq44gq4ru.streamlit.app/

## Screenshots
<img width="1470" height="736" alt="Screenshot 2026-10-05 at 3 45 09 PM" src="https://github.com/user-attachments/assets/8d77ba43-9131-4a7e-a6f1-ae980d081b56" />
<img width="1470" height="782" alt="Screenshot 2026-10-05 at 3 45 30 PM" src="https://github.com/user-attachments/assets/6c9ec1ef-8eaa-4090-ac22-0ad99beed537" />
<img width="1392" height="632" alt="Screenshot 2026-10-05 at 3 45 47 PM" src="https://github.com/user-attachments/assets/c521574c-14ab-4d93-bf06-2970b6d60f2e" />


## References
1. https://healthweb-back.health.ny.gov/statistics/sparcs/
2. https://hcup-us.ahrq.gov/news/exhibit_booth/hcup_fact_sheet.jsp
3. https://reliasmedia.com/articles/68520-relevance-of-length-of-stay-reductions
