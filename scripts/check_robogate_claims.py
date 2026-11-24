"""Re-derive RoboGate's published headline numbers from its public failure dictionary.

Usage: python -I check_robogate_claims.py <path-to-robogate-failure-dictionary>
Pure numpy; no sklearn. Logistic regression via IRLS, AUC via Mann-Whitney ranks.
"""
import json, sys, numpy as np
from pathlib import Path

root = Path(sys.argv[1])
load = lambda f: json.load(open(root / f))
S1, S2 = load("failure_dictionary_large.json"), load("franka_boundary_10k.json")
CONT = ["friction", "mass", "com_offset", "size", "ik_noise"]

def arr(ex, k): return np.array([e[k] for e in ex], float)

def auc(score, y):
    r = np.argsort(np.argsort(score)) + 1
    n1 = y.sum(); n0 = len(y) - n1
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)

def design(ex, interactions=True):
    cols = [np.log(arr(ex, "friction")), np.log(arr(ex, "mass"))] + [arr(ex, k) for k in CONT[2:]] + [arr(ex, "obstacles")]
    for cat in ["shape", "placement"]:
        vals = sorted({e[cat] for e in ex})[1:]
        cols += [np.array([e[cat] == v for e in ex], float) for v in vals]
    X = np.column_stack(cols)
    X = (X - X.mean(0)) / (X.std(0) + 1e-12)
    if interactions:
        X = np.column_stack([X, X[:, 0] * X[:, 1]])
    return np.column_stack([np.ones(len(X)), X])

def logreg(X, y, l2=1e-3, it=50):
    w = np.zeros(X.shape[1])
    for _ in range(it):
        p = 1 / (1 + np.exp(-X @ w))
        H = X.T @ (X * (p * (1 - p))[:, None]) + l2 * np.eye(len(w))
        w -= np.linalg.solve(H, X.T @ (p - y) + l2 * w)
    return w

def cv_auc(ex, folds=5, seed=0):
    X = design(ex); y = arr(ex, "success")
    idx = np.random.default_rng(seed).permutation(len(y)); out = np.zeros(len(y))
    for f in np.array_split(idx, folds):
        tr = np.setdiff1d(idx, f); w = logreg(X[tr], y[tr]); out[f] = X[f] @ w
    return auc(out, y), auc(X @ logreg(X, y), y)

def report(name, ex):
    y = arr(ex, "success")
    print(f"\n## {name}  n={len(ex)}  SR={y.mean():.4f}")
    for k in CONT:
        print(f"  corr(success,{k:10s}) = {np.corrcoef(arr(ex,k), y)[0,1]:+.3f}")
    m = arr(ex, "mass"); h = m > 0.93
    print(f"  SR | mass>0.93: {y[h].mean():.3f} (n={h.sum()})   SR | mass<=0.93: {y[~h].mean():.3f}")
    mu = arr(ex, "friction"); edges = np.quantile(mu, np.linspace(0, 1, 21))
    srs = [(lo, hi, y[(mu >= lo) & (mu < hi)].mean()) for lo, hi in zip(edges[:-1], edges[1:])]
    cross = next(((lo + hi) / 2 for lo, hi, s in srs if s >= 0.5), None)
    print(f"  friction where binned SR first reaches 50%: {cross}")
    cv, insample = cv_auc(ex)
    print(f"  logistic (+friction x mass) AUC: 5-fold CV={cv:.3f}  in-sample={insample:.3f}")
    print(f"  heuristic 1-fail_prob AUC (pre-computed field): {auc(-arr(ex,'fail_prob'), y):.3f}")
    print(f"  share with friction<0.3 & mass>=0.5: {((mu<0.3)&(m>=0.5)).mean():.3f}")
    print(f"  friction range [{mu.min():.3f},{mu.max():.3f}]  mass range [{m.min():.3f},{m.max():.3f}]")

e1, e2 = S1["experiments"], S2["experiments"]
report("Franka Stage 1 (uniform LHS)", e1)
report("Franka Stage 2 (boundary)", e2)
report("Franka combined", e1 + e2)
print("\nStage 2 sampling region (metadata):", json.dumps(S2["metadata"].get("boundary_ranges")))
print("Stage 2 other metadata keys:", [k for k in S2["metadata"] if k != "boundary_ranges"])
for f in ["ur5e_failure_dictionary.json", "ur3e_failure_dictionary.json", "ur10e_failure_dictionary.json"]:
    d = load(f); md = d["metadata"]
    print(f"\n{f}: metadata.robot={md.get('robot')!r} SR={d['summary']['success_rate']} failure_types={d['summary']['failure_types']}")
    print("   params:", sorted(k for k in d["experiments"][0] if k not in {"sample_idx","success","failure_type","cycle_time","dist_to_target"}))

# --- Fair test of "boundary sampling improves the risk model" -----------------
# Paper compares AUC on different datasets (uniform vs. uniform+boundary). A fair
# comparison holds the training budget fixed and scores both models on the SAME
# held-out uniform sample (the operating distribution the gate is meant to cover).
print("\nStage 2 emphasis metadata:", S2["metadata"].get("emphasis_region"), S2["metadata"].get("emphasis_fraction"))
rng = np.random.default_rng(7)
X1, y1 = design(e1), arr(e1, "success")
X2, y2 = design(e2), arr(e2, "success")
# design() standardizes per-dataset; rebuild jointly so features share a scale
Xall = design(e1 + e2); X1, X2 = Xall[:len(e1)], Xall[len(e1):]
res = []
for rep in range(20):
    p = rng.permutation(len(e1)); test, pool = p[:2000], p[2000:]
    n = 4000
    a = pool[:2 * n]                                   # 8k uniform
    b1 = pool[:n]; b2 = rng.permutation(len(e2))[:n]   # 4k uniform + 4k boundary
    wa = logreg(X1[a], y1[a])
    wb = logreg(np.vstack([X1[b1], X2[b2]]), np.concatenate([y1[b1], y2[b2]]))
    res.append((auc(X1[test] @ wa, y1[test]), auc(X1[test] @ wb, y1[test])))
res = np.array(res)
print(f"Equal budget (8k), test on held-out uniform 2k, 20 repeats:")
print(f"  uniform-only     AUC {res[:,0].mean():.3f} ± {res[:,0].std():.3f}")
print(f"  half + boundary  AUC {res[:,1].mean():.3f} ± {res[:,1].std():.3f}")
