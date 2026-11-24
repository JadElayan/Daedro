"""Simulator trust check: does grasp success follow the Coulomb bound 2*mu*N >= m*g?

Runs a noise-free friction x mass grid for each finger-contact model and reports how
often the sim's carried/not-carried result agrees with the closed-form prediction.
N is the per-finger normal force measured on an easy grasp with the same gripper.
"""
import itertools, json, sys
import numpy as np
from daedro.episode import run_episode
from daedro.scene import SceneParams

G = 9.81
mus = np.geomspace(0.05, 1.2, 9)
masses = np.geomspace(0.05, 2.0, 9)
out = {}
for contact in ("as_shipped", "flat_pad"):
    N = run_episode(SceneParams(1.0, 0.1, 0.02, 0.0), 0, finger_contact=contact).finger_normal_n
    agree, rows = 0, []
    for mu, m in itertools.product(mus, masses):
        r = run_episode(SceneParams(float(mu), float(m), 0.02, 0.0), 0, finger_contact=contact)
        carried = r.outcome not in ("grasp_miss", "slip_on_lift", "drop_in_transit")
        predicted = 2 * mu * N >= m * G
        agree += carried == predicted
        rows.append(dict(mu=round(float(mu), 3), m=round(float(m), 3), outcome=r.outcome, predicted_carry=bool(predicted),
                         N_meas=round(r.finger_normal_n, 1)))
    out[contact] = dict(N_nominal=round(N, 1), agreement=agree / len(rows), rows=rows)
    print(f"{contact:11s} nominal per-finger N = {N:5.1f}   agreement with Coulomb = {agree}/{len(rows)}")
    # grid: rows = mu (low->high), cols = mass (low->high); S success, x carried-but-misplaced, . not carried; * = disagrees
    for i, mu in enumerate(mus):
        line = ""
        for j in range(len(masses)):
            rr = rows[i * len(masses) + j]
            c = {"success": "S", "misplaced": "x"}.get(rr["outcome"], ".")
            line += c + ("*" if (c != ".") != rr["predicted_carry"] else " ")
        print(f"   mu={mu:5.3f} | {line}")
    print("              mass " + " ".join(f"{m:.2f}"[:4] for m in masses))
if len(sys.argv) > 1:
    json.dump(out, open(sys.argv[1], "w"), indent=1)
