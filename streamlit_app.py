# streamlit_app.py
import streamlit as st
import pandas as pd
from glob import glob
import plotly.express as px

st.set_page_config(page_title="UK Carbon Intensity", layout="wide")
st.title("UK Carbon Intensity – Mini Dashboard")

# --- locate latest processed CSV (supports both layouts) ---
candidates = sorted(glob("data/processed/uk_ci_processed_*.csv")) \
          or sorted(glob("notebooks/data/processed/uk_ci_processed_*.csv"))

if not candidates:
    st.warning(
        "No processed CSV found. Run:\n\n"
        "`python scripts/fetch_ci.py --days 30`"
    )
    st.stop()

latest_csv = candidates[-1]
df = pd.read_csv(latest_csv, parse_dates=["from_utc","to_utc"])
df["ci"] = df["actual_gco2_per_kwh"].fillna(df["forecast_gco2_per_kwh"])
df = df.sort_values("from_utc").reset_index(drop=True)
st.caption(f"Using: `{latest_csv}` — rows: {len(df):,}")

# --- KPIs ---
latest_ci = float(df.iloc[-1]["ci"])
daily = df.set_index("from_utc")["ci"].resample("D").mean()
roll7 = daily.rolling(7, min_periods=1).mean().iloc[-1]
c1, c2 = st.columns(2)
c1.metric("Latest half-hour (gCO₂/kWh)", f"{latest_ci:.0f}")
c2.metric("7-day average (gCO₂/kWh)", f"{roll7:.0f}")

# --- Daily trend ---
fig_daily = px.line(daily, labels={"value":"gCO₂/kWh","index":"Date (UTC)"},
                    title="Daily Average & 7-day Rolling")
fig_daily.add_scatter(x=daily.index, y=daily.rolling(7, min_periods=1).mean(),
                      name="7-day rolling")
st.plotly_chart(fig_daily, use_container_width=True)

# --- Hour-of-day profile ---
df["hour"] = df["from_utc"].dt.hour
hod = df.groupby("hour")["ci"].mean().reset_index()
fig_hod = px.line(hod, x="hour", y="ci",
                  labels={"hour":"Hour (UTC)","ci":"gCO₂/kWh"},
                  title="Average Carbon Intensity by Hour of Day (UTC)")
fig_hod.update_traces(mode="lines+markers")
st.plotly_chart(fig_hod, use_container_width=True)
