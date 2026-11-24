"""Example team-owned controller for Daedro: a waypoint pick-and-place written from scratch.

This is the shape a team's own code takes; Daedro only calls reset() and act().
"""
import numpy as np


def smooth(s):
    s = min(max(s, 0.0), 1.0)
    return 3 * s * s - 2 * s * s * s


class WaypointPick:
    def __init__(self, hover=0.15, carry=0.20, close_early_s=0.0):
        self.hover, self.carry = hover, carry
        self.close_early_s = close_early_s  # start closing the gripper this long before the descent ends

    def reset(self, obs):
        o, t = obs["object_pos"], obs["target_pos"]
        z = max(obs["object_half_size"], 0.0095)
        pick, place = np.array([o[0], o[1], z]), np.array([t[0], t[1], z + 0.005])
        up = np.array([0, 0, 1.0])
        # (duration s, start, end, gripper 1=open 0=closed)
        self.plan = [
            (1.5, obs["tcp"], pick + self.hover * up, 1.0),
            (1.0, pick + self.hover * up, pick, 1.0),
            (0.8, pick, pick, 0.0),
            (1.0, pick, pick + self.carry * up, 0.0),
            (1.5, pick + self.carry * up, place + self.carry * up, 0.0),
            (1.0, place + self.carry * up, place, 0.0),
            (0.5, place, place, 1.0),
            (0.5, place, place + self.hover * up, 1.0),
        ]
        self.descend_end = sum(p[0] for p in self.plan[:2])

    def act(self, obs):
        t, start = obs["t"], 0.0
        for dur, a, b, g in self.plan:
            if t < start + dur:
                s = smooth((t - start) / (0.8 * dur))
                if self.descend_end - self.close_early_s <= t < self.descend_end:
                    g = 0.0
                return {"tcp": a + s * (b - a), "gripper": g}
            start += dur
        return {"tcp": self.plan[-1][2], "gripper": 1.0}
