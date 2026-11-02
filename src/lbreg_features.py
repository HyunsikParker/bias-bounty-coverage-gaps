"""Candidate predictors for the leaderboard-calibrated linear estimator (permitted data only).

Inputs: Overture-derived tract features published by teddywasserman/overture-coverage-equity at commit
1c9033ae2373c9c0adbf4f2315bbf6d5485d6fe0 (MIT; built only from the challenge's Overture extracts, ACS and strata),
pct_urban from the supplied strata tables, and analysis/misfiled/classification_deserts.csv (src/misfiled_*.py). No TIGER, Microsoft footprint, HIFLD/USGS or CBP data, no USFS/CarbonPlan building columns.

Each predictor mirrors one part of the published coverage-gap definition:
  road_*     Overture named-class km against an estimate of the TIGER S1100+S1200 km built from Overture `routes`;
  fire_*     no Overture `fire_department` place where a station is likely (name evidence, other category, rural area);
  school_*, ems_*  the same for schools and EMS;
  cbp_*      Overture places per housing unit, low where establishments may outnumber places;
  region_*   region indicators (the road ratio is not comparable across regions).
Writes work/lbreg_features.parquet with GEOID, region and the predictors.
"""
import glob
import sys

import numpy as np
import pandas as pd

from pathlib import Path

ROOT = str(Path(__file__).resolve().parents[1])
TEDDY = sys.argv[1] if len(sys.argv) > 1 else ROOT + "/third_party/overture-coverage-equity/data/features"  # five <region>-features.parquet files
REGIONS = ["eastern-ok", "maricopa-az", "northern-ca", "south-central-tx", "eastern-wa"]


def main():
    t = pd.concat([pd.read_parquet(p) for p in sorted(glob.glob(TEDDY + "/*-features.parquet"))], ignore_index=True)
    # pct_urban (0-1 share) from the supplied strata tables; the only column of our own feature table the predictors use
    o = pd.concat([pd.read_parquet(f"{ROOT}/data/strata/{r}/{r}-strata-tract-table.parquet", columns=["GEOID", "pct_urban"])
                   for r in REGIONS], ignore_index=True)
    o["GEOID"] = o["GEOID"].astype(str)
    f = t.merge(o, on="GEOID", how="left")
    eps = 1e-9
    x = pd.DataFrame({"GEOID": f["GEOID"], "region": f["region"]})

    named = f["road_km_named"]
    for name, ref in [("road_g0", f["road_km_signed"]),
                      ("road_g05", f["road_km_signed"] + 0.5 * f["road_km_county_route"]),
                      ("road_g1", f["road_km_signed"] + f["road_km_county_route"])]:
        defined = ref > 0.1
        gap = np.where(defined, 1 - np.minimum(1, named / np.maximum(ref, eps)), 0.0)
        x[name] = gap * defined / (defined + 2)  # the road share of a three-way mean
        x[name + "_def"] = defined.astype(float)
    x["road_lowclass_share"] = f["road_km_signed_lowclass"] / (f["road_km_signed"] + eps)
    x["road_county_low_share"] = f["road_km_county_lowclass"] / (f["road_km_named"] + f["road_km_county_lowclass"] + eps)

    fire0 = (f["poi_fire"] == 0).astype(float)
    rural = 1 - f["pct_urban"].fillna(1.0)  # pct_urban is a 0-1 share
    x["fire_evidence"] = fire0 * ((f["poi_fire_name_other_cat"] + f["poi_fire_protection"]) > 0)
    x["fire0_rural"] = fire0 * rural
    x["fire0_logarea"] = fire0 * np.log1p(f["ALAND"] / 1e6)
    x["school_evidence"] = ((f["poi_schools"] == 0) & (f["poi_school_name_other_cat"] > 0)).astype(float)
    x["school0"] = (f["poi_schools"] == 0).astype(float)
    x["ems_evidence"] = ((f["poi_ems"] == 0) & (f["poi_ems_name_other_cat"] > 0)).astype(float)

    hu = f["acs_housing_units"].fillna(0)
    ratio = f["poi_n"] / np.maximum(hu, 1)
    x["cbp_lowplaces"] = np.clip(1 - ratio / np.nanmedian(ratio[hu > 50]), 0, 1) * (hu > 50)
    x["bld_osm_share"] = f["bld_n_osm"] / np.maximum(f["bld_n"], 1)
    for r in ["eastern-ok", "maricopa-az", "northern-ca", "south-central-tx"]:
        x["region_" + r.split("-")[0] + ("_" + r.split("-")[1] if r.count("-") > 1 else "")] = (f["region"] == r).astype(float)
    # region-specific road slopes: the TIGER S1200 set differs by region (county roads in OK, FM roads in TX)
    for r, short in [("eastern-ok", "ok"), ("south-central-tx", "tx"), ("maricopa-az", "az"), ("northern-ca", "ca")]:
        x["road_g1_" + short] = x["road_g1"] * (f["region"] == r)
        x["road_g0_" + short] = x["road_g0"] * (f["region"] == r)
    road_undef = 1 - x["road_g1_def"]
    x["fire0_rural_noroad"] = x["fire0_rural"] * road_undef  # the POI half weighs 1/2 when the road is undefined
    x["fire0_any"] = fire0
    x["fire0_noroad"] = fire0 * road_undef
    # tracts with no fire_department place that hold a public fire station filed under another category
    # (src/misfiled_stations.py + src/misfiled_report.py; Overture places only)
    cd = set(pd.read_csv(ROOT + "/analysis/misfiled/classification_deserts.csv", dtype={"GEOID": str}).GEOID)
    x["fire_classdesert"] = x["GEOID"].astype(str).isin(cd).astype(float)
    # building-source composition and density (Overture buildings only; added 2026-10-13 after bld_osm_share read -0.305)
    nb = np.maximum(f["bld_n"], 1)
    x["bld_ms_share"] = f["bld_n_ms"] / nb
    x["bld_esri_share"] = f["bld_n_esri"] / nb
    x["bld_google_share"] = f["bld_n_google"] / nb
    x["bld_per_hu_log"] = np.log1p(f["bld_n"] / np.maximum(f["acs_housing_units"].fillna(0), 1))
    x["bld_small_share"] = f["bld_n_small"] / nb
    Path(ROOT + "/work").mkdir(exist_ok=True)
    x.to_parquet(ROOT + "/work/lbreg_features.parquet", index=False)
    sc = x[x.region != "eastern-wa"]
    desc = sc.drop(columns=["GEOID", "region"]).agg(["mean", "std", "min", "max"]).T
    print(desc.round(4).to_string())


if __name__ == "__main__":
    main()
