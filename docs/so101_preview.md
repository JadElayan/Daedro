# SO-101 support: experimental

*2026-11-25. Simulation only. Use `robot = "so101"` under `[controller]`; see `examples/so101/`.*

The SO-101 is the low-cost arm used with Hugging Face LeRobot. Daedro loads MuJoCo Menagerie's `robotstudio_so101` model and runs the same scripted pick-and-place as the Franka, scaled down: 2 cm success radius, parts of 10–200 g and 1.8–2.6 cm, within ~20 cm of the base.

## What we fixed to get here
1. **Friction was being ignored.** Menagerie gives the gripper geoms contact *priority* with μ=1, which overrides the part's friction. The part now has higher priority, so its own friction governs the grasp.
2. **The fingertip frame sits on the fixed jaw.** Steering it onto the part's centre landed the fixed jaw on top of the part and pushed it aside. We add a grasp point between the jaws, measured from the model's jaw geometry.
3. **Wrong pointing axis.** Our grasp point uses the gripper body frame, where the fingers point along local −z; the first IK version aimed the wrong axis and never reached the table.
4. **Release flicked parts away.** The servo snapped the jaw fully open. Release now opens part-way on a ramp.

## Known limitations (why it's experimental)
- **Fragile grasp.** Small parts resting on the table reach only the fingertips, and Menagerie models the tips as a few 0.75 mm spheres. That point contact is unrealistically fragile: joint-target noise of 0.0003 rad (0.02°) drops success from 12/16 to 0/16. So the SO-101 envelope allows essentially no joint noise. Real SO-101 grasps are not this fragile.
- **Placement flakiness.** About a quarter of baseline runs end "misplaced": the part shifts as the jaw opens. Comparisons stay valid because both versions face identical, deterministic scenarios, but absolute success rates are not meaningful.
- **No physics cross-check yet.** The Franka was checked against the Coulomb friction bound (80/81 grid cells agree). The SO-101 isn't: its outcomes trend the right way with friction and grip, but the grasp contact above has to be fixed first.

## What would make it trustworthy
Model the jaw contact surfaces properly, then calibrate against a real SO-101: the same parts, grip settings and noise, comparing slip and drop rates. This is the point where owning a physical arm pays off.

## Demo
`examples/so101/`: tightening `jaw_close` from −0.17 to 0.10 rad (a gentler squeeze) regresses 45/100 scenarios, almost all `slip_on_lift`, p ≈ 1e-10.
