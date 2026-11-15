# Ola Ride Insights — Power BI Dashboard: Step-by-Step Build Guide

**Deliverable:** a 5-page interactive dashboard (`Ola_Ride_Insights.pbix`) answering the 10 Power BI questions, with KPIs, slicers, drill-through and tooltips.
**Companion files:** `01_power_query.m` · `02_dax_measures.dax` · `03_ola_theme.json` (paste-ready).
**Data:** `ola_rides_clean.csv` (103,024 bookings, 1–31 Jul 2024) or the MySQL table `ola_ride_insights.ola_rides` built earlier.

---
## Step 1 — Load the data
1. Power BI Desktop → **Home → Transform data** (opens Power Query).
2. **New Source → Blank Query → Advanced Editor**, paste `01_power_query.m`, name the query **`Fact_Rides`**.
3. Choose the source: **A (CSV)** works out of the box (edit the path); **B (MySQL)** needs the MySQL connector — uncomment the B lines and delete the A lines. Using MySQL makes your SQL work and dashboard one connected pipeline (good for the recruiter story).
4. **Close & Apply.**

What the script does (cleaning + feature engineering): sets data types, trims text, labels missing `Payment_Method` as *Not Applicable*, keeps missing ratings/distances as true nulls (so averages aren't diluted), adds `Booking_Date`, `Distance_Band`, `Driver_Rating_Band`, `Customer_Rating_Band`, and drops duplicate `Booking_ID`s.

## Step 2 — Data model (star schema)
1. **Modeling → New table** → paste `Dim_Date` and `Dim_Vehicle` from `02_dax_measures.dax`.
2. **Model view** → create relationships (many-to-one, single direction):
   - `Dim_Date[Date]` → `Fact_Rides[Booking_Date]`
   - `Dim_Vehicle[Vehicle_Type]` → `Fact_Rides[Vehicle_Type]`
3. Select `Dim_Date` → **Table tools → Mark as date table** → `Date`.
4. **Sort by column:** `Dim_Date[Weekday]` by `Weekday No`.
5. Create an empty table `_Measures = ROW("x",1)`, then paste every measure from the `.dax` file into it. Hide the `x` column; set formats (Revenue → `₹ #,0`; rates → `0.0%`; ratings → `0.00`).
6. Hide the raw numeric columns you don't want in field lists (`V_TAT`, `C_TAT`, flags).

## Step 3 — Canvas setup
- **View → Themes → Browse for themes →** `03_ola_theme.json`.
- **Page size:** 16:9 (1280×720). Page background `#F3F4F6`.
- **Header strip (all pages):** black rectangle 1280×56, title text in white, page navigator on the right.
- **Navigator:** *Insert → Buttons → Navigator → Page navigator* → place once, then copy to every page. Pages: **Overall · Vehicle Type · Revenue · Cancellation · Ratings**.
- **Left rail (160 px):** the slicers below, synced across pages (*View → Sync slicers*).

### Global slicers (sync on all pages)
| Slicer | Field | Style |
|---|---|---|
| Date | `Dim_Date[Date]` | Between (slider) |
| Vehicle Type | `Dim_Vehicle[Vehicle_Type]` | Dropdown, multi-select |
| Day Type | `Dim_Date[Day Type]` | Tile buttons |
| Day Part | `Fact_Rides[Day_Part]` | Dropdown |
| Payment Method | `Fact_Rides[Payment_Method]` | Dropdown (Revenue page only) |

Add a **"Clear all slicers" bookmark button** (*View → Bookmarks → Add*, with Data off, then link a button).

---
## Step 4 — Build the five pages

> Format tips for every visual: Title on (use sentence-style insight titles), data labels on, gridlines light, no borders. KPI cards use *callout value* 28 pt.

### Page 1 · OVERALL  *(Q1 Ride Volume Over Time · Q2 Booking Status Breakdown)*
| # | Visual | Fields | Notes |
|---|---|---|---|
| KPI×5 | Card | `Total Bookings`, `Successful Rides`, `Success Rate %`, `Total Revenue`, `Avg Booking Value` | Use **New card** with reference label; Success Rate % gets conditional font colour (red < 60 %, green ≥ 62 %) |
| **Q1** | Line + clustered column | X `Dim_Date[Date]` · columns `Total Bookings` · line `Bookings 7D Avg` | Turn on **drill down** (Date → Hour via `Hour_Of_Day` hierarchy if you add it). Tooltip: `Bookings vs Prev Day %`, `Success Rate %` |
| **Q2** | Donut | Legend `Booking_Status` · Values `Total Bookings` | Detail labels: category + %. Sort by value |
| Extra | Column | X `Hour_Of_Day` · Y `Total Bookings` | Peak-hour view |

**Expected values (validate):** 103,024 bookings · 63,967 successful (**62.1 %**) · Canceled by Driver 17.9 % · Canceled by Customer 10.2 % · Driver Not Found 9.8 % · Revenue ₹35,080,467.

### Page 2 · VEHICLE TYPE  *(Q3 Top 5 Vehicle Types by Ride Distance · Q4 Avg Customer Rating by Vehicle Type)*
| # | Visual | Fields | Notes |
|---|---|---|---|
| **Q3** | Clustered bar | Y `Vehicle_Type` · X `Total Distance (km)` | **Filter pane → Top N → Top 5 by `Total Distance (km)`**; data labels on |
| **Q4** | Clustered column | X `Vehicle_Type` · Y `Avg Customer Rating` | **Set Y axis min 3.5, max 4.5** — otherwise every bar looks identical (they're all ≈ 4.00); add average line |
| Table | Matrix | Rows `Vehicle_Type` · values `Total Bookings`, `Success Rate %`, `Total Revenue`, `Avg Distance (km)`, `Revenue per Km`, `Avg Driver Rating` | Data bars on revenue; colour scale on Success Rate % |

**Expected:** Top 5 distance → Prime Sedan **234,535** · E-Bike **230,842** · Bike **227,746** · Prime Plus **227,186** · Mini **225,703** (km). Ratings 3.99–4.01 for all vehicle types. Auto averages only 10.0 km vs ≈ 25 km for others → highest Revenue per Km (≈ ₹54.9).

### Page 3 · REVENUE  *(Revenue by Payment Method · Top 5 Customers by Total Booking Value · Ride Distance Distribution Per Day)*
| # | Visual | Fields | Notes |
|---|---|---|---|
| KPI×3 | Card | `Total Revenue`, `Revenue Lost`, `Revenue per Km` | |
| **Q6** | Donut (or bar) | Legend `Payment_Method` · Values `Total Revenue` | Visual-level filter `Payment_Method` ≠ *Not Applicable*; labels show value + % |
| **Q7** | Bar | Y `Customer_ID` · X `Total Revenue` | **Top N → Top 5 by `Total Revenue`**; add Tooltip: `Successful Rides` |
| **Q8** | 100 % stacked column + line | X `Dim_Date[Date]` · Y `Total Bookings` · Legend `Distance_Band` (sort by band) · line `Avg Distance (km)` | Distance band 0 filtered out via visual filter `Distance_Band` ≠ "0 (no ride)". Shows the distance mix of each day |
| Extra | Area | X `Dim_Date[Date]` · Y `Cumulative Revenue` | |

**Expected:** Cash ₹19,260,316 (54.9 %) · UPI ₹14,168,436 (40.4 %) · Credit Card ₹1,312,793 (3.7 %) · Debit Card ₹338,922 (1.0 %). Top 5 customers (successful rides): **CID836942 ₹6,019 · CID868113 ₹5,986 · CID695232 ₹5,962 · CID176493 ₹5,944 · CID902403 ₹5,938**. Daily completed-ride distance ranges 43,023 km to 50,677 km (peak 30 Jul); avg ride ≈ 22.9 km.

> **Definition note (Q7):** this ranks by *completed-ride* revenue (consistent with `Total Revenue`). If your rubric ranks by booking value across all bookings, change the visual's X to `Sum of Booking_Value` — the leader then becomes CID785112 (₹8,025). State your definition on the page footnote.

### Page 4 · CANCELLATION  *(Customer reasons · Driver reasons)*
| # | Visual | Fields | Notes |
|---|---|---|---|
| KPI×4 | Card | `Total Cancelled`, `Cancellation Rate %`, `Cancelled by Customer`, `Cancelled by Driver` | |
| **Q5a** | Bar | Y `Canceled_Rides_by_Customer` · X `Total Bookings` | Visual filter: `Canceled_Rides_by_Customer` is not blank |
| **Q5b** | Bar | Y `Canceled_Rides_by_Driver` · X `Total Bookings` | Visual filter: is not blank |
| Extra | Stacked column | X `Day_Part` · Y `Total Bookings` · Legend `Booking_Status` | When do failures happen |
| Extra | Treemap | Group `Booking_Status` · Values `Revenue Lost` | Business cost of failures |

**Expected — Customer reasons:** Driver not moving towards pickup **3,175** · Driver asked to cancel **2,670** · Change of plans **2,081** · AC not working **1,568** · Wrong address **1,005** (total 10,499).
**Driver reasons:** Personal & car issue **6,542** · Customer-related issue **5,413** · Customer coughing/sick **3,654** · More than permitted people **2,825** (total 18,434).
**Revenue lost:** ₹21.45 M (driver cancel ₹10.18 M · customer cancel ₹5.77 M · driver not found ₹5.50 M).

### Page 5 · RATINGS  *(Q9 Driver Ratings Distribution · Q10 Customer vs Driver Ratings)*
| # | Visual | Fields | Notes |
|---|---|---|---|
| KPI×3 | Card | `Avg Driver Rating`, `Avg Customer Rating`, `Rated Rides` | |
| **Q9** | Column (histogram) | X `Driver_Rating_Band` (as **text** category) · Y `Total Bookings` | Visual filter: band is not blank. Companion: same for `Customer_Rating_Band` |
| **Q10a** | Scatter | X `Avg Driver Rating` · Y `Avg Customer Rating` · Details `Dim_Date[Date]` + `Vehicle_Type` · Size `Successful Rides` | ~217 points; set both axes 3.5–4.5; add *Trend line* |
| **Q10b** | Matrix heat-map | Rows `Driver_Rating_Band` · Columns `Customer_Rating_Band` · Values `Total Bookings` | Conditional background colour scale |
| Extra | Clustered column | X `Vehicle_Type` · Y `Avg Driver Rating`, `Avg Customer Rating` | Axis 3.5–4.5 |

**Expected:** Avg driver rating **4.00**, avg customer rating **4.00**; driver ratings span 3.0–5.0 (rounded to whole stars: 14,373 rides at 3 · 35,367 at 4 · 14,227 at 5). Correlation between customer and driver ratings ≈ **0.00** — the trend line is flat.

---
## Step 5 — Interactivity checklist
- **Cross-filtering:** click a donut slice / bar → every visual on the page filters. Use *Format → Edit interactions* to stop KPI cards from filtering other visuals if you prefer.
- **Drill-through:** create a hidden page **"Vehicle Detail"** (matrix of routes: `Pickup_Location` → `Drop_Location`, `Total Bookings`, `Total Revenue`); drop `Vehicle_Type` in *Drill-through* so right-click → Drill through works from Page 2.
- **Tooltip pages:** *Page size → Tooltip*; add `Total Bookings`, `Success Rate %`, `Avg Booking Value`; assign to Q1 and Q3 visuals.
- **Bookmarks:** "Weekday view" and "Weekend view" buttons that toggle the `Day Type` slicer.
- **Dynamic titles:** bind Q1's title to `Title - Bookings` (*Title → fx → Field value*), and an insight text box to `Insight - Top Cancel Reason`.
- **Performance Analyzer** (*View → Performance analyzer*): every visual should render < 1 s — remove unused columns before loading if not.
- **Accessibility:** alt text on every visual, tab order set, theme contrast ≥ 4.5:1.

## Step 6 — Validate before publishing
Compare each visual with the SQL results from `ola_ride_insights_mysql.sql`:

| Check | Power BI | SQL |
|---|---|---|
| Bookings / successful | 103,024 / 63,967 | V1 / Q1 |
| Revenue (completed) | ₹35,080,467 | Q9 |
| Cancelled by customer | 10,499 | Q3 |
| Driver cancel – personal & car | 6,542 | Q5 |
| UPI rides / revenue | 25,881 / ₹14,168,436 | Q7 / B6 |
| Incomplete rides | 3,926 | Q10 |
| Avg rating per vehicle | 3.99–4.01 | Q8 |

## Step 7 — Publish & hand off
1. **File → Save** as `Ola_Ride_Insights.pbix`; **Home → Publish** to a workspace.
2. **Streamlit embed (project guideline):** in Power BI Service use **File → Embed report → Publish to web** (public data only) or the org embed link, then `st.components.v1.iframe(url, height=720)` in your Streamlit app next to the SQL results tables.
3. **Git:** commit `.pbix`, `.sql`, `.m`, `.dax`, theme and a README with 3–4 dashboard screenshots; add a one-page "Insights" section (below) to the repo README.

---
## Business insights & recommendations (use on your final slide)
1. **Only 62 % of bookings complete.** The 38 % that fail represent **₹21.45 M** of booking value — the single biggest lever.
2. **Drivers cancel 1.75× more than customers** (18.4 K vs 10.5 K). Personal/car issues (6.5 K) and "customer-related issue" (5.4 K) lead → introduce vehicle-readiness checks, driver availability scheduling and a clearer rider-conduct prompt.
3. **Customer-side cancellations are mostly caused by supply behaviour** (driver not approaching pickup, driver asking to cancel = 56 %) → add live-ETA nudges and penalise driver-initiated cancel requests.
4. **Incomplete rides (3,926)** split ~41 % customer demand / ~41 % vehicle breakdown / ~19 % other → preventive maintenance would remove a large share.
5. **Auto is the most revenue-efficient vehicle (≈ ₹55/km vs ≈ ₹22/km)** on short trips → prioritise Auto supply in dense short-hop zones.
6. **Cash (55 %) + UPI (40 %) = 95 % of revenue** → UPI-first incentives reduce cash handling and reconciliation cost.
7. **Ratings are uniform (≈ 4.0) and uncorrelated between riders and drivers** → the rating system gives little signal; consider tagged feedback (cleanliness, punctuality) to make it actionable.
