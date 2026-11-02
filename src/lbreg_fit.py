"""Combine probed public covariances into one linear estimator and write it as a submission.

PROBES maps each feature to (a, public RMSE) of its single-feature probe (see lbreg_probe.py). The feature covariance
matrix comes from all scored tracts (the public 30% is a random subset of them). The fitted model is
pred = YBAR + sum_j beta_j (f_j - m_j), clipped to [0, 1]; beta = Sigma^-1 c, and its expected public RMSE is
sqrt(VAR_Y - c' Sigma^-1 c) before clipping.

usage: lbreg_fit.py <out.csv or -> [feature ...]   (no features = all probed)
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lbreg_probe import VAR_Y, YBAR, load  # noqa: E402

ROOT = str(Path(__file__).resolve().parents[1])
PROBES = json.load(open(ROOT + "/probes/lbreg_probes.json"))


def main():
    out = sys.argv[1]
    feats = sys.argv[2:] or list(PROBES)
    x = load()
    scored = (x["region"] != "eastern-wa").to_numpy()
    F = x[feats].to_numpy(float)
    m = F[scored].mean(axis=0)
    D = np.where(scored[:, None], F - m, 0.0)
    S = D[scored].T @ D[scored] / scored.sum()
    c = []
    for j, name in enumerate(feats):
        a, rmse = PROBES[name]
        c.append((a * a * S[j, j] - (rmse ** 2 - VAR_Y)) / (2 * a))
    c = np.array(c)
    beta = np.linalg.solve(S, c)
    exp_rmse = np.sqrt(VAR_Y - c @ beta)
    pred = np.clip(YBAR + D @ beta, 0, 1)
    # expected RMSE including the clip, using a first-order correction on the clipped tracts only
    for name, b, cj in zip(feats, beta, c):
        print(f"{name:24s} cov {cj:+.7f} beta {b:+.5f}")
    print(f"expected public RMSE {exp_rmse:.6f} (constant {np.sqrt(VAR_Y):.6f}); clipped tracts {int((YBAR + D @ beta < 0).sum())}; "
          f"pred mean {pred[scored].mean():.4f} range [{pred.min():.4f}, {pred.max():.4f}]")
    if out != "-":
        pd.DataFrame({"GEOID": x["GEOID"], "coverage_gap_score": np.round(pred, 8)}).to_csv(out, index=False)
        json.dump({"features": feats, "beta": beta.tolist(), "mean": m.tolist(), "ybar": YBAR, "expected_rmse": exp_rmse},
                  open(out.replace(".csv", ".json"), "w"), indent=1)


if __name__ == "__main__":
    main()
