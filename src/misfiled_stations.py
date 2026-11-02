#!/usr/bin/env python3
"""Find emergency stations that are in the Overture places layer but outside the category consumers query.

The organiser's facility comparison (data/README.md) matches Overture places to fire stations on
categories.primary = 'fire_department' and to EMS on 'ambulance_and_ems_services'. A station whose record carries
another primary category (for example a community service or a government office) is present in the open map yet
counts as missing, and an application that searches by category does not find it either.

For every scored tract this script counts places whose primary category is the emergency category, and places whose
name identifies a fire or EMS station (or whose alternate categories include the emergency category) while the
primary category is something else. Permitted challenge data only: Overture places, census tract boundaries and the
strata table. Outputs go to analysis/misfiled/.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import EXTENSIONS, TEMP, sql_path  # noqa: E402

REGIONS = ["eastern-ok", "maricopa-az", "northern-ca", "south-central-tx", "eastern-wa"]
OUT = ROOT / "analysis" / "misfiled"

FIRE_NAME = (r"(fire[ -]?(station|dept|department|district|rescue|protection|company|house|hall|authority|"
             r"service|services|co\.?\b)|volunteer fire|\bv\.?f\.?d\.?\b|\bf\.?p\.?d\.?\b|bomberos|fire ?& ?rescue|"
             r"fire and rescue|firehouse)")
FIRE_EXCLUDE = (r"(grill|pizza|bbq|barbecue|\bbar\b|pub\b|church|firework|extinguisher|sprinkler|alarm|insurance|"
                r"firearm|wood|\bpit\b|stone|equipment|supply|supplies|museum|store|shop|restaurant|cafe|kitchen|"
                r"brew|smoke|fireplace|academy|training|auxiliary|association|foundation|credit union|apparel|"
                r"tavern|saloon|winery|distill|salon|tattoo|realty|church|ministr|chapel)")
EMS_NAME = r"(\bems\b|ambulance|emergency medical|rescue squad|paramedic|\bmedic\b)"
EMS_EXCLUDE = (r"(billing|training|academy|school|college|supply|supplies|equipment|uniform|insurance|repair|"
               r"transport services? inc|air ambulance card|chaser|veterinar|animal)")


def region_sql(region: str) -> str:
    ref = ROOT / "data" / "reference" / region
    strata_dir = ROOT / "data" / "strata" / region
    sample = ref / f"{region}-sample-submission.csv"
    tracts = strata_dir / f"{region}-census-tracts.parquet"
    strata = strata_dir / f"{region}-strata-tract-table.parquet"
    pois = ref / f"{region}-overture-pois.parquet"
    out_tract = OUT / f"{region}-tracts.parquet"
    out_poi = OUT / f"{region}-candidate-places.parquet"
    return f"""
SET extension_directory='{sql_path(EXTENSIONS)}';
SET memory_limit='4GB';
SET threads=4;
SET temp_directory='{sql_path(TEMP)}';
INSTALL spatial;
LOAD spatial;
CREATE OR REPLACE TEMP TABLE t AS
SELECT s.GEOID, g.NAMELSAD::VARCHAR AS tract_name, g.geometry,
       st.pop_total::BIGINT AS population, st.pct_urban::DOUBLE AS pct_urban, st.ur_class::VARCHAR AS ur_class,
       st.tribal_any::BOOLEAN AS tribal_any, st.aiannh_name::VARCHAR AS aiannh_name,
       st.svi_overall::DOUBLE AS svi_overall, st.svi_minority::DOUBLE AS svi_minority,
       st.usfs_WHP_mean::DOUBLE AS whp_mean, st.COUNTYFP::VARCHAR AS countyfp
FROM read_csv('{sql_path(sample)}', header=true, types={{'GEOID':'VARCHAR'}}) s
JOIN read_parquet('{sql_path(tracts)}') g ON g.GEOID::VARCHAR = s.GEOID
LEFT JOIN read_parquet('{sql_path(strata)}') st ON st.GEOID::VARCHAR = s.GEOID;
CREATE OR REPLACE TEMP TABLE p AS
SELECT t.GEOID, x.id, x.names.primary AS name, x.categories.primary AS category,
       coalesce(x.categories.alternate, []) AS alternates, x.confidence, x.operating_status,
       x.sources[1].dataset AS source, ST_X(x.geometry) AS lon, ST_Y(x.geometry) AS lat
FROM t JOIN read_parquet('{sql_path(pois)}') x ON ST_Intersects(t.geometry, x.geometry)
QUALIFY row_number() OVER (PARTITION BY x.id ORDER BY t.GEOID) = 1;
CREATE OR REPLACE TEMP TABLE c AS
SELECT *,
  category = 'fire_department' AS fire_primary,
  category = 'ambulance_and_ems_services' AS ems_primary,
  (regexp_matches(lower(coalesce(name, '')), '{FIRE_NAME}') AND NOT regexp_matches(lower(coalesce(name, '')), '{FIRE_EXCLUDE}')) AS fire_name,
  list_contains(alternates, 'fire_department') AS fire_alt,
  (regexp_matches(lower(coalesce(name, '')), '{EMS_NAME}') AND NOT regexp_matches(lower(coalesce(name, '')), '{EMS_EXCLUDE}')) AS ems_name,
  list_contains(alternates, 'ambulance_and_ems_services') AS ems_alt
FROM p;
COPY (SELECT '{region}' AS region, GEOID, id, name, category, alternates, confidence, operating_status, source, lon, lat,
             fire_primary, ems_primary, fire_name, fire_alt, ems_name, ems_alt
      FROM c WHERE fire_primary OR ems_primary OR fire_name OR fire_alt OR ems_name OR ems_alt)
  TO '{sql_path(out_poi)}' (FORMAT parquet);
COPY (
  SELECT '{region}' AS region, t.GEOID, t.tract_name, t.population, t.pct_urban, t.ur_class, t.tribal_any, t.aiannh_name,
         t.svi_overall, t.svi_minority, t.whp_mean, t.countyfp,
         count(c.id) FILTER (c.fire_primary) AS fire_primary_n,
         count(c.id) FILTER ((c.fire_name OR c.fire_alt) AND NOT c.fire_primary) AS fire_misfiled_n,
         count(c.id) FILTER (c.ems_primary) AS ems_primary_n,
         count(c.id) FILTER ((c.ems_name OR c.ems_alt) AND NOT c.ems_primary AND NOT c.fire_primary) AS ems_misfiled_n,
         count(c.id) AS places_n
  FROM t LEFT JOIN c ON c.GEOID = t.GEOID
  GROUP BY ALL
) TO '{sql_path(out_tract)}' (FORMAT parquet);
"""


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    TEMP.mkdir(parents=True, exist_ok=True)
    for region in REGIONS:
        sample = ROOT / "data" / "reference" / region / f"{region}-sample-submission.csv"
        if not sample.is_file():
            print(region, "no sample submission; skipped", flush=True)
            continue
        r = subprocess.run(["duckdb", "-c", region_sql(region)], capture_output=True, text=True)
        if r.returncode != 0:
            print(region, "FAILED", r.stderr[-1500:], flush=True)
            return 1
        print(region, "ok", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
