"""Set the coverage gap of every scored tract that holds no Overture road, building or place to 1.

Under the published definition each component compares an Overture count or length with a reference. With a zero
Overture numerator, any component that is defined has a gap of 1, and a tract in the authoritative sample list has at
least one defined component, so its score is 1. In the challenge package this applies to two Texas water tracts,
48039990000 and 48057990000. Unscored Eastern Washington rows are left as they are.

usage: python src/edge_no_overture.py <in.csv> <out.csv> [features_dir]
"""
import glob
import sys
from pathlib import Path

import pandas as pd

ROOT = str(Path(__file__).resolve().parents[1])


def main():
    src, dst = sys.argv[1], sys.argv[2]
    feats = sys.argv[3] if len(sys.argv) > 3 else ROOT + "/third_party/overture-coverage-equity/data/features"
    t = pd.concat([pd.read_parquet(p) for p in sorted(glob.glob(feats + "/*-features.parquet"))], ignore_index=True)
    t["GEOID"] = t["GEOID"].astype(str)
    empty = t[(t.region != "eastern-wa") & (t.road_km_all.fillna(0) <= 0) & (t.bld_n.fillna(0) == 0) & (t.poi_n.fillna(0) == 0)]
    sub = pd.read_csv(src, dtype={"GEOID": str})
    hit = sub.GEOID.isin(set(empty.GEOID))
    sub.loc[hit, "coverage_gap_score"] = 1.0
    sub.to_csv(dst, index=False)
    print(f"set {int(hit.sum())} tract(s) with no Overture data to 1: {sorted(sub.GEOID[hit])}")


if __name__ == "__main__":
    main()
