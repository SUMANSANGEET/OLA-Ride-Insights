"""
Ola Ride Insights - Streamlit Analytics App
===========================================
Ride-sharing & mobility analytics for July 2024 (103,024 bookings, Bengaluru).

Pipeline : Raw CSV -> cleaned SQLite/MySQL table -> SQL insights -> Power BI -> this app.
Run      : streamlit run app.py
"""

from __future__ import annotations

import base64
import os
import re
import sqlite3
import time
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
BASE = Path(__file__).parent
DB_PATH = BASE / "data" / "ola_rides.db"
ASSETS = BASE / "assets"

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAY_PARTS = ["Night (0-5)", "Morning (6-11)", "Afternoon (12-16)", "Evening (17-21)", "Late Night (22-23)"]
STATUS_COLORS = {
    "Success": "#2ECC71",
    "Canceled by Customer": "#FF6B35",
    "Canceled by Driver": "#E84393",
    "Driver Not Found": "#F4A300",
}
PALETTE = ["#0096C7", "#FF6B35", "#2ECC71", "#E84393", "#F4A300", "#7B61FF", "#00B4D8"]

LOGO_PATH = ASSETS / "OLA.jpeg"


@st.cache_resource(show_spinner=False)
def logo_data_uri() -> str:
    """Logo embedded as a base64 data URI (empty string if the file is missing)."""
    try:
        return "data:image/jpeg;base64," + base64.b64encode(LOGO_PATH.read_bytes()).decode()
    except OSError:
        return ""


def _page_icon():
    try:
        from PIL import Image
        return Image.open(LOGO_PATH)
    except Exception:
        return "🚖"


st.set_page_config(
    page_title="Ola Ride Insights | Analytics Dashboard",
    page_icon=_page_icon(),
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1400px;}
    .hero {background: linear-gradient(120deg,#0B1B33 0%,#12315B 55%,#0096C7 100%);
           padding: 1.4rem 1.8rem; border-radius: 14px; color: #fff; margin-bottom: 1rem;}
    .hero h1 {margin: 0; font-size: 1.9rem; color: #fff;}
    .hero p {margin: .25rem 0 0 0; color: #CFE8F5; font-size: .95rem;}
    .hero-row {display:flex; align-items:center; justify-content:space-between; gap:1.5rem; flex-wrap:wrap;}
    .brand {display:flex; align-items:center; gap:.6rem; margin-bottom:.35rem;}
    .brand .dot {width:14px; height:14px; border-radius:50%; border:4px solid #CDEB2D; display:inline-block;}
    .brand .tag {background:rgba(205,235,45,.18); color:#E6F78A; border:1px solid rgba(205,235,45,.45);
           padding:.1rem .6rem; border-radius:999px; font-size:.72rem; letter-spacing:.06em; text-transform:uppercase;}
    .chips {display:flex; gap:.6rem; flex-wrap:wrap; margin-top:.8rem;}
    .chip {background:rgba(255,255,255,.10); border:1px solid rgba(255,255,255,.22); border-radius:10px;
           padding:.35rem .8rem; color:#fff; font-size:.85rem; transition:all .2s ease; cursor:default;}
    .chip b {color:#CDEB2D; font-size:1.05rem; margin-right:.3rem;}
    .chip:hover {background:rgba(205,235,45,.22); transform:translateY(-2px);}
    .logo-link {display:block; line-height:0;}
    .logo-img {width:250px; max-width:100%; border-radius:14px; border:2px solid rgba(255,255,255,.25);
           box-shadow:0 6px 22px rgba(0,0,0,.35); transition:transform .3s ease, box-shadow .3s ease;}
    .logo-img:hover {transform:scale(1.05) rotate(-1deg); box-shadow:0 10px 30px rgba(205,235,45,.45);}
    .side-logo {width:100%; border-radius:12px; margin-bottom:.6rem; transition:transform .25s ease, box-shadow .25s ease;}
    .side-logo:hover {transform:scale(1.03); box-shadow:0 6px 18px rgba(15,23,42,.25);}
    div[data-testid="stMetric"] {background:#F8FAFC; border:1px solid #E2E8F0; border-radius:12px;
           padding: .8rem 1rem; box-shadow: 0 1px 2px rgba(15,23,42,.05);}
    div[data-testid="stMetricLabel"] {color:#475569;}
    .insight {background:#F0F9FF; border-left:4px solid #0096C7; padding:.7rem 1rem;
              border-radius:8px; margin:.45rem 0; color:#0F172A;}
    .reco {background:#F0FDF4; border-left:4px solid #2ECC71; padding:.7rem 1rem;
           border-radius:8px; margin:.45rem 0; color:#0F172A;}
    .footer {text-align:center; color:#64748B; font-size:.8rem; margin-top:2rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------- #
# Data access (SQL-first: everything is read from the SQLite database)
# --------------------------------------------------------------------------- #
@st.cache_resource(show_spinner=False)
def get_connection() -> sqlite3.Connection:
    """Read-only connection so user-supplied SQL can never modify the data."""
    return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, check_same_thread=False)


@st.cache_data(show_spinner=False)
def run_sql(query: str) -> pd.DataFrame:
    return pd.read_sql_query(query, get_connection())


@st.cache_resource(show_spinner="Loading bookings from SQL...")
def load_data() -> pd.DataFrame:
    # cache_resource keeps ONE shared DataFrame in memory (no pickle copy per rerun),
    # which fixes the MemoryError raised by cache_data's pickle.loads. Do not mutate it.
    df = pd.read_sql_query("SELECT * FROM ola_rides", get_connection())
    df["Date"] = pd.to_datetime(df["Date"])
    df["Hour"] = df["Hour"].astype(int)
    df["Revenue"] = df["Booking_Value"].where(df["Is_Success"] == 1, 0)
    df["Route"] = df["Pickup_Location"] + " → " + df["Drop_Location"]
    return df


# --------------------------------------------------------------------------- #
# SQL library: required questions (Q) + bonus business queries (B)
# --------------------------------------------------------------------------- #
SQL_LIBRARY: dict[str, dict[str, str]] = {
    "Q1 · All successful bookings": {
        "sql": "SELECT *\nFROM ola_rides\nWHERE Booking_Status = 'Success'\nORDER BY Date, Time;",
        "why": "System of record for completed rides; base population for revenue and rating analysis.",
    },
    "Q2 · Average ride distance by vehicle type": {
        "sql": """SELECT Vehicle_Type,
       COUNT(*)                     AS successful_rides,
       ROUND(AVG(Ride_Distance), 2) AS avg_distance_km
FROM ola_rides
WHERE Booking_Status = 'Success'
GROUP BY Vehicle_Type
ORDER BY avg_distance_km DESC;""",
        "why": "Autos serve short hops (~10 km); every other category averages ~25 km.",
    },
    "Q3 · Rides cancelled by customers": {
        "sql": "SELECT COUNT(*) AS cancelled_by_customer\nFROM ola_rides\nWHERE Booking_Status = 'Canceled by Customer';",
        "why": "Customer-side leakage of demand.",
    },
    "Q4 · Top 5 customers by number of rides": {
        "sql": """SELECT Customer_ID, COUNT(*) AS total_rides
FROM ola_rides
GROUP BY Customer_ID
ORDER BY total_rides DESC, Customer_ID
LIMIT 5;""",
        "why": "Customer base is very diffuse (≈95K unique customers); heavy repeat users are rare.",
    },
    "Q5 · Driver cancellations: personal & car issues": {
        "sql": "SELECT COUNT(*) AS driver_cancel_personal_car_issue\nFROM ola_rides\nWHERE Canceled_Rides_by_Driver = 'Personal & Car related issue';",
        "why": "The single largest driver-side cancellation reason, which makes it a fleet-quality and driver-support lever.",
    },
    "Q6 · Max / min driver rating for Prime Sedan": {
        "sql": "SELECT MAX(Driver_Ratings) AS max_driver_rating,\n       MIN(Driver_Ratings) AS min_driver_rating\nFROM ola_rides\nWHERE Vehicle_Type = 'Prime Sedan';",
        "why": "Rating range for the highest-success-rate category.",
    },
    "Q7 · Rides paid via UPI": {
        "sql": """SELECT Booking_ID, Customer_ID, Vehicle_Type, Pickup_Location, Drop_Location,
       Booking_Value, Payment_Method, Ride_Distance, Date, Time
FROM ola_rides
WHERE Payment_Method = 'UPI'
ORDER BY Date, Time;""",
        "why": "UPI is the main digital payment channel.",
    },
    "Q8 · Average customer rating by vehicle type": {
        "sql": """SELECT Vehicle_Type,
       COUNT(Customer_Rating)         AS rated_rides,
       ROUND(AVG(Customer_Rating), 2) AS avg_customer_rating
FROM ola_rides
GROUP BY Vehicle_Type
ORDER BY avg_customer_rating DESC, Vehicle_Type;""",
        "why": "Satisfaction is uniform (~4.0) across vehicle types, so differentiation must come from reliability, not quality.",
    },
    "Q9 · Total booking value of successful rides": {
        "sql": "SELECT COUNT(*) AS successful_rides,\n       SUM(Booking_Value) AS total_booking_value\nFROM ola_rides\nWHERE Booking_Status = 'Success';",
        "why": "Realised revenue; reconciles with the Power BI 'Successful Revenue' card.",
    },
    "Q10 · Incomplete rides with reasons": {
        "sql": """SELECT Incomplete_Rides_Reason AS reason,
       COUNT(*) AS incomplete_rides,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct_of_incomplete
FROM ola_rides
WHERE Incomplete_Rides = 'Yes'
GROUP BY Incomplete_Rides_Reason
ORDER BY incomplete_rides DESC;""",
        "why": "Roughly 4 in 5 incomplete rides are caused by customer demand or vehicle breakdown.",
    },
    "B1 · Daily trend: volume, outcomes, revenue": {
        "sql": """SELECT Date,
       COUNT(*)                                                    AS bookings,
       SUM(Is_Success)                                             AS successful,
       ROUND(100.0 * SUM(Is_Success) / COUNT(*), 2)                AS success_rate_pct,
       SUM(CASE WHEN Is_Success = 1 THEN Booking_Value ELSE 0 END) AS revenue
FROM ola_rides
GROUP BY Date
ORDER BY Date;""",
        "why": "Demand is flat day to day, so growth has to come from conversion, not seasonality.",
    },
    "B2 · Hourly demand and success rate": {
        "sql": """SELECT CAST(Hour AS INTEGER) AS Hour,
       COUNT(*)                                     AS bookings,
       ROUND(100.0 * SUM(Is_Success) / COUNT(*), 2) AS success_rate_pct
FROM ola_rides
GROUP BY Hour
ORDER BY Hour;""",
        "why": "Finds the hours where supply fails to meet demand.",
    },
    "B3 · Cancellation reasons with share": {
        "sql": """SELECT Cancel_By, Cancel_Reason, COUNT(*) AS cancellations,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_of_cancellations
FROM ola_rides
WHERE Cancel_By IS NOT NULL
GROUP BY Cancel_By, Cancel_Reason
ORDER BY cancellations DESC;""",
        "why": "Prioritises which operational fix removes the most cancellations.",
    },
    "B4 · Vehicle scorecard (CTE + RANK window)": {
        "sql": """WITH v AS (
  SELECT Vehicle_Type,
         COUNT(*)                                                    AS bookings,
         SUM(Is_Success)                                             AS successful,
         SUM(CASE WHEN Is_Success = 1 THEN Booking_Value ELSE 0 END) AS revenue,
         AVG(CASE WHEN Is_Success = 1 THEN Ride_Distance END)        AS avg_km
  FROM ola_rides
  GROUP BY Vehicle_Type
)
SELECT Vehicle_Type, bookings, successful,
       ROUND(100.0 * successful / bookings, 2) AS success_rate_pct,
       revenue,
       ROUND(avg_km, 2) AS avg_km,
       RANK() OVER (ORDER BY revenue DESC) AS revenue_rank
FROM v
ORDER BY revenue_rank;""",
        "why": "One ranked view for fleet-mix decisions.",
    },
    "B5 · Revenue by payment method": {
        "sql": """SELECT Payment_Method,
       COUNT(*)           AS rides,
       SUM(Booking_Value) AS revenue,
       ROUND(100.0 * SUM(Booking_Value) / SUM(SUM(Booking_Value)) OVER (), 2) AS share_pct
FROM ola_rides
WHERE Booking_Status = 'Success'
GROUP BY Payment_Method
ORDER BY revenue DESC;""",
        "why": "Cash still dominates, so there is headroom to push digital payments.",
    },
    "B6 · Top 10 busiest routes (successful rides)": {
        "sql": """SELECT Pickup_Location, Drop_Location, COUNT(*) AS rides,
       SUM(Booking_Value) AS revenue
FROM ola_rides
WHERE Booking_Status = 'Success'
GROUP BY Pickup_Location, Drop_Location
ORDER BY rides DESC
LIMIT 10;""",
        "why": "Guides driver positioning and surge planning.",
    },
    "B7 · Revenue lost to cancellations": {
        "sql": """SELECT Booking_Status,
       COUNT(*)           AS bookings,
       SUM(Booking_Value) AS booking_value
FROM ola_rides
GROUP BY Booking_Status
ORDER BY booking_value DESC;""",
        "why": "Quantifies the value of bookings that never converted.",
    },
}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def inr(x: float) -> str:
    """Format rupees in Indian units (Cr / L)."""
    if x >= 1e7:
        return f"₹{x / 1e7:,.2f} Cr"
    if x >= 1e5:
        return f"₹{x / 1e5:,.2f} L"
    return f"₹{x:,.0f}"


def style(fig: go.Figure, height: int = 380, legend: bool = True) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=50, b=10),
        template="plotly_white",
        colorway=PALETTE,
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, x=0),
        title=dict(font=dict(size=15)),
    )
    return fig


def show(fig: go.Figure, key: str) -> None:
    st.plotly_chart(fig, width="stretch", key=key)


def pct(a: float, b: float) -> float:
    return 100 * a / b if b else 0.0


def kpis(d: pd.DataFrame) -> dict:
    total = len(d)
    succ = int(d["Is_Success"].sum())
    return {
        "total": total,
        "succ": succ,
        "succ_rate": pct(succ, total),
        "cancel_rate": 100 - pct(succ, total),
        "revenue": float(d["Revenue"].sum()),
        "customers": d["Customer_ID"].nunique(),
    }


def csv_button(df: pd.DataFrame, name: str, key: str) -> None:
    st.download_button("⬇️ Download CSV", df.to_csv(index=False).encode(), f"{name}.csv", "text/csv", key=key)


# --------------------------------------------------------------------------- #
# SQL playground helpers
# --------------------------------------------------------------------------- #
PG_DEFAULT_SQL = (
    "SELECT Vehicle_Type,\n"
    "       COUNT(*)                                     AS bookings,\n"
    "       ROUND(100.0 * SUM(Is_Success) / COUNT(*), 2) AS success_rate_pct\n"
    "FROM ola_rides\n"
    "GROUP BY Vehicle_Type\n"
    "ORDER BY bookings DESC;"
)
PG_TIMEOUT_S = 10.0


def validate_sql(q: str) -> str | None:
    """Return an error message if the query is not a single read-only SELECT / WITH."""
    q = q.strip().rstrip(";").strip()
    if not q:
        return "Write a query first."
    if not re.match(r"^(select|with)\b", q, re.I):
        return "Only SELECT / WITH queries are allowed."
    if ";" in q:
        return "Only a single statement is allowed (remove extra semicolons)."
    return None


def run_playground_query(q: str, limit: int, explain: bool = False) -> tuple[pd.DataFrame, float, bool]:
    """Run a validated query on its own read-only connection with a row cap and a time limit."""
    q = q.strip().rstrip(";").strip()
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    t0 = time.perf_counter()
    conn.set_progress_handler(lambda: 1 if time.perf_counter() - t0 > PG_TIMEOUT_S else 0, 50_000)
    try:
        if explain:
            res = pd.read_sql_query(f"EXPLAIN QUERY PLAN {q}", conn)
            truncated = False
        else:
            res = pd.read_sql_query(f"SELECT * FROM ({q}) LIMIT {int(limit) + 1}", conn)
            truncated = len(res) > limit
            res = res.head(limit)
    finally:
        conn.set_progress_handler(None, 0)
        conn.close()
    return res, (time.perf_counter() - t0) * 1000, truncated


@st.cache_data(show_spinner=False, ttl=3600)
def schema_info() -> tuple[pd.DataFrame, int]:
    conn = get_connection()
    info = pd.read_sql_query("PRAGMA table_info(ola_rides)", conn)[["name", "type", "pk"]]
    info.columns = ["Column", "SQL type", "Primary key"]
    n = int(pd.read_sql_query("SELECT COUNT(*) AS n FROM ola_rides", conn)["n"].iloc[0])
    return info, n


@st.cache_data(show_spinner=False, max_entries=64)
def analysis_query(q: str, limit: int = 500) -> pd.DataFrame:
    """Small, row-capped results only (keeps the cache light)."""
    q = q.strip().rstrip(";").strip()
    return pd.read_sql_query(f"SELECT * FROM ({q}) LIMIT {int(limit)}", get_connection())


def _load_pg_sql(sql: str) -> None:
    st.session_state["pg_sql"] = sql


def _load_template() -> None:
    name = st.session_state.get("pg_template")
    if name in SQL_LIBRARY:
        st.session_state["pg_sql"] = SQL_LIBRARY[name]["sql"]


def auto_chart(res: pd.DataFrame, key: str) -> None:
    """One-click chart builder for any query result."""
    num = [c for c in res.columns if pd.api.types.is_numeric_dtype(res[c])]
    if res.empty or not num or len(res.columns) < 2:
        st.info("Charts need at least one numeric column and two columns in total.")
        return
    cat = [c for c in res.columns if c not in num] or list(res.columns)
    c1, c2, c3, c4 = st.columns(4)
    kind = c1.selectbox("Chart", ["Bar", "Line", "Scatter", "Pie"], key=f"{key}_kind")
    x = c2.selectbox("X axis", list(res.columns), index=list(res.columns).index(cat[0]), key=f"{key}_x")
    y_opts = [c for c in num if c != x] or num
    y = c3.selectbox("Y axis", y_opts, key=f"{key}_y")
    color = c4.selectbox("Colour by", ["(none)"] + [c for c in cat if c != x], key=f"{key}_c")
    color = None if color == "(none)" else color
    data = res.head(200)
    if kind == "Bar":
        fig = px.bar(data, x=x, y=y, color=color, color_discrete_sequence=PALETTE)
    elif kind == "Line":
        fig = px.line(data, x=x, y=y, color=color, markers=True, color_discrete_sequence=PALETTE)
    elif kind == "Scatter":
        fig = px.scatter(data, x=x, y=y, color=color, color_discrete_sequence=PALETTE)
    else:
        fig = px.pie(data, names=x, values=y, hole=0.45, color_discrete_sequence=PALETTE)
    show(style(fig, legend=bool(color) or kind == "Pie"), f"{key}_fig")


# SQL Analysis: chart recipe for each curated query (kind, x, y, colour)
ANALYSIS_CHARTS: dict[str, dict] = {
    "Q2 · Average ride distance by vehicle type": dict(kind="bar", x="Vehicle_Type", y="avg_distance_km"),
    "Q8 · Average customer rating by vehicle type": dict(kind="bar", x="Vehicle_Type", y="avg_customer_rating"),
    "B1 · Daily trend: volume, outcomes, revenue": dict(kind="line", x="Date", y=["bookings", "successful"]),
    "B2 · Hourly demand and success rate": dict(kind="combo", x="Hour", y="bookings", y2="success_rate_pct"),
    "B3 · Cancellation reasons with share": dict(kind="hbar", x="cancellations", y="Cancel_Reason", color="Cancel_By"),
    "B4 · Vehicle scorecard (CTE + RANK window)": dict(kind="bar", x="Vehicle_Type", y="revenue"),
    "B5 · Revenue by payment method": dict(kind="pie", x="Payment_Method", y="revenue"),
    "B6 · Top 10 busiest routes (successful rides)": dict(kind="route", y="rides"),
    "B7 · Revenue lost to cancellations": dict(kind="bar", x="Booking_Status", y="booking_value"),
}
SQL_SKILLS = {
    "Q": ["SELECT / WHERE", "GROUP BY", "ORDER BY / LIMIT", "Aggregates"],
    "B": ["CTEs (WITH)", "Window functions (RANK, SUM OVER)", "CASE WHEN", "Multi-column GROUP BY", "Share-of-total maths"],
}


def analysis_chart(title: str, res: pd.DataFrame, key: str) -> None:
    spec = ANALYSIS_CHARTS.get(title)
    if not spec or res.empty:
        return
    kind = spec["kind"]
    try:
        if kind == "bar":
            fig = px.bar(res, x=spec["x"], y=spec["y"], text_auto=".3s", color_discrete_sequence=PALETTE)
        elif kind == "line":
            fig = px.line(res, x=spec["x"], y=spec["y"], markers=True, color_discrete_sequence=PALETTE)
        elif kind == "hbar":
            fig = px.bar(res, x=spec["x"], y=spec["y"], color=spec.get("color"), orientation="h",
                         color_discrete_sequence=PALETTE)
            fig.update_layout(yaxis={"categoryorder": "total ascending"})
        elif kind == "pie":
            fig = px.pie(res, names=spec["x"], values=spec["y"], hole=0.5, color_discrete_sequence=PALETTE)
        elif kind == "route":
            r = res.copy()
            r["Route"] = r["Pickup_Location"] + " → " + r["Drop_Location"]
            fig = px.bar(r, x=spec["y"], y="Route", orientation="h", color_discrete_sequence=PALETTE)
            fig.update_layout(yaxis={"categoryorder": "total ascending"})
        else:  # combo: bars + line on a secondary axis
            fig = go.Figure()
            fig.add_bar(x=res[spec["x"]], y=res[spec["y"]], name=spec["y"], marker_color=PALETTE[0])
            fig.add_scatter(x=res[spec["x"]], y=res[spec["y2"]], name=spec["y2"], yaxis="y2",
                            mode="lines+markers", line=dict(color=PALETTE[1]))
            fig.update_layout(yaxis2=dict(overlaying="y", side="right", showgrid=False, title=spec["y2"]))
        fig.update_layout(xaxis_title=None)
        show(style(fig, legend=kind in {"line", "combo", "hbar"}), key)
    except Exception as e:  # never let a chart break the page
        st.caption(f"Chart unavailable: {e}")


def render_analysis(title: str, item: dict, key: str, preview: int = 500) -> None:
    st.markdown(f"#### {title}")
    res = analysis_query(item["sql"], preview)
    left, right = st.columns([1, 1.15])
    with left:
        st.code(item["sql"], language="sql")
    with right:
        if res.shape == (1, 1):
            v = res.iloc[0, 0]
            st.metric(res.columns[0].replace("_", " ").title(), f"{v:,}" if isinstance(v, (int, float)) else str(v))
        else:
            st.dataframe(res, width="stretch", hide_index=True, height=min(35 * (len(res) + 1) + 3, 320))
            if len(res) >= preview:
                st.caption(f"Preview limited to {preview} rows.")
    analysis_chart(title, res, f"{key}_chart")
    st.markdown(f"<div class='insight'>💡 <b>Insight:</b> {item['why']}</div>", unsafe_allow_html=True)
    c1, c2 = st.columns([1, 5])
    with c1:
        csv_button(res, key, f"{key}_dl")
    with c2:
        st.button("🧪 Open in Playground", key=f"{key}_open", on_click=_load_pg_sql, args=(item["sql"],))
    st.divider()


# --------------------------------------------------------------------------- #
# Load + sidebar filters
# --------------------------------------------------------------------------- #
df = load_data()

with st.sidebar:
    if logo_data_uri():
        st.markdown(f'<img class="side-logo" src="{logo_data_uri()}" alt="Ola logo">', unsafe_allow_html=True)
    st.header("🎛️ Filters")
    dmin, dmax = df["Date"].min().date(), df["Date"].max().date()
    date_range = st.date_input("Booking date", (dmin, dmax), min_value=dmin, max_value=dmax)
    vehicles = st.multiselect("Vehicle type", sorted(df["Vehicle_Type"].unique()))
    statuses = st.multiselect("Booking status", sorted(df["Booking_Status"].unique()))
    pays = st.multiselect("Payment method", sorted(df["Payment_Method"].dropna().unique()))
    parts = st.multiselect("Day part", DAY_PARTS)
    pickups = st.multiselect("Pickup location", sorted(df["Pickup_Location"].unique()))
    st.caption("Leave a filter empty to include everything.")

mask = pd.Series(True, index=df.index)
if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
    mask &= df["Date"].between(pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1]))
for col, sel in [
    ("Vehicle_Type", vehicles),
    ("Booking_Status", statuses),
    ("Payment_Method", pays),
    ("Day_Part", parts),
    ("Pickup_Location", pickups),
]:
    if sel:
        mask &= df[col].isin(sel)
f = df[mask]

with st.sidebar:
    st.metric("Bookings in view", f"{len(f):,}", f"{pct(len(f), len(df)):.1f}% of all")

_logo = logo_data_uri()
_succ = float(f["Is_Success"].mean() * 100) if len(f) else 0.0
_rev = float(f["Revenue"].sum()) if len(f) else 0.0
_logo_html = (
    f'<a class="logo-link" href="https://www.olacabs.com" target="_blank" rel="noopener" '
    f'title="Ola Cabs: ride-sharing analytics case study">'
    f'<img class="logo-img" src="{_logo}" alt="Ola logo"></a>'
    if _logo else ""
)
st.markdown(
    f"""
    <div class="hero">
      <div class="hero-row">
        <div>
          <div class="brand"><span class="dot"></span><span class="tag">Analytics Case Study</span></div>
          <h1>Ola Ride Insights</h1>
          <p>Ride-sharing &amp; mobility analytics · July 2024 · Bookings, revenue, cancellations and customer experience</p>
          <div class="chips">
            <span class="chip" title="Bookings matching the current filters"><b>{len(f):,}</b>bookings in view</span>
            <span class="chip" title="Share of bookings completed successfully"><b>{_succ:.1f}%</b>success rate</span>
            <span class="chip" title="Booking value of successful rides"><b>₹{_rev/1e6:,.2f}M</b>revenue</span>
          </div>
        </div>
        {_logo_html}
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if f.empty:
    st.warning("No bookings match the current filters. Widen the filters in the sidebar.")
    st.stop()

K = kpis(f)
s = f[f["Is_Success"] == 1]

tabs = st.tabs(
    ["📊 Overview", "🚗 Vehicle Types", "💰 Revenue", "❌ Cancellations", "⭐ Ratings",
     "🚀 Advanced", "🧪 SQL Playground", "📑 SQL Analysis", "🔎 Booking Search", "📈 Power BI", "💡 Insights"]
)

# --------------------------------------------------------------------------- #
# 1. Overview
# --------------------------------------------------------------------------- #
with tabs[0]:
    c = st.columns(6)
    c[0].metric("Total bookings", f"{K['total']:,}")
    c[1].metric("Successful rides", f"{K['succ']:,}")
    c[2].metric("Success rate", f"{K['succ_rate']:.1f}%")
    c[3].metric("Cancellation rate", f"{K['cancel_rate']:.2f}%")
    c[4].metric("Successful revenue", inr(K["revenue"]))
    c[5].metric("Unique customers", f"{K['customers']:,}")

    daily = f.groupby("Date").agg(Bookings=("Booking_ID", "count"), Successful=("Is_Success", "sum")).reset_index()
    l, r = st.columns([3, 2])
    fig = px.line(daily, x="Date", y=["Bookings", "Successful"], markers=True, title="Daily bookings vs successful rides")
    fig.update_layout(xaxis_title=None, yaxis_title="Rides", legend_title=None)
    with l:
        show(style(fig), "ov_daily")
    stat = f["Booking_Status"].value_counts().reset_index()
    fig = px.pie(stat, names="Booking_Status", values="count", hole=0.55, color="Booking_Status",
                 color_discrete_map=STATUS_COLORS, title="Booking outcome mix")
    with r:
        show(style(fig), "ov_status")

    l, r = st.columns(2)
    hr = f.groupby("Hour").agg(Bookings=("Booking_ID", "count"), Success=("Is_Success", "sum")).reset_index()
    hr["Success rate %"] = 100 * hr["Success"] / hr["Bookings"]
    fig = go.Figure()
    fig.add_bar(x=hr["Hour"], y=hr["Bookings"], name="Bookings", marker_color="#0096C7")
    fig.add_scatter(x=hr["Hour"], y=hr["Success rate %"], name="Success rate %", yaxis="y2",
                    mode="lines+markers", line=dict(color="#FF6B35"))
    fig.update_layout(title="Demand and success rate by hour",
                      yaxis2=dict(overlaying="y", side="right", range=[0, 100], title="Success %"),
                      xaxis=dict(title="Hour of day", dtick=2), yaxis_title="Bookings")
    with l:
        show(style(fig), "ov_hour")
    heat = f.pivot_table(index="Weekday", columns="Hour", values="Booking_ID", aggfunc="count").reindex(WEEKDAYS)
    fig = px.imshow(heat, aspect="auto", color_continuous_scale="Blues", title="Demand heatmap: weekday × hour")
    fig.update_layout(xaxis_title="Hour", yaxis_title=None)
    with r:
        show(style(fig, legend=False), "ov_heat")

    wk = f.groupby("Is_Weekend").agg(Bookings=("Booking_ID", "count"), Days=("Date", "nunique"),
                                      Success=("Is_Success", "sum")).reset_index()
    wk["Day type"] = wk["Is_Weekend"].map({0: "Weekday", 1: "Weekend"})
    wk["Avg bookings / day"] = wk["Bookings"] / wk["Days"]
    wk["Success rate %"] = 100 * wk["Success"] / wk["Bookings"]
    l, r = st.columns(2)
    fig = px.bar(wk, x="Day type", y="Avg bookings / day", text_auto=".0f", title="Average bookings per day: weekday vs weekend")
    with l:
        show(style(fig, 320, False), "ov_wk")
    dp = f.groupby("Day_Part").agg(Bookings=("Booking_ID", "count"), Success=("Is_Success", "sum")).reindex(DAY_PARTS).reset_index()
    dp["Success rate %"] = 100 * dp["Success"] / dp["Bookings"]
    fig = px.bar(dp, x="Day_Part", y="Success rate %", text_auto=".1f", title="Success rate by day part")
    fig.update_layout(xaxis_title=None, yaxis_range=[0, 100])
    with r:
        show(style(fig, 320, False), "ov_dp")

# --------------------------------------------------------------------------- #
# 2. Vehicle types
# --------------------------------------------------------------------------- #
with tabs[1]:
    g = f.groupby("Vehicle_Type")
    vt = pd.DataFrame({
        "Bookings": g["Booking_ID"].count(),
        "Successful rides": g["Is_Success"].sum(),
        "Total booking value": g["Booking_Value"].sum(),
        "Successful revenue": g["Revenue"].sum(),
    })
    vt["Success rate %"] = 100 * vt["Successful rides"] / vt["Bookings"]
    vt["Avg distance (km)"] = s.groupby("Vehicle_Type")["Ride_Distance"].mean()
    vt["Distance (km)"] = s.groupby("Vehicle_Type")["Ride_Distance"].sum()
    vt["Revenue / km"] = vt["Successful revenue"] / vt["Distance (km)"]
    vt["Avg customer rating"] = s.groupby("Vehicle_Type")["Customer_Rating"].mean()
    vt["Avg driver rating"] = s.groupby("Vehicle_Type")["Driver_Ratings"].mean()
    vt = vt.reset_index().sort_values("Successful revenue", ascending=False)

    best = vt.loc[vt["Success rate %"].idxmax()]
    top_rev = vt.iloc[0]
    c = st.columns(3)
    c[0].metric("Highest success rate", best["Vehicle_Type"], f"{best['Success rate %']:.1f}%")
    c[1].metric("Top revenue vehicle", top_rev["Vehicle_Type"], inr(top_rev["Successful revenue"]))
    c[2].metric("Most efficient (₹/km)", vt.loc[vt["Revenue / km"].idxmax(), "Vehicle_Type"],
                f"₹{vt['Revenue / km'].max():.1f}")

    l, r = st.columns(2)
    fig = px.bar(vt.sort_values("Successful revenue"), x="Successful revenue", y="Vehicle_Type", orientation="h",
                 text=vt.sort_values("Successful revenue")["Successful revenue"].map(inr), title="Successful revenue by vehicle type")
    fig.update_layout(yaxis_title=None)
    with l:
        show(style(fig, legend=False), "vt_rev")
    fig = px.bar(vt.sort_values("Success rate %"), x="Success rate %", y="Vehicle_Type", orientation="h",
                 text_auto=".1f", title="Success rate by vehicle type")
    fig.update_layout(yaxis_title=None, xaxis_range=[0, 100])
    with r:
        show(style(fig, legend=False), "vt_sr")
    l, r = st.columns(2)
    fig = px.bar(vt, x="Vehicle_Type", y=["Bookings", "Successful rides"], barmode="group", title="Bookings vs successful rides")
    fig.update_layout(xaxis_title=None, legend_title=None)
    with l:
        show(style(fig), "vt_book")
    fig = px.scatter(vt, x="Avg distance (km)", y="Revenue / km", size="Successful rides", color="Vehicle_Type",
                     title="Trip length vs revenue per km")
    with r:
        show(style(fig), "vt_scatter")

    st.subheader("Vehicle performance scorecard")
    st.dataframe(
        vt,
        width="stretch",
        hide_index=True,
        column_config={
            "Bookings": st.column_config.NumberColumn(format="%d"),
            "Successful rides": st.column_config.NumberColumn(format="%d"),
            "Total booking value": st.column_config.NumberColumn(format="₹%d"),
            "Successful revenue": st.column_config.NumberColumn(format="₹%d"),
            "Success rate %": st.column_config.ProgressColumn(format="%.2f", min_value=0, max_value=100),
            "Avg distance (km)": st.column_config.NumberColumn(format="%.2f"),
            "Distance (km)": st.column_config.NumberColumn(format="%d"),
            "Revenue / km": st.column_config.NumberColumn(format="%.2f"),
            "Avg customer rating": st.column_config.NumberColumn(format="%.2f"),
            "Avg driver rating": st.column_config.NumberColumn(format="%.2f"),
        },
    )
    csv_button(vt, "vehicle_scorecard", "dl_vt")

# --------------------------------------------------------------------------- #
# 3. Revenue
# --------------------------------------------------------------------------- #
with tabs[2]:
    total_val = float(f["Booking_Value"].sum())
    lost = total_val - K["revenue"]
    c = st.columns(4)
    c[0].metric("Total booking value", inr(total_val))
    c[1].metric("Realised revenue", inr(K["revenue"]))
    c[2].metric("Unrealised value", inr(lost), f"-{pct(lost, total_val):.1f}%", delta_color="inverse")
    c[3].metric("Avg fare (successful)", f"₹{s['Booking_Value'].mean():,.0f}" if len(s) else "-")

    l, r = st.columns(2)
    pay = s.groupby("Payment_Method").agg(Revenue=("Booking_Value", "sum"), Rides=("Booking_ID", "count")).reset_index()
    fig = px.pie(pay, names="Payment_Method", values="Revenue", hole=0.55, title="Revenue by payment method")
    with l:
        show(style(fig), "rev_pay")
    top = s.groupby("Customer_ID")["Booking_Value"].sum().nlargest(10).reset_index().sort_values("Booking_Value")
    fig = px.bar(top, x="Booking_Value", y="Customer_ID", orientation="h", text_auto=",.0f", title="Top 10 customers by successful value")
    fig.update_layout(yaxis_title=None, xaxis_title="₹")
    with r:
        show(style(fig, legend=False), "rev_top")

    l, r = st.columns(2)
    dr = f.groupby("Date")["Revenue"].sum().reset_index()
    dr["Cumulative"] = dr["Revenue"].cumsum()
    fig = go.Figure()
    fig.add_bar(x=dr["Date"], y=dr["Revenue"], name="Daily revenue", marker_color="#0096C7")
    fig.add_scatter(x=dr["Date"], y=dr["Cumulative"], name="Cumulative", yaxis="y2", line=dict(color="#FF6B35"))
    fig.update_layout(title="Daily and cumulative revenue", yaxis2=dict(overlaying="y", side="right"))
    with l:
        show(style(fig), "rev_daily")
    wf = go.Figure(go.Waterfall(
        x=["Total booking value", "Unsuccessful bookings", "Realised revenue"],
        measure=["absolute", "relative", "total"], y=[total_val, -lost, 0],
        text=[inr(total_val), "-" + inr(lost), inr(K["revenue"])],
        decreasing=dict(marker_color="#FF6B35"), totals=dict(marker_color="#2ECC71"),
        increasing=dict(marker_color="#00B4D8"),
    ))
    wf.update_layout(title="Revenue realisation bridge")
    with r:
        show(style(wf, legend=False), "rev_wf")

    routes = s.groupby("Route").agg(Rides=("Booking_ID", "count"), Revenue=("Booking_Value", "sum")).nlargest(10, "Rides").reset_index()
    fig = px.bar(routes.sort_values("Rides"), x="Rides", y="Route", orientation="h", text_auto=True, title="Top 10 routes by completed rides")
    fig.update_layout(yaxis_title=None)
    show(style(fig, 420, False), "rev_routes")

# --------------------------------------------------------------------------- #
# 4. Cancellations
# --------------------------------------------------------------------------- #
with tabs[3]:
    cc = int((f["Booking_Status"] == "Canceled by Customer").sum())
    dc = int((f["Booking_Status"] == "Canceled by Driver").sum())
    dn = int((f["Booking_Status"] == "Driver Not Found").sum())
    c = st.columns(4)
    c[0].metric("Customer cancellations", f"{cc:,}")
    c[1].metric("Driver cancellations", f"{dc:,}")
    c[2].metric("Driver not found", f"{dn:,}")
    c[3].metric("Cancellation rate", f"{K['cancel_rate']:.2f}%")

    l, r = st.columns(2)
    for col, who, color, key in [(l, "Customer", "#FF6B35", "cx_c"), (r, "Driver", "#E84393", "cx_d")]:
        d = f[f["Cancel_By"] == who]["Cancel_Reason"].value_counts().reset_index().sort_values("count")
        fig = px.bar(d, x="count", y="Cancel_Reason", orientation="h", text_auto=True,
                     title=f"{who} cancellation reasons", color_discrete_sequence=[color])
        fig.update_layout(yaxis_title=None, xaxis_title="Cancellations")
        with col:
            show(style(fig, legend=False), key)

    l, r = st.columns(2)
    mix = pd.crosstab(f["Vehicle_Type"], f["Booking_Status"], normalize="index").mul(100).reset_index().melt(
        id_vars="Vehicle_Type", var_name="Status", value_name="Share %")
    fig = px.bar(mix, x="Vehicle_Type", y="Share %", color="Status", color_discrete_map=STATUS_COLORS,
                 title="Outcome mix by vehicle type (100%)")
    fig.update_layout(xaxis_title=None, legend_title=None)
    with l:
        show(style(fig), "cx_veh")
    inc = f[f["Incomplete_Rides"] == "Yes"]["Incomplete_Rides_Reason"].value_counts().reset_index()
    fig = px.pie(inc, names="Incomplete_Rides_Reason", values="count", hole=0.55, title="Incomplete ride reasons")
    with r:
        show(style(fig), "cx_inc")

    cd = f[f["Is_Success"] == 0].groupby("Day_Part").size().reindex(DAY_PARTS).reset_index(name="Failed bookings")
    fig = px.bar(cd, x="Day_Part", y="Failed bookings", text_auto=True, title="Failed bookings by day part")
    fig.update_layout(xaxis_title=None)
    show(style(fig, 320, False), "cx_dp")

# --------------------------------------------------------------------------- #
# 5. Ratings
# --------------------------------------------------------------------------- #
with tabs[4]:
    c = st.columns(4)
    c[0].metric("Avg customer rating", f"{s['Customer_Rating'].mean():.2f}" if len(s) else "-")
    c[1].metric("Avg driver rating", f"{s['Driver_Ratings'].mean():.2f}" if len(s) else "-")
    c[2].metric("Rated rides", f"{s['Customer_Rating'].notna().sum():,}")
    c[3].metric("Rides rated ≥ 4.5 by customers", f"{pct((s['Customer_Rating'] >= 4.5).sum(), len(s)):.1f}%" if len(s) else "-")

    if s.empty:
        st.info("Ratings exist only for successful rides. Adjust the filters to include some.")
    else:
        l, r = st.columns(2)
        fig = px.histogram(s, x="Driver_Ratings", nbins=20, title="Driver ratings distribution", color_discrete_sequence=["#0096C7"])
        fig.update_layout(xaxis_title="Driver rating", yaxis_title="Rides")
        with l:
            show(style(fig, legend=False), "rt_d")
        fig = px.histogram(s, x="Customer_Rating", nbins=20, title="Customer ratings distribution", color_discrete_sequence=["#F4A300"])
        fig.update_layout(xaxis_title="Customer rating", yaxis_title="Rides")
        with r:
            show(style(fig, legend=False), "rt_c")
        l, r = st.columns(2)
        av = s.groupby("Vehicle_Type")[["Customer_Rating", "Driver_Ratings"]].mean().reset_index()
        fig = px.bar(av, x="Vehicle_Type", y=["Customer_Rating", "Driver_Ratings"], barmode="group", text_auto=".2f",
                     title="Average rating by vehicle type")
        fig.update_layout(yaxis_range=[3, 5], xaxis_title=None, legend_title=None)
        with l:
            show(style(fig), "rt_v")
        fig = px.density_heatmap(s, x="Driver_Ratings", y="Customer_Rating", nbinsx=20, nbinsy=20,
                                 color_continuous_scale="Blues", title="Customer vs driver rating density")
        with r:
            show(style(fig, legend=False), "rt_h")

# --------------------------------------------------------------------------- #
# 5b. Advanced analytics (all visuals respond to the sidebar filters)
# --------------------------------------------------------------------------- #
def tip(text: str) -> None:
    st.markdown(f"<div class='insight'>💡 <b>Insight:</b> {text}</div>", unsafe_allow_html=True)


def sklearn_ok() -> bool:
    try:
        import sklearn  # noqa: F401
        return True
    except ImportError:
        return False


def train_cancel_model(data: pd.DataFrame) -> dict:
    """Random Forest that predicts booking failure from information known at booking time only."""
    from sklearn.compose import ColumnTransformer
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score, roc_auc_score
    from sklearn.model_selection import train_test_split
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder

    d = data.sample(min(len(data), 40_000), random_state=42)
    top = list(data["Pickup_Location"].value_counts().head(25).index)
    X = pd.DataFrame({
        "Vehicle_Type": d["Vehicle_Type"].values,
        "Pickup": d["Pickup_Location"].where(d["Pickup_Location"].isin(top), "Other").values,
        "Weekday": d["Weekday"].values,
        "Hour": d["Hour"].values,
        "Is_Weekend": d["Is_Weekend"].astype(int).values,
    })
    y = (1 - d["Is_Success"]).astype(int).values
    cats = ["Vehicle_Type", "Pickup", "Weekday"]
    pre = ColumnTransformer([("cat", OneHotEncoder(handle_unknown="ignore"), cats)], remainder="passthrough")
    pipe = Pipeline([("pre", pre), ("rf", RandomForestClassifier(
        n_estimators=120, max_depth=10, min_samples_leaf=50, class_weight="balanced", n_jobs=-1, random_state=42))])
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y)
    pipe.fit(Xtr, ytr)
    proba = pipe.predict_proba(Xte)[:, 1]
    names = pipe.named_steps["pre"].get_feature_names_out()
    imp = pd.Series(pipe.named_steps["rf"].feature_importances_, index=names)
    agg: dict[str, float] = {}
    for n, v in imp.items():
        rest = n.split("__", 1)[1]
        base = next((c for c in X.columns if rest == c or rest.startswith(c + "_")), rest)
        agg[base] = agg.get(base, 0.0) + float(v)
    importance = pd.Series(agg).sort_values(ascending=False).rename("Importance").reset_index()
    importance.columns = ["Feature", "Importance"]
    return dict(
        model=pipe, auc=float(roc_auc_score(yte, proba)),
        acc=float(accuracy_score(yte, (proba >= 0.5).astype(int))),
        base_rate=float(y.mean()), importance=importance, top=top, n_train=len(Xtr),
        vehicles=sorted(data["Vehicle_Type"].unique()), weekdays=WEEKDAYS,
    )


with tabs[5]:
    st.subheader("🚀 Advanced Analytics")
    st.caption("Business-intelligence views built for decision-making. Every chart below responds to the sidebar filters "
               "(except the predictive model, which learns from the full dataset).")
    adv = st.tabs(["👥 Customer", "🛣️ Routes", "⚖️ Demand & Supply", "💲 Pricing", "🏆 Performance", "🤖 Predictive"])

    # ---------------------------- Customer intelligence ---------------------------- #
    with adv[0]:
        st.markdown("##### Customer segmentation (frequency × value)")
        cust = f.groupby("Customer_ID").agg(
            Frequency=("Booking_ID", "count"), Monetary=("Revenue", "sum"), Completed=("Is_Success", "sum")
        ).reset_index()
        pos = cust.loc[cust["Monetary"] > 0, "Monetary"]
        hv = float(pos.quantile(0.9)) if len(pos) else float("inf")
        cust["Segment"] = "One-time booker"
        cust.loc[cust["Frequency"] >= 2, "Segment"] = "Repeat customer"
        cust.loc[cust["Monetary"] >= hv, "Segment"] = "High-value customer"
        cust.loc[cust["Monetary"] == 0, "Segment"] = "No completed ride"
        seg = cust.groupby("Segment").agg(
            Customers=("Customer_ID", "count"), Revenue=("Monetary", "sum"), Avg_bookings=("Frequency", "mean")
        ).reset_index()
        seg["Share of customers %"] = (100 * seg["Customers"] / seg["Customers"].sum()).round(1)
        seg["Share of revenue %"] = (100 * seg["Revenue"] / seg["Revenue"].sum()).round(1) if seg["Revenue"].sum() else 0.0
        seg_colors = {"High-value customer": "#2ECC71", "Repeat customer": "#0096C7",
                      "One-time booker": "#F4A300", "No completed ride": "#E84393"}
        c1, c2 = st.columns(2)
        fig = px.treemap(seg, path=["Segment"], values="Customers", color="Segment", color_discrete_map=seg_colors,
                         custom_data=["Share of customers %", "Share of revenue %"],
                         title="Customer base by segment (size = customers)")
        fig.update_traces(texttemplate="%{label}<br>%{value:,} customers<br>%{customdata[0]}% of base",
                          hovertemplate="%{label}<br>Customers: %{value:,}<br>Revenue share: %{customdata[1]}%<extra></extra>")
        with c1:
            show(style(fig, legend=False), "adv_seg_tree")
        fig = px.bar(seg.sort_values("Revenue"), x="Revenue", y="Segment", orientation="h", color="Segment",
                     color_discrete_map=seg_colors, text="Share of revenue %", title="Revenue contribution by segment")
        fig.update_traces(texttemplate="%{text}%")
        fig.update_layout(yaxis_title=None)
        with c2:
            show(style(fig, legend=False), "adv_seg_rev")
        top_seg = seg.sort_values("Revenue", ascending=False).iloc[0]
        tip(f"<b>{top_seg['Segment']}</b> drive the largest revenue share (<b>{top_seg['Share of revenue %']}%</b>) from "
            f"<b>{top_seg['Share of customers %']}%</b> of customers. "
            f"Repeat customers are <b>{seg.loc[seg['Segment'] == 'Repeat customer', 'Share of customers %'].sum():.1f}%</b> "
            "of the base, so retention and loyalty offers are the biggest headroom.")

        st.markdown("##### Top customers by value")
        topc = cust.sort_values(["Monetary", "Frequency"], ascending=False).head(10)[
            ["Customer_ID", "Frequency", "Completed", "Monetary", "Segment"]]
        st.dataframe(topc, width="stretch", hide_index=True, column_config={
            "Monetary": st.column_config.NumberColumn("Revenue (₹)", format="₹%d")})
        csv_button(seg, "customer_segments", "dl_adv_seg")

        with st.expander("🤖 Machine-learning segmentation (K-Means)"):
            if not sklearn_ok():
                st.info("Install scikit-learn to enable this: `pip install scikit-learn`")
            else:
                k = st.slider("Number of clusters (k)", 2, 6, 4, key="adv_k")
                if st.toggle("Run K-Means on the filtered customers", key="adv_km"):
                    from sklearn.cluster import KMeans
                    from sklearn.preprocessing import StandardScaler
                    feats = cust[["Frequency", "Monetary"]].drop_duplicates()
                    if len(feats) < k:
                        st.warning("Not enough distinct customer profiles for that many clusters. Lower k.")
                    else:
                        Z = StandardScaler().fit_transform(np.log1p(cust[["Frequency", "Monetary"]]))
                        cust["Cluster"] = KMeans(n_clusters=k, n_init=5, random_state=42).fit_predict(Z)
                        order = cust.groupby("Cluster")["Monetary"].mean().sort_values().index
                        cust["Cluster"] = cust["Cluster"].map({c: f"Cluster {i + 1}" for i, c in enumerate(order)})
                        prof = cust.groupby("Cluster").agg(
                            Customers=("Customer_ID", "count"), Avg_bookings=("Frequency", "mean"),
                            Avg_revenue=("Monetary", "mean")).round(2).reset_index()
                        samp = cust.sample(min(len(cust), 4000), random_state=1)
                        fig = px.scatter(samp, x="Frequency", y="Monetary", color="Cluster",
                                         title="K-Means clusters (sample of customers)",
                                         labels={"Monetary": "Revenue (₹)"})
                        lc, rc = st.columns([1.4, 1])
                        with lc:
                            show(style(fig), "adv_km_fig")
                        with rc:
                            st.dataframe(prof, width="stretch", hide_index=True)
                        tip("Cluster 1 holds the lowest-value profiles and the highest cluster number the most valuable. "
                            "Use these groups to target win-back, loyalty and premium offers.")

    # ----------------------------- Route intelligence ----------------------------- #
    with adv[1]:
        st.markdown("##### Ride flow: pickup → drop (successful rides)")
        if s.empty:
            st.info("No successful rides in the current filter selection.")
        else:
            n_routes = st.slider("Number of top routes", 5, 30, 12, key="adv_nroutes")
            rt = s.groupby(["Pickup_Location", "Drop_Location"]).agg(
                rides=("Booking_ID", "count"), revenue=("Booking_Value", "sum"), avg_km=("Ride_Distance", "mean")
            ).reset_index().nlargest(n_routes, "rides")
            src = list(dict.fromkeys(rt["Pickup_Location"]))
            dst = list(dict.fromkeys(rt["Drop_Location"]))
            si = {k_: i for i, k_ in enumerate(src)}
            di = {k_: i + len(src) for i, k_ in enumerate(dst)}
            fig = go.Figure(go.Sankey(
                node=dict(label=src + dst, pad=14, thickness=16,
                          color=[PALETTE[0]] * len(src) + [PALETTE[1]] * len(dst)),
                link=dict(source=[si[a] for a in rt["Pickup_Location"]], target=[di[b] for b in rt["Drop_Location"]],
                          value=rt["rides"], color="rgba(0,150,199,0.25)",
                          customdata=rt["revenue"],
                          hovertemplate="%{source.label} → %{target.label}<br>Rides: %{value}<br>Revenue: ₹%{customdata:,.0f}<extra></extra>"),
            ))
            fig.update_layout(title=f"Top {n_routes} pickup → drop flows (left: pickup, right: drop)")
            show(style(fig, height=480, legend=False), "adv_sankey")
            best = rt.iloc[0]
            tip(f"The busiest corridor is <b>{best['Pickup_Location']} → {best['Drop_Location']}</b> with "
                f"<b>{int(best['rides'])}</b> rides ({inr(float(best['revenue']))}). The top {n_routes} routes carry "
                f"<b>{pct(rt['rides'].sum(), len(s)):.1f}%</b> of completed rides, so demand is widely spread. "
                "Position drivers by pickup zone rather than by a few fixed corridors.")
            st.dataframe(rt.rename(columns={"avg_km": "Avg km"}).round(1), width="stretch", hide_index=True,
                         column_config={"revenue": st.column_config.NumberColumn("Revenue (₹)", format="₹%d")})

        st.markdown("##### Location operational risk (pickup cancellation rate)")
        loc = f.groupby("Pickup_Location").agg(bookings=("Booking_ID", "count"), ok=("Is_Success", "sum")).reset_index()
        loc["failed"] = loc["bookings"] - loc["ok"]
        loc["failure_rate"] = (100 * loc["failed"] / loc["bookings"]).round(2)
        maxb = max(int(loc["bookings"].max()), 2)
        lc1, lc2 = st.columns(2)
        min_b = lc1.number_input("Min bookings per location", 1, maxb, min(30, maxb), key="adv_minb")
        top_n = lc2.slider("Locations to show", 5, 25, 15, key="adv_locn")
        risk = loc[loc["bookings"] >= min_b].nlargest(top_n, "failure_rate")
        if risk.empty:
            st.info("No location meets the minimum-bookings threshold. Lower it.")
        else:
            fig = px.bar(risk.sort_values("failure_rate"), x="failure_rate", y="Pickup_Location", orientation="h",
                         color="failure_rate", color_continuous_scale="Reds", hover_data=["bookings", "failed"],
                         title="Highest failure rates by pickup location", labels={"failure_rate": "Failure rate %"})
            fig.update_layout(yaxis_title=None, coloraxis_showscale=False)
            show(style(fig, legend=False, height=max(340, 24 * len(risk) + 90)), "adv_loc_risk")
            w = risk.iloc[0]
            tip(f"<b>{w['Pickup_Location']}</b> has the highest failure rate (<b>{w['failure_rate']}%</b> of "
                f"{int(w['bookings'])} bookings) versus <b>{100 - K['succ_rate']:.1f}%</b> overall. Prioritise driver supply "
                "and incentives in the locations at the top of this list.")

    # ----------------------------- Demand & supply ----------------------------- #
    with adv[2]:
        st.markdown("##### Vehicle × hour demand and fulfilment")
        metric = st.radio("Colour by", ["Booking volume", "Success rate %"], horizontal=True, key="adv_heat_metric")
        g = f.groupby(["Vehicle_Type", "Hour"]).agg(bookings=("Booking_ID", "count"), sr=("Is_Success", "mean")).reset_index()
        g["sr"] = (100 * g["sr"]).round(1)
        hours = list(range(24))
        order_v = g.groupby("Vehicle_Type")["bookings"].sum().sort_values(ascending=False).index.tolist()
        pv = g.pivot(index="Vehicle_Type", columns="Hour", values="bookings").reindex(index=order_v, columns=hours)
        ps = g.pivot(index="Vehicle_Type", columns="Hour", values="sr").reindex(index=order_v, columns=hours)
        z, other = (pv, ps) if metric == "Booking volume" else (ps, pv)
        fig = go.Figure(go.Heatmap(
            z=z.values, x=hours, y=order_v, customdata=other.values, colorscale="YlGnBu" if metric == "Booking volume" else "RdYlGn",
            hovertemplate=("Hour %{x}:00<br>%{y}<br>" + ("Bookings: %{z}<br>Success rate: %{customdata:.1f}%"
                           if metric == "Booking volume" else "Success rate: %{z:.1f}%<br>Bookings: %{customdata}")
                           + "<extra></extra>"),
            xgap=2, ygap=2))
        fig.update_layout(title=f"{metric} by vehicle type and hour", xaxis_title="Hour of day", yaxis_title=None,
                          xaxis=dict(dtick=1))
        show(style(fig, legend=False, height=360), "adv_heat")
        slots = g[g["bookings"] >= g["bookings"].median()].nsmallest(8, "sr")
        if not slots.empty:
            w = slots.iloc[0]
            tip(f"Weakest high-demand slot: <b>{w['Vehicle_Type']} at {int(w['Hour'])}:00</b> converts only "
                f"<b>{w['sr']}%</b> of <b>{int(w['bookings'])}</b> bookings. Fixing the slots below recovers the most rides.")
            st.markdown("**Fulfilment gaps (busy slots with the lowest success rate)**")
            st.dataframe(slots.rename(columns={"sr": "Success rate %"}), width="stretch", hide_index=True)

    # ----------------------------- Pricing intelligence ----------------------------- #
    with adv[3]:
        st.markdown("##### Fare distribution and fare vs distance (successful rides)")
        sp = s.dropna(subset=["Booking_Value", "Ride_Distance"])
        sp = sp[sp["Ride_Distance"] > 0]
        if len(sp) < 10:
            st.info("Not enough successful rides with fare and distance in the current filter selection.")
        else:
            c1, c2 = st.columns(2)
            fig = px.box(sp, x="Vehicle_Type", y="Booking_Value", color="Vehicle_Type", points="outliers",
                         title="Fare distribution by vehicle type", labels={"Booking_Value": "Fare (₹)"})
            fig.update_layout(xaxis_title=None)
            with c1:
                show(style(fig, legend=False), "adv_box")
            samp = sp.sample(min(len(sp), 4000), random_state=7)
            slope, icpt = np.polyfit(sp["Ride_Distance"], sp["Booking_Value"], 1)
            r2 = float(np.corrcoef(sp["Ride_Distance"], sp["Booking_Value"])[0, 1] ** 2)
            fig = px.scatter(samp, x="Ride_Distance", y="Booking_Value", color="Vehicle_Type", opacity=0.55,
                             title="Fare vs ride distance", labels={"Ride_Distance": "Distance (km)", "Booking_Value": "Fare (₹)"})
            xs = np.array([sp["Ride_Distance"].min(), sp["Ride_Distance"].max()])
            fig.add_scatter(x=xs, y=slope * xs + icpt, mode="lines", name="Linear fit",
                            line=dict(color="#0F172A", width=3, dash="dash"))
            with c2:
                show(style(fig), "adv_fare_scatter")
            med = sp.groupby("Vehicle_Type")["Booking_Value"].median().sort_values(ascending=False)
            m1, m2, m3 = st.columns(3)
            m1.metric("Price per km (fit)", f"₹{slope:,.1f}")
            m2.metric("Distance explains fare (R²)", f"{r2:.2f}")
            m3.metric("Highest median fare", f"{med.index[0]} · ₹{med.iloc[0]:,.0f}")
            resid = sp["Booking_Value"] - (slope * sp["Ride_Distance"] + icpt)
            mad = float(np.median(np.abs(resid - np.median(resid)))) or 1.0
            flag = sp.assign(Expected_fare=(slope * sp["Ride_Distance"] + icpt).round(0), Residual=resid.round(0))[
                np.abs(resid - np.median(resid)) > 3 * 1.4826 * mad]
            tip(f"Distance explains <b>{r2 * 100:.0f}%</b> of fare variation (about ₹{slope:,.1f} per km). "
                + ("A low R² means fares are driven by factors other than distance, such as vehicle class, surge or "
                   "pricing rules, which is worth auditing. " if r2 < 0.5 else "")
                + f"<b>{len(flag):,}</b> rides ({pct(len(flag), len(sp)):.1f}%) are priced unusually far from the trend.")
            if not flag.empty:
                with st.expander(f"🔎 Unusually priced rides ({len(flag):,})"):
                    cols = ["Booking_ID", "Vehicle_Type", "Ride_Distance", "Booking_Value", "Expected_fare", "Residual"]
                    st.dataframe(flag.reindex(flag["Residual"].abs().sort_values(ascending=False).index)[cols].head(50),
                                 width="stretch", hide_index=True)
                    csv_button(flag[cols], "pricing_anomalies", "dl_adv_anom")

    # ----------------------------- Advanced performance ----------------------------- #
    with adv[4]:
        st.markdown("##### Pareto analysis: what causes most failed bookings?")
        fail = f[f["Is_Success"] == 0].copy()
        if fail.empty:
            st.info("No failed bookings in the current filter selection.")
        else:
            fail["Reason"] = np.where(fail["Cancel_Reason"].notna(),
                                      fail["Cancel_By"].fillna("") + ": " + fail["Cancel_Reason"].fillna(""),
                                      fail["Booking_Status"])
            pr = fail["Reason"].value_counts().reset_index()
            pr.columns = ["Reason", "Count"]
            pr["Cum %"] = (100 * pr["Count"].cumsum() / pr["Count"].sum()).round(1)
            fig = go.Figure()
            fig.add_bar(x=pr["Reason"], y=pr["Count"], name="Failed bookings", marker_color=PALETTE[0])
            fig.add_scatter(x=pr["Reason"], y=pr["Cum %"], name="Cumulative %", yaxis="y2", mode="lines+markers",
                            line=dict(color=PALETTE[1]))
            fig.add_hline(y=80, line_dash="dot", line_color="#94A3B8", yref="y2")
            fig.update_layout(title="Cancellation reasons (Pareto)", yaxis_title="Failed bookings",
                              yaxis2=dict(overlaying="y", side="right", range=[0, 105], title="Cumulative %", showgrid=False),
                              xaxis_title=None)
            show(style(fig, height=420), "adv_pareto")
            k80 = int((pr["Cum %"] < 80).sum()) + 1
            tip(f"The top <b>{k80}</b> of <b>{len(pr)}</b> reasons explain <b>{pr['Cum %'].iloc[min(k80, len(pr)) - 1]:.0f}%</b> "
                f"of failed bookings. Biggest single cause: <b>{pr.iloc[0]['Reason']}</b> "
                f"({pct(pr.iloc[0]['Count'], pr['Count'].sum()):.0f}%). Fix that first.")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("##### Revenue leakage (waterfall)")
            tot = float(f["Booking_Value"].fillna(0).sum())
            lost = f[f["Is_Success"] == 0].groupby("Booking_Status")["Booking_Value"].sum().fillna(0).sort_values(ascending=False)
            if lost.sum() <= 0:
                st.info("No unrealised booking value in the current filter selection.")
            else:
                fig = go.Figure(go.Waterfall(
                    x=["Total booking value"] + list(lost.index) + ["Successful revenue"],
                    y=[tot] + [-float(v) for v in lost] + [0],
                    measure=["absolute"] + ["relative"] * len(lost) + ["total"],
                    connector=dict(line=dict(color="#CBD5E1")),
                    increasing=dict(marker=dict(color="#2ECC71")), decreasing=dict(marker=dict(color="#E84393")),
                    totals=dict(marker=dict(color="#0096C7"))))
                fig.update_layout(title="From booked value to realised revenue", xaxis_title=None, yaxis_title="₹")
                show(style(fig, legend=False), "adv_waterfall")
                tip(f"<b>{inr(float(lost.sum()))}</b> ({pct(float(lost.sum()), tot):.1f}%) of booked value never converts into "
                    f"revenue. The largest leak is <b>{lost.index[0]}</b> ({inr(float(lost.iloc[0]))}).")
        with c2:
            st.markdown("##### Customer vs driver satisfaction")
            sat = s.groupby("Vehicle_Type").agg(
                customer=("Customer_Rating", "mean"), driver=("Driver_Ratings", "mean"), rides=("Booking_ID", "count")).reset_index().dropna()
            if sat.empty:
                st.info("No rated rides in the current filter selection.")
            else:
                fig = px.scatter(sat, x="customer", y="driver", size="rides", color="Vehicle_Type", text="Vehicle_Type",
                                 size_max=48, title="Average ratings by vehicle type (bubble = rides)",
                                 labels={"customer": "Avg customer rating", "driver": "Avg driver rating"})
                fig.update_traces(textposition="top center")
                show(style(fig, legend=False), "adv_sat")
                gap = sat.assign(gap=(sat["customer"] - sat["driver"]).abs()).sort_values("gap", ascending=False).iloc[0]
                tip(f"<b>{gap['Vehicle_Type']}</b> shows the widest rating gap ({gap['gap']:.2f} points between customer "
                    "and driver ratings). Compare drivers and customers there to find the friction.")

        st.markdown("##### Daily performance calendar")
        d = f.groupby("Date").agg(bookings=("Booking_ID", "count"), ok=("Is_Success", "sum"), revenue=("Revenue", "sum")).reset_index()
        d["cancel"] = (100 - 100 * d["ok"] / d["bookings"]).round(1)
        d["week"] = d["Date"] - pd.to_timedelta(d["Date"].dt.weekday, unit="D")
        weeks = sorted(d["week"].unique())
        widx = {w: i for i, w in enumerate(weeks)}
        Z = np.full((7, len(weeks)), np.nan)
        T = np.full((7, len(weeks)), "", dtype=object)
        C = np.full((7, len(weeks), 3), np.nan)
        for r_ in d.itertuples():
            wd, wi = r_.Date.weekday(), widx[r_.week]
            Z[wd, wi] = r_.bookings
            T[wd, wi] = str(r_.Date.day)
            C[wd, wi] = [r_.revenue, r_.ok, r_.cancel]
        fig = go.Figure(go.Heatmap(
            z=Z, x=[pd.Timestamp(w).strftime("%d %b") for w in weeks], y=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            text=T, texttemplate="%{text}", customdata=C, colorscale="Blues", xgap=3, ygap=3,
            hovertemplate="Bookings: %{z}<br>Revenue: ₹%{customdata[0]:,.0f}<br>Successful rides: %{customdata[1]:.0f}"
                          "<br>Cancellation rate: %{customdata[2]:.1f}%<extra></extra>"))
        fig.update_layout(title="Daily bookings (columns = weeks starting on the date shown)", yaxis_autorange="reversed",
                          xaxis_title="Week starting")
        show(style(fig, legend=False, height=340), "adv_calendar")
        hi, lo = d.loc[d["bookings"].idxmax()], d.loc[d["bookings"].idxmin()]
        tip(f"Peak day: <b>{hi['Date']:%d %b}</b> ({int(hi['bookings']):,} bookings). Weakest day: <b>{lo['Date']:%d %b}</b> "
            f"({int(lo['bookings']):,}). A peak-to-trough gap of <b>{pct(hi['bookings'] - lo['bookings'], hi['bookings']):.0f}%</b> "
            "indicates how much driver capacity needs to flex.")

    # ----------------------------- Predictive ----------------------------- #
    with adv[5]:
        st.markdown("##### Cancellation risk model (Random Forest)")
        st.caption("Predicts whether a booking will fail using only information known at booking time "
                   "(vehicle, pickup zone, weekday, hour), which avoids data leakage. Trained on the full dataset.")
        if not sklearn_ok():
            st.info("Install scikit-learn to enable this tab: `pip install scikit-learn`")
        else:
            if st.button("⚙️ Train model", type="primary", key="adv_train"):
                with st.spinner("Training Random Forest..."):
                    st.session_state["adv_model"] = train_cancel_model(df)
            mdl = st.session_state.get("adv_model")
            if not mdl:
                st.info("Click **Train model** to fit the classifier (takes a few seconds).")
            else:
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("ROC-AUC (test)", f"{mdl['auc']:.3f}")
                m2.metric("Accuracy (test)", f"{mdl['acc'] * 100:.1f}%")
                m3.metric("Overall failure rate", f"{mdl['base_rate'] * 100:.1f}%")
                m4.metric("Training rows", f"{mdl['n_train']:,}")
                c1, c2 = st.columns([1, 1.2])
                imp = mdl["importance"]
                fig = px.bar(imp.sort_values("Importance"), x="Importance", y="Feature", orientation="h",
                             title="What drives failure risk? (feature importance)")
                fig.update_layout(yaxis_title=None)
                with c1:
                    show(style(fig, legend=False), "adv_imp")
                with c2:
                    st.markdown("**What-if: predict a booking's failure risk**")
                    w1, w2 = st.columns(2)
                    vt_ = w1.selectbox("Vehicle type", mdl["vehicles"], key="adv_wi_v")
                    pk_ = w2.selectbox("Pickup zone", mdl["top"] + ["Other"], key="adv_wi_p")
                    w3, w4 = st.columns(2)
                    wd_ = w3.selectbox("Weekday", mdl["weekdays"], key="adv_wi_d")
                    hr_ = w4.slider("Hour", 0, 23, 18, key="adv_wi_h")
                    row = pd.DataFrame([{"Vehicle_Type": vt_, "Pickup": pk_, "Weekday": wd_, "Hour": hr_,
                                         "Is_Weekend": int(wd_ in ("Saturday", "Sunday"))}])
                    prob = float(mdl["model"].predict_proba(row)[0, 1]) * 100
                    gauge = go.Figure(go.Indicator(
                        mode="gauge+number+delta", value=prob, number={"suffix": "%"},
                        delta={"reference": mdl["base_rate"] * 100, "suffix": " pts vs average", "increasing": {"color": "#E84393"},
                               "decreasing": {"color": "#2ECC71"}},
                        gauge={"axis": {"range": [0, 100]}, "bar": {"color": "#0096C7"},
                               "steps": [{"range": [0, 30], "color": "#DCFCE7"}, {"range": [30, 60], "color": "#FEF3C7"},
                                         {"range": [60, 100], "color": "#FEE2E2"}]}))
                    gauge.update_layout(title="Predicted failure probability")
                    show(style(gauge, legend=False, height=300), "adv_gauge")
                hrs = pd.DataFrame([{"Vehicle_Type": vt_, "Pickup": pk_, "Weekday": wd_, "Hour": h,
                                     "Is_Weekend": int(wd_ in ("Saturday", "Sunday"))} for h in range(24)])
                hrs["Failure risk %"] = (mdl["model"].predict_proba(hrs)[:, 1] * 100).round(1)
                fig = px.line(hrs, x="Hour", y="Failure risk %", markers=True,
                              title=f"Failure risk by hour: {vt_}, {pk_}, {wd_}")
                fig.add_hline(y=mdl["base_rate"] * 100, line_dash="dot", line_color="#94A3B8", annotation_text="average")
                show(style(fig, legend=False, height=300), "adv_risk_line")
                if mdl["auc"] < 0.58:
                    tip(f"ROC-AUC is only <b>{mdl['auc']:.2f}</b> (0.5 = random). Booking-time attributes alone barely predict "
                        "failure, so cancellations are driven by factors not captured here (driver availability, traffic, "
                        "customer intent). The honest conclusion: collect supply-side data to improve fulfilment.")
                else:
                    tip(f"The model separates failing from successful bookings with ROC-AUC <b>{mdl['auc']:.2f}</b>. "
                        f"<b>{imp.iloc[0]['Feature']}</b> is the strongest driver of risk. Use these scores to pre-assign "
                        "drivers or add incentives for high-risk requests.")

# --------------------------------------------------------------------------- #
# 6. SQL live playground
# --------------------------------------------------------------------------- #
with tabs[6]:
    st.subheader("🧪 SQL Live Playground")
    st.caption("Write SQL and run it live against the cleaned `ola_rides` table. Read-only, single statement, "
               f"{PG_TIMEOUT_S:.0f}s time limit. Press **Run query** to execute.")
    st.session_state.setdefault("pg_sql", PG_DEFAULT_SQL)
    st.session_state.setdefault("pg_history", [])

    schema, n_rows = schema_info()
    m1, m2, m3 = st.columns(3)
    m1.metric("Table", "ola_rides")
    m2.metric("Rows", f"{n_rows:,}")
    m3.metric("Columns", len(schema))
    with st.expander("📚 Schema & sample rows"):
        sc, sr = st.columns([1, 2])
        sc.dataframe(schema, width="stretch", hide_index=True, height=360)
        sr.dataframe(analysis_query("SELECT * FROM ola_rides", 8), width="stretch", hide_index=True)

    t1, t2 = st.columns([3, 1])
    t1.selectbox("Start from a template", [""] + list(SQL_LIBRARY), key="pg_template",
                 format_func=lambda x: x or "Choose a template (optional)…", on_change=_load_template)
    row_cap = t2.select_slider("Max rows", [100, 500, 1000, 5000], value=1000)

    st.text_area("SQL editor", key="pg_sql", height=220)
    b1, b2, _ = st.columns([1, 1.4, 4])
    run = b1.button("▶ Run query", type="primary")
    explain = b2.checkbox("Show query plan (EXPLAIN)")

    if run:
        q = st.session_state["pg_sql"]
        err = validate_sql(q)
        if err:
            st.error(err)
        else:
            try:
                res, ms, trunc = run_playground_query(q, row_cap, explain)
                st.session_state["pg_result"] = dict(res=res, ms=ms, trunc=trunc, explain=explain, q=q)
                hist = st.session_state["pg_history"]
                if not hist or hist[0]["sql"] != q:
                    hist.insert(0, dict(sql=q, rows=len(res), ms=ms))
                    del hist[10:]
            except sqlite3.OperationalError as e:
                msg = str(e)
                st.error("Query stopped: it exceeded the time limit. Add a WHERE or LIMIT clause."
                         if "interrupted" in msg.lower() else f"SQL error: {msg}")
            except Exception as e:
                st.error(f"Query error: {e}")

    out = st.session_state.get("pg_result")
    if out:
        res = out["res"]
        r1, r2, r3 = st.columns(3)
        r1.metric("Rows returned", f"{len(res):,}")
        r2.metric("Columns", len(res.columns))
        r3.metric("Run time", f"{out['ms']:.0f} ms")
        if out["trunc"]:
            st.warning(f"Result capped at {len(res):,} rows. Raise “Max rows” or add a LIMIT / WHERE clause.")
        if out["explain"]:
            st.caption("Query plan (SQLite EXPLAIN QUERY PLAN)")
        term = st.text_input("🔎 Search within results", "", key="pg_term")
        view = res
        if term:
            view = res[res.astype(str).apply(lambda col: col.str.contains(term, case=False, na=False)).any(axis=1)]
        st.dataframe(view, width="stretch", hide_index=True)
        csv_button(view, "playground_result", "dl_pg")
        if not out["explain"]:
            with st.expander("📈 Chart this result"):
                auto_chart(res, "pg_auto")

    if st.session_state["pg_history"]:
        with st.expander("🕘 Recent queries"):
            for i, h in enumerate(st.session_state["pg_history"]):
                hc1, hc2 = st.columns([6, 1])
                hc1.code(h["sql"], language="sql")
                hc2.caption(f"{h['rows']:,} rows · {h['ms']:.0f} ms")
                hc2.button("↩ Load", key=f"pg_hist_{i}", on_click=_load_pg_sql, args=(h["sql"],))

# --------------------------------------------------------------------------- #
# 6b. SQL analysis
# --------------------------------------------------------------------------- #
with tabs[7]:
    st.subheader("📑 SQL Analysis")
    st.caption("Every number below is produced live by SQL on the full dataset (not affected by the sidebar filters). "
               "Each analysis shows the query, its result, a chart and the business takeaway.")

    hl = analysis_query(
        """SELECT COUNT(*)                                                     AS bookings,
       ROUND(100.0 * SUM(Is_Success) / COUNT(*), 2)                AS success_rate_pct,
       SUM(CASE WHEN Is_Success = 1 THEN Booking_Value ELSE 0 END) AS revenue,
       ROUND(AVG(CASE WHEN Is_Success = 1 THEN Ride_Distance END), 2) AS avg_km,
       ROUND(AVG(Customer_Rating), 2)                              AS cust_rating,
       ROUND(AVG(Driver_Ratings), 2)                               AS drv_rating
FROM ola_rides""", 1,
    ).iloc[0]
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total bookings", f"{int(hl['bookings']):,}")
    k2.metric("Success rate", f"{hl['success_rate_pct']:.2f}%")
    k3.metric("Successful revenue", inr(float(hl["revenue"])))
    k4.metric("Avg ride distance", f"{hl['avg_km']:.1f} km")
    k5.metric("Avg rating (cust / driver)", f"{hl['cust_rating']:.2f} / {hl['drv_rating']:.2f}")

    sub = st.tabs(["💼 Business analysis (B1–B7)", "✅ Required questions (Q1–Q10)", "🧠 SQL skills"])
    with sub[0]:
        for title, item in SQL_LIBRARY.items():
            if title.startswith("B"):
                render_analysis(title, item, title.split(" ")[0].lower())
    with sub[1]:
        st.info("Q1 and Q10 return many rows, so only a 100-row preview is shown. Use the Playground for the full result.")
        for title, item in SQL_LIBRARY.items():
            if title.startswith("Q"):
                render_analysis(title, item, title.split(" ")[0].lower(), preview=100)
    with sub[2]:
        st.markdown("#### SQL techniques demonstrated")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Foundations (Q1–Q10)**")
            for sk in SQL_SKILLS["Q"]:
                st.markdown(f"- {sk}")
        with c2:
            st.markdown("**Advanced (B1–B7)**")
            for sk in SQL_SKILLS["B"]:
                st.markdown(f"- {sk}")
        st.markdown("<div class='insight'>💡 Pipeline: raw CSV → cleaned SQLite/MySQL table → SQL insights → "
                    "Power BI → this Streamlit app. The same queries exist in MySQL form in "
                    "<code>sql/ola_ride_insights_mysql.sql</code>.</div>", unsafe_allow_html=True)

# --------------------------------------------------------------------------- #
# 7. Booking search
# --------------------------------------------------------------------------- #
with tabs[8]:
    st.subheader("Booking search")
    st.caption("Searches within the sidebar-filtered bookings.")
    a, b, c3 = st.columns(3)
    q_id = a.text_input("Booking ID or Customer ID contains")
    q_loc = b.text_input("Pickup / drop location contains")
    fare = c3.slider("Booking value (₹)", int(f["Booking_Value"].min()), int(f["Booking_Value"].max()),
                     (int(f["Booking_Value"].min()), int(f["Booking_Value"].max())))
    sr = f[f["Booking_Value"].between(*fare)]
    if q_id:
        sr = sr[sr["Booking_ID"].str.contains(q_id, case=False, na=False) | sr["Customer_ID"].str.contains(q_id, case=False, na=False)]
    if q_loc:
        sr = sr[sr["Pickup_Location"].str.contains(q_loc, case=False, na=False) | sr["Drop_Location"].str.contains(q_loc, case=False, na=False)]
    st.write(f"**{len(sr):,}** bookings found")
    cols = ["Booking_ID", "Customer_ID", "Date", "Time", "Vehicle_Type", "Pickup_Location", "Drop_Location",
            "Booking_Status", "Booking_Value", "Payment_Method", "Ride_Distance", "Driver_Ratings", "Customer_Rating"]
    st.dataframe(sr[cols].head(1000), width="stretch", hide_index=True)
    csv_button(sr[cols], "booking_search", "dl_search")

# --------------------------------------------------------------------------- #
# 8. Power BI
# --------------------------------------------------------------------------- #
with tabs[9]:
    st.subheader("Power BI dashboard")
    url = ""
    try:
        url = st.secrets.get("POWERBI_EMBED_URL", "")
    except Exception:
        pass
    url = url or os.environ.get("POWERBI_EMBED_URL", "")
    if not url:
        url = st.text_input(
            "Power BI embed URL",
            placeholder="https://app.powerbi.com/view?r=...",
            help="Power BI Service → File → Embed report → Publish to web (public). Or set POWERBI_EMBED_URL in Streamlit secrets.",
        )
    if url.startswith("https://app.powerbi.com/"):
        st.iframe(url, height=720) if hasattr(st, "iframe") else components.iframe(url, height=720)
    else:
        st.info("Live embed not configured yet. Showing the five published dashboard pages. "
                "Add the 'Publish to web' link in Streamlit secrets (`POWERBI_EMBED_URL`) to embed the interactive report here.")
    pages = {
        "Overall Dashboard": "Overall_Dashboard.png",
        "Vehicle Type Analysis": "Vehicile_Type_Analysis.png",
        "Revenue Analysis": "Revenue_Analysis.png",
        "Cancellation Analysis": "Cancellation_Analysis.png",
        "Ratings Analysis": "Rating_Analysis.png",
    }
    with st.expander("Power BI report pages (screenshots)", expanded=not url):
        pt = st.tabs(list(pages))
        for t, (name, fn) in zip(pt, pages.items()):
            with t:
                if (ASSETS / fn).exists():
                    st.image(str(ASSETS / fn), width="stretch")

# --------------------------------------------------------------------------- #
# 9. Insights
# --------------------------------------------------------------------------- #
with tabs[10]:
    st.subheader("Key insights & recommendations")
    st.caption("Computed live from the current filter selection.")
    hrs = f.groupby("Hour").size()
    vsr = f.groupby("Vehicle_Type")["Is_Success"].mean() * 100
    canc = f[f["Cancel_By"].notna()]
    top_reason = canc.groupby(["Cancel_By", "Cancel_Reason"]).size().sort_values(ascending=False)
    cash = pct(s.loc[s["Payment_Method"] == "Cash", "Booking_Value"].sum(), s["Booking_Value"].sum())
    wkd = f.groupby("Is_Weekend").apply(lambda x: len(x) / x["Date"].nunique(), include_groups=False)
    lost = float(f["Booking_Value"].sum()) - K["revenue"]
    driver_share = pct((f["Cancel_By"] == "Driver").sum(), len(canc))

    ins = [
        f"<b>{K['cancel_rate']:.1f}%</b> of bookings fail to convert, leaving <b>{inr(lost)}</b> of booking value unrealised.",
        f"Drivers cause <b>{driver_share:.0f}%</b> of cancellations, which makes supply-side reliability the bigger lever than customer behaviour.",
    ]
    if len(top_reason):
        (who, why), n = top_reason.index[0], top_reason.iloc[0]
        ins.append(f"Largest single cancellation cause: <b>{why}</b> ({who.lower()}-side, {n:,} cases).")
    ins.append(f"Demand peaks at <b>{hrs.idxmax()}:00</b> ({hrs.max():,} bookings) and is almost flat across the day.")
    ins.append(f"Best success rate: <b>{vsr.idxmax()}</b> ({vsr.max():.1f}%); weakest: <b>{vsr.idxmin()}</b> ({vsr.min():.1f}%). The spread is narrow, so the problem is systemic rather than vehicle-specific.")
    ins.append(f"<b>Cash</b> accounts for <b>{cash:.0f}%</b> of realised revenue, so digital adoption still has headroom.")
    if len(s):
        ins.append(f"Average customer rating is <b>{s['Customer_Rating'].mean():.2f}</b> and driver rating <b>{s['Driver_Ratings'].mean():.2f}</b>. Satisfaction is stable, so fixing conversion matters more than service quality.")
    if len(wkd) == 2:
        ins.append(f"Weekdays average <b>{wkd[0]:,.0f}</b> bookings per day against <b>{wkd[1]:,.0f}</b> on weekends.")
    for t in ins:
        st.markdown(f"<div class='insight'>📌 {t}</div>", unsafe_allow_html=True)

    st.markdown("#### Recommended actions")
    for t in [
        "<b>Cut driver cancellations:</b> vehicle health checks, driver incentives for accepted rides and penalties for repeat cancels.",
        "<b>Cut 'driver not moving' cancels:</b> improve ETA accuracy and dispatch to the nearest driver to shorten pickup time.",
        "<b>Lift conversion in weak hours:</b> use hour-level success rates to schedule supply incentives where fulfilment dips.",
        "<b>Grow digital payments:</b> UPI cashback and wallet nudges to shift the cash share down.",
        "<b>Reduce incomplete rides:</b> targeted fleet maintenance for breakdowns and clearer in-app trip-change flows.",
    ]:
        st.markdown(f"<div class='reco'>✅ {t}</div>", unsafe_allow_html=True)

st.markdown(
    "<div class='footer'>Ola Ride Insights · SQL → Power BI → Streamlit · Built by P Suman Sangeet</div>",
    unsafe_allow_html=True,
)