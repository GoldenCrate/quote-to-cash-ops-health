"""
Quote-to-Cash Ops Health — Streamlit dashboard
================================================

A deal-desk / order-management operations dashboard for the quote-to-cash
pipeline. Built as a portfolio demo for an Order Management Analyst role.

Views
-----
1. Ops Overview .......... headline KPI tiles (volume, SLA, accuracy, cycle time)
2. Queue & Aging ......... open orders by stage, aging buckets, SLA breach flags
3. Discrepancy Audit ..... audits records against business rules (accuracy check)
4. Throughput & Accuracy . trend over time with threshold alerts
5. (each view ends with a "So what / recommendation" callout)

ALL DATA IS SYNTHETIC and generated locally with a fixed seed. No real
customer, revenue, or Sierra data is used.

Author: Leo Chan — github.com/GoldenCrate
"""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from data_gen import (
    AS_OF_DATE,
    STAGES,
    STAGE_SLA_DAYS,
    audit_orders,
    generate_orders,
)

# ---------------------------------------------------------------------------
# Thresholds / targets the ops team manages against (would be config in prod).
# ---------------------------------------------------------------------------
SLA_ATTAINMENT_TARGET = 0.90      # >= 90% of open orders within stage SLA
ACCURACY_TARGET = 0.97           # >= 97% of records clean (no rule violation)
CYCLE_TIME_TARGET_DAYS = 10      # avg quote-to-cash cycle target

# Knaflic-friendly, decluttered color roles.
C_PRIMARY = "#1f4e79"   # muted navy
C_ALERT = "#c0392b"     # red, reserved for "needs attention"
C_OK = "#2e7d5b"        # green, reserved for "good"
C_MUTED = "#b8c4ce"     # grey, for de-emphasized context


# ---------------------------------------------------------------------------
# Data loading (cached)
# ---------------------------------------------------------------------------
@st.cache_data
def load_data() -> pd.DataFrame:
    return generate_orders()


@st.cache_data
def load_audit(df: pd.DataFrame) -> pd.DataFrame:
    return audit_orders(df)


def pct(x: float) -> str:
    return f"{x * 100:.1f}%"


# ---------------------------------------------------------------------------
# Page config + header
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Quote-to-Cash Ops Health",
    page_icon="📦",
    layout="wide",
)

df = load_data()
audit = load_audit(df)

# Derived, order-level clean flag (any violation => not clean).
flagged_ids = set(audit["order_id"].unique())
df = df.copy()
df["has_violation"] = df["order_id"].isin(flagged_ids)

st.title("Quote-to-Cash Ops Health")
st.caption(
    f"Deal-desk / order-management operations dashboard  ·  as of "
    f"{AS_OF_DATE.date()}  ·  **100% synthetic demo data**"
)

st.sidebar.title("Views")
view = st.sidebar.radio(
    "Go to",
    [
        "Ops Overview",
        "Queue & Aging",
        "Discrepancy Audit",
        "Throughput & Accuracy",
    ],
    label_visibility="collapsed",
)
st.sidebar.markdown("---")
st.sidebar.markdown(
    "**About**\n\nSynthetic quote-to-cash records with intentionally injected "
    "data-quality defects, to demonstrate an ops accuracy / SLA monitor.\n\n"
    "Author: **Leo Chan** — [github.com/GoldenCrate](https://github.com/GoldenCrate)"
)

# Shared aggregates.
open_df = df[df["status"] == "Open"]
closed_df = df[df["status"] == "Closed"]
n_total = len(df)
n_open = len(open_df)
n_closed = len(closed_df)

sla_attainment = (
    1.0 - (open_df["sla_breached"].sum() / n_open) if n_open else 1.0
)
error_rate = df["has_violation"].sum() / n_total if n_total else 0.0
accuracy_rate = 1.0 - error_rate
avg_cycle = closed_df["cycle_time_days"].mean() if n_closed else float("nan")


def recommendation(text: str) -> None:
    """Render a consistent 'So what / recommendation' callout."""
    st.markdown("### So what")
    st.info(text)


# ===========================================================================
# VIEW 1 — OPS OVERVIEW (KPI tiles)
# ===========================================================================
if view == "Ops Overview":
    st.subheader("Headline operations KPIs")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Orders processed", f"{n_total:,}", help="Total records in window")
    c2.metric(
        "SLA attainment (open)",
        pct(sla_attainment),
        delta=pct(sla_attainment - SLA_ATTAINMENT_TARGET),
        help=f"Open orders within stage SLA. Target {pct(SLA_ATTAINMENT_TARGET)}.",
    )
    c3.metric(
        "Accuracy rate",
        pct(accuracy_rate),
        delta=pct(accuracy_rate - ACCURACY_TARGET),
        help=f"Records with no business-rule violation. Target {pct(ACCURACY_TARGET)}.",
    )
    c4.metric(
        "Avg cycle time",
        f"{avg_cycle:.1f} d",
        delta=f"{avg_cycle - CYCLE_TIME_TARGET_DAYS:+.1f} d vs target",
        delta_color="inverse",
        help=f"Quote-to-cash days for closed orders. Target {CYCLE_TIME_TARGET_DAYS}d.",
    )

    st.markdown("---")
    a, b = st.columns(2)

    with a:
        st.markdown("**Order status split**")
        status_counts = (
            df["status"].value_counts().rename_axis("status").reset_index(name="orders")
        )
        chart = (
            alt.Chart(status_counts)
            .mark_bar()
            .encode(
                x=alt.X("orders:Q", title=None),
                y=alt.Y("status:N", title=None, sort="-x"),
                color=alt.Color(
                    "status:N",
                    scale=alt.Scale(
                        domain=["Open", "Closed"], range=[C_PRIMARY, C_MUTED]
                    ),
                    legend=None,
                ),
                tooltip=["status", "orders"],
            )
            .properties(height=140)
        )
        labels = chart.mark_text(align="left", dx=4, color="#333").encode(
            text="orders:Q"
        )
        st.altair_chart(chart + labels, width='stretch')

    with b:
        st.markdown("**Where the accuracy gap comes from**")
        rule_counts = (
            audit["rule"].value_counts().rename_axis("rule").reset_index(name="count")
        )
        chart = (
            alt.Chart(rule_counts)
            .mark_bar(color=C_ALERT)
            .encode(
                x=alt.X("count:Q", title="violations"),
                y=alt.Y("rule:N", title=None, sort="-x"),
                tooltip=["rule", "count"],
            )
            .properties(height=180)
        )
        labels = chart.mark_text(align="left", dx=4, color="#333").encode(
            text="count:Q"
        )
        st.altair_chart(chart + labels, width='stretch')

    miss = []
    if sla_attainment < SLA_ATTAINMENT_TARGET:
        miss.append(
            f"SLA attainment {pct(sla_attainment)} is below the "
            f"{pct(SLA_ATTAINMENT_TARGET)} target"
        )
    if accuracy_rate < ACCURACY_TARGET:
        miss.append(
            f"accuracy {pct(accuracy_rate)} is below the {pct(ACCURACY_TARGET)} target"
        )
    if avg_cycle > CYCLE_TIME_TARGET_DAYS:
        miss.append(
            f"avg cycle time {avg_cycle:.1f}d exceeds the {CYCLE_TIME_TARGET_DAYS}d target"
        )
    msg = (
        "Two of the three managed metrics are off-target: "
        + "; ".join(miss)
        + ". The accuracy gap is concentrated in **price-math mismatches** — the "
        "single highest-leverage fix is a validation rule at quote entry that "
        "recomputes line totals before a record can advance to Deal-Desk Review."
    ) if miss else (
        "All three managed metrics are on target. Maintain the current controls "
        "and keep monitoring the throughput trend for early drift."
    )
    recommendation(msg)


# ===========================================================================
# VIEW 2 — QUEUE & AGING
# ===========================================================================
elif view == "Queue & Aging":
    st.subheader("Open-order queue, aging, and SLA breaches")

    n_breach = int(open_df["sla_breached"].sum())
    k1, k2, k3 = st.columns(3)
    k1.metric("Open orders", f"{n_open:,}")
    k2.metric("SLA breaches", f"{n_breach:,}", help="Open orders past stage SLA")
    k3.metric("SLA attainment", pct(sla_attainment))

    st.markdown("---")
    left, right = st.columns(2)

    with left:
        st.markdown("**Booking & Approval hold the most at-risk orders**")
        by_stage = (
            open_df.groupby("stage")
            .agg(open_orders=("order_id", "size"), breaches=("sla_breached", "sum"))
            .reindex(STAGES[:-1])
            .fillna(0)
            .reset_index()
        )
        by_stage["within_sla"] = by_stage["open_orders"] - by_stage["breaches"]
        melt = by_stage.melt(
            id_vars="stage",
            value_vars=["within_sla", "breaches"],
            var_name="band",
            value_name="orders",
        )
        chart = (
            alt.Chart(melt)
            .mark_bar()
            .encode(
                x=alt.X("orders:Q", title="open orders", stack="zero"),
                y=alt.Y("stage:N", title=None, sort=STAGES[:-1]),
                color=alt.Color(
                    "band:N",
                    scale=alt.Scale(
                        domain=["within_sla", "breaches"], range=[C_MUTED, C_ALERT]
                    ),
                    legend=alt.Legend(title=None, orient="bottom"),
                ),
                tooltip=["stage", "band", "orders"],
            )
            .properties(height=220)
        )
        st.altair_chart(chart, width='stretch')

    with right:
        st.markdown("**Aging profile of the open queue**")
        bins = [-1, 2, 5, 10, 10_000]
        labels = ["0-2 d", "3-5 d", "6-10 d", "10+ d"]
        aging = open_df.copy()
        aging["bucket"] = pd.cut(aging["days_in_stage"], bins=bins, labels=labels)
        agg = (
            aging.groupby("bucket", observed=False)
            .size()
            .reindex(labels)
            .reset_index(name="orders")
        )
        agg.columns = ["bucket", "orders"]
        agg["color"] = [C_MUTED, C_MUTED, C_PRIMARY, C_ALERT]
        chart = (
            alt.Chart(agg)
            .mark_bar()
            .encode(
                x=alt.X("bucket:N", title="days in current stage", sort=labels),
                y=alt.Y("orders:Q", title="open orders"),
                color=alt.Color("color:N", scale=None, legend=None),
                tooltip=["bucket", "orders"],
            )
            .properties(height=220)
        )
        lab = chart.mark_text(dy=-6, color="#333").encode(text="orders:Q")
        st.altair_chart(chart + lab, width='stretch')

    st.markdown("**SLA-breached orders — oldest first (work these down)**")
    breach_tbl = (
        open_df[open_df["sla_breached"]]
        .sort_values("days_in_stage", ascending=False)
        .loc[
            :,
            ["order_id", "stage", "segment", "region", "rep",
             "days_in_stage", "stage_sla_days", "line_total"],
        ]
        .head(25)
        .rename(columns={"days_in_stage": "days_in_stage", "stage_sla_days": "sla_days"})
    )
    st.dataframe(breach_tbl, width='stretch', hide_index=True)

    oldest = int(open_df["days_in_stage"].max()) if n_open else 0
    recommendation(
        f"{n_breach:,} of {n_open:,} open orders ({pct(n_breach / n_open)}) are past "
        f"their stage SLA, with the oldest sitting **{oldest} days** in stage. Breaches "
        "concentrate in the **Approval** and **Booking** stages, which is where "
        "hand-offs stall. Recommend a daily stand-up worklist sorted by days-in-stage "
        "and an escalation trigger at day 3 in Approval so aged orders are actioned "
        "before they slip."
    )


# ===========================================================================
# VIEW 3 — DISCREPANCY AUDIT
# ===========================================================================
elif view == "Discrepancy Audit":
    st.subheader("Data-quality / accuracy audit against business rules")
    st.caption(
        "Every order is checked against four rules. A record is 'clean' only if it "
        "passes all of them. This is the accuracy control for the ops queue."
    )

    n_viol_orders = df["has_violation"].sum()
    k1, k2, k3 = st.columns(3)
    k1.metric("Records audited", f"{n_total:,}")
    k2.metric("Records with ≥1 violation", f"{int(n_viol_orders):,}")
    k3.metric(
        "Accuracy rate",
        pct(accuracy_rate),
        delta=pct(accuracy_rate - ACCURACY_TARGET),
        help=f"Target {pct(ACCURACY_TARGET)}",
    )

    st.markdown("---")
    left, right = st.columns([3, 2])

    with left:
        st.markdown("**Price-math mismatches dominate the violation mix**")
        rule_counts = (
            audit.groupby(["rule", "severity"])
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
        )
        chart = (
            alt.Chart(rule_counts)
            .mark_bar()
            .encode(
                x=alt.X("count:Q", title="violations"),
                y=alt.Y("rule:N", title=None, sort="-x"),
                color=alt.Color(
                    "severity:N",
                    scale=alt.Scale(
                        domain=["High", "Medium"], range=[C_ALERT, "#e8a33d"]
                    ),
                    legend=alt.Legend(title="severity", orient="bottom"),
                ),
                tooltip=["rule", "severity", "count"],
            )
            .properties(height=220)
        )
        lab = chart.mark_text(align="left", dx=4, color="#333").encode(text="count:Q")
        st.altair_chart(chart + lab, width='stretch')

    with right:
        st.markdown("**Rules applied**")
        st.markdown(
            "- **Price math mismatch** (High): `line_total` ≠ "
            "`qty × unit_price × (1 − discount)`\n"
            "- **Missing required field** (Med): `segment` or `product` blank\n"
            "- **Non-positive quantity / unit price** (High)\n"
            "- **Duplicate order ID** (High): same `order_id` on 2+ records"
        )

    st.markdown("**Violation detail (filterable)**")
    rule_filter = st.multiselect(
        "Filter by rule",
        options=sorted(audit["rule"].unique()),
        default=sorted(audit["rule"].unique()),
    )
    shown = audit[audit["rule"].isin(rule_filter)]
    st.dataframe(shown, width='stretch', hide_index=True)
    st.download_button(
        "Download violations as CSV",
        shown.to_csv(index=False).encode("utf-8"),
        file_name="qtc_violations.csv",
        mime="text/csv",
    )

    high = int((audit["severity"] == "High").sum())
    recommendation(
        f"The audit caught **{len(audit)} violations across {int(n_viol_orders)} orders** "
        f"({high} High-severity), pulling accuracy to {pct(accuracy_rate)} — below the "
        f"{pct(ACCURACY_TARGET)} target. Roughly half are **price-math mismatches** that a "
        "single entry-time validation rule would prevent, and the **duplicate order IDs** "
        "point to a missing uniqueness constraint. Fix those two at the source and "
        "accuracy clears target without adding manual QA headcount."
    )


# ===========================================================================
# VIEW 4 — THROUGHPUT & ACCURACY TREND
# ===========================================================================
elif view == "Throughput & Accuracy":
    st.subheader("Throughput & accuracy trend, with threshold alerts")

    grain = st.radio("Time grain", ["Weekly", "Daily"], horizontal=True)
    freq = "W" if grain == "Weekly" else "D"

    tdf = df.copy()
    tdf["period"] = tdf["created_date"].dt.to_period(freq).dt.start_time
    trend = (
        tdf.groupby("period")
        .agg(
            orders=("order_id", "size"),
            violations=("has_violation", "sum"),
        )
        .reset_index()
    )
    trend["accuracy"] = 1.0 - trend["violations"] / trend["orders"]
    # Drop the trailing partial period so the trend isn't misleading.
    if len(trend) > 1:
        trend = trend.iloc[:-1]

    st.markdown("**Order throughput is steady; watch for volume dips**")
    base = alt.Chart(trend).encode(
        x=alt.X("period:T", title=None)
    )
    bars = base.mark_bar(color=C_PRIMARY, opacity=0.85).encode(
        y=alt.Y("orders:Q", title="orders created"),
        tooltip=[
            alt.Tooltip("period:T", title="period"),
            alt.Tooltip("orders:Q"),
        ],
    )
    st.altair_chart(bars.properties(height=220), width='stretch')

    st.markdown(
        f"**Accuracy repeatedly dips below the {pct(ACCURACY_TARGET)} target line**"
    )
    acc_line = base.mark_line(color=C_PRIMARY, point=True).encode(
        y=alt.Y(
            "accuracy:Q",
            title="accuracy",
            scale=alt.Scale(domain=[min(0.8, trend["accuracy"].min() - 0.02), 1.0]),
            axis=alt.Axis(format="%"),
        ),
        tooltip=[
            alt.Tooltip("period:T", title="period"),
            alt.Tooltip("accuracy:Q", format=".1%"),
            alt.Tooltip("violations:Q"),
        ],
    )
    target_rule = (
        alt.Chart(pd.DataFrame({"y": [ACCURACY_TARGET]}))
        .mark_rule(color=C_ALERT, strokeDash=[6, 4])
        .encode(y="y:Q")
    )
    # Highlight breach points in red.
    breach_pts = (
        alt.Chart(trend[trend["accuracy"] < ACCURACY_TARGET])
        .mark_point(color=C_ALERT, size=70, filled=True)
        .encode(x="period:T", y="accuracy:Q")
    )
    st.altair_chart(
        (acc_line + target_rule + breach_pts).properties(height=260),
        width='stretch',
    )

    n_below = int((trend["accuracy"] < ACCURACY_TARGET).sum())
    st.caption(
        f"Red dashed line = {pct(ACCURACY_TARGET)} accuracy target. "
        f"Red dots = periods below target ({n_below} of {len(trend)})."
    )

    recommendation(
        f"Throughput is stable, but accuracy sits below the {pct(ACCURACY_TARGET)} target "
        f"in **{n_below} of {len(trend)}** periods — this is a systemic input-quality "
        "problem, not a one-off spike. Because the defects are structural (price math, "
        "duplicates), they will not improve without a source-side control. Recommend "
        "wiring the four audit rules into the order-entry form as blocking validations "
        "and re-baselining the accuracy target to 99% once they are live."
    )
