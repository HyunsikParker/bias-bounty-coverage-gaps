#!/usr/bin/env python3
"""Summarise places with fire-department names that Overture files outside 'fire_department'.

Run after misfiled_stations.py. A place is a candidate when its primary name matches a fire-department pattern
(fire department, volunteer fire, fire district, fire protection district, fire & rescue, emergency services
district, ...), does not match a business pattern (inc, llc, sprinkler, extinguisher, alarm, ...), is not in a plainly
unrelated category, and is not marked permanently_closed. A candidate is filed elsewhere when its primary category is
not 'fire_department'. Candidates are records whose names point to a fire department; whether each one is an
operating station was not checked against any outside source.

A tract has no fire_department place when no place in it, of any operating status, has that primary category (what a
category query sees). It is a classification desert when it has no fire_department place but holds at least one
candidate filed elsewhere.

Writes analysis/misfiled/: misfiled_fire_stations.csv, classification_deserts.csv, strata_table.csv,
volunteer_table.csv, source_table.csv, precision_sample.csv (60 rows, seed 7 after sorting by record id) and
summary.json.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
A = ROOT / "analysis" / "misfiled"
REGIONS = ["eastern-ok", "maricopa-az", "northern-ca", "south-central-tx", "eastern-wa"]
FIRE_NAME = re.compile(r"(fire (department|dept\.?|district|station|rescue|company (no\.? ?)?\d+|co\.? (no\.? ?)?\d+)|"
                       r"volunteer fire|\bv\.?f\.?d\b|fire protection district|\bf\.?p\.?d\b|fire ?& ?rescue|"
                       r"fire and rescue|fire-rescue|emergency services district|\besd\b ?#? ?\d)", re.I)
BUSINESS = re.compile(r"(\binc\b|\bllc\b|l\.l\.c|\bcorp|\bltd\b|systems|sprinkler|extinguisher|equipment|apparatus|"
                      r"alarm|supply|subs\b|roofing|parts|auto|grill|pizza|bar\b|training|academy|museum|association|"
                      r"auxiliary|foundation|store|shop|consult|engineer|inspection|services, |security|safety|"
                      r"rec hall|4 hire|for hire|historic|city hall and)", re.I)
UNRELATED = {"cannabis_dispensary", "kids_recreation_and_party", "landmark_and_historical_buildings", "restaurant",
             "bar", "sandwich_shop", "fast_food_restaurant", "pizza_restaurant", "beverage_supplier", "brewery",
             "winery", "museum", "party_and_event_planning", "tire_dealer_and_repair", "roofing"}
VOLUNTEER = re.compile(r"(volunteer|\bv\.?f\.?d\b|\bvol\.?\b)", re.I)


def load_places() -> pd.DataFrame:
    p = pd.concat([pd.read_parquet(A / f"{r}-candidate-places.parquet") for r in REGIONS], ignore_index=True)
    for b in ["fire_primary", "ems_primary", "fire_name", "fire_alt", "ems_name", "ems_alt"]:
        p[b] = p[b].fillna(False).astype(bool)
    name = p["name"].fillna("")
    p["candidate"] = (name.map(lambda s: bool(FIRE_NAME.search(s)) and not BUSINESS.search(s))
                      & ~p["category"].isin(UNRELATED) & (p["operating_status"] != "permanently_closed"))
    p["filed_elsewhere"] = p.candidate & ~p.fire_primary
    p["volunteer"] = name.map(lambda s: bool(VOLUNTEER.search(s)))
    return p.sort_values("id").reset_index(drop=True)  # DuckDB output order varies between runs


def load_tracts(p: pd.DataFrame) -> pd.DataFrame:
    t = pd.concat([pd.read_parquet(A / f"{r}-tracts.parquet") for r in REGIONS], ignore_index=True)
    t["filed_elsewhere_n"] = t.GEOID.map(p[p.filed_elsewhere].groupby("GEOID").size()).fillna(0).astype(int)
    t["no_fire_category"] = t.fire_primary_n == 0
    t["classification_desert"] = t.no_fire_category & (t.filed_elsewhere_n > 0)
    t["rural"] = t.pct_urban < 0.5
    t["wildfire_top_quartile"] = t.whp_mean >= t.whp_mean.quantile(0.75)
    t["rural_and_wildfire"] = t.rural & t.wildfire_top_quartile
    return t


def main() -> int:
    p = load_places()
    t = load_tracts(p)
    c = p[p.candidate]
    mis = p[p.filed_elsewhere].copy()

    rows = []
    for col in ["rural", "tribal_any", "wildfire_top_quartile", "rural_and_wildfire"]:
        for val, g in t.groupby(col):
            nf = g[g.no_fire_category]
            rows.append({"stratum": col, "value": bool(val), "tracts": len(g), "no_fire_category": int(len(nf)),
                         "classification_deserts": int(g.classification_desert.sum()),
                         "share_of_no_fire_tracts": round(float(nf.classification_desert.mean()), 4) if len(nf) else None,
                         "population_in_classification_deserts": int(g[g.classification_desert].population.sum())})
    pd.DataFrame(rows).to_csv(A / "strata_table.csv", index=False)

    vol = c.groupby(["region", "volunteer"]).filed_elsewhere.agg(candidates="size", filed_elsewhere="sum").reset_index()
    vol_all = c.groupby("volunteer").filed_elsewhere.agg(candidates="size", filed_elsewhere="sum").reset_index()
    vol_all.insert(0, "region", "all")
    vol = pd.concat([vol, vol_all], ignore_index=True)
    vol["share"] = (vol.filed_elsewhere / vol.candidates).round(4)
    vol.to_csv(A / "volunteer_table.csv", index=False)
    src = c.groupby(c.source.fillna("<none>")).filed_elsewhere.agg(candidates="size", filed_elsewhere="sum").reset_index()
    src["share"] = (src.filed_elsewhere / src.candidates).round(4)
    src.to_csv(A / "source_table.csv", index=False)

    keep = ["region", "GEOID", "id", "name", "category", "operating_status", "source", "confidence", "lon", "lat"]
    mis = mis.merge(t[["GEOID", "tract_name", "countyfp", "pct_urban", "tribal_any", "aiannh_name", "whp_mean",
                       "fire_primary_n"]], on="GEOID", how="left")
    mis[keep + ["tract_name", "countyfp", "pct_urban", "tribal_any", "aiannh_name", "whp_mean", "fire_primary_n"]] \
        .sort_values(["region", "GEOID", "id"]).to_csv(A / "misfiled_fire_stations.csv", index=False)
    t[t.classification_desert][["region", "GEOID", "tract_name", "countyfp", "population", "pct_urban", "tribal_any",
                                "aiannh_name", "whp_mean", "filed_elsewhere_n"]] \
        .sort_values(["region", "GEOID"]).to_csv(A / "classification_deserts.csv", index=False)
    mis.sample(min(60, len(mis)), random_state=7)[["id", "region", "name", "category", "operating_status", "source"]] \
        .to_csv(A / "precision_sample.csv", index=False)

    summary = {
        "scored_tracts": int(len(t)),
        "permanently_closed_name_matches_excluded": int((p.candidate.eq(False) & (p.operating_status == "permanently_closed")
                                                         & p["name"].fillna("").map(lambda s: bool(FIRE_NAME.search(s)) and not BUSINESS.search(s))
                                                         & ~p["category"].isin(UNRELATED)).sum()),
        "candidates": int(len(c)),
        "candidates_filed_fire_department": int(c.fire_primary.sum()),
        "candidates_filed_elsewhere": int(len(mis)),
        "filed_elsewhere_categories": mis.category.fillna("<none>").value_counts().head(12).to_dict(),
        "filed_elsewhere_operating_status": mis.operating_status.fillna("<missing>").value_counts().to_dict(),
        "candidates_operating_status": c.operating_status.fillna("<missing>").value_counts().to_dict(),
        "tracts_without_fire_department_place": int(t.no_fire_category.sum()),
        "classification_deserts": int(t.classification_desert.sum()),
        "population_in_classification_deserts": int(t[t.classification_desert].population.sum()),
        "rural_classification_deserts_in_top_wildfire_quartile": int((t.classification_desert & t.rural_and_wildfire).sum()),
        "rural_classification_deserts": int((t.classification_desert & t.rural).sum()),
    }
    (A / "summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))
    print(pd.read_csv(A / "strata_table.csv").to_string(index=False))
    print(vol.to_string(index=False))
    print(src.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
