# 🚖 Ola Ride Insights: SQL → Power BI → Streamlit

Interactive analytics app for 103,024 Ola bookings (July 2024): booking trends, vehicle performance, revenue, cancellations and ratings.

## Features
- 9 tabs: Overview, Vehicle Types, Revenue, Cancellations, Ratings, **SQL Explorer**, **Booking Search**, **Power BI**, **Insights**
- Sidebar filters: date, vehicle, status, payment, day part, pickup location
- SQL Explorer: 17 curated queries (10 required + 7 bonus, with business takeaways) and a read-only custom SQL editor
- Power BI embed (live iframe) with screenshot fallback
- CSV downloads, auto-generated insights and recommendations

## Project structure
```
app.py                       Streamlit app
data/ola_rides.db            Cleaned SQLite database (table: ola_rides)
sql/ola_ride_insights_mysql.sql   MySQL scripts (setup, clean, 10 questions, bonus)
powerbi/OLA_RIDE_INSIGHTS.pbix    Power BI report
assets/                      Dashboard screenshots
requirements.txt
```

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy (Streamlit Community Cloud)
1. Push this folder to a GitHub repo (`git init && git add . && git commit -m "Ola Ride Insights" && git push`).
2. share.streamlit.io → **New app** → select repo, branch `main`, main file `app.py` → Deploy.
3. Power BI live embed: Power BI Service → open the report → **File → Embed report → Publish to web (public)** → copy the link.
   In the app's **Settings → Secrets** add:
   ```toml
   POWERBI_EMBED_URL = "https://app.powerbi.com/view?r=..."
   ```
   (Publish to web makes the report public. Use only non-sensitive data.)

## Key results
| KPI | Value |
|---|---|
| Total bookings | 103,024 |
| Successful rides | 63,967 (62.1%) |
| Cancellation rate | 37.91% |
| Successful revenue | ₹3.51 Cr |
| Unique customers | 94,544 |
| Avg customer / driver rating | 4.00 / 4.00 |

## Business takeaways
- Driver cancellations are the largest failure source (18.4K vs 10.5K customer); "Personal & Car related issue" is the top reason.
- Success rate is nearly identical across vehicle types (61–63%), so the problem is systemic.
- Cash is ~55% of realised revenue; UPI ~40%.
- ₹2.15 Cr of booking value never converts to revenue.

Built by P Suman Sangeet · Data Analytics Capstone
