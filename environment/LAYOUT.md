# LAYOUT.md — AnyScene Solarpunk Rooftop Botanical Conservatory (`courtyard_env`)

Reference-first architectural environment layout derived from `refs/env-concept.jpg` and `refs/env-plan.jpg` (generated via `nano-banana-flow`).

---

## 1. Coordinate System & Walkable Scale

- **Axes (Blender)**: `+X` East (FLORA-01 initial forward), `+Y` North, `+Z` up; **origin `(0, 0, 0)`** on the flat walkable travertine plaza floor (`Z = 0.000 m`).
- **Overall Rooftop Terrace**: **`18.0 m × 18.0 m`** (`X ∈ [-9.0, +9.0]`, `Y ∈ [-9.0, +9.0]`).
- **Navigable Floor Guarantee**: Every walkable walkway and the central `7.0 m` diameter circular plaza sit strictly flat at `Z = 0.000 m` so `FLORA-01`'s analytical IK gaits maintain `0.00 mm` ground penetration and `0.00 mm` foot slip everywhere.
- **Clearance Guarantee**: Minimum walkway corridor width between any planter bench and perimeter/dock/pool is **`>= 2.6 m`** (over 5× `FLORA-01`'s 0.44 m track width).

---

## 2. Site Elements & Exact Coordinates (Metres)

| Zone / Prop | Center `(X, Y)` m | Dimensions (m) | Collider Type | Interactive Role |
|---|---|---|---|---|
| **Central Travertine Plaza** | `(0.0, 0.0)` | `Ø 7.2 m` concentric stone inlay | Walkable (`Z = 0.0`) | Robot spawn & wide turning arena |
| **4 Terraced Octagonal Planter Islands** (`NW, NE, SW, SE`) | `(±5.1, ±5.1)` | Outer concrete/cedar bench `Ø 4.3 m`, upper ceramic rim `Ø 2.7 m`, brass misting hoop `H = 2.65 m` | Circle `r = 2.25 m` each | 4 Botanical Care Stations (`[E]` Inspect & Mist → Bloom!) |
| **North Solar Charging & Hydration Dock** | `(0.0, +6.6)` | Base pad `2.8 × 2.2 m`, arched matte-white solar canopy bay `H = 1.95 m` | Rear pylon AABB (front pad walkable!) | Drive onto pad → Solar Sync status |
| **South Reflective Rainwater Basin** | `(0.0, -6.7)` | `3.2 m` wide × `3.4 m` deep, dark basalt coping `H = 0.16 m`, mirror water `Z = 0.06 m` | AABB `[-1.75..1.75, -8.5..-4.9]` | Reflective water landmark |
| **Overhead Steel & Cedar Conservatory Arches** | Spanning `Y = -8.6 → +8.6` | 7 sweeping parabolic dark-steel & warm-cedar arched ribs (`X = -7.2..+7.2`, crown `Z = 5.6 m`) + cedar purlins | Perimeter footings `r = 0.28 m` | Signature golden-hour dappled shadows |
| **8 Solar Pathway Bollards** | Circle `r = 3.9 m` & cardinal walkways | `Ø 0.12 m × H 0.62 m` dark anodized posts w/ glowing lime-warm rings | Circle `r = 0.18 m` | Wayfinding & night glow |
| **Perimeter Glass & Cedar Balustrade** | `X, Y = ±8.85 m` | `H = 1.05 m` tinted architectural glass panels, cedar handrail, dark steel posts | Walkable boundary clamp `±8.2 m` | Clean rooftop enclosure |
| **Distant Solarpunk Skyline Ring** | `r = 26..42 m` | Low-poly terraced green-rooftop architectural towers around horizon | Visual backdrop only | 360° depth & turning parallax |
