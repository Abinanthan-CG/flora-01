# PARTS.md — Solarpunk Botanical Quadruped (`flora_quad`)

Reference-first engineering breakdown written from measurements calibrated directly off the approved 6-view orthographic turnaround (`refs/turnaround.png`) and mechanism close-up plates (`refs/closeup_front_leg.png`, `refs/closeup_rear_leg.png`, `refs/closeup_canopy_planter.png`).

---

## 1. Coordinate System, Origin & Calibrated Dimensions

- **Axes**: `+X` forward (nose), `+Y` left (robot's left), `+Z` up.
- **Origin `(0, 0, 0)`**: on the level ground plane (`Z = 0.000 m`), directly beneath the dorsal planter / torso centre.
- **Calibration**: measured off `refs/turnaround.png` (`LEFT_SIDE` = 461 px nose-to-tail, 373 px ground-to-canopy; `FRONT` = 161 px shoulder width → **368.8 px/m** at target 1.250 m length).

| Envelope Metric | Target (m) | Span |
|---|---:|---|
| Overall length (nose bezel to rear battery pods) | **1.250** | `X ∈ [-0.625, +0.625]` |
| Overall width (outer front shoulder armor cowls) | **0.440** | `Y ∈ [-0.220, +0.220]` |
| Overall height (ground to front crown of arched canopy) | **1.010** | `Z ∈ [0.000, +1.010]` |
| Dorsal back deck height | **0.655** | `Z ≈ 0.655` |
| Dorsal planter collar top height | **0.725** | `Z ≈ 0.725` |
| Belly ground clearance (chest keel / mid-belly) | **0.415 / 0.455** | `Z ≥ 0.415` |
| Leg track centreline width | **0.350** | `Y = ±0.175` (outer paw edge `±0.204`) |
| Main torso carapace width | **0.310** | `Y ∈ [-0.155, +0.155]` |

### Joint Housing Diameters (Real Spot-Class Hardware)

| Mechanism | Diameter (m) | Notes |
|---|---:|---|
| Front shoulder & rear hip rotary drums | `0.104` | Machined 2-step silver aluminum bearing housing + 4-bolt dark hub cap |
| Front elbow & rear knee rotary drums | `0.080` | 4-bolt silver bearing drum + chunky lime-green front/upper wrap guard |
| Front wrist & rear hock/ankle drums | `0.056` | Forked clevis joint with countersunk axle pin |
| Front forearm hydraulic cylinder / chrome rod | `0.024 / 0.013` | Two-part aiming actuator; rod slides inside barrel across full stroke |
| Rear braided yellow conduit hoses | `0.011` | Twin flexible hydraulic/irrigation lines with silver crimp collars |
| Canopy pedestal pitch drum | `0.070` | Twin side drums with lime-green recessed caps |

---

## 2. Structural Load Path

How this Spot-class field robot carries its chassis, soil/water planter payload (~12 kg), batteries, and dynamic walking loads:

1. **Spine & Bulkhead Core**: A continuous dark-anodized aluminum box-section monocoque spine (`X ∈ [-0.46, +0.34]`) carries bending between the front shoulder bulkhead (`X = +0.205`) and rear hip bulkhead (`X = -0.360`). The white faceted carapace shells are bolt-on protective weather fairings around this structural spine.
2. **Dorsal Payload Transfer**: The octagonal planter tray sits recessed into a flanged saddle directly over the neutral mid-span of the monocoque spine (`X = -0.025`), transferring soil + canopy wind loads straight down into the twin side longitudinal rails. The curved Y-pedestal bolts into a rotary pitch axle seated in the central turret boss.
3. **Front Legs (Actuated Strut + External Hydraulic Assist)**:
   - Abduction servo (`front_hip_ab_L/R`) inside the front bulkhead supports the main shoulder pitch drum (`front_shoulder_L/R`, `X = +0.205, Z = 0.555`).
   - A heavy dark aluminum upper arm (`L = 0.250 m`) transfers load downward-aft to the rotary elbow drum (`front_elbow_L/R`, `X = +0.095, Z = 0.330`).
   - A tapered channel-section forearm (`L = 0.352 m`) angles forward-down to the wrist drum (`X = +0.340, Z = 0.078`), braced in tension/compression by the **external chrome hydraulic actuator** mounted between a rear crank lug on `front_shoulder` (just below/aft of the elbow pin) and a lower clevis lug on `front_elbow` (near the wrist). Because the cylinder barrel and sliding rod live on separate aiming bones (`front_hyd_cyl_L/R` and `front_hyd_rod_L/R`), every degree of elbow flexion produces real physical piston stroke.
   - A forked wrist clevis transfers ground reaction force into the transverse-ribbed rubber paw pad (`Z = 0.000`).
4. **Rear Legs (Digitigrade 3-Joint Canine Linkage)**:
   - Abduction servo (`rear_hip_ab_L/R`) carries the rear hip pitch drum (`rear_hip_L/R`, `X = -0.360, Z = 0.535`).
   - Tapered thigh (`L = 0.197 m`) transfers load slightly forward-down to the knee drum (`rear_knee_L/R`, `X = -0.330, Z = 0.340`).
   - Tapered shin (`L = 0.234 m`) sweeps aft-down to the hock drum (`rear_hock_L/R`, `X = -0.485, Z = 0.165`).
   - Lower metatarsal strut (`L = 0.136 m`) drops steeply down-forward to the ankle clevis (`X = -0.455, Z = 0.032`) and flat treaded rear paw pad (`Z = 0.000`).
   - Twin braided yellow hoses carry hydraulic/coolant pressure from under-pod rear manifolds into hip crimp fittings and down behind the knee into the shin block.

---

## 3. Tie-Break Decisions Where References Disagree

1. **Front paw rest angle**: In `refs/turnaround.png` side views the front paws tip slightly onto their front toe edge; in the 3D rest pose **all four paw soles sit 100% flat on `Z = 0.000 m`** (matching ground contact physics for clean walk/idle cycles and zero foot-clip).
2. **Rear dorsal deck**: Approved `refs/turnaround.png` wins — clean matte-white faceted rear deck behind the planter with twin angled rear antenna vanes and NO rear-butt solar panel. Solar arrays exist exclusively on (a) sloped front hood, (b) left/right mid-body flanks, and (c) elevated arched solar canopy.
3. **Rear battery pack**: Approved `refs/turnaround.png` and `refs/closeup_rear_leg.png` win — split symmetric left/right dark charcoal armored pods flanking the central spine, with vertical glowing lime-green spacer columns, outer vertical amber indicator slits, and rear glowing green X-vents.
4. **Canopy tilt**: Approved `refs/turnaround.png` and `refs/concept.png` agree — arched leaf-shaped photovoltaic canopy pitches **front-edge high (`Z = 1.008 m`) to rear-edge lower (`Z = 0.905 m`)** (~11° upward sweep toward the nose), with 6 recessed yellow-lime LED grow-light pads and 1 forward amber tip indicator on the underside.

---

## 4. Complete Armature & Part-to-Bone Table

Naming rule enforced by assertion: **zero mesh object may share a name with any bone**. All bones are prefixed `B_` (or clean skeleton names) and all mesh parts are prefixed `P_`.

| Bone Name | Parent | Pivot `(X, Y, Z)` m | Rotation DOF | Attached Rigid Mesh Parts (`P_*`) |
|---|---|---|---|---|
| `B_root` | — | `(0.000, 0.000, 0.000)` | Loc + Rot (world placement) | *(none — control root)* |
| `B_torso` | `B_root` | `(0.000, 0.000, 0.540)` | Loc + Rot (body bob, pitch, roll) | `P_chassis_spine`, `P_chest_grille`, `P_carapace_main`, `P_solar_hood`, `P_solar_flank_L/R`, `P_planter_collar`, `P_planter_soil`, `P_planter_moss`, `P_planter_plants`, `P_rear_pods`, `P_rear_pod_glows`, `P_belly_conduit_L/R` |
| `B_neck` | `B_torso` | `(+0.335, 0.000, 0.595)` | Pitch Y, Yaw Z | `P_neck_collar`, `P_neck_shell` |
| `B_head` | `B_neck` | `(+0.465, 0.000, 0.588)` | Pitch Y, Yaw Z, Roll X | `P_head_shell`, `P_head_bezel`, `P_head_optics`, `P_head_chin` |
| `B_canopy_yaw` | `B_torso` | `(-0.025, 0.000, 0.720)` | Yaw Z (sun tracking) | `P_pedestal_turret` |
| `B_canopy_pitch` | `B_canopy_yaw` | `(-0.025, 0.000, 0.775)` | Pitch Y (sun tilt) | `P_pedestal_drums`, `P_pedestal_yfork`, `P_canopy_shell`, `P_canopy_solar`, `P_canopy_leds` |
| `B_ant_L`, `B_ant_R` | `B_torso` | `(-0.375, ±0.068, 0.640)` | Pitch Y | `P_ant_vane_L/R`, `P_ant_tip_L/R` |
| `B_FL_ab`, `B_FR_ab` | `B_torso` | `(+0.205, ±0.132, 0.555)` | Roll X (abduction) | `P_FL/FR_shoulder_mount` |
| `B_FL_upper`, `B_FR_upper` | `B_FL/FR_ab` | `(+0.205, ±0.175, 0.555)` | Pitch Y | `P_FL/FR_shoulder_drum`, `P_FL/FR_shoulder_cowl`, `P_FL/FR_shoulder_vents`, `P_FL/FR_upper_arm`, `P_FL/FR_elbow_stator` |
| `B_FL_lower`, `B_FR_lower` | `B_FL/FR_upper` | `(+0.095, ±0.175, 0.330)` | Pitch Y | `P_FL/FR_elbow_drum`, `P_FL/FR_elbow_collar`, `P_FL/FR_forearm`, `P_FL/FR_wrist_clevis` |
| `B_FL_paw`, `B_FR_paw` | `B_FL/FR_lower` | `(+0.340, ±0.175, 0.078)` | Pitch Y (flat foot) | `P_FL/FR_wrist_drum`, `P_FL/FR_paw_ankle`, `P_FL/FR_paw_pad` |
| `B_FL_hyd_cyl`, `B_FR_hyd_cyl` | `B_FL/FR_upper` | solved anchor on upper arm | Track-to `rod_tip` | `P_FL/FR_hyd_barrel` |
| `B_FL_hyd_rod`, `B_FR_hyd_rod` | `B_FL/FR_lower` | solved anchor on forearm | Track-to `cyl_base` | `P_FL/FR_hyd_rod` |
| `B_RL_ab`, `B_RR_ab` | `B_torso` | `(-0.360, ±0.132, 0.535)` | Roll X (abduction) | `P_RL/RR_hip_mount` |
| `B_RL_thigh`, `B_RR_thigh` | `B_RL/RR_ab` | `(-0.360, ±0.175, 0.535)` | Pitch Y | `P_RL/RR_hip_drum`, `P_RL/RR_hip_cowl`, `P_RL/RR_thigh`, `P_RL/RR_hip_hose_upper` |
| `B_RL_shin`, `B_RR_shin` | `B_RL/RR_thigh` | `(-0.330, ±0.175, 0.340)` | Pitch Y | `P_RL/RR_knee_drum`, `P_RL/RR_knee_collar`, `P_RL/RR_shin` |
| `B_RL_hock`, `B_RR_hock` | `B_RL/RR_shin` | `(-0.485, ±0.175, 0.165)` | Pitch Y | `P_RL/RR_hock_drum`, `P_RL/RR_metatarsal` |
| `B_RL_paw`, `B_RR_paw` | `B_RL/RR_hock` | `(-0.455, ±0.175, 0.032)` | Pitch Y (flat foot) | `P_RL/RR_paw_ankle`, `P_RL/RR_paw_pad` |
| *(flexible skin)* | `B_RL/RR_thigh` + `B_RL/RR_shin` | smooth blended weights | Deforms with knee | `P_RL/RR_hose_flex` (braided yellow conduit flexing smoothly across knee) |

**Total bones**: 34 (1 root + 1 torso + 2 head/neck + 2 canopy + 2 antennae + 12 front legs incl. 4 aiming actuator bones + 14 rear legs? Let's count: 1 root + 1 torso + 2 neck/head + 2 canopy + 2 antennae + 2×6 front legs = 12 + 2×5 rear legs = 10 → **30 bones** cleanly!).

---

## 5. Planned Actions (Evaluated, Clamped & Clash-Checked)

All actions are generated analytically via our 2-link / 3-link analytical IK limb solver inside `build_quadruped.py`, guaranteeing zero foot slip during stance and flat paw contact (`Z = 0.000 m`):

1. **`Idle_Scan`** (120 frames @ 24 fps, 5.0 s looping): Subtle breathing torso rise/fall (±8 mm), curious head scan left/right/down, solar canopy slow sun-tracking yaw/pitch sway, gentle antenna twitch, all 4 feet locked solidly on ground.
2. **`Walk_Cycle`** (48 frames @ 24 fps, 2.0 s seamless lateral-sequence quadruped gait: `RL → FL → RR → FR`, 75% duty factor so at least 3 paws are always grounded — overlapping gait just like a real quadruped, stride 0.32 m, lift height 0.075 m, subtle torso pitch/roll/bob, head stabilization, antenna sway, active front hydraulic piston stroking!).
3. **`Trot_Cycle`** (28 frames @ 24 fps, ~1.17 s brisk diagonal quadruped trot: `(FL+RR)` alternating with `(FR+RL)`, stride 0.42 m, lift 0.095 m, energetic torso bounce, swept-back antennae, canopy counter-stabilizing pitch!).
4. **`Inspect_Plant`** (96 frames @ 24 fps, 4.0 s): Quadruped lowers into a graceful front-bow / crouch inspection pose (front chest lowers 12 cm, front elbows flex sharply driving full hydraulic stroke, head dips to scan the ground, canopy tilts forward to keep solar panels angled toward the sun, then rises smoothly back to neutral).
5. **`Sun_Bloom_Stretch`** (96 frames @ 24 fps, 4.0 s): Solarpunk sun-salutation hero pose — torso lifts slightly with a regal nose-up tilt, front-right paw performs a graceful forward step salute, antennae perk alertly, and the solar canopy smoothly swivels ±30° and tilts open toward the sun.

---

## 6. Verification Targets

- **Triangle budget**: ~28,000–55,000 triangles (hero articulated robotics asset with real chamfers, bolts, machined drums, botanical foliage, braided hoses), **0 n-gons**.
- **Bounding box accuracy**: `< 5 mm` against calibrated envelope (`1.250 × 0.440 × 1.010 m`).
- **Actuator safety assertion**: `build_quadruped.py` samples EVERY frame of ALL 4 actions and asserts `rod_inside_barrel_margin >= 0.015 m` and `rod_exposed_margin >= 0.015 m` (fails the build if a piston could ever detach or bottom out).
- **Inter-bone clash check**: BVH triangle-intersection check comparing every rigid part against non-adjacent bones across sampled action frames; reports any new clashes not in rest pose.
- **Export & re-import verification**: `flora_quad.glb` and `flora_quad.blend`, plus `flora_quad_info.json`, verified by `verify_glb.py` re-imported into a factory-empty Blender 5.2 scene.
