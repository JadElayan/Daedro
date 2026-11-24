"""Random vs. LHS on the MuJoCo loop.

1. Reference: one large LHS campaign (n=2000) as the best estimate of the true landscape.
2. Ten small campaigns (n=100) per method, different seeds. Compare how far each small
   campaign's success-rate estimate lands from the reference, and how well a logistic
   model fit on it ranks the reference episodes (AUC).
Writes every campaign to results/ as JSONL so any number here can be re-derived.
"""
import json, sys
from pathlib import Path
import numpy as np
from daedro.campaign import run_campaign

OUT = Path("results"); OUT.mkdir(exist_ok=True)

def save(res, name):
    with open(OUT / name, "w") as f:
        f.write(json.dumps({"metadata": res["metadata"]}) + "\n")
        for r in res["rows"]: f.write(json.dumps(r) + "\n")

def feats(rows):
    X = np.array([[np.log(r["friction"]), np.log(r["mass"]), r["half_size"], r["ik_noise"]] for r in rows])
    return X

def fit_auc(train, test):
    mu, sd = feats(train).mean(0), feats(train).std(0) + 1e-12
    z = lambda rows: np.column_stack([np.ones(len(rows)), (f := (feats(rows) - mu) / sd), f[:, 0] * f[:, 1]])
    X, y = z(train), np.array([r["success"] for r in train], float)
    w = np.zeros(X.shape[1])
    for _ in range(50):
        p = 1 / (1 + np.exp(-X @ w)); H = X.T @ (X * (p * (1 - p))[:, None]) + 1e-2 * np.eye(len(w))
        w -= np.linalg.solve(H, X.T @ (p - y) + 1e-2 * w)
    s, yt = z(test) @ w, np.array([r["success"] for r in test])
    rk = np.argsort(np.argsort(s)) + 1; n1 = yt.sum(); n0 = len(yt) - n1
    return (rk[yt == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)

ref = run_campaign("lhs", 2000, 1); save(ref, "reference_lhs_n2000_seed1.jsonl")
ref_sr = ref["metadata"]["success_rate"]
print("reference", json.dumps(ref["metadata"]), flush=True)
summary = {"reference_sr": ref_sr, "small": {}}
for method in ("random", "lhs"):
    srs, aucs = [], []
    for seed in range(100, 110):
        r = run_campaign(method, 100, seed); save(r, f"{method}_n100_seed{seed}.jsonl")
        srs.append(r["metadata"]["success_rate"]); aucs.append(fit_auc(r["rows"], ref["rows"]))
    srs, aucs = np.array(srs), np.array(aucs)
    summary["small"][method] = dict(sr=srs.tolist(), auc=aucs.tolist(),
                                    sr_rmse_vs_ref=float(np.sqrt(np.mean((srs - ref_sr) ** 2))),
                                    auc_mean=float(aucs.mean()), auc_std=float(aucs.std()))
    print(method, json.dumps(summary["small"][method]), flush=True)
json.dump(summary, open(OUT / "random_vs_lhs_summary.json", "w"), indent=1)
