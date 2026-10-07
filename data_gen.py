"""
data_gen.py — Synthetic Quote-to-Cash order data generator.

Produces a reproducible (fixed-seed) set of order/booking records that mimic a
deal-desk / quote-to-cash operations queue. Intentionally injects a known set of
data-quality defects (math errors, missing fields, duplicate IDs, bad values) so
the dashboard's discrepancy-audit view has real violations to catch.

ALL DATA IS SYNTHETIC. No real customer, revenue, or Sierra data is used.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SEED = 42
N_ORDERS = 1600
# "Today" is pinned so the app is fully reproducible regardless of run date.
AS_OF_DATE = pd.Timestamp("2026-10-06")
WINDOW_DAYS = 120  # orders created across the trailing ~4 months

# Quote-to-cash pipeline stages, in order. The last one is terminal (closed).
STAGES = ["Quote Drafted", "Deal-Desk Review", "Approval", "Booking", "Invoiced"]
TERMINAL_STAGE = "Invoiced"

# Per-stage SLA target (business days a record is allowed to sit in that stage).
STAGE_SLA_DAYS = {
    "Quote Drafted": 2,
    "Deal-Desk Review": 3,
    "Approval": 2,
    "Booking": 2,
    "Invoiced": 1,
}

SEGMENTS = ["Enterprise", "Mid-Market", "SMB"]
REGIONS = ["AMER", "EMEA", "APAC"]
PRODUCTS = [
    "Agent Platform - Base",
    "Agent Platform - Pro",
    "Voice Add-on",
    "Analytics Add-on",
    "Premium Support",
]
UNIT_PRICE_BY_PRODUCT = {
    "Agent Platform - Base": 1200.0,
    "Agent Platform - Pro": 2800.0,
    "Voice Add-on": 600.0,
    "Analytics Add-on": 450.0,
    "Premium Support": 900.0,
}
REPS = [f"Rep-{i:02d}" for i in range(1, 13)]


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------
def generate_orders() -> pd.DataFrame:
    """Return a synthetic quote-to-cash order DataFrame with injected defects."""
    rng = np.random.default_rng(SEED)

    # --- base fields -------------------------------------------------------
    order_ids = [f"ORD-{100000 + i}" for i in range(N_ORDERS)]
    quote_ids = [f"Q-{200000 + i}" for i in range(N_ORDERS)]

    # Creation dates skewed toward recent (more recent activity = more open).
    age_days = rng.integers(0, WINDOW_DAYS, size=N_ORDERS)
    created_date = AS_OF_DATE - pd.to_timedelta(age_days, unit="D")

    segment = rng.choice(SEGMENTS, size=N_ORDERS, p=[0.30, 0.45, 0.25])
    region = rng.choice(REGIONS, size=N_ORDERS, p=[0.55, 0.28, 0.17])
    product = rng.choice(PRODUCTS, size=N_ORDERS)
    rep = rng.choice(REPS, size=N_ORDERS)

    quantity = rng.integers(1, 40, size=N_ORDERS).astype(float)
    unit_price = np.array([UNIT_PRICE_BY_PRODUCT[p] for p in product], dtype=float)
    discount_pct = np.round(rng.choice([0, 0, 0, 5, 10, 15, 20], size=N_ORDERS) / 100.0, 2)

    # Correct line total: qty * unit_price * (1 - discount).
    line_total = np.round(quantity * unit_price * (1.0 - discount_pct), 2)

    # --- lifecycle: stage, open/closed, aging -----------------------------
    # Older orders are more likely to have progressed to later stages / closed.
    stage: list[str] = [""] * N_ORDERS
    stage_entered_date: list[pd.Timestamp] = [pd.NaT] * N_ORDERS
    closed_date: list[pd.Timestamp] = [pd.NaT] * N_ORDERS

    for i in range(N_ORDERS):
        a = int(age_days[i])
        # Probability of being closed grows with age.
        close_prob = min(0.92, 0.10 + a / WINDOW_DAYS * 0.9)
        if rng.random() < close_prob:
            st = TERMINAL_STAGE
            # Closed somewhere between a little after creation and now.
            cycle = int(rng.integers(3, 18))
            cd = created_date[i] + pd.Timedelta(days=min(cycle, max(1, a)))
            closed_date[i] = cd
            stage_entered_date[i] = cd
        else:
            # Open: sits in one of the non-terminal stages, weighted to earlier.
            st = rng.choice(STAGES[:-1], p=[0.32, 0.30, 0.22, 0.16])
            # Entered the stage some days ago (this drives aging / SLA breach).
            # Most records are recent; a right-skewed tail creates realistic
            # SLA breaches without making breaches the norm.
            days_in_stage = int(min(a + 2, round(rng.exponential(1.9))))
            stage_entered_date[i] = AS_OF_DATE - pd.Timedelta(days=days_in_stage)
        stage[i] = st

    df = pd.DataFrame(
        {
            "order_id": order_ids,
            "quote_id": quote_ids,
            "created_date": created_date,
            "segment": segment,
            "region": region,
            "product": product,
            "rep": rep,
            "quantity": quantity,
            "unit_price": unit_price,
            "discount_pct": discount_pct,
            "line_total": line_total,
            "stage": stage,
            "stage_entered_date": pd.to_datetime(stage_entered_date),
            "closed_date": pd.to_datetime(closed_date),
        }
    )

    df["status"] = np.where(df["stage"] == TERMINAL_STAGE, "Closed", "Open")

    # Days the record has been sitting in its current stage (aging).
    df["days_in_stage"] = (AS_OF_DATE - df["stage_entered_date"]).dt.days.clip(lower=0)

    # Cycle time (created -> closed) in days, for closed orders only.
    df["cycle_time_days"] = (df["closed_date"] - df["created_date"]).dt.days

    # SLA target for the current stage + breach flag for OPEN records.
    df["stage_sla_days"] = df["stage"].map(STAGE_SLA_DAYS)
    df["sla_breached"] = (df["status"] == "Open") & (
        df["days_in_stage"] > df["stage_sla_days"]
    )

    # ------------------------------------------------------------------
    # Inject KNOWN data-quality defects for the audit view to catch.
    # Counts are fixed so the README / app can state expected findings.
    # ------------------------------------------------------------------
    df = df.reset_index(drop=True)
    defect_rng = np.random.default_rng(SEED + 1)

    def pick(n: int, exclude: set[int]) -> list[int]:
        choices = [i for i in range(len(df)) if i not in exclude]
        return list(defect_rng.choice(choices, size=n, replace=False))

    used: set[int] = set()

    # 1) Math errors: line_total != quantity * unit_price * (1 - discount). (40)
    math_idx = pick(40, used)
    used.update(math_idx)
    for i in math_idx:
        # Corrupt the stored total by a random multiplicative or additive error.
        factor = defect_rng.choice([0.9, 1.1, 1.25, 0.5])
        df.loc[i, "line_total"] = np.round(df.loc[i, "line_total"] * factor + 1, 2)

    # 2) Missing required fields: null customer segment or product. (25)
    missing_idx = pick(25, used)
    used.update(missing_idx)
    for j, i in enumerate(missing_idx):
        if j % 2 == 0:
            df.loc[i, "segment"] = np.nan
        else:
            df.loc[i, "product"] = np.nan

    # 3) Non-positive quantity or unit price. (18)
    badval_idx = pick(18, used)
    used.update(badval_idx)
    for j, i in enumerate(badval_idx):
        if j % 2 == 0:
            df.loc[i, "quantity"] = defect_rng.choice([0, -1, -5])
        else:
            df.loc[i, "unit_price"] = defect_rng.choice([0.0, -100.0])

    # 4) Duplicate order IDs: overwrite some IDs with an existing one. (12 dupes)
    dup_idx = pick(12, used)
    used.update(dup_idx)
    donor_pool = [i for i in range(len(df)) if i not in used]
    donors = list(defect_rng.choice(donor_pool, size=len(dup_idx), replace=False))
    for i, d in zip(dup_idx, donors):
        df.loc[i, "order_id"] = df.loc[d, "order_id"]

    # Shuffle so defects aren't clustered at the end, then stable sort by date.
    df = df.sample(frac=1.0, random_state=SEED).reset_index(drop=True)
    df = df.sort_values("created_date").reset_index(drop=True)

    return df


# ---------------------------------------------------------------------------
# Business-rule audit (shared by the app's discrepancy view)
# ---------------------------------------------------------------------------
def audit_orders(df: pd.DataFrame) -> pd.DataFrame:
    """Audit orders against business rules; return one row per violation.

    Columns: order_id, rule, detail, severity.
    """
    rows: list[dict] = []

    # Rule A — line total must equal quantity * unit_price * (1 - discount).
    expected = (df["quantity"] * df["unit_price"] * (1.0 - df["discount_pct"])).round(2)
    mask = (
        df["quantity"].notna()
        & df["unit_price"].notna()
        & (df["line_total"].round(2) != expected)
    )
    for _, r in df[mask].iterrows():
        exp = round(r["quantity"] * r["unit_price"] * (1.0 - r["discount_pct"]), 2)
        rows.append(
            {
                "order_id": r["order_id"],
                "rule": "Price math mismatch",
                "detail": f"line_total {r['line_total']:.2f} != expected {exp:.2f}",
                "severity": "High",
            }
        )

    # Rule B — required fields must be present.
    for field in ["segment", "product"]:
        mask = df[field].isna()
        for _, r in df[mask].iterrows():
            rows.append(
                {
                    "order_id": r["order_id"],
                    "rule": "Missing required field",
                    "detail": f"{field} is blank",
                    "severity": "Medium",
                }
            )

    # Rule C — quantity and unit_price must be positive.
    mask = df["quantity"].notna() & (df["quantity"] <= 0)
    for _, r in df[mask].iterrows():
        rows.append(
            {
                "order_id": r["order_id"],
                "rule": "Non-positive quantity",
                "detail": f"quantity = {r['quantity']}",
                "severity": "High",
            }
        )
    mask = df["unit_price"].notna() & (df["unit_price"] <= 0)
    for _, r in df[mask].iterrows():
        rows.append(
            {
                "order_id": r["order_id"],
                "rule": "Non-positive unit price",
                "detail": f"unit_price = {r['unit_price']}",
                "severity": "High",
            }
        )

    # Rule D — order IDs must be unique.
    dup_ids = df["order_id"].value_counts()
    dup_ids = dup_ids[dup_ids > 1].index.tolist()
    for oid in dup_ids:
        count = int((df["order_id"] == oid).sum())
        rows.append(
            {
                "order_id": oid,
                "rule": "Duplicate order ID",
                "detail": f"appears {count} times",
                "severity": "High",
            }
        )

    audit = pd.DataFrame(rows, columns=["order_id", "rule", "detail", "severity"])
    return audit


if __name__ == "__main__":
    data = generate_orders()
    violations = audit_orders(data)
    print(f"Generated {len(data)} synthetic orders.")
    print(f"Open: {(data['status'] == 'Open').sum()} | "
          f"Closed: {(data['status'] == 'Closed').sum()}")
    print(f"SLA breaches (open): {int(data['sla_breached'].sum())}")
    print(f"Audit violations found: {len(violations)}")
    print(violations["rule"].value_counts().to_string())
