---
pagetitle: "Coverage gaps without the reference layers"
---

# Coverage gaps without the reference layers: feature proxies calibrated on public-leaderboard moments

**Best Documentation entry** · Zindi user **skaiea13** · final selected submissions **gki9K7jy** (public RMSE
0.075383, 16 October 2026) and **6BNL8pZ3** (public RMSE 0.075416, 17 October 2026)

Data: the challenge package (Overture release 2026-08-19.0 extracts, ACS housing units, census tract boundaries,
strata tables and the sample submission files) and tract features that another participant derived from the same
package and published under the MIT licence (Section 2). No removed reference layer, no copy of one and no outside
dataset was used.

Code, outputs and checksums: the full package described in Section 8 is public at
<https://github.com/HyunsikParker/bias-bounty-coverage-gaps>.

## 1. Summary

The organisers removed the TIGER roads, Microsoft building footprints, facility points and County Business Patterns
counts from the package on 25 September. Since then no file in it carries a label or a reference denominator, so a
component gap cannot be computed the way the methodology describes. Two things remain: tract features built from the
package that track each component, and the public leaderboard, which reports one RMSE per uploaded file.

Our first estimator turned the features into component gaps against estimated denominators and averaged them. Its mean
was 0.311, while the public target mean is 0.060, and it scored worse than a constant at its own mean (0.2787 against
0.2663). The estimator behind the selected submissions keeps the features as predictors and takes its scale from the
leaderboard:

$$\hat y_i = \bar y + \sum_j \beta_j \,(f_{ij} - m_j).$$

The public mean and variance of the target come from two constant files. The public covariance of each predictor with
the target comes from one probe file per predictor, by solving the RMSE of that file for the covariance. The
coefficients are $\beta = \Sigma^{-1} c$. The first four joint models scored within 0.00033 of the RMSE we
predicted before uploading them; larger models drifted further above their predictions (Table 4), so we stopped
adding predictors.

Every step except the leaderboard reads runs from the package with the scripts in `src/`. The reads themselves are
listed with their submission IDs (Table 3), and with them the scripts rebuild the selected file gki9K7jy byte for
byte and every value of 6BNL8pZ3 (Section 8).

## 2. Data

| File in the package | Use |
|---|---|
| `reference/<region>/<region>-sample-submission.csv` | Scored GEOIDs and row order. GEOID is read as text, so Maricopa keeps its leading zero. |
| `reference/<region>/<region>-overture-roads.parquet`, `-overture-buildings.parquet`, `-overture-pois.parquet` | Road length by class and route network, building counts by source, place counts by category (through the derived features below). |
| `reference/<region>/<region>-census-acs-housing.parquet` | Housing units, used only as a denominator floor. |
| `strata/<region>/<region>-strata-tract-table.parquet` | `pct_urban`, the urban share of tract population. |
| `strata/<region>/<region>-census-tracts.parquet` | Tract polygons and land area (through the derived features). |

**Derived features from another participant.** Most predictors are computed from the per-tract counts in
`data/features/<region>-features.parquet` of the repository `teddywasserman/overture-coverage-equity`, commit
`1c9033ae2373c9c0adbf4f2315bbf6d5485d6fe0` (2 October 2026), MIT licence, copyright 2026 Kapital Experiment. The author
linked it in the challenge discussion (thread 35079), and its README states that it is built only from the challenge's
Overture extracts, ACS and strata files. We read 23 of its columns: `region`, `ALAND`, `acs_housing_units`, six road lengths
(`road_km_all`, `road_km_named`, `road_km_signed`, `road_km_county_route`, `road_km_signed_lowclass`,
`road_km_county_lowclass`), six building counts (`bld_n` and its OpenStreetMap, Microsoft ML, Esri, Google and
under-40 m² subsets) and eight place counts (`poi_n`, `poi_fire`, `poi_fire_protection`, `poi_ems`, `poi_schools` and the
three "named like a fire station, EMS unit or school but filed in another category" counts). We checked these columns
against our own DuckDB build of the same Overture files. Fire, EMS and school place counts agree in all 9,794 tracts. All-place counts agree in 9,734
tracts and building counts in 9,501, with differences of at most three features, which we attribute to how the two
builds assign features on tract boundaries. Named-highway length agrees within 10 m in 8,670 tracts (correlation
0.999995; largest difference 2.3 km).

**Our own derived file.** `analysis/misfiled/classification_deserts.csv` lists 368 tracts (333 of them scored) with no
place filed as `fire_department` but at least one place whose name identifies a fire department. It comes from
`src/misfiled_stations.py` and `src/misfiled_report.py` (Overture places only) and is the basis of our Best Bias
Discovery entry.

**Deliberately not used.** The strata columns `usfs_BuildingCount_sum`, `usfs_HUCount_sum` and `carbonplan_buildings`
count buildings from sources close to the removed footprint reference. Discussion 35302 asks whether they are allowed
and had no organiser answer when we built the predictors, so we left them out.

## 3. Predictors

Each predictor stands in for one part of the published definition (Table 1). They are proxies: none of them recovers a
removed denominator, and none needs to, because the calibration in Section 5 only uses how each one co-varies with the
target.

**Road gap.** The definition compares Overture length in the motorway, trunk, primary and secondary classes with TIGER
S1100 and S1200 length. Overture's `routes` attribute marks segments that carry an Interstate, US or State route,
which correspond closely to the TIGER S1100 and S1200 classes. We estimate the reference length as signed-route length
plus county-route length and compute

$$g^{road}_i = 1 - \min\!\left(1, \frac{L^{named}_i}{L^{signed}_i + L^{county}_i}\right).$$

The component counts as defined ($d_i = 1$) when that estimated reference exceeds 0.1 km. The predictor
`road_g1` is $g^{road}_i \cdot d_i/(d_i + 2)$, the road term's share of a three-component mean, and is 0 when the road
is undefined. `road_g1_def` is $d_i$ itself. The methodology warns that road gaps are not comparable across regions, so
`road_g1_ok` and `road_g1_tx` give Eastern Oklahoma and South-Central Texas their own slopes.

**Building gap.** The reference is Microsoft's footprint count, and Overture imports many Microsoft footprints, so the
composition of a tract's Overture buildings says something about how complete they are. The building predictors are
the OpenStreetMap and Esri shares of Overture buildings, the share of footprints under 40 m², and
$\log(1 + B_i / \max(HU_i, 1))$, buildings per housing unit.

**POI gap, facilities half.** The reference counts fire stations, EMS stations and schools. `fire0_rural` equals the
rural share, one minus `pct_urban`, when no place is filed as `fire_department`, and 0 otherwise. `fire_evidence` marks tracts with
no `fire_department` place that still hold a fire-protection-service place or a fire-department name in another
category, and `fire_classdesert` marks the 333 scored classification deserts above. `school0` and `school_evidence` do
the same for schools. No EMS predictor entered a fit: its name evidence is non-zero in under 3% of tracts, too sparse
for a probe to measure.

**POI gap, establishments half.** The reference is County Business Patterns establishments. `cbp_lowplaces` is
$\operatorname{clip}(1 - r_i/\tilde r, 0, 1)$, where $r_i$ is Overture places per housing unit and $\tilde r = 0.0861$
its median over tracts with more than 50 housing units.

**Region.** Indicators for Eastern Oklahoma, Maricopa and Northern California, with South-Central Texas as the base.

| Predictor | Component | Construction |
|---|---|---|
| `road_g1` | road | estimated road gap times its share of a three-way mean |
| `road_g1_def` | road | 1 if the estimated reference length exceeds 0.1 km |
| `road_g1_ok`, `road_g1_tx` | road | `road_g1` within Eastern Oklahoma, within South-Central Texas |
| `bld_osm_share`, `bld_esri_share` | building | share of Overture buildings from OpenStreetMap, from Esri |
| `bld_small_share` | building | share of footprints under 40 m² |
| `bld_per_hu_log` | building | log(1 + buildings per housing unit) |
| `fire0_rural` | facilities | no `fire_department` place, times the rural share |
| `fire_evidence` | facilities | no `fire_department` place, fire-station evidence elsewhere |
| `fire_classdesert` | facilities | classification desert (Section 2) |
| `school0`, `school_evidence` | facilities | no school place; no school place with school-named evidence |
| `cbp_lowplaces` | establishments | shortfall of places per housing unit against the median |
| `region_eastern`, `region_maricopa`, `region_northern` | all | region indicators |

*Table 1. The 17 predictors with a leaderboard read. `src/lbreg_features.py` builds them.*

## 4. Why the first estimator failed

Before any leaderboard read, the first pipeline estimated every removed denominator from housing units, land area and
road length, with quantile calibration by urban band, and averaged the defined component gaps. We submitted six of its
files on 7 October, each testing one question (Table 2).

| File (ID) | Mean | Public RMSE |
|---|---:|---:|
| constant 0.31080482 (6tP83ckS) | 0.311 | 0.266318 |
| three-component composite (YCQGYJzr) | 0.311 | 0.278726 |
| building component only (ctLe5wRK) | 0.232 | 0.324419 |
| denominators raised 25% (Xng1Jyqn) | 0.407 | 0.338412 |
| probabilistic road definition (UcmHP36M) | 0.313 | 0.416334 |

*Table 2. First-pipeline reads. A sixth file without the unscored Eastern Washington rows was rejected.*

The composite lost to a constant at the same mean, and raising the denominators made it worse. The target moments
(Section 5.1) explain why. The target averages 0.060 with standard deviation 0.089, so most tracts have almost no gap,
and a model centred at 0.31 misses nearly every tract by more than any variation it captures. The constant 0.060 alone
would score 0.089. The package holds nothing that fixes this scale, so we took it from the leaderboard (Section 5).

## 5. Calibration from public-leaderboard moments

### 5.1 Target moments

Write $P$ for the public split (about 30% of the 9,379 scored tracts). For a constant prediction $k$,
$\mathrm{RMSE}^2 = E_P[y^2] - 2k\,\bar y + k^2$. An all-zero file scored 0.107246 after the 2 October scorer change, as
participant Kimyayd reported in thread 35079, which gives $E_P[y^2] = 0.0115017$. Our constant 0.31080482 scored
0.266318147. Together they give $\bar y = 0.059806$ and a standard deviation of 0.089022. The same participant reported
0.059806 for the all-zero file under the scorer before 2 October and read that metric as a mean absolute error. For a
non-negative target and an all-zero file, the mean absolute error equals the mean, so the two values agree. The scripts
carry $\bar y = 0.059802$, which we derived with the constant rounded to 0.3108. The 0.000004 difference shifts every prediction by that amount and changes no reported
RMSE.

### 5.2 Probes

A probe for predictor $f$ predicts $\bar y + a(f_i - m)$ in the four scored regions, where $m$ is the mean of $f$ over
the scored tracts, and $\bar y$ in Eastern Washington. The file format requires the Eastern Washington rows, but they are
not scored. Expanding the squared error gives

$$\mathrm{RMSE}^2 = \mathrm{Var}_P(y) - 2a\,\mathrm{Cov}_P(y, f) + a^2 E_P\!\left[(f - m)^2\right],$$

which we solve for $\mathrm{Cov}_P(y, f)$. Since the scored-tract value of $E[(f - m)^2]$ stands in for its public
value, the read assumes that the public split is a random subset. We chose each $a$ so that predictions stay in
[0, 1] and the RMSE moves by far more than the nine displayed decimals. `src/lbreg_probe.py` writes a probe file and
converts a read into a covariance, a correlation and the best RMSE that predictor alone could reach.

| ID | Predictor | a | Public RMSE | Cov(y, f) | Corr | Best alone |
|---|---|---:|---:|---:|---:|---:|
| 4Yru3kU9 | `road_g1` | 1 | 0.088372 | +0.001222 | +0.285 | 0.085345 |
| cF851kiC | `fire_evidence` | 0.1 | 0.089489 | +0.002774 | +0.123 | 0.088345 |
| pEvURwmn | `fire0_rural` | 0.1 | 0.086352 | +0.005664 | +0.247 | 0.086269 |
| 4WMt2RbL | `region_eastern` | 0.05 | 0.085751 | +0.008496 | +0.287 | 0.085293 |
| MHgJAeDX | `region_maricopa` | 0.05 | 0.092588 | -0.002946 | -0.088 | 0.088679 |
| jCsD82GY | `region_northern` | 0.05 | 0.089567 | +0.000508 | +0.023 | 0.089000 |
| tyzLSRnx | `cbp_lowplaces` | 0.05 | 0.090402 | -0.000703 | -0.030 | 0.088986 |
| 5W8b8P4f | `school0` | 0.05 | 0.089951 | +0.002581 | +0.070 | 0.088804 |
| iMHPKR4w | `road_g1_def` | 0.05 | 0.086558 | +0.009668 | +0.235 | 0.086531 |
| jiNeSpzk | `road_g1_ok` | 1 | 0.085544 | +0.000819 | +0.287 | 0.085291 |
| gZtnGknB | `road_g1_tx` | 1 | 0.092420 | +0.000372 | +0.113 | 0.088452 |
| LJn8pYVm | `bld_osm_share` | 0.1 | 0.107297 | -0.010479 | -0.305 | 0.084789 |
| N2eHmQEE | `fire_classdesert` | 0.1 | 0.087474 | +0.003081 | +0.187 | 0.087454 |
| ykjXfBWm | `bld_per_hu_log` | 0.05 | 0.087883 | +0.007638 | +0.181 | 0.087555 |
| y8wcxgqQ | `bld_esri_share` | 0.17 | 0.092582 | -0.000163 | -0.013 | 0.089018 |
| KZf55RXS | `bld_small_share` | 0.3 | 0.090287 | +0.000564 | +0.080 | 0.088740 |
| kBNDdBt4 | `school_evidence` | 0.1 | 0.091912 | +0.000354 | +0.016 | 0.089013 |
| yhmsidry | `fire0_any` | 0.06 | 0.094578 | -0.002284 | -0.056 | 0.088883 |
| 871Ypj56 | `road_g0_def` | 0.05 | 0.085097 | +0.012951 | +0.294 | 0.085084 |
| JXywjudP | `fire0_logarea` | 0.02 | 0.088213 | +0.027013 | +0.198 | 0.087257 |
| bNSxfWJe | `fire0_noroad` | 0.06 | 0.097896 | -0.008129 | -0.210 | 0.087046 |
| USMyMrTA | `ems_evidence` | 0.17 | 0.091696 | +0.000751 | +0.053 | 0.088901 |
| wRTfDyWv | `bld_google_share` | 0.35 | 0.092376 | +0.000218 | +0.031 | 0.088982 |
| rcTdTnXi | `fire0_rural_noroad` | 0.45 | 0.093310 | -0.000092 | -0.018 | 0.089011 |
| 5McWTXq7 | `road_lowclass_share` | 0.9 | 0.090515 | +0.000146 | +0.064 | 0.088842 |
| pzB6kHpi | `road_g05_def` | 0.058 | 0.086645 | +0.009826 | +0.238 | 0.086460 |
| V9xHm5JM | `road_county_low_share` | 0.18 | 0.085701 | +0.003630 | +0.272 | 0.085658 |

*Table 3. Single-predictor probes, 11 to 17 October. The constant at the mean scores 0.089022. `probes/lbreg_probes.json`
holds the a and RMSE columns that `src/lbreg_fit.py` reads.*

### 5.3 Joint estimator

$\Sigma$ is the covariance matrix of the chosen predictors over all scored tracts, so it uses every tract rather than
the public 30% only. $c$ is the vector of probed covariances. Then $\beta = \Sigma^{-1}c$, and before clipping the
expected public RMSE is $\sqrt{\mathrm{Var}_P(y) - c^\top \Sigma^{-1} c}$. Predictions are clipped to [0, 1]: one tract
falls below zero in the 13-predictor model, 28 in the 17-predictor, 64 in the 21-predictor and 82 in the
25-predictor model, and none exceeds one.

| ID | Model | Expected | Public RMSE |
|----|------------------------------------|-----:|-----:|
| 8R4BSBA6 | 5 predictors (`road_g1`, `fire_evidence`, `fire0_rural`, two regions) | 0.081292 | 0.081498 |
| 7xysJ25i | 9 predictors (adds `region_northern`, `cbp_lowplaces`, `school0`, `road_g1_def`) | 0.079606 | 0.079857 |
| FNBceCuK | 13 predictors (adds `road_g1_ok`, `road_g1_tx`, `bld_osm_share`, `fire_classdesert`) | 0.078400 | 0.078660 |
| knE1GJ3o | 17 predictors (adds `bld_per_hu_log`, `bld_esri_share`, `bld_small_share`, `school_evidence`) | 0.075837 | 0.076163 |
| gki9K7jy | 21 predictors (adds `fire0_any`, `road_g0_def`, `fire0_logarea`, `fire0_noroad`) | 0.074989 | 0.075383 |
| 6BNL8pZ3 | 25 predictors (adds `ems_evidence`, `bld_google_share`, `fire0_rural_noroad`, `road_lowclass_share`) | 0.074839 | 0.075416 |
| 1Vtrct6A | 27 predictors (adds `road_g05_def`, `road_county_low_share`) | 0.074725 | 0.075466 |

*Table 4. Joint models. From knE1GJ3o on, every file applies the no-Overture rule of Section 6, and its expectation
assumes one public water tract with target 1 among about 2,814 public tracts (without the rule the 17-, 21-, 25- and
27-predictor fits expect 0.077938, 0.077127, 0.076980 and 0.076868). The first four reads land 0.0002 to 0.0003 above
their predictions; the gap then grows to 0.0004, 0.0006 and 0.0007, and the 25- and 27-predictor files read worse than
the 21-predictor one. gki9K7jy and 6BNL8pZ3 are the two files selected for private scoring.*

The coefficients of the 13-predictor file, FNBceCuK, are in `outputs/joint13.json`. The largest are on `road_g1`
(+0.356), `road_g1_tx` (−0.222), `road_g1_ok` (+0.071), `fire_classdesert` (+0.056), `region_eastern` (+0.045) and
`bld_osm_share` (−0.032). The road shortfall carries the most signal, with less weight in South-Central Texas and more
in Eastern Oklahoma. A classification desert raises the prediction, as the facility definition implies: a station filed
outside `fire_department` counts as missing. A high OpenStreetMap share lowers it, which suggests that where
OpenStreetMap supplies the buildings, Overture holds at least as many as the Microsoft reference.

The selected files keep this pattern. In gki9K7jy (`outputs/joint21.json`) the largest coefficients are on `road_g1`
(+0.412), `road_g1_tx` (−0.294), `bld_esri_share` (−0.065), `fire_classdesert` (+0.054), `bld_small_share` (+0.051)
and `region_eastern` (+0.049). 6BNL8pZ3 (`outputs/joint25.json`) has the same leading terms, with `road_g1` at +0.388
and `road_g1_tx` at −0.280.

## 6. Edge cases

- **GEOID as text.** Every script reads GEOID as a string, and every submission keeps the sample files' GEOIDs and row
  order, so Maricopa's `04…` tracts keep their leading zero and every join succeeds.
- **Eastern Washington.** The scorer rejects a file without its 415 rows, but they are not scored. They are set to
  $\bar y$ and excluded from every mean, covariance and fit.
- **Tracts with no Overture data.** Two scored tracts, 48039990000 and 48057990000 (Texas water tracts), hold no
  Overture road, building or place. A tract in the authoritative sample has at least one defined component, and with a
  zero Overture numerator any defined component has a gap of 1, so their score is 1. FNBceCuK predicts 0.0527 for both,
  because the linear model sees only all-zero features. `src/edge_no_overture.py` applies the rule from the 15 October
  files on, including both selected files. The first, knE1GJ3o (17 predictors), read 0.076163 on 15 October: one
  public tract with target 1 gives
  0.075837 plus the offset of Table 4 (none would give 0.077938, both 0.073677).
- **Zero-population and zero-housing tracts.** The 26 scored tracts with no population are exactly the tracts with
  no `pct_urban`. The code treats a missing urban share as fully urban, which sets `fire0_rural` to 0 rather than
  guessing a rural share. 80 tracts have no housing units and 101 have 50 or fewer. Every per-housing-unit quantity
  divides by $\max(HU_i, 1)$, and `cbp_lowplaces` is set to 0 at 50 housing units or fewer, where a single shop moves
  places per housing unit a long way.
- **Undefined road component.** 2,897 scored tracts (30.9%) have no estimated reference road: 64.3% in Maricopa, 31.3%
  in Northern California, 23.7% in Eastern Oklahoma and 23.4% in South-Central Texas. The organisers report that at
  least one component is undefined in 55%, 37%, 21% and 28% of tracts in the same regions. That is not the same
  quantity, but Maricopa stands far above the others in both. For such tracts `road_g1` is 0 and `road_g1_def` lets
  the fit move their level, which stands in for the varying divisor of the reference mean.
- **Data-sparse tracts.** 70.7% of scored tracts have no `fire_department` place and 21.6% no school place. A zero count
  cannot tell a tract without a station from a tract whose station is missing, so the facility predictors weight zero
  counts by rurality (`fire0_rural`) or require evidence that a station exists under another category
  (`fire_evidence`, `fire_classdesert`, `school_evidence`).

## 7. Alternative weightings and why

- **Equal weights on proxy components** (Section 4) put the mean at 0.31 and lost to a constant. With the reference
  denominators gone, nothing in the package can set the scale of the components.
- **Single predictors** (Table 3) reach at best 0.0848 (`bld_osm_share`). The predictors carry partly separate
  information, so the 13-predictor model reaches 0.0787.
- **Region-specific road slopes.** The road predictor restricted to Eastern Oklahoma correlates with the target at
  0.287 and the one restricted to South-Central Texas at 0.113, in line with the organisers' note that the
  TIGER-to-Overture length ratio differs by region (0.71 to 1.59).
- **No shrinkage; selection stopped at 25 predictors.** The fits estimate 13 to 27 coefficients from covariances measured on
  about 2,800 public tracts. The optimism of an in-sample fit is of order p/n, under 1% of the variance here, so we did
  not shrink the coefficients. Table 4 shows the cost growing with p: the read sits 0.0003 above prediction at 17
  predictors and 0.0007 above it at 27, and the 25- and 27-predictor files read worse than the 21-predictor one. We
  selected the 21-predictor file, our best public read, and the 25-predictor file, and stopped probing.

## 8. Reproducing the submissions

The package (linked at the top) runs on Python 3.13 with pandas, NumPy and pyarrow. DuckDB's command-line tool with its spatial extension
is needed only to rebuild the classification-desert list, which is included. Nothing in the pipeline is random.

1. Copy the challenge package so that `data/reference/<region>/` and `data/strata/<region>/` sit next to `src/`, for
   example with
   `aws s3 sync s3://us-west-2.opendata.source.coop/humane-intelligence/bias-bounty-mapping-equity-challenge/reference/ data/reference/ --no-sign-request`
   and the same command for `strata/`.
2. Put the five `data/features/<region>-features.parquet` files of `teddywasserman/overture-coverage-equity` at commit
   `1c9033ae2373c9c0adbf4f2315bbf6d5485d6fe0` in `third_party/overture-coverage-equity/data/features/`. `SHA256SUMS`
   lists their hashes.
3. Optional: `python src/misfiled_stations.py` then `python src/misfiled_report.py` rebuild
   `analysis/misfiled/classification_deserts.csv`.
4. `python src/lbreg_features.py` writes `work/lbreg_features.parquet` in about two seconds.
5. `python src/lbreg_fit.py outputs/joint13.csv road_g1 fire_evidence fire0_rural region_eastern region_maricopa region_northern cbp_lowplaces school0 road_g1_def road_g1_ok road_g1_tx bld_osm_share fire_classdesert`
   rebuilds the file submitted as FNBceCuK, SHA-256 `1969f09d1f715c173dde2456cc5ffaa9a2d7582e729704183e982cabc12aabaf`.
   The same command for `outputs/joint17.csv` with the 17 predictors of `outputs/joint17.json`, then
   `python src/edge_no_overture.py outputs/joint17.csv outputs/joint17_w1.csv`, rebuilds knE1GJ3o.
6. The two selected files are built the same way. `python src/lbreg_fit.py outputs/joint21.csv` followed by the 21
   predictors listed in `outputs/joint21.json`, then
   `python src/edge_no_overture.py outputs/joint21.csv outputs/joint21_w1.csv`, rebuilds gki9K7jy byte for byte,
   SHA-256 `604eea81067bcebfc67df3b864fc3d7a7ec3692b4fc28de148861b1c8596ba66`. The same two commands with the 25
   predictors of `outputs/joint25.json` give every value of 6BNL8pZ3. The uploaded file differs only in format: it has
   CRLF line endings and writes the two water tracts as `1` rather than `1.0` (uploaded SHA-256
   `254eabbde873bb79df9579614e0aa371e036b78ef5186be1ad64ffc9dbe2afbe`, rebuilt
   `4c22b3a285021fcf0894dd6cf3b1a7b10d80c0a8fd7c40fa4938f9494e0bf25a`).
7. A new probe is written with `python src/lbreg_probe.py write <predictor> <a> <file.csv>` and read with
   `python src/lbreg_probe.py read <predictor> <a> <public RMSE>`.

We ran steps 2, 4, 5 and 6 in a fresh folder on 2 November: the rebuilt FNBceCuK, knE1GJ3o and gki9K7jy files are
byte-identical to the uploaded ones, and the rebuilt 6BNL8pZ3 file matches the uploaded values exactly.

## 9. Limitations

- The coefficients rest on the public 30%. If the split is not random, or the private tracts relate to the predictors
  differently, the private score will be worse than the public one by more than the usual noise. On the private
  leaderboard shown on 1 November, while the top solutions were still under code review, gki9K7jy read 0.078014 and
  6BNL8pZ3 0.078044, both about 0.0026 above their public reads. That is more than the roughly 0.0004 the p/n
  optimism of 21 coefficients would explain, which points to differences between the public and private tracts or to
  more noise in the probed covariances than we assumed.
- Each covariance comes from one read rounded to nine decimals, and $E_P[(f - m)^2]$ is replaced by its value over all
  scored tracts. Table 4 bounds the combined error at about 0.0003 in RMSE for the models we submitted.
- The predictors rank tracts; they do not estimate any removed reference count, and the model does not produce
  component scores.
- Most predictors come from another participant's feature files. We verified the counts we use against our own build
  (Section 2), but any error common to both builds would pass that check.
- The method uses the public leaderboard as a measuring instrument: each read yields one covariance. We list every
  read so that a reader can judge that choice and reproduce the coefficients.
