# Quote-to-Cash Ops Health

An order-management / deal-desk operations dashboard for the **quote-to-cash**
pipeline, built with Streamlit. It monitors the two things an order-management
analyst lives on: **hitting SLAs against deadlines** and **catching accuracy /
data-quality problems before they ship downstream**.

> **All data is 100% synthetic**, generated locally with a fixed random seed.
> No real customer, revenue, or company data is used. See the disclaimer below.

---

## Why this project

Quote-to-cash ops is fundamentally about *accuracy under deadline pressure and
end-to-end ownership of the order lifecycle*. This dashboard demonstrates that
end to end: it ingests a booking queue, measures SLA attainment and cycle time,
audits every record against business rules, and turns each view into a concrete
recommendation an analyst could act on tomorrow.

## Views

| View | What it answers |
|------|-----------------|
| **1. Ops Overview** | Headline KPI tiles — orders processed, SLA attainment %, accuracy rate (error/discrepancy rate), and average cycle time — each with a target and a delta vs. target. |
| **2. Queue & Aging** | The open-order queue by pipeline stage, aging buckets (0-2 / 3-5 / 6-10 / 10+ days in stage), SLA-breach flags, and a worklist of the oldest breached orders. |
| **3. Discrepancy Audit** | An accuracy control that audits every order against four business rules (price math, missing fields, non-positive values, duplicate IDs), ranks violations by severity, and exports them. |
| **4. Throughput & Accuracy** | Throughput and accuracy trended over time (weekly/daily) with a target threshold line and automatic alert markers on periods that breach it. |

Every view ends with a **"So what"** recommendation that states the takeaway and
the next action, rather than leaving the reader to interpret the chart.

## Business rules checked (the accuracy audit)

- **Price math mismatch** (High): `line_total` must equal `quantity × unit_price × (1 − discount)`.
- **Missing required field** (Medium): `segment` or `product` must not be blank.
- **Non-positive quantity / unit price** (High): both must be `> 0`.
- **Duplicate order ID** (High): each `order_id` must be unique.

The synthetic generator intentionally injects a known set of these defects so the
audit has real violations to catch (~113 violations across the seeded dataset).

## Design

Charts follow Cole Nussbaumer Knaflic's *Storytelling with Data* principles:
takeaway sentence titles (not just "Orders by stage"), decluttered axes, direct
data labels, and color used sparingly — grey for context, red reserved for
"needs attention", green for "on target".

## Run it locally

```bash
# 1. (optional) create a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. install dependencies
pip install -r requirements.txt

# 3. launch the dashboard
streamlit run app.py
```

Then open the URL Streamlit prints (default http://localhost:8501).

You can also regenerate / inspect the synthetic data on its own:

```bash
python data_gen.py
```

## Project structure

```
app.py            # Streamlit multi-view dashboard
data_gen.py       # Synthetic data generator + business-rule audit
requirements.txt  # Dependencies
README.md         # This file
.gitignore
```

## Synthetic-data disclaimer

This project uses **only synthetic data** produced by `data_gen.py` with a fixed
seed (`SEED = 42`) for full reproducibility. The records, customers, prices,
SLAs, and defects are fabricated for demonstration purposes. Nothing here
represents, or is derived from, any real company's data.

## Author

**Leo Chan** — [github.com/GoldenCrate](https://github.com/GoldenCrate)
