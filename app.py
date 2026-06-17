import streamlit as st


# ============================================================
# CLEAN FUND SCREENER DISPLAY TABLES
# Hide quartile / percentile / vintage benchmark columns
# ============================================================

_ORIGINAL_ST_DATAFRAME_CLEAN = st.dataframe

def _clean_screener_dataframe(data=None, *args, **kwargs):
    try:
        import pandas as _pd

        if isinstance(data, _pd.DataFrame):
            hidden_keywords = [
                "quartile",
                "percentile",
                "vintage_benchmark_label",
                "benchmark_result",
                "peer_funds",
            ]

            cols_to_hide = []
            for col in data.columns:
                col_lower = str(col).lower()
                if any(word in col_lower for word in hidden_keywords):
                    cols_to_hide.append(col)

            data = data.drop(columns=cols_to_hide, errors="ignore")

    except Exception:
        pass

    return _ORIGINAL_ST_DATAFRAME_CLEAN(data, *args, **kwargs)

st.dataframe = _clean_screener_dataframe

# Also clean data editor if the app uses it anywhere
if hasattr(st, "data_editor"):
    _ORIGINAL_ST_DATA_EDITOR_CLEAN = st.data_editor

    def _clean_screener_data_editor(data=None, *args, **kwargs):
        try:
            import pandas as _pd

            if isinstance(data, _pd.DataFrame):
                hidden_keywords = [
                    "quartile",
                    "percentile",
                    "vintage_benchmark_label",
                    "benchmark_result",
                    "peer_funds",
                ]

                cols_to_hide = []
                for col in data.columns:
                    col_lower = str(col).lower()
                    if any(word in col_lower for word in hidden_keywords):
                        cols_to_hide.append(col)

                data = data.drop(columns=cols_to_hide, errors="ignore")

        except Exception:
            pass

        return _ORIGINAL_ST_DATA_EDITOR_CLEAN(data, *args, **kwargs)

    st.data_editor = _clean_screener_data_editor

# ============================================================
# END CLEAN FUND SCREENER DISPLAY TABLES
# ============================================================






import pandas as pd
import sqlite3
import requests
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

from core.gpt_copilot_helpers import ask_gpt_allocator
from web_research_helpers import get_manager_web_research

st.set_page_config(page_title="Allocator Intelligence Platform", layout="wide")

API_BASE = "https://api.lp-data.com"
DB_FILE = "institutional_funds.db"
LP_FILE = "lp_funds_all_with_report_evidence.csv"
MATCH_FILE = "unified_fund_matches.csv"
INSTITUTIONAL_ONLY_FILE = "institutional_only_funds.csv"
RECOMMENDATIONS_FILE = "investment_recommendations.csv"
BENCHMARK_CONTEXT_FILE = "benchmark_quartile_context.csv"


# ============================================================
# LOAD DATA
# ============================================================

@st.cache_data
def load_institutional_only_funds():
    try:
        inst = pd.read_csv(INSTITUTIONAL_ONLY_FILE)
    except Exception:
        return pd.DataFrame()

    inst = inst.rename(columns={
        "irr_percent": "irr_max",
        "tvpi": "tvpi_max",
        "dpi": "dpi_max"
    })

    if "fund_id" not in inst.columns:
        inst["fund_id"] = "inst_only_" + inst.index.astype(str)

    inst["data_source"] = "Institutional Only"
    inst["suspect_data"] = False

    for col in ["irr_max", "tvpi_max", "dpi_max", "vintage_year"]:
        if col in inst.columns:
            inst[col] = pd.to_numeric(inst[col], errors="coerce")

    return inst


@st.cache_data
def load_lp_data():
    df = pd.read_csv(LP_FILE)

    if "name" in df.columns and "fund_name" not in df.columns:
        df = df.rename(columns={"name": "fund_name"})

    for col in ["irr_max", "tvpi_max", "dpi_max", "vintage_year", "final_close_size_usd"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["data_source"] = "LP Data"

    df["suspect_data"] = (
        (df["tvpi_max"] > 10) |
        (df["dpi_max"] > 10) |
        (df["irr_max"] > 1)
    )

    return df


@st.cache_data
def load_matches():
    try:
        matches = pd.read_csv(MATCH_FILE)
    except Exception:
        return pd.DataFrame()

    for col in matches.columns:
        if any(x in col for x in ["score", "irr", "tvpi", "dpi", "quarter_count", "change", "trend"]):
            matches[col] = pd.to_numeric(matches[col], errors="coerce")

    return matches


@st.cache_data
def load_database():
    conn = sqlite3.connect(DB_FILE)

    try:
        timeseries = pd.read_sql("SELECT * FROM institutional_fund_timeseries", conn)
    except Exception:
        timeseries = pd.DataFrame()

    try:
        inst_summary = pd.read_sql("SELECT * FROM institutional_fund_timeseries_summary", conn)
    except Exception:
        inst_summary = pd.DataFrame()

    try:
        inst_raw = pd.read_sql("SELECT * FROM institutional_fund_performance_deduped", conn)
    except Exception:
        inst_raw = pd.DataFrame()

    try:
        manager_profiles = pd.read_sql("SELECT * FROM manager_profiles", conn)
    except Exception:
        manager_profiles = pd.DataFrame()

    conn.close()

    return timeseries, inst_summary, inst_raw, manager_profiles


@st.cache_data
def load_report_pipeline_csvs():
    try:
        raw_reports = pd.read_csv("app_raw_reports.csv")
    except Exception:
        raw_reports = pd.DataFrame()

    try:
        ready_reports = pd.read_csv("app_ready_reports.csv")
    except Exception:
        ready_reports = pd.DataFrame()

    return raw_reports, ready_reports


@st.cache_data
def load_investment_recommendations():
    try:
        recs = pd.read_csv(RECOMMENDATIONS_FILE)
    except Exception:
        return pd.DataFrame()

    for col in [
        "irr_max",
        "tvpi_max",
        "dpi_max",
        "vintage_year",
        "vintage_age",
        "rank_score",
        "institutional_trend_score",
        "match_score",
        "red_flag_count",
    ]:
        if col in recs.columns:
            recs[col] = pd.to_numeric(recs[col], errors="coerce")

    return recs



@st.cache_data
def load_benchmark_context():
    try:
        bench = pd.read_csv(BENCHMARK_CONTEXT_FILE)
    except Exception:
        return pd.DataFrame()

    for col in ["vintage_year", "ersri_irr_percent", "funds_invested_in"]:
        if col in bench.columns:
            bench[col] = pd.to_numeric(bench[col], errors="coerce")

    return bench


# ============================================================
# FORMAT HELPERS
# ============================================================

def fmt_pct(value):
    if pd.isna(value):
        return "N/A"
    try:
        value = float(value)
        if value <= 1:
            return f"{value * 100:.1f}%"
        return f"{value:.1f}%"
    except Exception:
        return "N/A"


def fmt_x(value):
    if pd.isna(value):
        return "N/A"
    try:
        return f"{float(value):.2f}x"
    except Exception:
        return "N/A"


def fmt_num(value):
    if pd.isna(value):
        return "N/A"
    try:
        return f"{float(value):.1f}"
    except Exception:
        return "N/A"


# ============================================================
# SCORING
# ============================================================

def calculate_rank_score(row):
    irr = row.get("irr_max", 0)
    tvpi = row.get("tvpi_max", 0)
    dpi = row.get("dpi_max", 0)

    irr = 0 if pd.isna(irr) else irr
    tvpi = 0 if pd.isna(tvpi) else tvpi
    dpi = 0 if pd.isna(dpi) else dpi

    irr_score = max(0, min((irr * 100) / 30, 1)) * 35
    tvpi_score = max(0, min(tvpi / 3, 1)) * 35
    dpi_score = max(0, min(dpi / 2, 1)) * 25

    penalty = 0

    if tvpi > 10:
        penalty += 40
    if dpi > 10:
        penalty += 40
    if irr > 1:
        penalty += 40

    return round(max(0, irr_score + tvpi_score + dpi_score - penalty), 1)


def assign_quartiles(data):
    data = data.copy()

    data["overall_benchmark_score"] = (
        data["irr_max"].fillna(0) * 100 * 0.40
        + data["tvpi_max"].fillna(0) * 10 * 0.40
        + data["dpi_max"].fillna(0) * 10 * 0.20
    )

    try:
        data["overall_quartile"] = pd.qcut(
            data["overall_benchmark_score"].rank(method="first", ascending=False),
            4,
            labels=["Q1", "Q2", "Q3", "Q4"]
        )
        data["overall_quartile"] = data["overall_quartile"].astype(str)
    except Exception:
        data["overall_quartile"] = "N/A"

    return data


# ============================================================
# LP DATA QUARTERLY HISTORY
# ============================================================

@st.cache_data(show_spinner=False)
def get_lp_holdings(fund_id):
    if str(fund_id).startswith("inst_only_"):
        return pd.DataFrame()

    url = f"{API_BASE}/funds/{fund_id}/holdings?skip=0&limit=1000"

    try:
        r = requests.get(url, timeout=30)
    except Exception:
        return pd.DataFrame()

    if r.status_code != 200:
        return pd.DataFrame()

    items = r.json().get("items", [])

    if not items:
        return pd.DataFrame()

    h = pd.DataFrame(items)

    if "as_of_date" in h.columns:
        h["as_of_date"] = pd.to_datetime(h["as_of_date"], errors="coerce")

    for col in ["net_irr", "tvpi", "dpi", "nav_usd", "commitment_usd"]:
        if col in h.columns:
            h[col] = pd.to_numeric(h[col], errors="coerce")

    return h.dropna(subset=["as_of_date"]).sort_values("as_of_date")


def clean_lp_quarterly(holdings):
    clean = holdings.groupby("as_of_date", as_index=False).agg(
        net_irr=("net_irr", "median"),
        tvpi=("tvpi", "median"),
        dpi=("dpi", "median"),
        nav_usd=("nav_usd", "sum"),
        commitment_usd=("commitment_usd", "sum"),
        lp_count=("lp_name", "nunique")
    )

    clean["net_irr_percent"] = clean["net_irr"] * 100

    clean.loc[clean["tvpi"] > 10, "tvpi"] = None
    clean.loc[clean["dpi"] > 10, "dpi"] = None
    clean.loc[clean["net_irr_percent"] > 100, "net_irr_percent"] = None
    clean.loc[clean["net_irr_percent"] < -100, "net_irr_percent"] = None

    return clean.sort_values("as_of_date")


# ============================================================
# MEMO
# ============================================================

def make_allocator_memo(selected, has_inst, manager_row=None):
    fund_name = selected.get("fund_name", "")
    manager = selected.get("manager_name", "")
    lp_irr = selected.get("irr_max", 0) * 100
    lp_tvpi = selected.get("tvpi_max", 0)
    lp_dpi = selected.get("dpi_max", 0)
    score = selected.get("rank_score", 0)
    quartile = selected.get("overall_quartile", "N/A")
    source = selected.get("data_source", "N/A")

    memo = f"""
### Allocator Memo

**{fund_name}** is managed by **{manager}**.

Source: **{source}**

Based on available data, the fund currently shows **{lp_irr:.1f}% IRR**, **{lp_tvpi:.2f}x TVPI**, and **{lp_dpi:.2f}x DPI**.

Internal Score: **{score:.1f}/100**  
Overall Quartile: **{quartile}**

**Quartile Meaning**
- **Q1** = Top 25%
- **Q2** = 25%–50%
- **Q3** = 50%–75%
- **Q4** = Bottom 25%
"""

    if manager_row is not None and not manager_row.empty:
        r = manager_row.iloc[0]

        memo += f"""

### Manager Profile

**{manager}** has **{int(r.get("lp_fund_count", 0))} funds** in the LP dataset.

Manager-level metrics:
- Average LP IRR: **{fmt_pct(r.get("avg_lp_irr", None))}**
- Average LP TVPI: **{fmt_x(r.get("avg_lp_tvpi", None))}**
- Average LP DPI: **{fmt_x(r.get("avg_lp_dpi", None))}**
- Institutional matches: **{int(r.get("institutional_match_count", 0)) if pd.notna(r.get("institutional_match_count", None)) else 0}**
- Average institutional trend score: **{fmt_num(r.get("avg_trend_score", None))}**
- Manager percentile: **{fmt_pct(r.get("manager_percentile", None))}**
- Manager quartile: **{r.get("manager_quartile", "N/A")}**
"""

    if has_inst:
        memo += f"""
### Institutional Validation

This fund matched to institutional pension-report data.

Institutional match:
- Institutional fund name: **{selected.get("institutional_fund_name", "")}**
- Match score: **{selected.get("match_score", 0):.2f}**
- Latest institutional TVPI: **{selected.get("institutional_latest_tvpi", 0):.2f}x**
- Latest institutional IRR: **{selected.get("institutional_latest_irr", 0):.1f}%**
- Quarters observed: **{int(selected.get("institutional_quarter_count", 0)) if pd.notna(selected.get("institutional_quarter_count", None)) else 0}**
- Total TVPI change: **{selected.get("institutional_tvpi_change_total", 0):.2f}x**
- Institutional trend score: **{selected.get("institutional_trend_score", 0):.1f}**
"""
    else:
        memo += """

### Institutional Validation

No institutional pension-report match was found yet, or this fund is from the institutional-only dataset.
"""

    return memo


# ============================================================
# MAIN DATA LOAD
# ============================================================

df = load_lp_data()
institutional_only_df = load_institutional_only_funds()

if not institutional_only_df.empty:
    needed_cols = df.columns.tolist()

    for col in needed_cols:
        if col not in institutional_only_df.columns:
            institutional_only_df[col] = pd.NA

    institutional_only_df = institutional_only_df[needed_cols]
    df = pd.concat([df, institutional_only_df], ignore_index=True)

matches = load_matches()
timeseries, inst_summary, inst_raw, manager_profiles = load_database()
raw_reports, ready_reports = load_report_pipeline_csvs()
recommendations = load_investment_recommendations()
benchmark_context = load_benchmark_context()

df["rank_score"] = df.apply(calculate_rank_score, axis=1)
df = assign_quartiles(df)


# ============================================================
# APP HEADER
# ============================================================







st.title("Allocator Intelligence Platform")
st.caption("Unified LP Data + institutional pension-report intelligence + GPT allocator copilot.")

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Unified Fund Screener",
    "Manager Intelligence",
    "GPT Allocator Copilot",
    "Data Sources",
    "Investment Recommendations",
    "Benchmark / Quartile Context"
])


# ============================================================
# TAB 1 — FUND SCREENER
# ============================================================

with tab1:
    st.subheader("Unified Fund Screener")

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        sub_strategy = st.selectbox(
            "Sub Strategy",
            ["All"] + sorted(df["sub_strategy"].dropna().unique()),
            key="fund_screener_sub_strategy"
        )

    with c2:
        geography = st.selectbox(
            "Geography",
            ["All"] + sorted(df["geography"].dropna().unique()),
            key="fund_screener_geography"
        )

    with c3:
        vintage_filter = st.selectbox(
            "Vintage",
            ["All"] + sorted(df["vintage_year"].dropna().astype(int).unique(), reverse=True),
            key="fund_screener_vintage"
        )

    with c4:
        quartile_filter = st.selectbox(
            "Overall Score Quartile",
            ["All", "Q1", "Q2", "Q3", "Q4"],
            key="fund_screener_quartile"
        )

    min_irr = st.slider("Minimum IRR (%)", 0.0, 70.0, 10.0, 0.5, key="fund_screener_min_irr")
    min_tvpi = st.slider("Minimum TVPI", 0.0, 10.0, 1.2, 0.1, key="fund_screener_min_tvpi")
    min_dpi = st.slider("Minimum DPI", 0.0, 10.0, 0.5, 0.1, key="fund_screener_min_dpi")

    c6, c7 = st.columns(2)

    with c6:
        only_with_inst = st.checkbox(
            "Only show funds with institutional match",
            value=False,
            key="fund_screener_only_inst"
        )

    with c7:
        hide_suspect = st.checkbox(
            "Hide suspicious outliers",
            value=True,
            key="fund_screener_hide_suspect"
        )

    filtered = df.copy()

    if hide_suspect:
        filtered = filtered[filtered["suspect_data"] == False]

    if sub_strategy != "All":
        filtered = filtered[filtered["sub_strategy"] == sub_strategy]

    if geography != "All":
        filtered = filtered[filtered["geography"] == geography]

    if vintage_filter != "All":
        filtered = filtered[filtered["vintage_year"] == vintage_filter]

    if quartile_filter != "All":
        filtered = filtered[filtered["overall_quartile"] == quartile_filter]

    filtered = filtered[
        (filtered["irr_max"].fillna(0) * 100 >= min_irr) &
        (filtered["tvpi_max"].fillna(0) >= min_tvpi) &
        (filtered["dpi_max"].fillna(0) >= min_dpi)
    ]

    if not matches.empty:
        filtered = filtered.merge(
            matches,
            left_on="fund_id",
            right_on="lp_fund_id",
            how="left"
        )

    if only_with_inst:
        if "canonical_fund_id" in filtered.columns:
            filtered = filtered[filtered["canonical_fund_id"].notna()]
        else:
            filtered = filtered.iloc[0:0]

    sort_cols = []
    ascending = []

    if "overall_quartile" in filtered.columns:
        sort_cols.append("overall_quartile")
        ascending.append(True)

    if "institutional_trend_score" in filtered.columns:
        sort_cols.append("institutional_trend_score")
        ascending.append(False)

    if "rank_score" in filtered.columns:
        sort_cols.append("rank_score")
        ascending.append(False)

    if sort_cols:
        filtered = filtered.sort_values(
            sort_cols,
            ascending=ascending,
            na_position="last"
        )

    
    # Vintage Benchmark Quartile filter
    if "overall_vintage_quartile" in filtered.columns:
        vintage_benchmark_quartile_filter = st.selectbox(
            "Vintage Benchmark Quartile",
            ["All", "Q1", "Q2", "Q3", "Q4"],
            key="vintage_benchmark_quartile_filter"
        )

        if vintage_benchmark_quartile_filter != "All":
            filtered = filtered[
                filtered["overall_vintage_quartile"].astype(str) == vintage_benchmark_quartile_filter
            ]
    else:
        vintage_benchmark_quartile_filter = "All"

    if filtered.empty:
        st.warning("No funds match these filters.")
        st.stop()

    filtered["open_label"] = (
        filtered["fund_name"].fillna("Unknown Fund")
        + " | "
        + filtered["manager_name"].fillna("Unknown Manager")
        + " | "
        + filtered["data_source"].fillna("Unknown")
        + " | "
        + filtered["overall_quartile"].fillna("N/A")
        + " | Score "
        + filtered["rank_score"].round(1).astype(str)
    )

    selected_label = st.selectbox(
        "Open fund detail",
        filtered["open_label"].tolist(),
        key="fund_screener_open_fund"
    )

    selected = filtered[filtered["open_label"] == selected_label].iloc[0]
    fund_id = selected["fund_id"]
    has_inst = pd.notna(selected.get("canonical_fund_id"))

    table_cols = [
        "data_source",
        "rank_score",
        "overall_quartile",
        "overall_vintage_quartile",
        "vintage_benchmark_label",
        "irr_vintage_quartile",
        "tvpi_vintage_quartile",
        "dpi_vintage_quartile",
        "irr_vintage_percentile",
        "tvpi_vintage_percentile",
        "dpi_vintage_percentile",

        "fund_name",
        "manager_name",
        "sub_strategy",
        "geography",
        "vintage_year",
        "irr_max",
        "tvpi_max",
        "dpi_max",
    ]

    extra_cols = [
    "institutional_fund_name",
    "institutional_quarter_count",
    "institutional_latest_tvpi",
    "institutional_latest_irr",
    "institutional_tvpi_change_total",
    "institutional_trend_score",
    "match_score",

    "report_evidence_count",
    "best_report_confidence",
    "best_report_evidence_score",
    "report_sources",
    "report_urls",
    "report_mentions",
]
        
    

    table_cols = [c for c in table_cols + extra_cols if c in filtered.columns]

    st.dataframe(filtered[table_cols], width="stretch", height=360)

    st.divider()

    st.markdown(f"## {selected.get('fund_name', '')}")
    st.caption(f"Manager: {selected.get('manager_name', '')}")
    st.write(f"Source: **{selected.get('data_source', 'N/A')}**")

    manager_name = selected.get("manager_name", "")
    manager_row = pd.DataFrame()

    if not manager_profiles.empty and manager_name:
        manager_row = manager_profiles[
            manager_profiles["manager_name"].astype(str).str.lower() == str(manager_name).lower()
        ]

    k1, k2, k3, k4, k5, k6, k7 = st.columns(7)

    k1.metric("Score", f"{selected.get('rank_score', 0):.1f}")
    k2.metric("Overall Score Quartile", selected.get("overall_quartile", "N/A"))
    k3.metric("Vintage", int(selected["vintage_year"]) if pd.notna(selected["vintage_year"]) else "N/A")
    k4.metric("IRR", f"{selected.get('irr_max', 0) * 100:.1f}%")
    k5.metric("TVPI", f"{selected.get('tvpi_max', 0):.2f}x")
    k6.metric("DPI", f"{selected.get('dpi_max', 0):.2f}x")

    if has_inst:
        k7.metric("Inst Trend", f"{selected.get('institutional_trend_score', 0):.1f}")
    else:
        k7.metric("Inst Trend", "No match")

    # ========================================================
    # SELECTED FUND VS VINTAGE BENCHMARK
    # ========================================================

    st.divider()
# Selected Fund vs Vintage Benchmark section removed from front page.


    st.subheader("AI Investment Memo")

    if st.button("Generate Full AI Memo", key="fund_screener_generate_memo"):
        question = f"""
Give a detailed institutional allocator memo.

Fund: {selected.get('fund_name','')}
Manager: {selected.get('manager_name','')}
Source: {selected.get('data_source','')}

DATABASE PERFORMANCE FACTS:
- IRR: {selected.get('irr_max',0)*100:.1f}%
- TVPI: {selected.get('tvpi_max',0):.2f}x
- DPI: {selected.get('dpi_max',0):.2f}x
- Score: {selected.get('rank_score',0):.1f}
- Quartile: {selected.get('overall_quartile','N/A')}
- Institutional Trend Score: {selected.get('institutional_trend_score', 'N/A')}

Write:
1. Executive Summary
2. Fund Overview
3. Manager Assessment
4. Performance Analysis
5. Quartile / Benchmark Interpretation
6. Strengths
7. Risks
8. Diligence Questions
9. Final Allocator View
"""

        with st.spinner("Researching manager on the web..."):
            web_research = get_manager_web_research(
                selected.get("manager_name", "")
            )

        question = question + f"""

WEB RESEARCH ON MANAGER:

{web_research}

Instructions:

Use BOTH:
1. LP Data / database performance metrics
2. Institutional pension-report data
3. Web research

Structure the memo as:

1. Executive Summary
2. Firm Background
3. Team & Leadership
4. Strategy Overview
5. Fund Performance Analysis
6. Benchmark / Quartile Analysis
7. Recent Fundraising & News
8. Strengths
9. Risks
10. Due Diligence Questions
11. Final Allocator Recommendation

Clearly distinguish:
- Database facts
- Web research
- Allocator opinion
"""

        with st.spinner("Generating allocator memo..."):
            memo = ask_gpt_allocator(question)

        st.markdown(memo)

        # ========================================================
        # Vintage Benchmark Memo Add-on
        # ========================================================

        st.markdown("### Vintage Benchmark")

        memo_selected_vintage = selected.get("vintage_year", None)

        if pd.isna(memo_selected_vintage):
            st.warning("No vintage benchmark available because this fund has no vintage year.")
        else:
            memo_selected_vintage = int(memo_selected_vintage)

            memo_peer_df = df.copy()

            memo_peer_df["vintage_year"] = pd.to_numeric(
                memo_peer_df["vintage_year"],
                errors="coerce"
            )

            for col in ["irr_max", "tvpi_max", "dpi_max"]:
                if col in memo_peer_df.columns:
                    memo_peer_df[col] = pd.to_numeric(memo_peer_df[col], errors="coerce")

            memo_peer_df["irr_percent"] = memo_peer_df["irr_max"].apply(
                lambda x: x * 100 if pd.notna(x) and x <= 1 else x
            )

            memo_peer_df = memo_peer_df[
                memo_peer_df["vintage_year"] == memo_selected_vintage
            ].copy()

            memo_peer_df = memo_peer_df[
                (
                    memo_peer_df["irr_percent"].isna() |
                    ((memo_peer_df["irr_percent"] >= -100) & (memo_peer_df["irr_percent"] <= 100))
                )
                &
                (
                    memo_peer_df["tvpi_max"].isna() |
                    ((memo_peer_df["tvpi_max"] >= 0) & (memo_peer_df["tvpi_max"] <= 10))
                )
                &
                (
                    memo_peer_df["dpi_max"].isna() |
                    ((memo_peer_df["dpi_max"] >= 0) & (memo_peer_df["dpi_max"] <= 10))
                )
            ]

            def memo_percentile_to_quartile(percentile):
                if pd.isna(percentile):
                    return "N/A"
                if percentile >= 75:
                    return "Q1"
                elif percentile >= 50:
                    return "Q2"
                elif percentile >= 25:
                    return "Q3"
                else:
                    return "Q4"

            def memo_quartile_to_score(quartile):
                if quartile == "Q1":
                    return 4
                elif quartile == "Q2":
                    return 3
                elif quartile == "Q3":
                    return 2
                elif quartile == "Q4":
                    return 1
                return None

            def memo_score_to_quartile(score):
                if pd.isna(score):
                    return "N/A"
                if score >= 3.5:
                    return "Q1"
                elif score >= 2.5:
                    return "Q2"
                elif score >= 1.5:
                    return "Q3"
                else:
                    return "Q4"

            def memo_score_to_label(score):
                if pd.isna(score):
                    return "Not enough data"
                if score >= 3.7:
                    return "Exceptional vs same-vintage peers"
                elif score >= 3.0:
                    return "Strong / top quartile vs same-vintage peers"
                elif score >= 2.3:
                    return "Above median vs same-vintage peers"
                elif score >= 1.7:
                    return "Below median vs same-vintage peers"
                else:
                    return "Weak vs same-vintage peers"

            def memo_metric_result(metric_name, fund_value, peer_series):
                peer_series = pd.to_numeric(peer_series, errors="coerce").dropna()

                if pd.isna(fund_value) or peer_series.empty:
                    return {
                        "metric": metric_name,
                        "fund_value": None,
                        "average": None,
                        "p75": None,
                        "percentile": None,
                        "quartile": "N/A",
                    }

                fund_value = float(fund_value)
                average = peer_series.mean()
                p75 = peer_series.quantile(0.75)
                percentile = (peer_series <= fund_value).mean() * 100
                quartile = memo_percentile_to_quartile(percentile)

                return {
                    "metric": metric_name,
                    "fund_value": fund_value,
                    "average": average,
                    "p75": p75,
                    "percentile": percentile,
                    "quartile": quartile,
                }

            memo_fund_irr = selected.get("irr_max", None)

            if pd.notna(memo_fund_irr):
                memo_fund_irr = float(memo_fund_irr)
                if memo_fund_irr <= 1:
                    memo_fund_irr = memo_fund_irr * 100

            memo_results = [
                memo_metric_result(
                    "IRR (%)",
                    memo_fund_irr,
                    memo_peer_df["irr_percent"] if "irr_percent" in memo_peer_df.columns else pd.Series(dtype=float),
                ),
                memo_metric_result(
                    "TVPI",
                    selected.get("tvpi_max", None),
                    memo_peer_df["tvpi_max"] if "tvpi_max" in memo_peer_df.columns else pd.Series(dtype=float),
                ),
                memo_metric_result(
                    "DPI",
                    selected.get("dpi_max", None),
                    memo_peer_df["dpi_max"] if "dpi_max" in memo_peer_df.columns else pd.Series(dtype=float),
                ),
            ]

            memo_result_df = pd.DataFrame(memo_results)

            memo_result_df["quartile_score"] = memo_result_df["quartile"].apply(memo_quartile_to_score)
            memo_valid_scores = memo_result_df["quartile_score"].dropna()

            if memo_valid_scores.empty:
                memo_overall_score = None
                memo_overall_quartile = "N/A"
                memo_overall_label = "Not enough data"
            else:
                memo_overall_score = memo_valid_scores.mean()
                memo_overall_quartile = memo_score_to_quartile(memo_overall_score)
                memo_overall_label = memo_score_to_label(memo_overall_score)

            def memo_format_value(metric, value):
                if pd.isna(value):
                    return "N/A"
                if metric == "IRR (%)":
                    return f"{float(value):.1f}%"
                return f"{float(value):.2f}x"

            memo_result_df["Fund Value"] = memo_result_df.apply(
                lambda r: memo_format_value(r["metric"], r["fund_value"]),
                axis=1
            )

            memo_result_df["Vintage Average"] = memo_result_df.apply(
                lambda r: memo_format_value(r["metric"], r["average"]),
                axis=1
            )

            memo_result_df["Vintage 75th Percentile"] = memo_result_df.apply(
                lambda r: memo_format_value(r["metric"], r["p75"]),
                axis=1
            )

            memo_result_df["Vintage Percentile Rank"] = memo_result_df["percentile"].apply(
                lambda x: "N/A" if pd.isna(x) else f"{x:.1f}%"
            )

            memo_display = memo_result_df[
                [
                    "metric",
                    "Fund Value",
                    "Vintage Average",
                    "Vintage 75th Percentile",
                    "Vintage Percentile Rank",
                    "quartile",
                ]
            ].rename(columns={
                "metric": "Metric",
                "quartile": "Vintage Quartile",
            })

            st.write(
                f"This fund is compared against **{len(memo_peer_df):,} LP Data funds** from vintage **{memo_selected_vintage}**."
            )

            m1, m2, m3, m4 = st.columns(4)

            memo_irr_row = memo_result_df[memo_result_df["metric"] == "IRR (%)"]
            memo_tvpi_row = memo_result_df[memo_result_df["metric"] == "TVPI"]
            memo_dpi_row = memo_result_df[memo_result_df["metric"] == "DPI"]

            if not memo_irr_row.empty:
                m1.metric("IRR Vintage Quartile", memo_irr_row.iloc[0]["quartile"], memo_irr_row.iloc[0]["Vintage Percentile Rank"])

            if not memo_tvpi_row.empty:
                m2.metric("TVPI Vintage Quartile", memo_tvpi_row.iloc[0]["quartile"], memo_tvpi_row.iloc[0]["Vintage Percentile Rank"])

            if not memo_dpi_row.empty:
                m3.metric("DPI Vintage Quartile", memo_dpi_row.iloc[0]["quartile"], memo_dpi_row.iloc[0]["Vintage Percentile Rank"])

            m4.metric("Overall Vintage Quartile", memo_overall_quartile, memo_overall_label)

            st.dataframe(memo_display, width="stretch", height=180)

            st.markdown("#### Updated Quartile Meaning")

            st.markdown("""
        - **Overall Score Quartile** = rank based on your internal scoring system.
        - **Vintage Benchmark Quartile** = rank versus LP Data funds from the same vintage year.
        - **Q1** = top 25%.
        - **Q2** = 25%–50%.
        - **Q3** = 50%–75%.
        - **Q4** = bottom 25%.
        """)

            if memo_overall_quartile == "Q1":
                st.success(f"**Vintage benchmark conclusion:** {memo_overall_quartile} — {memo_overall_label}.")
            elif memo_overall_quartile == "Q2":
                st.info(f"**Vintage benchmark conclusion:** {memo_overall_quartile} — {memo_overall_label}.")
            elif memo_overall_quartile == "Q3":
                st.warning(f"**Vintage benchmark conclusion:** {memo_overall_quartile} — {memo_overall_label}.")
            elif memo_overall_quartile == "Q4":
                st.error(f"**Vintage benchmark conclusion:** {memo_overall_quartile} — {memo_overall_label}.")
            else:
                st.warning("Vintage benchmark conclusion: not enough data.")


    else:
        memo_text = make_allocator_memo(selected, has_inst, manager_row)

        # Clean ONLY the allocator memo text.
        # Keep the memo, but remove quartile/Q1-Q4 language.
        import re as _memo_cleaner

        # Remove the single Overall Quartile line.
        memo_text = _memo_cleaner.sub(
            r"(?m)^\s*Overall Quartile:.*\n?",
            "",
            memo_text
        )

        # Remove the Quartile Meaning section and its Q1-Q4 bullets only.
        memo_text = _memo_cleaner.sub(
            r"(?s)\n?\s*Quartile Meaning\s*\n\s*[-*•]?\s*Q1\s*=.*?\n\s*[-*•]?\s*Q4\s*=.*?(?=\n\s*Institutional Validation|\Z)",
            "\n",
            memo_text
        )

        # Remove any leftover Q1/Q2/Q3/Q4 bullet lines if formatting differs.
        memo_text = _memo_cleaner.sub(
            r"(?m)^\s*[-*•]?\s*Q[1-4]\s*=.*\n?",
            "",
            memo_text
        )

        # Remove empty repeated lines.
        memo_text = _memo_cleaner.sub(r"\n{3,}", "\n\n", memo_text)

        st.markdown(memo_text)


# ============================================================
# TAB 2 — MANAGER INTELLIGENCE
# ============================================================

with tab2:
    st.subheader("Manager Intelligence")

    if manager_profiles.empty:
        st.warning("No manager_profiles table found. Run build_manager_profiles.py first.")
    else:
        managers = manager_profiles.copy()

        if "manager_quality_score" in managers.columns:
            managers = managers.sort_values("manager_quality_score", ascending=False)
        else:
            managers = managers.sort_values("manager_name")

        st.write(f"Managers profiled: **{len(managers)}**")

        selected_manager = st.selectbox(
            "Open Manager Profile",
            managers["manager_name"].dropna().astype(str).tolist(),
            key="manager_intelligence_open_manager"
        )

        profile_df = managers[managers["manager_name"].astype(str) == selected_manager]

        if profile_df.empty:
            st.warning("No profile found for this manager.")
        else:
            profile = profile_df.iloc[0]

            st.markdown(f"## {selected_manager}")

            manager_funds = df[
                df["manager_name"].astype(str).str.lower() == str(selected_manager).lower()
            ].copy()

            if not manager_funds.empty and not matches.empty and "fund_id" in manager_funds.columns:
                manager_funds = manager_funds.merge(
                    matches,
                    left_on="fund_id",
                    right_on="lp_fund_id",
                    how="left"
                )

            c1, c2, c3, c4, c5, c6 = st.columns(6)

            c1.metric(
                "LP Funds",
                int(profile.get("lp_fund_count", 0)) if pd.notna(profile.get("lp_fund_count", None)) else len(manager_funds)
            )

            c2.metric("Avg LP IRR", fmt_pct(profile.get("avg_lp_irr", None)))
            c3.metric("Avg LP TVPI", fmt_x(profile.get("avg_lp_tvpi", None)))
            c4.metric("Avg LP DPI", fmt_x(profile.get("avg_lp_dpi", None)))
            c5.metric(
                "Inst Matches",
                int(profile.get("institutional_match_count", 0)) if pd.notna(profile.get("institutional_match_count", None)) else 0
            )
            c6.metric("Overall Score Quartile", profile.get("manager_quartile", "N/A"))

            d1, d2, d3, d4, d5 = st.columns(5)

            d1.metric("Percentile", fmt_pct(profile.get("manager_percentile", None)))
            d2.metric("Best LP TVPI", fmt_x(profile.get("best_lp_tvpi", None)))
            d3.metric("Best LP IRR", fmt_pct(profile.get("best_lp_irr", None)))
            d4.metric(
                "Earliest Vintage",
                int(profile.get("earliest_vintage")) if pd.notna(profile.get("earliest_vintage", None)) else "N/A"
            )
            d5.metric(
                "Latest Vintage",
                int(profile.get("latest_vintage")) if pd.notna(profile.get("latest_vintage", None)) else "N/A"
            )

            st.divider()

            st.markdown("### Manager Snapshot")

            avg_tvpi = profile.get("avg_lp_tvpi", None)
            avg_dpi = profile.get("avg_lp_dpi", None)
            avg_irr = profile.get("avg_lp_irr", None)
            inst_matches = profile.get("institutional_match_count", 0)

            snapshot_points = []

            if pd.notna(avg_tvpi):
                if avg_tvpi >= 2.0:
                    snapshot_points.append("Strong average TVPI.")
                elif avg_tvpi >= 1.5:
                    snapshot_points.append("Good average TVPI.")
                else:
                    snapshot_points.append("Moderate / weaker average TVPI.")

            if pd.notna(avg_dpi):
                if avg_dpi >= 1.0:
                    snapshot_points.append("Realizations look meaningful.")
                elif avg_dpi >= 0.3:
                    snapshot_points.append("DPI is still developing.")
                else:
                    snapshot_points.append("Low DPI / limited realized value so far.")

            if pd.notna(avg_irr):
                irr_pct = avg_irr * 100 if avg_irr <= 1 else avg_irr
                if irr_pct >= 20:
                    snapshot_points.append("IRR profile is strong.")
                elif irr_pct >= 10:
                    snapshot_points.append("IRR profile is acceptable.")
                else:
                    snapshot_points.append("IRR profile is weak or missing.")

            if pd.notna(inst_matches) and inst_matches > 0:
                snapshot_points.append("Institutional validation exists.")
            else:
                snapshot_points.append("No institutional validation found yet.")

            if not snapshot_points:
                snapshot_points.append("Limited data available for this manager.")

            st.info(" ".join(snapshot_points))

            st.markdown("### Top Funds for This Manager")

            if manager_funds.empty:
                st.warning("No related funds found for this manager.")
            else:
                if "rank_score" in manager_funds.columns:
                    manager_funds = manager_funds.sort_values("rank_score", ascending=False)
                elif "tvpi_max" in manager_funds.columns:
                    manager_funds = manager_funds.sort_values("tvpi_max", ascending=False)

                top_fund_cols = [
                    "fund_name",
                    "vintage_year",
                    "sub_strategy",
                    "geography",
                    "irr_max",
                    "tvpi_max",
                    "dpi_max",
                    "rank_score",
                    "overall_quartile",
                    "institutional_fund_name",
                    "institutional_trend_score",
                    "match_score",
                ]

                top_fund_cols = [c for c in top_fund_cols if c in manager_funds.columns]

                st.dataframe(
                    manager_funds[top_fund_cols].head(20),
                    width="stretch",
                    height=350
                )

                st.divider()

                st.markdown("### Manager Fund Charts")

                chart_df = manager_funds.copy()
                chart_df["fund_label"] = chart_df["fund_name"].fillna("Unknown Fund").astype(str)

                chart_left, chart_right = st.columns(2)

                with chart_left:
                    if "tvpi_max" in chart_df.columns and chart_df["tvpi_max"].notna().sum() > 0:
                        tvpi_chart_df = chart_df.dropna(subset=["tvpi_max"]).sort_values("tvpi_max", ascending=False).head(15)

                        fig = px.bar(
                            tvpi_chart_df,
                            x="fund_label",
                            y="tvpi_max",
                            title="Top Funds by TVPI",
                            labels={
                                "fund_label": "Fund",
                                "tvpi_max": "TVPI"
                            }
                        )

                        fig.update_layout(xaxis_tickangle=-45)
                        st.plotly_chart(fig, width="stretch")
                    else:
                        st.warning("No TVPI data available for chart.")

                with chart_right:
                    if "irr_max" in chart_df.columns and chart_df["irr_max"].notna().sum() > 0:
                        irr_chart_df = chart_df.dropna(subset=["irr_max"]).copy()
                        irr_chart_df["irr_percent"] = irr_chart_df["irr_max"].apply(
                            lambda x: x * 100 if pd.notna(x) and x <= 1 else x
                        )

                        irr_chart_df = irr_chart_df.sort_values("irr_percent", ascending=False).head(15)

                        fig = px.bar(
                            irr_chart_df,
                            x="fund_label",
                            y="irr_percent",
                            title="Top Funds by IRR",
                            labels={
                                "fund_label": "Fund",
                                "irr_percent": "IRR (%)"
                            }
                        )

                        fig.update_layout(xaxis_tickangle=-45)
                        st.plotly_chart(fig, width="stretch")
                    else:
                        st.warning("No IRR data available for chart.")

                st.divider()

                st.markdown("### All Funds for This Manager")

                st.dataframe(
                    manager_funds[top_fund_cols],
                    width="stretch",
                    height=450
                )

            st.divider()

            st.markdown("### Raw Manager Profile Row")
            st.dataframe(profile_df, width="stretch", height=150)


# ============================================================
# TAB 3 — GPT COPILOT
# ============================================================

with tab3:
    st.subheader("GPT Allocator Copilot")

    if "copilot_messages" not in st.session_state:
        st.session_state["copilot_messages"] = []

    user_question = st.text_area(
        "Ask anything",
        placeholder="Example: What do you think about Union Square Ventures?",
        height=120,
        key="gpt_copilot_question"
    )

    col_a, col_b = st.columns([1, 1])

    with col_a:
        ask_button = st.button("Ask GPT Copilot", key="gpt_copilot_ask")

    with col_b:
        clear_button = st.button("Clear Chat", key="gpt_copilot_clear")

    if clear_button:
        st.session_state["copilot_messages"] = []
        st.rerun()

    if ask_button and user_question.strip():
        st.session_state["copilot_messages"].append({
            "role": "user",
            "content": user_question
        })

        with st.spinner("Analyzing allocator database..."):
            answer = ask_gpt_allocator(
                user_question,
                st.session_state["copilot_messages"]
            )

        st.session_state["copilot_messages"].append({
            "role": "assistant",
            "content": answer
        })

    for msg in st.session_state["copilot_messages"]:
        if msg["role"] == "user":
            st.markdown(f"### You\n{msg['content']}")
        else:
            st.markdown(f"### GPT Allocator Copilot\n{msg['content']}")
            st.divider()


# ============================================================
# TAB 4 — DATA SOURCES
# ============================================================

with tab4:
    st.subheader("Data Sources / Pipeline Status")

    st.markdown("## Live Report Discovery Pipeline")

    rr1, rr2, rr3, rr4 = st.columns(4)

    rr1.metric("Reports Found", len(raw_reports))
    rr2.metric("Website-Ready Reports", len(ready_reports))

    if not raw_reports.empty and "extraction_status" in raw_reports.columns:
        failed_count = raw_reports["extraction_status"].astype(str).str.contains(
            "failed|403|404|pdf_read_failed",
            case=False,
            na=False
        ).sum()

        skipped_count = raw_reports["extraction_status"].astype(str).str.contains(
            "manual_skip",
            case=False,
            na=False
        ).sum()
    else:
        failed_count = 0
        skipped_count = 0

    rr3.metric("Failed / Blocked", int(failed_count))
    rr4.metric("Manual Skips", int(skipped_count))

    st.markdown("### Website-Ready Reports")

    if ready_reports.empty:
        st.warning("No true fund-level website-ready reports yet.")
    else:
        st.dataframe(ready_reports, width="stretch", height=250)

    st.markdown("### All Discovered Reports")

    if raw_reports.empty:
        st.warning("No report pipeline data found. Run: python export_report_pipeline_for_app.py")
    else:
        st.dataframe(raw_reports, width="stretch", height=400)

    st.divider()

    ds1, ds2, ds3, ds4, ds5 = st.columns(5)

    ds1.metric("Total Funds Loaded", len(df))
    ds2.metric("Institutional-Only Funds", len(institutional_only_df))
    ds3.metric("Unified Matches", len(matches))

    if not inst_raw.empty and "source_file" in inst_raw.columns:
        institutional_report_count = inst_raw["source_file"].nunique()
    else:
        institutional_report_count = 0

    ds4.metric("Institutional Reports", institutional_report_count)
    ds5.metric("Manager Profiles", len(manager_profiles))

    st.markdown("### Institutional Only Funds")
    st.dataframe(institutional_only_df, width="stretch", height=400)

    st.markdown("### Unified Match Table")
    st.dataframe(matches, width="stretch", height=400)

    st.markdown("### Manager Profiles")
    st.dataframe(manager_profiles.head(500), width="stretch", height=400)

    st.markdown("### Institutional Raw Records")
    st.dataframe(inst_raw.head(500), width="stretch", height=400)


# ============================================================
# TAB 5 — INVESTMENT RECOMMENDATIONS
# ============================================================

with tab5:
    st.subheader("Investment Recommendations")

    if recommendations.empty:
        st.warning("No investment recommendations found yet.")
        st.code("python build_investment_recommendations.py")
    else:
        rec1, rec2, rec3, rec4, rec5 = st.columns(5)

        rec1.metric("Total Funds", len(recommendations))
        rec2.metric("Strong Candidates", int((recommendations["investment_recommendation"] == "Strong Candidate").sum()))
        rec3.metric("Good Candidates", int((recommendations["investment_recommendation"] == "Good Candidate").sum()))
        rec4.metric("Watchlist", int((recommendations["investment_recommendation"] == "Watchlist").sum()))
        rec5.metric(
            "Weak / Avoid",
            int(recommendations["investment_recommendation"].astype(str).str.contains("Avoid|Weak", na=False).sum())
        )

        st.markdown("### Filters")

        f1, f2, f3, f4 = st.columns(4)

        with f1:
            recommendation_filter = st.selectbox(
                "Recommendation",
                ["All"] + sorted(recommendations["investment_recommendation"].dropna().astype(str).unique().tolist()),
                key="recommendations_recommendation_filter"
            )

        with f2:
            if "sub_strategy" in recommendations.columns:
                strategy_filter = st.selectbox(
                    "Strategy",
                    ["All"] + sorted(recommendations["sub_strategy"].dropna().astype(str).unique().tolist()),
                    key="recommendations_strategy_filter"
                )
            else:
                strategy_filter = "All"

        with f3:
            if "geography" in recommendations.columns:
                geography_filter = st.selectbox(
                    "Geography",
                    ["All"] + sorted(recommendations["geography"].dropna().astype(str).unique().tolist()),
                    key="recommendations_geography_filter"
                )
            else:
                geography_filter = "All"

        with f4:
            if "data_confidence" in recommendations.columns:
                confidence_filter = st.selectbox(
                    "Data Confidence",
                    ["All"] + sorted(recommendations["data_confidence"].dropna().astype(str).unique().tolist()),
                    key="recommendations_confidence_filter"
                )
            else:
                confidence_filter = "All"

        view = recommendations.copy()

        if recommendation_filter != "All":
            view = view[view["investment_recommendation"] == recommendation_filter]

        if strategy_filter != "All" and "sub_strategy" in view.columns:
            view = view[view["sub_strategy"].astype(str) == strategy_filter]

        if geography_filter != "All" and "geography" in view.columns:
            view = view[view["geography"].astype(str) == geography_filter]

        if confidence_filter != "All" and "data_confidence" in view.columns:
            view = view[view["data_confidence"].astype(str) == confidence_filter]

        if "rank_score" in view.columns:
            view = view.sort_values("rank_score", ascending=False)
        elif "tvpi_max" in view.columns:
            view = view.sort_values("tvpi_max", ascending=False)

        preferred_cols = [
            "investment_recommendation",
            "reason_summary",
            "data_confidence",
            "red_flag_count",
            "red_flag_reasons",
            "fund_name",
            "manager_name",
            "vintage_year",
            "vintage_age",
            "sub_strategy",
            "geography",
            "irr_max",
            "tvpi_max",
            "dpi_max",
            "irr_quality",
            "tvpi_quality",
            "dpi_quality",
            "has_institutional_match",
            "institutional_fund_name",
            "institutional_trend_score",
            "match_score",
            "rank_score",
            "overall_quartile",
        ]

        preferred_cols = [c for c in preferred_cols if c in view.columns]

        st.write(f"Funds shown: **{len(view)}**")

        st.dataframe(
            view[preferred_cols],
            width="stretch",
            height=650
        )

        st.download_button(
            "Download Investment Recommendations CSV",
            data=recommendations.to_csv(index=False),
            file_name="investment_recommendations.csv",
            mime="text/csv",
            key="download_investment_recommendations"
        )

# ============================================================

# ============================================================

# ============================================================

# ============================================================

# ============================================================

# ============================================================

# ============================================================

# ============================================================

# ============================================================

# ============================================================

# ============================================================
# TAB 6 — LP DATA VINTAGE BENCHMARK CONTEXT
# ============================================================

with tab6:
    st.subheader("LP Data Vintage Benchmark / Quartile Context")

    st.markdown("""
This section uses your **full LP Data fund universe** to create vintage-year benchmark charts.

It groups LP Data funds by vintage year and shows the distribution of fund performance for each vintage.

Use the filters below to benchmark against a better peer group:
- same strategy,
- same geography,
- sensible vintage group.
""")

    if df.empty:
        st.warning("No LP Data found.")
    else:
        benchmark_df = df.copy()

        # -----------------------------
        # Clean columns
        # -----------------------------
        if "vintage_year" in benchmark_df.columns:
            benchmark_df["vintage_year"] = pd.to_numeric(
                benchmark_df["vintage_year"],
                errors="coerce"
            )

        for col in ["irr_max", "tvpi_max", "dpi_max"]:
            if col in benchmark_df.columns:
                benchmark_df[col] = pd.to_numeric(benchmark_df[col], errors="coerce")

        if "irr_max" in benchmark_df.columns:
            benchmark_df["irr_percent"] = benchmark_df["irr_max"].apply(
                lambda x: x * 100 if pd.notna(x) and x <= 1 else x
            )

        # -----------------------------
        # Main filters
        # -----------------------------
        st.markdown("### Benchmark Filters")

        f1, f2, f3, f4 = st.columns(4)

        with f1:
            strategy_filter = st.selectbox(
                "Strategy",
                [
                    "All",
                    "buyout",
                    "venture_capital",
                    "growth",
                ],
                key="benchmark_strategy_filter"
            )

        with f2:
            geography_filter = st.selectbox(
                "Geography",
                [
                    "All",
                    "asia_pacific",
                    "emerging_markets",
                    "europe",
                    "global",
                    "latin_america",
                    "north_america",
                ],
                key="benchmark_geography_filter"
            )

        with f3:
            vintage_focus = st.selectbox(
                "Vintage Focus",
                [
                    "All available vintages",
                    "Mature vintages only",
                    "Recent / developing vintages",
                    "2008 and newer",
                    "Specific vintage",
                ],
                key="benchmark_vintage_focus"
            )

        with f4:
            metric_choice = st.selectbox(
                "Metric",
                ["IRR (%)", "TVPI", "DPI"],
                key="lp_vintage_benchmark_metric"
            )

        # -----------------------------
        # Smart strategy filter
        # -----------------------------
        if strategy_filter != "All":

            search_cols = []

            for possible_col in ["sub_strategy", "strategy", "fund_name", "manager_name"]:
                if possible_col in benchmark_df.columns:
                    search_cols.append(possible_col)

            if not search_cols:
                st.warning("No strategy/sub_strategy/fund_name columns found for strategy filtering.")
                st.stop()

            combined_strategy_text = pd.Series("", index=benchmark_df.index)

            for col in search_cols:
                combined_strategy_text = (
                    combined_strategy_text
                    + " "
                    + benchmark_df[col].astype(str).str.lower().str.strip()
                )

            if strategy_filter == "buyout":
                mask = combined_strategy_text.str.contains(
                    "buyout|buy out|lbo|private equity",
                    case=False,
                    na=False
                )

            elif strategy_filter == "venture_capital":
                mask = combined_strategy_text.str.contains(
                    "venture|venture capital|vc",
                    case=False,
                    na=False
                )

            elif strategy_filter == "growth":
                mask = combined_strategy_text.str.contains(
                    "growth|growth equity",
                    case=False,
                    na=False
                )

            else:
                mask = pd.Series(True, index=benchmark_df.index)

            benchmark_df = benchmark_df[mask]

        # -----------------------------
        # Geography filter
        # -----------------------------
        if geography_filter != "All" and "geography" in benchmark_df.columns:
            benchmark_df = benchmark_df[
                benchmark_df["geography"].astype(str).str.lower().str.strip() == geography_filter
            ]

        if benchmark_df.empty or benchmark_df["vintage_year"].dropna().empty:
            st.warning("No benchmark data found for these filters.")
            st.stop()

        # -----------------------------
        # Vintage focus filter
        # -----------------------------
        available_vintages = sorted(
            benchmark_df["vintage_year"].dropna().astype(int).unique().tolist()
        )

        current_year = 2026

        if vintage_focus == "Mature vintages only":
            # Good for DPI because these funds have had time to realize exits.
            benchmark_df = benchmark_df[
                benchmark_df["vintage_year"] <= current_year - 8
            ]

        elif vintage_focus == "Recent / developing vintages":
            # Useful for TVPI/early performance, but DPI may be naturally low.
            benchmark_df = benchmark_df[
                benchmark_df["vintage_year"] >= current_year - 7
            ]

        elif vintage_focus == "2008 and newer":
            benchmark_df = benchmark_df[
                benchmark_df["vintage_year"] >= 2008
            ]

        elif vintage_focus == "Specific vintage":
            selected_vintage = st.selectbox(
                "Select specific vintage",
                available_vintages,
                key="benchmark_specific_vintage"
            )

            benchmark_df = benchmark_df[
                benchmark_df["vintage_year"] == selected_vintage
            ]

        if benchmark_df.empty or benchmark_df["vintage_year"].dropna().empty:
            st.warning("No benchmark data found for this vintage focus.")
            st.stop()

        # -----------------------------
        # Label + year controls
        # -----------------------------
        c_label, c_year = st.columns(2)

        with c_label:
            label_choice = st.selectbox(
                "Show average labels",
                [
                    "Alternating all years",
                    "Every 2nd year",
                    "Every 3rd year",
                    "No labels",
                ],
                key="lp_vintage_label_density"
            )

        with c_year:
            min_year_available = int(benchmark_df["vintage_year"].dropna().min())
            max_year_available = int(benchmark_df["vintage_year"].dropna().max())

            if min_year_available == max_year_available:
                year_range = (min_year_available, max_year_available)
                st.info(f"Showing one vintage year: {min_year_available}")
            else:
                year_range = st.slider(
                    "Vintage year range",
                    min_value=min_year_available,
                    max_value=max_year_available,
                    value=(min_year_available, max_year_available),
                    key="lp_vintage_year_range"
                )

        st.caption(f"Rows after filters: {len(benchmark_df):,}")

        # -----------------------------
        # Metric selection
        # -----------------------------
        if metric_choice == "IRR (%)":
            metric_col = "irr_percent"
            y_label = "IRR (%)"
            chart_title = "LP Data Fund IRR by Vintage"
        elif metric_choice == "TVPI":
            metric_col = "tvpi_max"
            y_label = "TVPI"
            chart_title = "LP Data Fund TVPI by Vintage"
        else:
            metric_col = "dpi_max"
            y_label = "DPI"
            chart_title = "LP Data Fund DPI by Vintage"

        if metric_col not in benchmark_df.columns:
            st.warning(f"Missing metric column: {metric_col}")
            st.stop()

        chart_df = benchmark_df.dropna(subset=["vintage_year", metric_col]).copy()

        chart_df = chart_df[
            (chart_df["vintage_year"] >= year_range[0]) &
            (chart_df["vintage_year"] <= year_range[1])
        ]

        # Remove extreme outliers for readable benchmark charts
        if metric_choice == "IRR (%)":
            chart_df = chart_df[
                (chart_df[metric_col] >= -100) &
                (chart_df[metric_col] <= 100)
            ]
        else:
            chart_df = chart_df[
                (chart_df[metric_col] >= 0) &
                (chart_df[metric_col] <= 10)
            ]

        if chart_df.empty:
            st.warning("No usable data for this metric and filter selection.")
            st.stop()

        chart_df["vintage_year"] = chart_df["vintage_year"].astype(int)
        chart_df = chart_df.sort_values("vintage_year")

        vintage_summary = chart_df.groupby("vintage_year").agg(
            fund_count=(metric_col, "count"),
            average_value=(metric_col, "mean"),
            median_value=(metric_col, "median"),
            q1_value=(metric_col, lambda x: x.quantile(0.25)),
            q3_value=(metric_col, lambda x: x.quantile(0.75)),
            min_value=(metric_col, "min"),
            max_value=(metric_col, "max"),
        ).reset_index()

        # -----------------------------
        # Metrics
        # -----------------------------
        m1, m2, m3, m4 = st.columns(4)

        m1.metric("Funds in Benchmark", f"{len(chart_df):,}")
        m2.metric("Vintage Years", chart_df["vintage_year"].nunique())
        m3.metric("Earliest Vintage", int(chart_df["vintage_year"].min()))
        m4.metric("Latest Vintage", int(chart_df["vintage_year"].max()))

        st.markdown(f"## {chart_title}")

        filter_caption_parts = []

        if strategy_filter != "All":
            filter_caption_parts.append(f"Strategy: {strategy_filter}")

        if geography_filter != "All":
            filter_caption_parts.append(f"Geography: {geography_filter}")

        filter_caption_parts.append(f"Vintage focus: {vintage_focus}")

        st.caption("Benchmark peer group: " + " | ".join(filter_caption_parts))

        # -----------------------------
        # Chart
        # -----------------------------
        fig = go.Figure()

        for vintage in sorted(chart_df["vintage_year"].unique()):
            one_vintage = chart_df[chart_df["vintage_year"] == vintage]

            fig.add_trace(go.Box(
                y=one_vintage[metric_col],
                x=[vintage] * len(one_vintage),
                name=str(vintage),
                boxpoints=False,
                marker_color="rgba(160, 190, 220, 0.65)",
                line_color="rgba(60, 120, 170, 1)",
                fillcolor="rgba(190, 205, 220, 0.55)",
                showlegend=False,
                hovertemplate=(
                    f"Vintage {vintage}<br>"
                    f"{metric_choice}: %{{y:.2f}}"
                    "<extra></extra>"
                )
            ))

        average_labels = []
        label_positions = []

        for i, row in vintage_summary.reset_index(drop=True).iterrows():
            value = row["average_value"]

            if metric_choice == "IRR (%)":
                label = f"{value:.1f}%"
            else:
                label = f"{value:.2f}x"

            if label_choice == "No labels":
                show_label = False
                position = "top center"
            elif label_choice == "Every 2nd year":
                show_label = i == 0 or i == len(vintage_summary) - 1 or i % 2 == 0
                position = "top center" if i % 4 == 0 else "bottom center"
            elif label_choice == "Every 3rd year":
                show_label = i == 0 or i == len(vintage_summary) - 1 or i % 3 == 0
                position = "top center" if i % 6 == 0 else "bottom center"
            else:
                show_label = True
                position = "top center" if i % 2 == 0 else "bottom center"

            average_labels.append(label if show_label else "")
            label_positions.append(position)

        fig.add_trace(go.Scatter(
            x=vintage_summary["vintage_year"],
            y=vintage_summary["average_value"],
            mode="markers+text" if label_choice != "No labels" else "markers",
            marker=dict(
                symbol="diamond",
                size=11,
                color="green",
                line=dict(color="black", width=1)
            ),
            text=average_labels,
            textposition=label_positions,
            textfont=dict(size=12, color="#111111"),
            name="Average",
            showlegend=True,
            cliponaxis=False,
            hovertemplate=(
                "Vintage %{x}<br>"
                "Average: %{y:.2f}"
                "<extra></extra>"
            )
        ))

        min_year = int(vintage_summary["vintage_year"].min())
        max_year = int(vintage_summary["vintage_year"].max())

        fig.update_layout(
            title=f"{chart_title} — Filtered Benchmark Universe",
            xaxis_title="Vintage Year",
            yaxis_title=y_label,
            height=900,
            template="plotly_white",
            margin=dict(l=60, r=60, t=110, b=150),
            hovermode="x unified",
            font=dict(size=14),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.03,
                xanchor="right",
                x=1
            )
        )

        if min_year == max_year:
            x_range = [min_year - 1, max_year + 1]
        else:
            x_range = [min_year - 0.75, max_year + 0.75]

        fig.update_xaxes(
            type="linear",
            tickmode="linear",
            tick0=min_year,
            dtick=1,
            range=x_range,
            tickangle=45,
            tickfont=dict(size=11)
        )

        if metric_choice == "IRR (%)":
            fig.update_yaxes(ticksuffix="%", gridcolor="rgba(0,0,0,0.08)")
        else:
            fig.update_yaxes(ticksuffix="x", gridcolor="rgba(0,0,0,0.08)")

        st.plotly_chart(fig, width="stretch")

        # -----------------------------
        # Summary table
        # -----------------------------
        st.markdown("### Vintage Summary Table")

        display_summary = vintage_summary.copy()

        for col in ["average_value", "median_value", "q1_value", "q3_value", "min_value", "max_value"]:
            if metric_choice == "IRR (%)":
                display_summary[col] = display_summary[col].round(1)
            else:
                display_summary[col] = display_summary[col].round(2)

        display_summary = display_summary.rename(columns={
            "vintage_year": "Vintage",
            "fund_count": "# Funds",
            "average_value": "Average",
            "median_value": "Median",
            "q1_value": "Q1 / 25th Percentile",
            "q3_value": "Q3 / 75th Percentile",
            "min_value": "Min",
            "max_value": "Max",
        })

        display_summary = display_summary[
            [
                "Vintage",
                "# Funds",
                "Average",
                "Median",
                "Q1 / 25th Percentile",
                "Q3 / 75th Percentile",
                "Min",
                "Max",
            ]
        ]

        st.dataframe(display_summary, width="stretch", height=420)

        st.info("""
Vintage Focus meaning:

- **All available vintages** = everything matching Strategy and Geography.
- **Mature vintages only** = older funds, more useful for DPI.
- **Recent / developing vintages** = newer funds, useful for early TVPI/IRR, but DPI may be naturally low.
- **2008 and newer** = excludes older legacy funds.
- **Specific vintage** = look at one vintage year only.

For DPI, use **Mature vintages only** most of the time.
""")



# ============================================================
# BOTTOM FUND QUARTERLY HISTORY CHARTS
# ============================================================

import pandas as _bottom_chart_pd
import plotly.graph_objects as _bottom_go
from pathlib import Path as _BottomChartPath

@st.cache_data
def _load_bottom_quarterly_history():
    file_path = _BottomChartPath("lp_funds_with_quarters.xlsx")
    if not file_path.exists():
        return _bottom_chart_pd.DataFrame()

    qdf = _bottom_chart_pd.read_excel(file_path)

    qdf["latest_date"] = _bottom_chart_pd.to_datetime(qdf["latest_date"], errors="coerce")
    qdf["vintage"] = _bottom_chart_pd.to_numeric(qdf["vintage"], errors="coerce")
    qdf["net_irr"] = _bottom_chart_pd.to_numeric(qdf["net_irr"], errors="coerce")
    qdf["tvpi"] = _bottom_chart_pd.to_numeric(qdf["tvpi"], errors="coerce")
    qdf["dpi"] = _bottom_chart_pd.to_numeric(qdf["dpi"], errors="coerce")
    qdf["nav_usd"] = _bottom_chart_pd.to_numeric(qdf["nav_usd"], errors="coerce")

    qdf = qdf.dropna(subset=["fund_id", "fund_name", "manager", "latest_date"])
    qdf = qdf.sort_values(["manager", "fund_name", "latest_date"])
    qdf["irr_percent"] = qdf["net_irr"] * 100

    qdf["fund_selector"] = (
        qdf["manager"].astype(str)
        + " - "
        + qdf["fund_name"].astype(str)
        + " | Vintage "
        + qdf["vintage"].fillna("").astype(str).str.replace(".0", "", regex=False)
    )

    return qdf

def _make_history_chart(fund_hist, all_qdf, metric, selected_name, title, subtitle, y_tick_suffix=""):
    fig = _bottom_go.Figure()

    fig.add_trace(
        _bottom_go.Scatter(
            x=fund_hist["latest_date"],
            y=fund_hist[metric],
            mode="lines+markers",
            name=selected_name[:32] + ("..." if len(selected_name) > 32 else ""),
            line=dict(width=3),
            marker=dict(size=6)
        )
    )

    median_df = (
        all_qdf.dropna(subset=["latest_date", metric])
        .groupby("latest_date", as_index=False)[metric]
        .median()
        .sort_values("latest_date")
    )

    if not median_df.empty:
        fig.add_trace(
            _bottom_go.Scatter(
                x=median_df["latest_date"],
                y=median_df[metric],
                mode="lines+markers",
                name="Median",
                line=dict(width=2, dash="dot"),
                marker=dict(size=5)
            )
        )

    fig.update_layout(
        title=dict(
            text=f"<b>{title}</b><br><span style='font-size:13px;color:#475569'>{subtitle}</span>",
            x=0.02,
            xanchor="left"
        ),
        height=330,
        margin=dict(l=35, r=20, t=70, b=45),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.28,
            xanchor="left",
            x=0
        ),
        hovermode="x unified",
        paper_bgcolor="white",
        plot_bgcolor="white",
        xaxis=dict(title="", showgrid=True, gridcolor="#eef2f7"),
        yaxis=dict(title="", showgrid=True, gridcolor="#eef2f7", ticksuffix=y_tick_suffix)
    )

    return fig

_bottom_qdf = _load_bottom_quarterly_history()

if not _bottom_qdf.empty:
    st.divider()
    st.markdown("## Fund quarterly history")
    st.caption("Select a fund to see its quarterly IRR, TVPI, DPI and NAV history.")

    _fund_options = (
        _bottom_qdf[["fund_id", "fund_selector"]]
        .drop_duplicates()
        .sort_values("fund_selector")
    )

    _selected_label = st.selectbox(
        "Select fund",
        _fund_options["fund_selector"].tolist(),
        key="bottom_quarterly_fund_selector"
    )

    _selected_fund_id = _fund_options.loc[
        _fund_options["fund_selector"] == _selected_label,
        "fund_id"
    ].iloc[0]

    _fund_hist = _bottom_qdf[_bottom_qdf["fund_id"] == _selected_fund_id].sort_values("latest_date")

    if not _fund_hist.empty:
        _latest = _fund_hist.tail(1).iloc[0]

        _k1, _k2, _k3, _k4 = st.columns(4)
        _k1.metric("Latest IRR", f"{_latest['net_irr']:.1%}" if _bottom_chart_pd.notna(_latest["net_irr"]) else "N/A")
        _k2.metric("Latest TVPI", f"{_latest['tvpi']:.2f}x" if _bottom_chart_pd.notna(_latest["tvpi"]) else "N/A")
        _k3.metric("Latest DPI", f"{_latest['dpi']:.2f}x" if _bottom_chart_pd.notna(_latest["dpi"]) else "N/A")
        _k4.metric("Latest NAV", f"${_latest['nav_usd']:,.0f}" if _bottom_chart_pd.notna(_latest["nav_usd"]) else "N/A")

        _selected_short_name = str(_latest["fund_name"])

        _c1, _c2, _c3 = st.columns(3)

        with _c1:
            with st.container(border=True):
                _fig_irr = _make_history_chart(
                    _fund_hist,
                    _bottom_qdf,
                    "irr_percent",
                    _selected_short_name,
                    "IRR Over Time",
                    "Net IRR by quarter over time",
                    y_tick_suffix="%"
                )
                st.plotly_chart(_fig_irr, use_container_width=True)

        with _c2:
            with st.container(border=True):
                _fig_tvpi = _make_history_chart(
                    _fund_hist,
                    _bottom_qdf,
                    "tvpi",
                    _selected_short_name,
                    "TVPI Over Time",
                    "Total value to paid-in by quarter over time",
                    y_tick_suffix="x"
                )
                st.plotly_chart(_fig_tvpi, use_container_width=True)

        with _c3:
            with st.container(border=True):
                _fig_dpi = _make_history_chart(
                    _fund_hist,
                    _bottom_qdf,
                    "dpi",
                    _selected_short_name,
                    "DPI Over Time",
                    "Distributions to paid-in by quarter over time",
                    y_tick_suffix="x"
                )
                st.plotly_chart(_fig_dpi, use_container_width=True)

        with st.container(border=True):
            _nav_fig = _bottom_go.Figure()
            _nav_fig.add_trace(
                _bottom_go.Scatter(
                    x=_fund_hist["latest_date"],
                    y=_fund_hist["nav_usd"],
                    mode="lines+markers",
                    name="NAV",
                    line=dict(width=3),
                    marker=dict(size=6)
                )
            )
            _nav_fig.update_layout(
                title=dict(
                    text="<b>NAV Over Time</b><br><span style='font-size:13px;color:#475569'>Net asset value by quarter over time</span>",
                    x=0.02,
                    xanchor="left"
                ),
                height=330,
                margin=dict(l=35, r=20, t=70, b=45),
                hovermode="x unified",
                paper_bgcolor="white",
                plot_bgcolor="white",
                xaxis=dict(title="", showgrid=True, gridcolor="#eef2f7"),
                yaxis=dict(title="", showgrid=True, gridcolor="#eef2f7", tickprefix="$")
            )
            st.plotly_chart(_nav_fig, use_container_width=True)

        with st.expander("Show quarterly data table"):
            _show = _fund_hist[[
                "latest_date",
                "quarter",
                "net_irr",
                "tvpi",
                "dpi",
                "nav_usd"
            ]].copy()
            _show["latest_date"] = _show["latest_date"].dt.date
            _show["net_irr"] = _show["net_irr"].map(lambda x: f"{x:.1%}" if _bottom_chart_pd.notna(x) else "")
            _show["tvpi"] = _show["tvpi"].map(lambda x: f"{x:.2f}x" if _bottom_chart_pd.notna(x) else "")
            _show["dpi"] = _show["dpi"].map(lambda x: f"{x:.2f}x" if _bottom_chart_pd.notna(x) else "")
            _show["nav_usd"] = _show["nav_usd"].map(lambda x: f"${x:,.0f}" if _bottom_chart_pd.notna(x) else "")
            st.dataframe(_show, use_container_width=True)

else:
    st.warning("Quarterly history file not found. Expected lp_funds_with_quarters.xlsx in this folder.")

# ============================================================
# END BOTTOM FUND QUARTERLY HISTORY CHARTS
# ============================================================


