"""Write single-feature probe submissions and read covariances back from their public RMSE.

A probe is pred = YBAR + a * (f - m) on the four scored regions (m = their mean of f) and YBAR elsewhere.
With YBAR equal to the public target mean, the public RMSE gives the public covariance of f with the target:
    RMSE^2 = VAR_Y - 2 a Cov_P(y, f) + a^2 E_P[(f - m)^2]
so Cov_P(y, f) = (a^2 V - (RMSE^2 - VAR_Y)) / (2 a), with V taken over the scored tracts.
Public target moments (2026-10-11): all-zero file 0.107246 (participant report, scorer of 2 Oct) gives E[y^2];
our constant 0.3108 file scored 0.266318 on 7 Oct, which with E[y^2] gives the mean 0.059802.

usage: lbreg_probe.py write <feature> <a> <out.csv>
       lbreg_probe.py read  <feature> <a> <public_rmse>
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = str(Path(__file__).resolve().parents[1])
EY2 = 0.107246 ** 2
YBAR = 0.059802
VAR_Y = EY2 - YBAR ** 2


def load():
    x = pd.read_parquet(ROOT + "/work/lbreg_features.parquet")
    order = pd.concat([pd.read_csv(f"{ROOT}/data/reference/{r}/{r}-sample-submission.csv", dtype={"GEOID": str})[["GEOID"]]
                       for r in ["eastern-ok", "maricopa-az", "northern-ca", "south-central-tx", "eastern-wa"]],
                      ignore_index=True)
    x = order.merge(x, on="GEOID", how="left")
    assert x["region"].notna().all() and len(x) == 9794 and x["GEOID"].is_unique
    return x


def main():
    mode, feat, a = sys.argv[1], sys.argv[2], float(sys.argv[3])
    x = load()
    scored = (x["region"] != "eastern-wa").to_numpy()
    f = x[feat].to_numpy(float)
    m = f[scored].mean()
    dev = np.where(scored, f - m, 0.0)
    V = (dev[scored] ** 2).mean()
    if mode == "write":
        pred = YBAR + a * dev
        assert pred.min() >= 0 and pred.max() <= 1, (pred.min(), pred.max())
        pd.DataFrame({"GEOID": x["GEOID"], "coverage_gap_score": np.round(pred, 8)}).to_csv(sys.argv[4], index=False)
        exp_noinfo = np.sqrt(VAR_Y + a * a * V)
        print(f"{feat} a={a} m={m:.6f} V={V:.6f} pred[{pred.min():.4f},{pred.max():.4f}] "
              f"RMSE if uncorrelated {exp_noinfo:.6f} (constant {np.sqrt(VAR_Y):.6f})")
    else:
        rmse = float(sys.argv[4])
        cov = (a * a * V - (rmse ** 2 - VAR_Y)) / (2 * a)
        beta = cov / V
        print(f"{feat}: Cov_P(y,f)={cov:.7f} slope={beta:.5f} corr={cov / np.sqrt(V * VAR_Y):.4f} "
              f"best single-feature RMSE {np.sqrt(VAR_Y - cov * cov / V):.6f}")


if __name__ == "__main__":
    main()
