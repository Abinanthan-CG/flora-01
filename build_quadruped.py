# build_quadruped.py — Reference-first articulated Solarpunk Botanical Quadruped ("flora_quad")
# Track B (AnyMachine pipeline) — Pass 3 Hero Polish build script for Blender 5.2 headless.
#
# Usage:
#   blender -b --factory-startup -t 4 --python build_quadruped.py -- [--nobake] [--size 1024] [--spp 12]
#
# Conventions (see PARTS.md):
#   +X forward (nose), +Y left, +Z up, origin (0, 0, 0) on level ground beneath dorsal planter.
#   Real-world Spot-class dimensions: 1.250 m long x 0.440 m wide x 1.010 m tall (canopy crown).
#
# Pass 3 Hero Polish Upgrades:
#   - High-resolution aerospace curved leaf solar canopy (24x16) with 6 cobalt-navy PV sub-panels,
#     beveled LED diffuser bezels, 12 sculpted underside heat-sink louvers, and amber tip bar.
#   - Smooth 16-segment organic-sculpted Y-forked pedestal with glowing lime throat, rear vent
#     grille, 6-bolt mounting flange, and twin-leaf side sprout.
#   - Multi-layer botanical garden: drip-irrigation ring with brass misting nozzles, dual-tone
#     velvety moss cushions (deep forest + sunlit chartreuse tufts), UV-veined broad-leaf sprouts,
#     15-pinnae curved fern fronds, and 3-leaf clovers with dedicated leaf-venation PBR maps.
#   - Sculpted canine head & gently downward-sloped neck with machined aluminum lens barrels,
#     reflective dark inner camera glass, recessed cheek seams, and hex bolts.
#   - Dynamic forward-swept faceted carapace, 3D-crowned shoulder cowls with recessed dual-row
#     amber louver pockets & mounting bolts, CNC-milled leg side pockets, clamshell bolted lime
#     joint collars, two-step harmonic rotary drums, and banjo-fitted chrome hydraulic actuators.
#   - 5th hero action ("Sun_Bloom_Stretch") — sun-tracking canopy sweep & proud stretch pose.
#   - Expanded Cycles contact AO bake across all 23 hero shell, leg, drum & canopy parts.

import bpy
import bmesh
import math
import os
import sys
import json
import random
import numpy as np
from mathutils import Vector, Matrix, Euler

V = Vector
HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "out")
TEX_DIR = os.path.join(OUT_DIR, "textures")

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
NOBAKE = "--nobake" in argv
BAKE_SIZE = int(argv[argv.index("--size") + 1]) if "--size" in argv else 1024
BAKE_SPP = int(argv[argv.index("--spp") + 1]) if "--spp" in argv else 12

# ==============================================================================
# 1. CALIBRATED DIMENSIONS & JOINT COORDINATES (target: 1.250 x 0.440 x 1.010 m)
# ==============================================================================
Y_LEG = 0.172
Y_AB = 0.130

FL_AB  = V((0.205, Y_AB,  0.548))
FL_SH  = V((0.205, Y_LEG, 0.548))
FL_EL  = V((0.098, Y_LEG, 0.320))
FL_WR  = V((0.356, Y_LEG, 0.076))
FL_PAW = V((0.376, Y_LEG, 0.000))

RL_AB   = V((-0.360, Y_AB,  0.538))
RL_HIP  = V((-0.360, Y_LEG, 0.538))
RL_KNEE = V((-0.328, Y_LEG, 0.335))
RL_HOCK = V((-0.488, Y_LEG, 0.162))
RL_ANK  = V((-0.456, Y_LEG, 0.032))
RL_PAW  = V((-0.448, Y_LEG, 0.000))

P_TORSO        = V(( 0.000, 0.000, 0.540))
P_NECK         = V(( 0.340, 0.000, 0.592))
P_HEAD         = V(( 0.468, 0.000, 0.580))
P_CANOPY_YAW   = V((-0.025, 0.000, 0.715))
P_CANOPY_PITCH = V((-0.025, 0.000, 0.768))
P_ANT_L        = V((-0.380, 0.068, 0.638))

L_F1 = (FL_EL - FL_SH).length
L_F2 = (FL_WR - FL_EL).length
L_R1 = (RL_KNEE - RL_HIP).length
L_R2 = (RL_HOCK - RL_KNEE).length
L_R3 = (RL_ANK - RL_HOCK).length

# ==============================================================================
# 2. ANALYTICAL 3D KINEMATICS & 5-ACTION SOLVER
# ==============================================================================
def sag_angle(v):
    return math.atan2(-v.x, -v.z)


def solve_2link_xz(p0, p2, L1, L2, bend_sign):
    dx = p2.x - p0.x
    dz = p2.z - p0.z
    d = math.hypot(dx, dz)
    d = max(abs(L1 - L2) + 0.012, min(L1 + L2 - 0.008, d))
    a = (L1 * L1 - L2 * L2 + d * d) / (2.0 * d)
    h = math.sqrt(max(0.0, L1 * L1 - a * a))
    ux, uz = dx / d, dz / d
    px, pz = -uz, ux
    return V((p0.x + a * ux + bend_sign * h * px, p0.y, p0.z + a * uz + bend_sign * h * pz))


F_TH1_REST = sag_angle(FL_EL - FL_SH)
F_TH2_REST = sag_angle(FL_WR - FL_EL)
R_TH1_REST = sag_angle(RL_KNEE - RL_HIP)
R_TH2_REST = sag_angle(RL_HOCK - RL_KNEE)
R_TH3_REST = sag_angle(RL_ANK - RL_HOCK)


def solve_front_leg_3d(torso_loc, torso_rot, side_sign, paw_world, paw_pitch=0.0):
    """Exact 3D abduction + 2-link sagittal IK (places paw at exact (x, y, z) on ground during lateral yaw turns!)."""
    tr, tp, ty = torso_rot
    R_t = Euler((tr, tp, ty), "XYZ").to_matrix()
    ab_rest = V((FL_AB.x, side_sign * Y_AB, FL_AB.z))
    ab_w = P_TORSO + torso_loc + R_t @ (ab_rest - P_TORSO)
    # Solve exact roll angle phi_ab around world X so the leg plane passes through paw_world.y at paw_world.z!
    L_off = side_sign * (Y_LEG - Y_AB)
    dy = paw_world.y - ab_w.y
    dz = max(0.08, ab_w.z - paw_world.z)
    R_yz = math.hypot(dy, dz)
    sin_arg = max(-0.92, min(0.92, L_off / R_yz))
    # Right-hand roll around +X: (0, L_off, -H) -> (0, L_off cos(phi) + H sin(phi), L_off sin(phi) - H cos(phi))
    # Therefore dy = L_off cos(phi) + H sin(phi) => phi = atan2(dy, dz) - asin(L_off / R_yz)
    phi_world = math.atan2(dy, dz) - math.asin(sin_arg)
    d_ab = phi_world - tr
    # Compensate tiny 2.6mm paw-edge dip during lateral hip roll so sole never penetrates Z=0
    dz_comp = max(0.08, dz - 0.029 * abs(math.sin(phi_world)))
    H_plane = math.sqrt(max(0.04, (dy * dy + dz_comp * dz_comp) - L_off * L_off))

    # Project into rotated leg plane: shoulder pivot sits at (ab_w.x, 0, ab_w.z), paw at (paw_world.x, 0, ab_w.z - H_plane)
    sh_2d = V((ab_w.x, side_sign * Y_LEG, ab_w.z))
    paw_2d = V((paw_world.x, side_sign * Y_LEG, ab_w.z - H_plane))
    R_p = Matrix.Rotation(paw_pitch, 3, 'Y')
    wr_2d = paw_2d + R_p @ (FL_WR - FL_PAW)
    wr_2d.y = sh_2d.y
    el_2d = solve_2link_xz(sh_2d, wr_2d, L_F1, L_F2, bend_sign=-1.0)
    th1 = sag_angle(el_2d - sh_2d)
    th2 = sag_angle(wr_2d - el_2d)
    d_sh = th1 - (tp + F_TH1_REST)
    d_el = (th2 - th1) - (F_TH2_REST - F_TH1_REST)
    d_wr = paw_pitch - (tp + d_sh + d_el)
    return (d_sh, d_el, d_wr), d_ab


def solve_rear_leg_3d(torso_loc, torso_rot, side_sign, paw_world, paw_pitch=0.0, meta_tilt_extra=0.0):
    """Exact 3D abduction + 3-link digitigrade IK for zero-slip lateral yaw turns."""
    tr, tp, ty = torso_rot
    R_t = Euler((tr, tp, ty), "XYZ").to_matrix()
    ab_rest = V((RL_AB.x, side_sign * Y_AB, RL_AB.z))
    ab_w = P_TORSO + torso_loc + R_t @ (ab_rest - P_TORSO)
    L_off = side_sign * (Y_LEG - Y_AB)
    dy = paw_world.y - ab_w.y
    dz = max(0.08, ab_w.z - paw_world.z)
    R_yz = math.hypot(dy, dz)
    phi_world = math.atan2(dy, dz) - math.asin(max(-0.92, min(0.92, L_off / R_yz)))
    d_ab = phi_world - tr
    dz_comp = max(0.08, dz - 0.029 * abs(math.sin(phi_world)))
    H_plane = math.sqrt(max(0.04, (dy * dy + dz_comp * dz_comp) - L_off * L_off))

    hip_2d = V((ab_w.x, side_sign * Y_LEG, ab_w.z))
    paw_2d = V((paw_world.x, side_sign * Y_LEG, ab_w.z - H_plane))
    R_p = Matrix.Rotation(paw_pitch, 3, 'Y')
    ank_2d = paw_2d + R_p @ (RL_ANK - RL_PAW)
    ank_2d.y = hip_2d.y
    th3 = R_TH3_REST + paw_pitch * 0.5 + meta_tilt_extra
    hock_2d = ank_2d - V((-math.sin(th3) * L_R3, 0.0, -math.cos(th3) * L_R3))
    v_ha = hock_2d - hip_2d
    max_r = L_R1 + L_R2 - 0.015
    if v_ha.length > max_r:
        hock_2d = hip_2d + v_ha.normalized() * max_r
        th3 = sag_angle(ank_2d - hock_2d)
    knee_2d = solve_2link_xz(hip_2d, hock_2d, L_R1, L_R2, bend_sign=+1.0)
    th1 = sag_angle(knee_2d - hip_2d)
    th2 = sag_angle(hock_2d - knee_2d)
    d_hip = th1 - (tp + R_TH1_REST)
    d_knee = (th2 - th1) - (R_TH2_REST - R_TH1_REST)
    d_hock = (th3 - th2) - (R_TH3_REST - R_TH2_REST)
    d_paw = paw_pitch - (tp + d_hip + d_knee + d_hock)
    return (d_hip, d_knee, d_hock, d_paw), d_ab


def solve_front_leg_pose(torso_loc, torso_rot, side_sign, paw_world, paw_pitch=0.0):
    tr, tp, ty = torso_rot
    R_t = Euler((tr, tp, ty), "XYZ").to_matrix()
    ab_rest = V((FL_AB.x, side_sign * Y_AB, FL_AB.z))
    sh_from_ab = V((0.0, side_sign * (Y_LEG - Y_AB), 0.0))
    ab_w = P_TORSO + torso_loc + R_t @ (ab_rest - P_TORSO)
    sh_w = ab_w + Matrix.Rotation(tp, 3, 'Y') @ sh_from_ab

    R_p = Matrix.Rotation(paw_pitch, 3, 'Y')
    wr_w = V((paw_world.x, sh_w.y, paw_world.z)) + R_p @ (FL_WR - FL_PAW)
    el_w = solve_2link_xz(sh_w, wr_w, L_F1, L_F2, bend_sign=-1.0)
    th1 = sag_angle(el_w - sh_w)
    th2 = sag_angle(wr_w - el_w)
    return th1 - (tp + F_TH1_REST), (th2 - th1) - (F_TH2_REST - F_TH1_REST), paw_pitch - (tp + (th1 - (tp + F_TH1_REST)) + ((th2 - th1) - (F_TH2_REST - F_TH1_REST)))


def solve_rear_leg_pose(torso_loc, torso_rot, side_sign, paw_world, paw_pitch=0.0, meta_tilt_extra=0.0):
    tr, tp, ty = torso_rot
    R_t = Euler((tr, tp, ty), "XYZ").to_matrix()
    ab_rest = V((RL_AB.x, side_sign * Y_AB, RL_AB.z))
    hip_from_ab = V((0.0, side_sign * (Y_LEG - Y_AB), 0.0))
    ab_w = P_TORSO + torso_loc + R_t @ (ab_rest - P_TORSO)
    hip_w = ab_w + Matrix.Rotation(tp, 3, 'Y') @ hip_from_ab

    R_p = Matrix.Rotation(paw_pitch, 3, 'Y')
    ank_w = V((paw_world.x, hip_w.y, paw_world.z)) + R_p @ (RL_ANK - RL_PAW)
    th3 = R_TH3_REST + paw_pitch * 0.5 + meta_tilt_extra
    hock_w = ank_w - V((-math.sin(th3) * L_R3, 0.0, -math.cos(th3) * L_R3))
    v_ha = hock_w - hip_w
    max_r = L_R1 + L_R2 - 0.015
    if v_ha.length > max_r:
        hock_w = hip_w + v_ha.normalized() * max_r
        th3 = sag_angle(ank_w - hock_w)
    knee_w = solve_2link_xz(hip_w, hock_w, L_R1, L_R2, bend_sign=+1.0)
    th1 = sag_angle(knee_w - hip_w)
    th2 = sag_angle(hock_w - knee_w)
    d_hip = th1 - (tp + R_TH1_REST)
    d_knee = (th2 - th1) - (R_TH2_REST - R_TH1_REST)
    d_hock = (th3 - th2) - (R_TH3_REST - R_TH2_REST)
    return d_hip, d_knee, d_hock, paw_pitch - (tp + d_hip + d_knee + d_hock)


def foot_traj(phase, stride, lift, duty=0.75):
    p = phase % 1.0
    if p < duty:
        u = p / duty
        return stride * (0.5 - u), 0.0, 0.0
    else:
        u = (p - duty) / (1.0 - duty)
        s = u * u * u * (10.0 + u * (-15.0 + 6.0 * u))
        return stride * (-0.5 + s), lift * (math.sin(math.pi * u) ** 1.4), 0.22 * math.sin(2.0 * math.pi * u)


def sample_action_poses(name):
    frames = []
    if name == "Idle_Scan":
        n_fr = 120
        for f in range(n_fr):
            t = f / n_fr; a = 2.0 * math.pi * t
            tz = 0.008 * math.sin(2.0 * a); tp = 0.014 * math.sin(a); tr = 0.010 * math.sin(a + 0.6)
            tloc = V((0.004 * math.sin(a), 0.0, tz)); trot = (tr, tp, 0.0)
            frames.append(dict(
                frame=f + 1, torso_loc=tloc, torso_rot=trot,
                neck=(0.0, 0.07 * math.sin(a), 0.22 * math.sin(a)),
                head=(0.05 * math.sin(2 * a), 0.13 * math.sin(a + 0.4), 0.28 * math.sin(a)),
                canopy_yaw=0.36 * math.sin(a), canopy_pitch=0.10 * math.sin(2 * a + 0.5),
                ant_L=0.08 * math.sin(3 * a), ant_R=0.08 * math.sin(3 * a + 0.7),
                FL=solve_front_leg_pose(tloc, trot, +1, FL_PAW),
                FR=solve_front_leg_pose(tloc, trot, -1, V((FL_PAW.x, -Y_LEG, 0.0))),
                RL=solve_rear_leg_pose(tloc, trot, +1, RL_PAW),
                RR=solve_rear_leg_pose(tloc, trot, -1, V((RL_PAW.x, -Y_LEG, 0.0))),
                ab=(-tr, -tr, -tr, -tr),
            ))
    elif name == "Walk_Cycle":
        n_fr, stride, lift = 48, 0.26, 0.068
        for f in range(n_fr):
            t = f / n_fr; a = 2.0 * math.pi * t
            tz = 0.012 * math.sin(2.0 * a) - 0.010
            tp = 0.024 * math.sin(2.0 * a + 0.4)
            tr = 0.020 * math.sin(a)
            tloc = V((0.008 * math.sin(2.0 * a), 0.012 * math.sin(a), tz)); trot = (tr, tp, 0.0)
            fl_dx, fl_dz, fl_p = foot_traj(t - 0.25, stride, lift, 0.75)
            fr_dx, fr_dz, fr_p = foot_traj(t - 0.75, stride, lift, 0.75)
            rl_dx, rl_dz, rl_p = foot_traj(t - 0.00, stride, lift, 0.75)
            rr_dx, rr_dz, rr_p = foot_traj(t - 0.50, stride, lift, 0.75)
            frames.append(dict(
                frame=f + 1, torso_loc=tloc, torso_rot=trot,
                neck=(0.0, -tp * 0.6 + 0.03 * math.sin(2 * a), -0.06 * math.sin(a)),
                head=(-tr * 0.5, -tp * 0.4, 0.05 * math.sin(a)),
                canopy_yaw=0.05 * math.sin(a), canopy_pitch=-tp * 0.7,
                ant_L=0.10 + 0.06 * math.sin(2 * a), ant_R=0.10 + 0.06 * math.sin(2 * a + 0.4),
                FL=solve_front_leg_pose(tloc, trot, +1, FL_PAW + V((fl_dx, 0.0, fl_dz)), fl_p),
                FR=solve_front_leg_pose(tloc, trot, -1, V((FL_PAW.x + fr_dx, -Y_LEG, fr_dz)), fr_p),
                RL=solve_rear_leg_pose(tloc, trot, +1, RL_PAW + V((rl_dx, 0.0, rl_dz)), rl_p, meta_tilt_extra=-0.35 * rl_dx),
                RR=solve_rear_leg_pose(tloc, trot, -1, V((RL_PAW.x + rr_dx, -Y_LEG, rr_dz)), rr_p, meta_tilt_extra=-0.35 * rr_dx),
                ab=(-tr, -tr, -tr, -tr),
            ))
    elif name == "Trot_Cycle":
        n_fr, stride, lift = 28, 0.34, 0.088
        for f in range(n_fr):
            t = f / n_fr; a = 2.0 * math.pi * t
            tz = 0.020 * math.sin(2.0 * a) - 0.022
            tp = 0.036 * math.sin(2.0 * a + 0.3) + 0.02
            tr = 0.016 * math.sin(a)
            tloc = V((0.012 * math.sin(2.0 * a), 0.0, tz)); trot = (tr, tp, 0.0)
            fl_dx, fl_dz, fl_p = foot_traj(t, stride, lift, 0.56)
            rr_dx, rr_dz, rr_p = foot_traj(t, stride, lift, 0.56)
            fr_dx, fr_dz, fr_p = foot_traj(t - 0.5, stride, lift, 0.56)
            rl_dx, rl_dz, rl_p = foot_traj(t - 0.5, stride, lift, 0.56)
            frames.append(dict(
                frame=f + 1, torso_loc=tloc, torso_rot=trot,
                neck=(0.0, -tp * 0.7 - 0.04, 0.0), head=(-tr * 0.6, -tp * 0.3 + 0.04, 0.0),
                canopy_yaw=0.0, canopy_pitch=-tp * 0.85,
                ant_L=0.22 + 0.08 * math.sin(2 * a), ant_R=0.22 + 0.08 * math.sin(2 * a),
                FL=solve_front_leg_pose(tloc, trot, +1, FL_PAW + V((fl_dx, 0.0, fl_dz)), fl_p),
                FR=solve_front_leg_pose(tloc, trot, -1, V((FL_PAW.x + fr_dx, -Y_LEG, fr_dz)), fr_p),
                RL=solve_rear_leg_pose(tloc, trot, +1, RL_PAW + V((rl_dx, 0.0, rl_dz)), rl_p, meta_tilt_extra=-0.32 * rl_dx),
                RR=solve_rear_leg_pose(tloc, trot, -1, V((RL_PAW.x + rr_dx, -Y_LEG, rr_dz)), rr_p, meta_tilt_extra=-0.32 * rr_dx),
                ab=(-tr, -tr, -tr, -tr),
            ))
    elif name == "Inspect_Plant":
        n_fr = 96
        for f in range(n_fr):
            t = f / n_fr
            u = 0.5 * (1.0 - math.cos(2.0 * math.pi * t))
            crouch = u * u * (3.0 - 2.0 * u)
            scan = math.sin(4.0 * math.pi * t) * crouch
            tloc = V((-0.024 * crouch, 0.0, -0.088 * crouch)); trot = (0.0, 0.165 * crouch, 0.0)
            frames.append(dict(
                frame=f + 1, torso_loc=tloc, torso_rot=trot,
                neck=(0.0, 0.16 * crouch, 0.20 * scan),
                head=(0.08 * scan, 0.18 * crouch, 0.25 * scan),
                canopy_yaw=0.25 * scan, canopy_pitch=-0.20 * crouch,
                ant_L=-0.15 * crouch + 0.06 * scan, ant_R=-0.15 * crouch - 0.06 * scan,
                FL=solve_front_leg_pose(tloc, trot, +1, FL_PAW),
                FR=solve_front_leg_pose(tloc, trot, -1, V((FL_PAW.x, -Y_LEG, 0.0))),
                RL=solve_rear_leg_pose(tloc, trot, +1, RL_PAW),
                RR=solve_rear_leg_pose(tloc, trot, -1, V((RL_PAW.x, -Y_LEG, 0.0))),
                ab=(0.0, 0.0, 0.0, 0.0),
            ))
    elif name == "Sun_Bloom_Stretch":
        # 5th signature action: proud solarpunk sun-salutation stretch + canopy sun-tracking sweep!
        n_fr = 96
        for f in range(n_fr):
            t = f / n_fr
            u = 0.5 * (1.0 - math.cos(2.0 * math.pi * t))
            lift_u = u * u * (3.0 - 2.0 * u)
            sweep = math.sin(2.0 * math.pi * t)
            # Subtle regal upward lift & slight nose-up tilt as canopy tracks the sun
            tloc = V((0.022 * lift_u, 0.0, 0.020 * lift_u - 0.022 * (1.0 - lift_u) * math.sin(math.pi * t)))
            trot = (0.0, -0.075 * lift_u, 0.0)
            # Front-right paw performs a crisp graceful salute step forward while resting at frame 1 & 96
            fr_u = max(0.0, math.sin(math.pi * max(0.0, min(1.0, (t - 0.18) / 0.64))))
            fr_dz = 0.072 * (fr_u ** 1.4)
            fr_dx = 0.085 * fr_u
            fr_p  = 0.26 * fr_u
            frames.append(dict(
                frame=f + 1, torso_loc=tloc, torso_rot=trot,
                neck=(0.0, -0.14 * lift_u, 0.14 * sweep),
                head=(0.05 * sweep, -0.10 * lift_u, 0.18 * sweep),
                canopy_yaw=0.52 * sweep,
                canopy_pitch=0.18 * lift_u,
                ant_L=-0.18 * lift_u + 0.05 * sweep,
                ant_R=-0.18 * lift_u - 0.05 * sweep,
                FL=solve_front_leg_pose(tloc, trot, +1, FL_PAW),
                FR=solve_front_leg_pose(tloc, trot, -1, V((FL_PAW.x + fr_dx, -Y_LEG, fr_dz)), fr_p),
                RL=solve_rear_leg_pose(tloc, trot, +1, RL_PAW),
                RR=solve_rear_leg_pose(tloc, trot, -1, V((RL_PAW.x, -Y_LEG, 0.0))),
                ab=(0.0, 0.0, 0.0, 0.0),
            ))
    elif name == "Walk_Back":
        # Cautious reverse lateral-sequence quadruped gait (0.00 mm slip at v = 0.1333 m/s, stride = 0.20 m)
        n_fr, stride, lift = 48, 0.20, 0.058
        for f in range(n_fr):
            t = f / n_fr; a = 2.0 * math.pi * t
            tz = 0.010 * math.sin(2.0 * a) - 0.010
            tp = -0.022 * math.sin(2.0 * a + 0.4) + 0.018  # slight careful forward weight shift
            tr = 0.016 * math.sin(a)
            tloc = V((-0.006 * math.sin(2.0 * a), -0.010 * math.sin(a), tz)); trot = (tr, tp, 0.0)
            # Reversed trajectory: stance moves paw FORWARD (+X) relative to body -> body moves BACKWARD (-X)!
            def back_traj(ph):
                dx, dz, p = foot_traj(ph, stride, lift, 0.75)
                return -dx, dz, -p * 0.7
            fl_dx, fl_dz, fl_p = back_traj(t - 0.00)
            rr_dx, rr_dz, rr_p = back_traj(t - 0.25)
            fr_dx, fr_dz, fr_p = back_traj(t - 0.50)
            rl_dx, rl_dz, rl_p = back_traj(t - 0.75)
            frames.append(dict(
                frame=f + 1, torso_loc=tloc, torso_rot=trot,
                neck=(0.0, 0.04, 0.14 * math.sin(a)),
                head=(0.0, 0.05, 0.18 * math.sin(a)),
                canopy_yaw=-0.06 * math.sin(a), canopy_pitch=-tp * 0.65,
                ant_L=-0.10 + 0.05 * math.sin(2 * a), ant_R=-0.10 + 0.05 * math.sin(2 * a + 0.5),
                FL=solve_front_leg_pose(tloc, trot, +1, FL_PAW + V((fl_dx, 0.0, fl_dz)), fl_p),
                FR=solve_front_leg_pose(tloc, trot, -1, V((FL_PAW.x + fr_dx, -Y_LEG, fr_dz)), fr_p),
                RL=solve_rear_leg_pose(tloc, trot, +1, RL_PAW + V((rl_dx, 0.0, rl_dz)), rl_p, meta_tilt_extra=-0.30 * rl_dx),
                RR=solve_rear_leg_pose(tloc, trot, -1, V((RL_PAW.x + rr_dx, -Y_LEG, rr_dz)), rr_p, meta_tilt_extra=-0.30 * rr_dx),
                ab=(-tr, -tr, -tr, -tr),
            ))
    elif name in ("Turn_Left", "Turn_Right"):
        # EXACT 3D ZERO-SLIP SPOT IN-PLACE YAW TURN (continuous circular arc stance + lateral swing!):
        # dir_s = +1 for Turn_Left (+yaw CCW around +Z), -1 for Turn_Right (-yaw CW)
        # During stance (duty=0.56 over T=1.00s, 24 frames), every grounded paw rotates by -dir_s*d_psi around Z
        # => exact zero-slip angular speed omega = 0.24 / (0.56 * 1.0) = 0.42857 rad/s (24.6 deg/s)!
        dir_s = +1.0 if name == "Turn_Left" else -1.0
        n_fr = 24
        d_psi = 0.24  # 13.75 deg lateral arc per step (~9.5cm front / ~10.8cm rear crisp visible sidestep!)
        lift = 0.068
        duty = 0.56

        def yaw_paw_target(base_p, phase):
            p = phase % 1.0
            if p < duty:
                u = p / duty
                psi = dir_s * d_psi * (0.5 - u)  # sweeps opposite body rotation -> 0.00mm floor slip!
                dz = 0.0
            else:
                u = (p - duty) / (1.0 - duty)
                s = u * u * u * (10.0 + u * (-15.0 + 6.0 * u))
                psi = dir_s * d_psi * (-0.5 + s)  # swings ahead into the turn!
                dz = lift * (math.sin(math.pi * u) ** 1.4)
            c, sn = math.cos(psi), math.sin(psi)
            return V((base_p.x * c - base_p.y * sn, base_p.x * sn + base_p.y * c, dz))

        for f in range(n_fr):
            t = f / n_fr; a = 2.0 * math.pi * t
            tz = 0.014 * math.sin(2.0 * a) - 0.016
            tp = 0.010 * math.sin(2.0 * a)
            tr = 0.016 * math.sin(a) * dir_s
            tloc = V((0.0, 0.0, tz)); trot = (tr, tp, 0.0)

            p_fl = yaw_paw_target(FL_PAW, t)
            p_rr = yaw_paw_target(V((RL_PAW.x, -Y_LEG, 0.0)), t)
            p_fr = yaw_paw_target(V((FL_PAW.x, -Y_LEG, 0.0)), t - 0.5)
            p_rl = yaw_paw_target(RL_PAW, t - 0.5)

            fl_j, ab_fl = solve_front_leg_3d(tloc, trot, +1, p_fl)
            fr_j, ab_fr = solve_front_leg_3d(tloc, trot, -1, p_fr)
            rl_j, ab_rl = solve_rear_leg_3d(tloc, trot, +1, p_rl)
            rr_j, ab_rr = solve_rear_leg_3d(tloc, trot, -1, p_rr)

            frames.append(dict(
                frame=f + 1, torso_loc=tloc, torso_rot=trot,
                neck=(0.0, 0.03, 0.18 * dir_s),
                head=(0.04 * dir_s, 0.03, 0.24 * dir_s),
                canopy_yaw=-0.10 * dir_s, canopy_pitch=-tp * 0.6,
                ant_L=0.06 + 0.05 * math.sin(2 * a), ant_R=0.06 - 0.05 * math.sin(2 * a),
                FL=fl_j, FR=fr_j, RL=rl_j, RR=rr_j,
                ab=(ab_fl, ab_fr, ab_rl, ab_rr),
            ))
    return frames


ACTION_NAMES = [
    "Idle_Scan", "Walk_Cycle", "Walk_Back", "Trot_Cycle",
    "Turn_Left", "Turn_Right", "Inspect_Plant", "Sun_Bloom_Stretch"
]
ALL_ACTIONS = {nm: sample_action_poses(nm) for nm in ACTION_NAMES}


def solve_front_hydraulic_anchors():
    elbow_angles = [0.0]
    for frames in ALL_ACTIONS.values():
        for fr in frames:
            elbow_angles.append(fr["FL"][1])
            elbow_angles.append(fr["FR"][1])
    el_min, el_max = min(elbow_angles), max(elbow_angles)
    u_fa = (FL_WR - FL_EL).normalized()
    n_fa = V((-u_fa.z, 0.0, u_fa.x))

    best = None
    for along_u in np.linspace(-0.048, -0.022, 7):
        for drop_n in np.linspace(-0.046, -0.028, 7):
            a_rel = u_fa * along_u + n_fa * drop_n
            if a_rel.length < 0.042 or a_rel.length > 0.062:
                continue
            for s_b in np.linspace(0.68, 0.80, 5):
                for b_drop in np.linspace(-0.028, -0.021, 3):
                    b_rel0 = u_fa * (L_F2 * s_b) + n_fa * b_drop
                    dists, levers = [], []
                    for d_el in elbow_angles:
                        b_rot = Matrix.Rotation(d_el, 3, 'Y') @ b_rel0
                        vec = b_rot - a_rel
                        d = vec.length
                        dists.append(d)
                        levers.append(abs(a_rel.x * vec.z - a_rel.z * vec.x) / d)
                    d_min, d_max = min(dists), max(dists)
                    d_rest = (b_rel0 - a_rel).length
                    L_rod = d_min - 0.032
                    L_cyl = 0.55 * d_rest
                    eng_min = L_cyl + L_rod - d_max
                    exp_min = d_min - L_cyl
                    min_lever = min(levers)
                    if eng_min < 0.035 or exp_min < 0.045 or min_lever < 0.026:
                        continue
                    score = min_lever * 10.0 + (b_rel0 - a_rel).normalized().dot(u_fa) * 2.0 + min(eng_min, exp_min) * 3.0
                    if best is None or score > best["score"]:
                        best = dict(
                            score=score, a_world_L=FL_EL + a_rel, b_world_L=FL_EL + b_rel0,
                            a_rel=a_rel, b_rel=b_rel0,
                            d_rest=d_rest, d_min=d_min, d_max=d_max, stroke=d_max - d_min,
                            L_cyl=L_cyl, L_rod=L_rod, eng_min=eng_min, exp_min=exp_min,
                            min_lever=min_lever, el_range_deg=(math.degrees(el_min), math.degrees(el_max)),
                        )
    assert best is not None and best["eng_min"] >= 0.035 and best["exp_min"] >= 0.045
    return best


HYD = solve_front_hydraulic_anchors()
print(
    f"HYDRAULIC SOLVER OK: d_rest={HYD['d_rest']*1000:.1f}mm range=[{HYD['d_min']*1000:.1f}, {HYD['d_max']*1000:.1f}]mm "
    f"stroke={HYD['stroke']*1000:.1f}mm engage>={HYD['eng_min']*1000:.1f}mm exposed>={HYD['exp_min']*1000:.1f}mm "
    f"lever>={HYD['min_lever']*1000:.1f}mm"
)

# ==============================================================================
# 3. PROCEDURAL PBR TEXTURES (BLENDER 5.2 COLORSPACE-SAFE SAVE + RELOAD)
# ==============================================================================
def ensure_image_png(filepath, arr_rgba, colorspace="sRGB"):
    h, w, _ = arr_rgba.shape
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    name = os.path.basename(filepath)
    if name in bpy.data.images:
        bpy.data.images.remove(bpy.data.images[name])
    im = bpy.data.images.new(name, width=w, height=h, alpha=True)
    im.colorspace_settings.name = colorspace
    im.pixels.foreach_set(np.clip(arr_rgba[::-1], 0.0, 1.0).astype(np.float32).ravel())
    im.update()
    im.filepath_raw = filepath
    im.file_format = "PNG"
    im.save()
    bpy.data.images.remove(im)

    im_loaded = bpy.data.images.load(filepath)
    im_loaded.colorspace_settings.name = colorspace
    im_loaded.name = name
    assert np.array(im_loaded.pixels[:128]).max() > 0.01, f"Texture {name} empty!"
    return im_loaded


def generate_solar_textures():
    S = 1024
    y, x = np.mgrid[0:S, 0:S].astype(np.float32) / S
    nx, ny = 6.0, 6.0
    cx = (x * nx) % 1.0; cy = (y * ny) % 1.0
    ix = np.floor(x * nx); iy = np.floor(y * ny)
    cell_var = ((np.sin(ix * 12.9898 + iy * 78.233) * 43758.5453) % 1.0) - 0.5

    col = np.zeros((S, S, 4), dtype=np.float32)
    col[..., 0] = 0.042 + 0.012 * cell_var
    col[..., 1] = 0.092 + 0.016 * cell_var
    col[..., 2] = 0.278 + 0.032 * cell_var
    col[..., 3] = 1.0

    finger = (np.abs(((cy * 16.0) % 1.0) - 0.5) < 0.034)
    busbar = (np.abs(cx - 0.28) < 0.011) | (np.abs(cx - 0.72) < 0.011)
    border = (cx < 0.018) | (cx > 0.982) | (cy < 0.018) | (cy > 0.982)
    corner = (np.minimum(cx, 1.0 - cx) + np.minimum(cy, 1.0 - cy)) < 0.095

    col[finger, :3] = col[finger, :3] * 0.74 + np.array([0.42, 0.50, 0.65]) * 0.26
    col[busbar, :3] = np.array([0.55, 0.61, 0.68])
    seam = border | corner
    col[seam, :3] = np.array([0.60, 0.64, 0.65])

    orm = np.zeros((S, S, 4), dtype=np.float32)
    orm[..., 0] = np.where(border, 0.78, 1.0)
    orm[..., 1] = np.where(seam, 0.45, 0.17)
    orm[..., 2] = np.where(busbar | finger, 0.68, 0.10)
    orm[..., 3] = 1.0

    h = np.ones((S, S), dtype=np.float32); h[border] = 0.35; h[busbar] = 0.92
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 2.5
    gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 2.5
    ln = np.sqrt(gx * gx + gy * gy + 1.0)
    nrm = np.zeros((S, S, 4), dtype=np.float32)
    nrm[..., 0] = 0.5 + 0.5 * (-gx / ln); nrm[..., 1] = 0.5 + 0.5 * (gy / ln); nrm[..., 2] = 0.5 + 0.5 * (1.0 / ln); nrm[..., 3] = 1.0
    return (
        ensure_image_png(os.path.join(TEX_DIR, "solar_color.png"), col, "sRGB"),
        ensure_image_png(os.path.join(TEX_DIR, "solar_orm.png"), orm, "Non-Color"),
        ensure_image_png(os.path.join(TEX_DIR, "solar_normal.png"), nrm, "Non-Color"),
    )


def generate_leaf_textures():
    """Crisp 512x512 botanical leaf venation BaseColor, ORM & Normal maps (UV: u across width, v along length)."""
    S = 512
    v, u = np.mgrid[0:S, 0:S].astype(np.float32) / S
    du = np.abs(u - 0.5) * 2.0  # 0 at midrib, 1 at leaf margin

    # Central midrib + angled branching lateral veins
    midrib = np.exp(-((du / 0.045) ** 2)) * (1.0 - 0.55 * v)
    vein_wave = np.sin(2.0 * math.pi * (v * 9.0 - du * 2.4))
    lat_vein = np.clip((vein_wave - 0.72) / 0.28, 0.0, 1.0) * (1.0 - 0.4 * du) * (1.0 - 0.35 * v)
    veins = np.clip(midrib + 0.55 * lat_vein, 0.0, 1.0)

    # Natural chlorophyll gradient: richer emerald base -> bright sunlit chartreuse tip & veins
    col = np.zeros((S, S, 4), dtype=np.float32)
    col[..., 0] = 0.24 + 0.22 * v + 0.16 * veins + 0.06 * du
    col[..., 1] = 0.50 + 0.22 * v + 0.14 * veins
    col[..., 2] = 0.10 + 0.06 * v + 0.07 * veins
    col[..., 3] = 1.0

    orm = np.zeros((S, S, 4), dtype=np.float32)
    orm[..., 0] = 0.92 + 0.08 * veins
    orm[..., 1] = 0.42 - 0.08 * veins + 0.06 * du
    orm[..., 2] = 0.0
    orm[..., 3] = 1.0

    h = 0.5 + 0.38 * veins - 0.12 * du
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 3.0
    gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 3.0
    ln = np.sqrt(gx * gx + gy * gy + 1.0)
    nrm = np.zeros((S, S, 4), dtype=np.float32)
    nrm[..., 0] = 0.5 + 0.5 * (-gx / ln); nrm[..., 1] = 0.5 + 0.5 * (gy / ln); nrm[..., 2] = 0.5 + 0.5 * (1.0 / ln); nrm[..., 3] = 1.0
    return (
        ensure_image_png(os.path.join(TEX_DIR, "leaf_color.png"), col, "sRGB"),
        ensure_image_png(os.path.join(TEX_DIR, "leaf_orm.png"), orm, "Non-Color"),
        ensure_image_png(os.path.join(TEX_DIR, "leaf_normal.png"), nrm, "Non-Color"),
    )


def generate_braid_textures():
    S = 512
    y, x = np.mgrid[0:S, 0:S].astype(np.float32) / S
    weave = np.maximum(0.5 + 0.5 * np.sin(2.0 * math.pi * (x * 16.0 + y * 16.0)),
                       0.5 + 0.5 * np.sin(2.0 * math.pi * (x * 16.0 - y * 16.0)))
    col = np.zeros((S, S, 4), dtype=np.float32)
    col[..., 0] = 0.62 + 0.24 * weave; col[..., 1] = 0.56 + 0.22 * weave; col[..., 2] = 0.10 + 0.08 * weave; col[..., 3] = 1.0
    orm = np.zeros((S, S, 4), dtype=np.float32)
    orm[..., 0] = 0.72 + 0.28 * weave; orm[..., 1] = 0.60 - 0.14 * weave; orm[..., 2] = 0.04; orm[..., 3] = 1.0
    gx = (np.roll(weave, -1, 1) - np.roll(weave, 1, 1)) * 3.0
    gy = (np.roll(weave, -1, 0) - np.roll(weave, 1, 0)) * 3.0
    ln = np.sqrt(gx * gx + gy * gy + 1.0)
    nrm = np.zeros((S, S, 4), dtype=np.float32)
    nrm[..., 0] = 0.5 + 0.5 * (-gx / ln); nrm[..., 1] = 0.5 + 0.5 * (gy / ln); nrm[..., 2] = 0.5 + 0.5 * (1.0 / ln); nrm[..., 3] = 1.0
    return (
        ensure_image_png(os.path.join(TEX_DIR, "braid_color.png"), col, "sRGB"),
        ensure_image_png(os.path.join(TEX_DIR, "braid_orm.png"), orm, "Non-Color"),
        ensure_image_png(os.path.join(TEX_DIR, "braid_normal.png"), nrm, "Non-Color"),
    )


def generate_micro_surface_textures(tag, base_rgb, rough_base, metal_val, grain=0.025, scratch=0.03):
    S = 512
    rng = np.random.default_rng(abs(hash(tag)) % (2**31))
    n_hi = rng.normal(0.0, 1.0, (S, S)).astype(np.float32)
    n_lo = rng.normal(0.0, 1.0, (S // 8, S // 8)).astype(np.float32)
    n_lo = np.repeat(np.repeat(n_lo, 8, axis=0), 8, axis=1)
    for _ in range(4):
        n_lo = 0.25 * (np.roll(n_lo, 1, 0) + np.roll(n_lo, -1, 0) + np.roll(n_lo, 1, 1) + np.roll(n_lo, -1, 1))
    if metal_val > 0.5:
        n_hi = 0.25 * n_hi + 0.75 * np.mean(n_hi, axis=1, keepdims=True)
    h = 0.5 + 0.16 * n_lo + 0.06 * n_hi

    col = np.zeros((S, S, 4), dtype=np.float32)
    for c in range(3):
        col[..., c] = np.clip(base_rgb[c] * (1.0 + grain * n_lo + scratch * 0.35 * n_hi), 0.01, 0.99)
    col[..., 3] = 1.0

    orm = np.zeros((S, S, 4), dtype=np.float32)
    orm[..., 0] = np.clip(0.96 + 0.04 * n_lo, 0.85, 1.0)
    orm[..., 1] = np.clip(rough_base + 0.05 * n_lo + 0.02 * n_hi, 0.06, 0.96)
    orm[..., 2] = metal_val
    orm[..., 3] = 1.0

    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 1.2
    gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 1.2
    ln = np.sqrt(gx * gx + gy * gy + 1.0)
    nrm = np.zeros((S, S, 4), dtype=np.float32)
    nrm[..., 0] = 0.5 + 0.5 * (-gx / ln); nrm[..., 1] = 0.5 + 0.5 * (gy / ln); nrm[..., 2] = 0.5 + 0.5 * (1.0 / ln); nrm[..., 3] = 1.0
    return (
        ensure_image_png(os.path.join(TEX_DIR, f"{tag}_color.png"), col, "sRGB"),
        ensure_image_png(os.path.join(TEX_DIR, f"{tag}_orm.png"), orm, "Non-Color"),
        ensure_image_png(os.path.join(TEX_DIR, f"{tag}_normal.png"), nrm, "Non-Color"),
    )


# ==============================================================================
# 4. MATERIAL LIBRARY (100% glTF-2.0 NATIVE PBR)
# ==============================================================================
MATS = {}

def make_pbr_mat(name, im_col, im_orm, im_nrm, uv_scale=1.0, normal_str=0.28, coat=0.0):
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (uv_scale, uv_scale, uv_scale)
    nt.links.new(tc.outputs["UV"], mp.inputs["Vector"])

    tc_node = nt.nodes.new("ShaderNodeTexImage"); tc_node.image = im_col
    nt.links.new(mp.outputs["Vector"], tc_node.inputs["Vector"])
    nt.links.new(tc_node.outputs["Color"], bsdf.inputs["Base Color"])

    to_node = nt.nodes.new("ShaderNodeTexImage"); to_node.image = im_orm
    nt.links.new(mp.outputs["Vector"], to_node.inputs["Vector"])
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(to_node.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
    nt.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])

    grp = bpy.data.node_groups.get("glTF Material Output") or bpy.data.node_groups.new("glTF Material Output", "ShaderNodeTree")
    if not grp.interface.items_tree:
        grp.interface.new_socket("Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
    gn = nt.nodes.new("ShaderNodeGroup"); gn.node_tree = grp
    nt.links.new(sep.outputs["Red"], gn.inputs[0])

    tn_node = nt.nodes.new("ShaderNodeTexImage"); tn_node.image = im_nrm
    nt.links.new(mp.outputs["Vector"], tn_node.inputs["Vector"])
    nm = nt.nodes.new("ShaderNodeNormalMap"); nm.inputs["Strength"].default_value = normal_str
    nt.links.new(tn_node.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])

    if coat > 0.0 and "Coat Weight" in bsdf.inputs:
        bsdf.inputs["Coat Weight"].default_value = coat
        bsdf.inputs["Coat Roughness"].default_value = 0.12
    MATS[name] = m
    return m


def make_emissive_mat(name, base_rgb, emit_rgb, strength=3.5, rough=0.18):
    m = bpy.data.materials.new(name)
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (*base_rgb, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Emission Color"].default_value = (*emit_rgb, 1.0)
    bsdf.inputs["Emission Strength"].default_value = strength
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    MATS[name] = m
    return m


def build_materials():
    make_pbr_mat("M_white_armor", *generate_micro_surface_textures("white_armor", (0.875, 0.880, 0.848), 0.36, 0.03, 0.025, 0.018), uv_scale=3.0, normal_str=0.14, coat=0.08)
    make_pbr_mat("M_charcoal", *generate_micro_surface_textures("charcoal", (0.23, 0.24, 0.248), 0.42, 0.58, 0.055, 0.045), uv_scale=3.5, normal_str=0.25)
    make_pbr_mat("M_dark_rubber", *generate_micro_surface_textures("dark_rubber", (0.13, 0.138, 0.142), 0.78, 0.05, 0.055, 0.04), uv_scale=4.0, normal_str=0.35)
    make_pbr_mat("M_lime_accent", *generate_micro_surface_textures("lime_accent", (0.71, 0.825, 0.42), 0.35, 0.06, 0.032, 0.02), uv_scale=3.0, normal_str=0.18, coat=0.06)
    make_pbr_mat("M_machined_alum", *generate_micro_surface_textures("machined_alum", (0.74, 0.76, 0.75), 0.25, 0.88, 0.04, 0.04), uv_scale=2.5, normal_str=0.20)
    make_pbr_mat("M_brass", *generate_micro_surface_textures("brass", (0.78, 0.62, 0.28), 0.26, 0.90, 0.03, 0.02), uv_scale=2.5, normal_str=0.15)
    make_pbr_mat("M_chrome", *generate_micro_surface_textures("chrome", (0.91, 0.93, 0.94), 0.07, 0.98, 0.01, 0.01), uv_scale=2.0, normal_str=0.04)
    make_pbr_mat("M_lens_glass", *generate_micro_surface_textures("lens_glass", (0.04, 0.06, 0.07), 0.05, 0.10, 0.01, 0.01), uv_scale=1.0, normal_str=0.02, coat=0.95)
    make_pbr_mat("M_solar", *generate_solar_textures(), uv_scale=1.0, normal_str=0.45, coat=0.50)
    make_pbr_mat("M_yellow_braid", *generate_braid_textures(), uv_scale=1.0, normal_str=0.62)
    make_pbr_mat("M_soil", *generate_micro_surface_textures("soil", (0.17, 0.125, 0.082), 0.94, 0.0, 0.22, 0.14), uv_scale=4.0, normal_str=0.80)
    make_pbr_mat("M_moss_deep", *generate_micro_surface_textures("moss_deep", (0.20, 0.36, 0.095), 0.90, 0.0, 0.24, 0.15), uv_scale=5.0, normal_str=0.85)
    make_pbr_mat("M_moss_bright", *generate_micro_surface_textures("moss_bright", (0.39, 0.58, 0.16), 0.86, 0.0, 0.24, 0.15), uv_scale=5.5, normal_str=0.82)
    make_pbr_mat("M_foliage_stem", *generate_micro_surface_textures("foliage_stem", (0.32, 0.52, 0.14), 0.52, 0.0, 0.10, 0.05), uv_scale=2.0, normal_str=0.22)
    make_pbr_mat("M_foliage_leaf", *generate_leaf_textures(), uv_scale=1.0, normal_str=0.42, coat=0.08)

    make_emissive_mat("M_glow_lime",  (0.55, 1.0, 0.15), (0.45, 1.0, 0.08), strength=3.6)
    make_emissive_mat("M_glow_grow",  (0.88, 1.0, 0.24), (0.82, 1.0, 0.14), strength=4.6)
    make_emissive_mat("M_glow_amber", (1.0, 0.50, 0.04), (1.0, 0.42, 0.02), strength=4.0)
    make_emissive_mat("M_glow_mint",  (0.46, 0.96, 0.58), (0.35, 0.94, 0.48), strength=3.0)
    make_emissive_mat("M_glow_soft_lime", (0.68, 0.92, 0.34), (0.58, 0.92, 0.22), strength=1.4, rough=0.40)


# ==============================================================================
# 5. HARD-SURFACE GEOMETRY BUILDERS
# ==============================================================================
PART_REGISTRY = []

def _quad_caps(bm):
    ng = [f for f in bm.faces if len(f.verts) > 4]
    if ng:
        r = bmesh.ops.triangulate(bm, faces=ng, quad_method="BEAUTY", ngon_method="BEAUTY")
        bmesh.ops.join_triangles(bm, faces=r["faces"], angle_face_threshold=0.02, angle_shape_threshold=3.14)


def finalize_mesh(bm, name, mat_name, bone_name, smooth_angle=44.0, uv_mode="box", flex_bones=None):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    _quad_caps(bm)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()

    ngons = sum(1 for p in me.polygons if len(p.vertices) > 4)
    assert ngons == 0, f"Mesh {name} has {ngons} n-gons!"

    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    for mn in (mat_name if isinstance(mat_name, (list, tuple)) else [mat_name]):
        me.materials.append(MATS[mn])

    for p in me.polygons:
        p.use_smooth = True
    me.set_sharp_from_angle(angle=math.radians(smooth_angle))
    mod = obj.modifiers.new("WeightedNormal", "WEIGHTED_NORMAL")
    mod.keep_sharp = True; mod.weight = 60; mod.mode = "FACE_AREA"
    with bpy.context.temp_override(object=obj, active_object=obj, selected_objects=[obj]):
        bpy.ops.object.modifier_apply(modifier=mod.name)

    if not me.uv_layers:
        uv_layer = me.uv_layers.new(name="UVMap")
        if uv_mode == "planar_z":
            xs = [v.co.x for v in me.vertices]; ys = [v.co.y for v in me.vertices]
            x0, x1 = min(xs), max(xs); y0, y1 = min(ys), max(ys)
            dx, dy = max(1e-5, x1 - x0), max(1e-5, y1 - y0)
            for p in me.polygons:
                for li in p.loop_indices:
                    co = me.vertices[me.loops[li].vertex_index].co
                    uv_layer.data[li].uv = ((co.x - x0) / dx, (co.y - y0) / dy)
        else:
            for p in me.polygons:
                n = p.normal
                ax = max(range(3), key=lambda k: abs(n[k]))
                for li in p.loop_indices:
                    co = me.vertices[me.loops[li].vertex_index].co
                    uv_layer.data[li].uv = (co.y, co.z) if ax == 0 else ((co.x, co.z) if ax == 1 else (co.x, co.y))

    PART_REGISTRY.append(dict(obj=obj, bone=bone_name, flex_bones=flex_bones))
    return obj


def bm_add_box(bm, mn, mx, bev=0.0, seg=1, mat_idx=0, xf=None):
    mn, mx = V(mn), V(mx)
    res = bmesh.ops.create_cube(bm, size=1.0)
    verts = res["verts"]
    for v in verts:
        co = V([mn[i] + (v.co[i] + 0.5) * (mx[i] - mn[i]) for i in range(3)])
        v.co = (xf @ co) if xf is not None else co
    faces = list({f for v in verts for f in v.link_faces})
    for f in faces: f.material_index = mat_idx
    if bev > 0:
        edges = list({e for f in faces for e in f.edges})
        r = bmesh.ops.bevel(bm, geom=edges, offset=bev, offset_type="OFFSET", segments=seg, profile=0.5, affect="EDGES", clamp_overlap=True)
        for f in r["faces"]: f.material_index = mat_idx
    return verts


def bm_add_prism(bm, origin, ex, ey, outline, t0, t1, bev=0.0, mat_idx=0):
    O, ex, ey = V(origin), V(ex).normalized(), V(ey).normalized()
    ez = ex.cross(ey).normalized()
    N = len(outline)
    a = [bm.verts.new(O + ex * p[0] + ey * p[1] + ez * t0) for p in outline]
    b = [bm.verts.new(O + ex * p[0] + ey * p[1] + ez * t1) for p in outline]
    new_faces = []
    for i in range(N):
        j = (i + 1) % N
        f = bm.faces.new((a[i], a[j], b[j], b[i])); f.material_index = mat_idx; new_faces.append(f)
    f0 = bm.faces.new(list(reversed(a))); f1 = bm.faces.new(b)
    f0.material_index = f1.material_index = mat_idx; new_faces.extend([f0, f1])
    if bev > 0:
        bm.normal_update()
        edges = list({e for f in new_faces for e in f.edges if len(e.link_faces) == 2 and e.calc_face_angle(0) > 0.35})
        r = bmesh.ops.bevel(bm, geom=edges, offset=bev, segments=1, profile=0.5, affect="EDGES", clamp_overlap=True)
        for f in r["faces"]: f.material_index = mat_idx


def bm_add_cyl(bm, p0, p1, r0, r1=None, n=20, caps=(True, True), bev=0.0, mat_idx=0):
    p0, p1 = V(p0), V(p1)
    r1 = r0 if r1 is None else r1
    ax = (p1 - p0).normalized()
    ex = ax.cross(V((0, 0, 1))).normalized() if abs(ax.z) < 0.9 else ax.cross(V((1, 0, 0))).normalized()
    ey = ax.cross(ex).normalized()
    a = [bm.verts.new(p0 + (ex * math.cos(2 * math.pi * i / n) + ey * math.sin(2 * math.pi * i / n)) * r0) for i in range(n)]
    b = [bm.verts.new(p1 + (ex * math.cos(2 * math.pi * i / n) + ey * math.sin(2 * math.pi * i / n)) * r1) for i in range(n)]
    new_faces = []
    for i in range(n):
        j = (i + 1) % n
        f = bm.faces.new((a[i], a[j], b[j], b[i])); f.material_index = mat_idx; new_faces.append(f)
    if caps[0]: f = bm.faces.new(list(reversed(a))); f.material_index = mat_idx; new_faces.append(f)
    if caps[1]: f = bm.faces.new(b); f.material_index = mat_idx; new_faces.append(f)
    if bev > 0:
        edges = list({e for f in new_faces for e in f.edges if len(e.link_faces) == 2 and any(len(lf.verts) == n for lf in e.link_faces)})
        r = bmesh.ops.bevel(bm, geom=edges, offset=bev, segments=1, profile=0.5, affect="EDGES", clamp_overlap=True)
        for f in r["faces"]: f.material_index = mat_idx


def bm_add_bolt(bm, p, normal, r=0.0042, h=0.0032, mat_idx=0):
    p, n = V(p), V(normal).normalized()
    bm_add_cyl(bm, p - n * 0.001, p + n * h, r, n=6, caps=(False, True), bev=r * 0.16, mat_idx=mat_idx)
    bm_add_cyl(bm, p - n * 0.001, p + n * (h * 0.35), r * 1.38, n=12, caps=(False, True), mat_idx=mat_idx)


def bm_add_loft(bm, rings, cap_start=True, cap_end=True, mat_idx=0):
    v_rings = [[bm.verts.new(V(p)) for p in ring] for ring in rings]
    n = len(rings[0])
    for ra, rb in zip(v_rings, v_rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            f = bm.faces.new((ra[i], ra[j], rb[j], rb[i])); f.material_index = mat_idx
    if cap_start: bm.faces.new(list(reversed(v_rings[0]))).material_index = mat_idx
    if cap_end:   bm.faces.new(v_rings[-1]).material_index = mat_idx


def oct_ring_yz(x, yc, zc, hw, hh, ch_top=0.28, ch_bot=0.25):
    ct_y, ct_z = hw * (1.0 - ch_top), hh * (1.0 - ch_top)
    cb_y, cb_z = hw * (1.0 - ch_bot), hh * (1.0 - ch_bot)
    return [
        (x, yc + ct_y, zc + hh), (x, yc - ct_y, zc + hh),
        (x, yc - hw,   zc + ct_z), (x, yc - hw,   zc - cb_z),
        (x, yc - cb_y, zc - hh), (x, yc + cb_y, zc - hh),
        (x, yc + hw,   zc - cb_z), (x, yc + hw,   zc + ct_z),
    ]


def bm_add_rotary_drum(bm, center, width, radius, side_sign=+1, mat_alum=0, mat_dark=1, bolts=True):
    """Pass 3: Two-step harmonic-drive rotary drum with machined bearing race, recessed groove & 4 hex bolts."""
    c = V(center)
    y_in = c.y - side_sign * width * 0.50
    y_out = c.y + side_sign * width * 0.50
    # Main dark stator barrel
    bm_add_cyl(bm, (c.x, y_in, c.z), (c.x, y_out, c.z), radius * 0.93, n=28, bev=0.002, mat_idx=mat_dark)
    # Two-step brushed silver outer bearing race with subtle dark bearing seal groove
    bm_add_cyl(bm, (c.x, y_out - side_sign * 0.013, c.z), (c.x, y_out + side_sign * 0.002, c.z), radius, radius * 0.97, n=28, bev=0.0022, mat_idx=mat_alum)
    bm_add_cyl(bm, (c.x, y_out - side_sign * 0.001, c.z), (c.x, y_out + side_sign * 0.0045, c.z), radius * 0.80, radius * 0.78, n=24, mat_idx=mat_dark)
    bm_add_cyl(bm, (c.x, y_out + side_sign * 0.002, c.z), (c.x, y_out + side_sign * 0.006, c.z), radius * 0.72, radius * 0.69, n=24, bev=0.0012, mat_idx=mat_alum)
    # Inner side silver flange ring
    bm_add_cyl(bm, (c.x, y_in - side_sign * 0.002, c.z), (c.x, y_in + side_sign * 0.010, c.z), radius * 0.96, n=24, bev=0.002, mat_idx=mat_alum)
    # Recessed dark 4-bolt hub cap + central alignment boss
    bm_add_cyl(bm, (c.x, y_out + side_sign * 0.004, c.z), (c.x, y_out + side_sign * 0.0075, c.z), radius * 0.58, n=22, bev=0.0012, mat_idx=mat_dark)
    bm_add_cyl(bm, (c.x, y_out + side_sign * 0.006, c.z), (c.x, y_out + side_sign * 0.0095, c.z), radius * 0.16, n=14, bev=0.001, mat_idx=mat_alum)
    if bolts:
        br = radius * 0.39
        for k in range(4):
            ang = math.radians(45 + 90 * k)
            bm_add_bolt(bm, (c.x + br * math.cos(ang), y_out + side_sign * 0.0072, c.z + br * math.sin(ang)),
                        (0, side_sign, 0), r=radius * 0.088, h=0.0028, mat_idx=mat_alum)


def bm_add_tube(bm, pts, radius, n=12, mat_idx=0, uv_layer=None):
    pts = [V(p) for p in pts]; m = len(pts)
    tans = [(pts[1] - pts[0]).normalized() if i == 0 else ((pts[-1] - pts[-2]).normalized() if i == m - 1 else (pts[i + 1] - pts[i - 1]).normalized()) for i in range(m)]
    ex = tans[0].orthogonal().normalized(); ey = tans[0].cross(ex).normalized()
    rings = []; arc = [0.0]
    for i, p in enumerate(pts):
        if i > 0:
            arc.append(arc[-1] + (pts[i] - pts[i - 1]).length)
            axis = tans[i - 1].cross(tans[i])
            if axis.length > 1e-6:
                ang = math.acos(max(-1.0, min(1.0, tans[i - 1].dot(tans[i]))))
                ex = (Matrix.Rotation(ang, 3, axis.normalized()) @ ex).normalized()
                ey = tans[i].cross(ex).normalized()
        rings.append([bm.verts.new(p + (ex * math.cos(2 * math.pi * k / n) + ey * math.sin(2 * math.pi * k / n)) * radius) for k in range(n)])
    for i in range(m - 1):
        v0 = arc[i] / (2.0 * math.pi * radius); v1 = arc[i + 1] / (2.0 * math.pi * radius)
        for k in range(n):
            k2 = (k + 1) % n
            f = bm.faces.new((rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k])); f.material_index = mat_idx
            if uv_layer is not None:
                u0, u1 = k / n, (k + 1) / n
                for lp, uv in zip(f.loops, [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]): lp[uv_layer].uv = uv


def eval_bezier(p0, p1, p2, p3, steps=20):
    p0, p1, p2, p3 = V(p0), V(p1), V(p2), V(p3)
    return [((1 - i / steps)**3) * p0 + 3 * ((1 - i / steps)**2) * (i / steps) * p1 + 3 * (1 - i / steps) * ((i / steps)**2) * p2 + ((i / steps)**3) * p3 for i in range(steps + 1)]


# ==============================================================================
# 6. PART BUILDERS (PASS 3 HERO POLISH)
# ==============================================================================
def build_torso_and_carapace():
    # --- 1. Dark Anodized Monocoque Spine, Ribbed Belly Keel & Side Diagnostic Modules ---
    bm = bmesh.new()
    spine_sections = [
        oct_ring_yz( 0.345, 0.0, 0.545, 0.090, 0.072, 0.35, 0.35),
        oct_ring_yz( 0.255, 0.0, 0.515, 0.118, 0.098, 0.30, 0.34),
        oct_ring_yz( 0.100, 0.0, 0.525, 0.124, 0.104, 0.26, 0.34),
        oct_ring_yz(-0.080, 0.0, 0.542, 0.120, 0.092, 0.26, 0.32),
        oct_ring_yz(-0.260, 0.0, 0.556, 0.116, 0.076, 0.28, 0.30),
        oct_ring_yz(-0.440, 0.0, 0.552, 0.112, 0.068, 0.28, 0.30),
    ]
    bm_add_loft(bm, spine_sections, True, True, mat_idx=0)
    keel_pts = [(0.24, 0.424), (-0.04, 0.436), (-0.34, 0.492), (-0.34, 0.542), (0.24, 0.522)]
    bm_add_prism(bm, (0, 0, 0), (1, 0, 0), (0, 0, 1), keel_pts, -0.095, 0.095, bev=0.008, mat_idx=1)
    # Underside cooling skid fins
    for k in range(6):
        xk = -0.24 + k * 0.070
        zk = 0.430 + max(0.0, (-xk - 0.04) * 0.18)
        bm_add_box(bm, (xk, -0.074, zk - 0.008), (xk + 0.028, 0.074, zk + 0.006), bev=0.002, mat_idx=0)
    # Recessed lower flank heat-sink louver slats + amber & lime diagnostic indicators + silver manifold bolts
    for sy in (-1, 1):
        for k in range(6):
            xk = -0.22 + k * 0.024
            zk = 0.486 - k * 0.0055
            bm_add_box(bm, (xk, sy * 0.106, zk), (xk + 0.013, sy * 0.125, zk + 0.036), bev=0.0018, mat_idx=1)
        bm_add_box(bm, (-0.195, sy * 0.114, 0.486), (-0.172, sy * 0.127, 0.502), bev=0.001, mat_idx=2)
        bm_add_box(bm, (-0.165, sy * 0.114, 0.483), (-0.150, sy * 0.126, 0.495), bev=0.001, mat_idx=3)
        # Machined belly manifold clamp bar
        bm_add_box(bm, (-0.28, sy * 0.096, 0.486), (-0.23, sy * 0.122, 0.514), bev=0.003, mat_idx=4)
        bm_add_bolt(bm, (-0.255, sy * 0.122, 0.500), (0, sy, 0), r=0.004, h=0.003, mat_idx=4)
    finalize_mesh(bm, "P_chassis_spine", ["M_charcoal", "M_dark_rubber", "M_glow_amber", "M_glow_lime", "M_machined_alum"], "B_torso", uv_mode="box")

    # --- 2. Front Chest Radiator Intake Grille ---
    bm = bmesh.new()
    chest_xf = Matrix.Translation((0.295, 0.0, 0.482)) @ Matrix.Rotation(math.radians(-28), 4, 'Y')
    bm_add_box(bm, (-0.045, -0.064, -0.056), (0.045, 0.064, 0.056), bev=0.007, mat_idx=0, xf=chest_xf)
    for k in range(7):
        zk = -0.040 + k * 0.013
        bm_add_box(bm, (0.035, -0.050, zk), (0.051, 0.050, zk + 0.0055), bev=0.001, mat_idx=1, xf=chest_xf)
    # 4 tiny corner bolts on chest grille bezel
    for sy in (-1, 1):
        for sz in (-1, 1):
            bp = chest_xf @ V((0.045, sy * 0.055, sz * 0.044))
            bn = chest_xf.to_3x3() @ V((1, 0, 0))
            bm_add_bolt(bm, bp, bn, r=0.0032, h=0.0022, mat_idx=2)
    finalize_mesh(bm, "P_chest_grille", ["M_charcoal", "M_dark_rubber", "M_machined_alum"], "B_torso", uv_mode="box")

    # --- 3. Sculpted Faceted Matte-White Carapace Shell with Recessed Panel Seams & Fasteners ---
    bm = bmesh.new()
    # Front bulkhead ends cleanly at X=0.336 (before B_neck pivot at 0.340) so rotating neck NEVER clips!
    carapace_rings = [
        oct_ring_yz( 0.336, 0.0, 0.592, 0.076, 0.050, 0.34, 0.32),
        oct_ring_yz( 0.255, 0.0, 0.568, 0.130, 0.090, 0.30, 0.34),
        oct_ring_yz( 0.145, 0.0, 0.562, 0.156, 0.098, 0.28, 0.38),
        oct_ring_yz( 0.000, 0.0, 0.568, 0.154, 0.092, 0.32, 0.38),
        oct_ring_yz(-0.155, 0.0, 0.580, 0.148, 0.078, 0.32, 0.36),
        oct_ring_yz(-0.295, 0.0, 0.594, 0.136, 0.060, 0.30, 0.32),
        oct_ring_yz(-0.425, 0.0, 0.596, 0.124, 0.048, 0.28, 0.30),
        oct_ring_yz(-0.455, 0.0, 0.590, 0.106, 0.042, 0.28, 0.30),
    ]
    bm_add_loft(bm, carapace_rings, True, True, mat_idx=0)

    for sy in (-1, 1):
        # Swept faceted diamond side flank panel (2-layer stepped relief!)
        pts_flank = [
            (-0.272, 0.564), (-0.06, 0.488), (0.14, 0.468),
            (0.22, 0.558), (0.15, 0.634), (-0.18, 0.632), (-0.276, 0.602)
        ]
        if sy < 0: pts_flank = list(reversed(pts_flank))
        t0, t1 = sorted((-sy * 0.132, -sy * 0.158))
        bm_add_prism(bm, (0, 0, 0), (1, 0, 0), (0, 0, 1), pts_flank, t0, t1, bev=0.008, mat_idx=0)
        # Forward-swept crisp diagonal upper rib panel accent (proud +4mm outside flank to avoid z-fighting!)
        pts_chev = [(-0.16, 0.548), (0.04, 0.512), (0.13, 0.568), (0.07, 0.608), (-0.14, 0.606)]
        if sy < 0: pts_chev = list(reversed(pts_chev))
        t0v, t1v = sorted((-sy * 0.155, -sy * 0.166))
        bm_add_prism(bm, (0, 0, 0), (1, 0, 0), (0, 0, 1), pts_chev, t0v, t1v, bev=0.004, mat_idx=0)
        # Subtle dark panel trim + lime service tab cleanly offset outside flank
        bm_add_box(bm, (-0.12, sy * 0.157, 0.546), (-0.04, sy * 0.167, 0.553), bev=0.001, mat_idx=1)
        bm_add_box(bm, (-0.235, sy * 0.148, 0.578), (-0.205, sy * 0.161, 0.592), bev=0.0015, mat_idx=3)
        # Real machined silver mounting bolts at carapace flank panel corners
        for bx, bz in ((0.06, 0.588), (-0.12, 0.590), (-0.04, 0.526), (-0.255, 0.585)):
            bm_add_bolt(bm, (bx, sy * 0.166 if bx > -0.15 else sy * 0.158, bz), (0, sy, 0), r=0.0036, h=0.0024, mat_idx=2)

        # Front white chest fairing cheek wrapping around radiator grille (stays behind X=0.332!)
        pts_ch = [(0.19, 0.452), (0.320, 0.495), (0.332, 0.592), (0.19, 0.618)]
        if sy < 0: pts_ch = list(reversed(pts_ch))
        t0c, t1c = sorted((-sy * 0.088, -sy * 0.126))
        bm_add_prism(bm, (0, 0, 0), (1, 0, 0), (0, 0, 1), pts_ch, t0c, t1c, bev=0.007, mat_idx=0)

    # Clean matte-white rear dorsal maintenance hatch (NO rear solar panel — supports twin antennae!)
    bm_add_box(bm, (-0.432, -0.095, 0.628), (-0.232, 0.095, 0.654), bev=0.008, mat_idx=0)
    # Stepped inspection hatch cleanly raised +4mm above rear deck (zero coplanar z-fighting!)
    bm_add_box(bm, (-0.340, -0.064, 0.653), (-0.256, 0.064, 0.658), bev=0.001, mat_idx=1)
    bm_add_box(bm, (-0.335, -0.059, 0.657), (-0.261, 0.059, 0.662), bev=0.002, mat_idx=0)
    for sx in (-0.327, -0.269):
        for sy in (-0.051, 0.051):
            bm_add_bolt(bm, (sx, sy, 0.662), (0, 0, 1), r=0.0032, h=0.002, mat_idx=2)
    # Crisp dark transverse panel-seam grooves cleanly raised +3mm above carapace crown
    bm_add_box(bm, (0.150, -0.132, 0.659), (0.160, 0.132, 0.665), bev=0.001, mat_idx=1)
    bm_add_box(bm, (-0.240, -0.124, 0.654), (-0.232, 0.124, 0.660), bev=0.001, mat_idx=1)
    finalize_mesh(bm, "P_carapace_main", ["M_white_armor", "M_dark_rubber", "M_machined_alum", "M_lime_accent"], "B_torso", uv_mode="box")

    # --- 4. Flush Sloped Front-Hood Photovoltaic Solar Panel (ends cleanly at X=0.332 behind neck joint!) ---
    bm = bmesh.new()
    v_bez = [
        V((0.158,  0.104, 0.666)), V((0.158, -0.104, 0.666)),
        V((0.330, -0.062, 0.650)), V((0.330,  0.062, 0.650)),
    ]
    b0 = [bm.verts.new(p - V((0, 0, 0.010))) for p in v_bez]
    b1 = [bm.verts.new(p + V((0, 0, 0.005))) for p in v_bez]
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((b0[i], b0[j], b1[j], b1[i])).material_index = 1
    v_sol = [
        V((0.166,  0.095, 0.673)), V((0.166, -0.095, 0.673)),
        V((0.322, -0.055, 0.656)), V((0.322,  0.055, 0.656)),
    ]
    s0 = [bm.verts.new(p) for p in v_sol]
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((b1[i], b1[j], s0[j], s0[i])).material_index = 1
    bm.faces.new(list(reversed(s0))).material_index = 0
    uv_lay = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        for lp in f.loops:
            co = lp.vert.co
            lp[uv_lay].uv = ((co.x - 0.162) / 0.20, (co.y + 0.098) / 0.196)
    finalize_mesh(bm, "P_solar_hood", ["M_solar", "M_dark_rubber"], "B_torso", uv_mode="box")

    # --- 5. Flush Left & Right Mid-Flank Photovoltaic Solar Panels (clash-free clearance!) ---
    for sy, tag in ((+1, "L"), (-1, "R")):
        bm = bmesh.new()
        pts_o = [
            V(( 0.148, sy * 0.102, 0.668)),
            V((-0.232, sy * 0.100, 0.660)),
            V((-0.248, sy * 0.156, 0.616)),
            V(( 0.114, sy * 0.160, 0.616)),
        ]
        if sy < 0: pts_o = list(reversed(pts_o))
        nrm = (pts_o[1] - pts_o[0]).cross(pts_o[3] - pts_o[0]).normalized()
        if nrm.z < 0: nrm = -nrm
        b0 = [bm.verts.new(p - nrm * 0.010) for p in pts_o]
        b1 = [bm.verts.new(p + nrm * 0.006) for p in pts_o]
        for i in range(4):
            j = (i + 1) % 4
            bm.faces.new((b0[i], b0[j], b1[j], b1[i])).material_index = 1
        ctr = sum(pts_o, V((0, 0, 0))) / 4.0
        pts_in = [ctr + (p - ctr) * 0.92 + nrm * 0.008 for p in pts_o]
        s0 = [bm.verts.new(p) for p in pts_in]
        for i in range(4):
            j = (i + 1) % 4
            bm.faces.new((b1[i], b1[j], s0[j], s0[i])).material_index = 1
        bm.faces.new(s0).material_index = 0
        uv_lay = bm.loops.layers.uv.new("UVMap")
        for f in bm.faces:
            for lp in f.loops:
                co = lp.vert.co
                lp[uv_lay].uv = ((co.x + 0.255) / 0.41, (abs(co.y) - 0.10) / 0.14)
        finalize_mesh(bm, f"P_solar_flank_{tag}", ["M_solar", "M_dark_rubber"], "B_torso", uv_mode="box")

    # --- 6. Rear Dual-Bay Battery / Reservoir Pods & Glowing X-Vents ---
    bm_pod = bmesh.new(); bm_glow = bmesh.new()
    bm_add_box(bm_pod, (-0.545, -0.042, 0.490), (-0.420, 0.042, 0.602), bev=0.006, mat_idx=0)
    for sy in (-1, 1):
        bm_add_box(bm_pod, (-0.482, sy * 0.048, 0.492), (-0.436, sy * 0.122, 0.606), bev=0.005, mat_idx=1)
        bm_add_box(bm_glow, (-0.476, sy * 0.056, 0.502), (-0.442, sy * 0.128, 0.598), bev=0.003, mat_idx=0)
        y_in, y_out = sorted((sy * 0.036, sy * 0.146))
        bm_add_box(bm_pod, (-0.623, y_in, 0.480), (-0.480, y_out, 0.614), bev=0.011, mat_idx=0)
        y_mid = 0.5 * (y_in + y_out)
        # Stepped rear protective bezel + corner bolts + X-vents
        bm_add_box(bm_pod, (-0.625, y_mid - 0.042, 0.498), (-0.617, y_mid + 0.042, 0.596), bev=0.004, mat_idx=1)
        for dy_b in (-0.036, 0.036):
            for dz_b in (-0.040, 0.040):
                bm_add_bolt(bm_pod, (-0.624, y_mid + dy_b, 0.547 + dz_b), (-1, 0, 0), r=0.0028, h=0.002, mat_idx=2)
        for sx in (-1, 1):
            for sz in (-1, 1):
                xf = Matrix.Translation((-0.624, y_mid + sx * 0.021, 0.547 + sz * 0.022)) @ Matrix.Rotation(math.radians(42 * sx * sz), 4, 'X')
                bm_add_box(bm_glow, (-0.0025, -0.0035, -0.013), (0.002, 0.0035, 0.013), bev=0.0008, mat_idx=0, xf=xf)
        # Side vertical amber status strip in recessed dark frame
        bm_add_box(bm_pod, (-0.568, sy * 0.141, 0.500), (-0.542, sy * 0.149, 0.592), bev=0.002, mat_idx=1)
        bm_add_box(bm_glow, (-0.562, sy * 0.144, 0.506), (-0.548, sy * 0.150, 0.586), bev=0.001, mat_idx=1)
        # Top release latch handle & underside hydraulic manifold
        bm_add_box(bm_pod, (-0.585, y_mid - 0.026, 0.612), (-0.525, y_mid + 0.026, 0.620), bev=0.002, mat_idx=2)
        bm_add_box(bm_pod, (-0.545, y_mid - 0.024, 0.460), (-0.495, y_mid + 0.024, 0.484), bev=0.004, mat_idx=2)
    finalize_mesh(bm_pod, "P_rear_pods", ["M_charcoal", "M_dark_rubber", "M_machined_alum"], "B_torso", uv_mode="box")
    finalize_mesh(bm_glow, "P_rear_pod_glows", ["M_glow_lime", "M_glow_amber"], "B_torso", uv_mode="box")

    # --- 7. Under-Pod to Rear-Hip Braided Yellow Hoses with Hex Crimp Fittings ---
    for sy, tag in ((+1, "L"), (-1, "R")):
        bm = bmesh.new(); uv_lay = bm.loops.layers.uv.new("UVMap")
        pts = eval_bezier((-0.520, sy * 0.090, 0.465), (-0.500, sy * 0.115, 0.436),
                          (-0.425, sy * 0.152, 0.446), (-0.398, sy * 0.164, 0.518), steps=20)
        bm_add_tube(bm, pts, 0.0066, n=14, mat_idx=0, uv_layer=uv_lay)
        bm_add_cyl(bm, pts[0], pts[2], 0.0096, n=12, mat_idx=1)
        bm_add_cyl(bm, pts[1], pts[3], 0.0110, n=6, mat_idx=1)
        bm_add_cyl(bm, pts[-3], pts[-1], 0.0096, n=12, mat_idx=1)
        bm_add_cyl(bm, pts[-4], pts[-2], 0.0110, n=6, mat_idx=1)
        finalize_mesh(bm, f"P_belly_conduit_{tag}", ["M_yellow_braid", "M_machined_alum"], "B_torso", uv_mode="box")


def build_planter_and_foliage():
    """Pass 3: drip-irrigation ring w/ brass nozzles, dual-tone velvety moss, UV-veined botanical foliage."""
    cx, cz = -0.025, 0.656
    hx, hy, ch = 0.178, 0.114, 0.036

    def oct_2d(ax, ay, c):
        return [
            ( ax - c,  ay), (-ax + c,  ay), (-ax,  ay - c), (-ax, -ay + c),
            (-ax + c, -ay), ( ax - c, -ay), ( ax, -ay + c), ( ax,  ay - c),
        ]

    # --- 1. Octagonal Planter Collar + Inner Drip-Irrigation Manifold w/ Brass Misting Nozzles ---
    bm = bmesh.new()
    outer0 = [(cx + x, y, cz - 0.008) for x, y in oct_2d(hx + 0.012, hy + 0.012, ch + 0.004)]
    outer1 = [(cx + x, y, cz + 0.020) for x, y in oct_2d(hx + 0.006, hy + 0.006, ch + 0.002)]
    bm_add_loft(bm, [outer0, outer1], True, False, mat_idx=1)
    rim_out_bot = [(cx + x, y, cz + 0.016) for x, y in oct_2d(hx + 0.008, hy + 0.008, ch)]
    rim_out_mid = [(cx + x, y, cz + 0.044) for x, y in oct_2d(hx, hy, ch)]
    rim_out_top = [(cx + x, y, cz + 0.064) for x, y in oct_2d(hx - 0.016, hy - 0.014, ch * 0.85)]
    rim_in_top  = [(cx + x, y, cz + 0.062) for x, y in oct_2d(hx - 0.036, hy - 0.030, ch * 0.72)]
    rim_in_bot  = [(cx + x, y, cz + 0.020) for x, y in oct_2d(hx - 0.038, hy - 0.032, ch * 0.72)]
    bm_add_loft(bm, [rim_out_bot, rim_out_mid, rim_out_top, rim_in_top, rim_in_bot], False, True, mat_idx=0)
    # Corner clamp latches + hex bolts
    for sx in (-1, 1):
        for sy in (-1, 1):
            bm_add_box(bm, (cx + sx * (hx - 0.028) - 0.009, sy * (hy - 0.014) - 0.007, cz + 0.024),
                           (cx + sx * (hx - 0.028) + 0.009, sy * (hy - 0.014) + 0.007, cz + 0.056), bev=0.002, mat_idx=1)
            bm_add_bolt(bm, (cx + sx * (hx - 0.028), sy * (hy - 0.007), cz + 0.042), (0, sy, 0), r=0.003, h=0.002, mat_idx=2)
    # Inner stainless drip-irrigation pipe ring + 6 brass micro-misting nozzles pointing inward at sprouts!
    ring_pts = [(cx + x, y, cz + 0.056) for x, y in oct_2d(hx - 0.034, hy - 0.028, ch * 0.72)]
    ring_pts.append(ring_pts[0])
    bm_add_tube(bm, ring_pts, 0.0032, n=8, mat_idx=2)
    for nx_, ny_ in ((-0.125, 0.048), (-0.125, -0.048), (0.0, 0.080), (0.0, -0.080), (0.125, 0.048), (0.125, -0.048)):
        p0 = V((cx + nx_, ny_, cz + 0.056))
        d_in = (V((cx, 0.0, cz + 0.072)) - p0).normalized()
        bm_add_cyl(bm, p0, p0 + d_in * 0.011, 0.0038, 0.0026, n=8, mat_idx=3)
    finalize_mesh(bm, "P_planter_collar", ["M_lime_accent", "M_dark_rubber", "M_machined_alum", "M_brass"], "B_torso", uv_mode="box")

    # --- 2. Sculpted Dark Soil Bed ---
    bm = bmesh.new()
    res = bmesh.ops.create_grid(bm, x_segments=16, y_segments=12, size=1.0)
    for v in res["verts"]:
        px = v.co.x * (hx - 0.035); py = v.co.y * (hy - 0.029)
        r_oct = abs(px) / (hx - 0.035) + abs(py) / (hy - 0.029)
        if r_oct > 1.62:
            sc = 1.62 / r_oct; px *= sc; py *= sc
        bump = 0.008 * math.sin(px * 48.0) * math.cos(py * 55.0) + 0.014 * (1.0 - min(1.0, (px / hx)**2 + (py / hy)**2))
        v.co = V((cx + px, py, cz + 0.054 + bump))
    finalize_mesh(bm, "P_planter_soil", "M_soil", "B_torso", smooth_angle=75.0, uv_mode="planar_z")

    # --- 3. Dual-Tone Layered Velvety Moss Cushions (Deep Forest Base + Sunlit Chartreuse Crowns!) ---
    bm = bmesh.new()
    base_moss = [
        (-0.125,  0.042, 0.034), (-0.105, -0.044, 0.035), (-0.065,  0.062, 0.032),
        ( 0.065,  0.056, 0.034), ( 0.095, -0.045, 0.036), ( 0.122,  0.014, 0.034),
        ( 0.028, -0.062, 0.030), (-0.025,  0.066, 0.030), (-0.135, -0.004, 0.032),
        ( 0.056,  0.004, 0.028), (-0.080,  0.008, 0.030), ( 0.108,  0.050, 0.028),
        (-0.050, -0.060, 0.030), ( 0.128, -0.024, 0.028), (-0.010, -0.068, 0.026),
        ( 0.012,  0.068, 0.026), ( 0.138,  0.002, 0.026), (-0.142,  0.024, 0.026),
        (-0.088,  0.048, 0.028), ( 0.082, -0.016, 0.028), (-0.072, -0.028, 0.028),
    ]
    for mx, my, rad in base_moss:
        res = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=rad)
        for v in res["verts"]:
            p = v.co
            n = 1.0 + 0.28 * math.sin(p.x * 185 + mx * 45) * math.cos(p.y * 195 + my * 45) + 0.18 * math.sin(p.z * 210)
            v.co = V((cx + mx + p.x * n * 1.25, my + p.y * n * 1.15, cz + 0.066 + p.z * n * 0.72))
        for f in {f for v in res["verts"] for f in v.link_faces}:
            f.material_index = 0
    # Upper sunlit bright chartreuse moss micro-tufts crowning the mounds!
    rng = random.Random(108)
    for mx, my, rad in base_moss[::1]:
        for _ in range(2):
            ox = mx + rng.uniform(-0.016, 0.016)
            oy = my + rng.uniform(-0.014, 0.014)
            tr = rad * rng.uniform(0.45, 0.65)
            res = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=tr)
            for v in res["verts"]:
                p = v.co
                n = 1.0 + 0.30 * math.sin(p.x * 260 + ox * 70) * math.cos(p.y * 260 + oy * 70)
                v.co = V((cx + ox + p.x * n * 1.15, oy + p.y * n * 1.10, cz + 0.076 + p.z * n * 0.65))
            for f in {f for v in res["verts"] for f in v.link_faces}:
                f.material_index = 1
    finalize_mesh(bm, "P_planter_moss", ["M_moss_deep", "M_moss_bright"], "B_torso", smooth_angle=82.0, uv_mode="box")

    # --- 4. UV-Veined Lush Botanical Foliage (Broad Sprouts, 15-Pinnae Ferns & Clovers!) ---
    bm = bmesh.new()
    uv_lay = bm.loops.layers.uv.new("UVMap")

    def add_leaf(base, dir_v, up_v, length, width, arch=0.22, cup=0.18):
        d = V(dir_v).normalized(); u = V(up_v).normalized()
        side = d.cross(u).normalized(); u = side.cross(d).normalized()
        w_prof = [0.06, 0.72, 1.00, 0.68, 0.04]
        u_prof = [0.0, 0.25, 0.55, 0.82, 1.0]
        rows = []
        for s, wp in zip(u_prof, w_prof):
            z_drop = -arch * length * (s * s) + 0.28 * arch * length * s
            c = V(base) + d * (s * length) + u * z_drop
            hw = 0.5 * width * wp; cup_z = cup * hw
            rows.append((bm.verts.new(c + side * hw + u * cup_z), bm.verts.new(c), bm.verts.new(c - side * hw + u * cup_z)))
        for idx, (r0, r1) in enumerate(zip(rows, rows[1:])):
            v0, v1 = u_prof[idx], u_prof[idx + 1]
            fL = bm.faces.new((r0[0], r0[1], r1[1], r1[0])); fL.material_index = 1
            for lp, uv in zip(fL.loops, [(0.0, v0), (0.5, v0), (0.5, v1), (0.0, v1)]): lp[uv_lay].uv = uv
            fR = bm.faces.new((r0[1], r0[2], r1[2], r1[1])); fR.material_index = 1
            for lp, uv in zip(fR.loops, [(0.5, v0), (1.0, v0), (1.0, v1), (0.5, v1)]): lp[uv_lay].uv = uv

    def add_sprout_cluster(base, scale=1.0, yaw=0.0):
        base = V(base)
        top = base + V((0.012 * math.cos(yaw), 0.012 * math.sin(yaw), 0.094 * scale))
        bm_add_cyl(bm, base, top, 0.0034 * scale, 0.0020 * scale, n=6, caps=(False, True), mat_idx=0)
        for i in range(6):
            ang = yaw + i * 1.06
            p_b = base.lerp(top, 0.40 + 0.11 * i)
            d = V((math.cos(ang) * 0.84, math.sin(ang) * 0.84, 0.56 - 0.05 * i))
            add_leaf(p_b, d, V((0, 0, 1)), 0.072 * scale, 0.034 * scale, arch=0.25)

    def add_fern_frond(base, yaw, pitch_deg, length):
        base = V(base)
        d0 = V((math.cos(yaw) * math.cos(math.radians(pitch_deg)),
                math.sin(yaw) * math.cos(math.radians(pitch_deg)),
                math.sin(math.radians(pitch_deg))))
        side = V((-math.sin(yaw), math.cos(yaw), 0.0))
        steps = 10
        pts = [base + d0 * ((i / steps) * length) - V((0, 0, 0.36 * length * (i / steps)**2)) for i in range(steps + 1)]
        bm_add_tube(bm, pts, 0.0020, n=6, mat_idx=0, uv_layer=uv_lay)
        for i in range(2, steps):
            s = i / steps
            pin_len = 0.040 * math.sin(math.pi * s) + 0.008
            tan = (pts[min(steps, i + 1)] - pts[max(0, i - 1)]).normalized()
            for sg in (-1, 1):
                ldir = (side * sg * 0.85 + tan * 0.45 + V((0, 0, 0.16))).normalized()
                add_leaf(pts[i], ldir, V((0, 0, 1)), pin_len, pin_len * 0.42, arch=0.18, cup=0.10)

    def add_clover(base, yaw, scale=1.0):
        base = V(base); top = base + V((0, 0, 0.046 * scale))
        bm_add_cyl(bm, base, top, 0.0018 * scale, 0.0014 * scale, n=5, caps=(False, False), mat_idx=0)
        for i in range(3):
            ang = yaw + i * (2.0 * math.pi / 3.0)
            add_leaf(top, V((math.cos(ang), math.sin(ang), 0.16)), V((0, 0, 1)), 0.030 * scale, 0.026 * scale, arch=0.15, cup=0.16)

    z_p = cz + 0.068
    add_sprout_cluster((cx + 0.092,  0.036, z_p), scale=1.24, yaw=0.25)
    add_sprout_cluster((cx + 0.086, -0.038, z_p), scale=1.10, yaw=2.15)
    add_sprout_cluster((cx - 0.088, -0.034, z_p), scale=1.20, yaw=3.55)
    add_sprout_cluster((cx - 0.078,  0.046, z_p), scale=1.08, yaw=1.35)
    add_fern_frond((cx - 0.108,  0.018, z_p), yaw=math.radians(162), pitch_deg=52, length=0.156)
    add_fern_frond((cx - 0.100, -0.024, z_p), yaw=math.radians(202), pitch_deg=48, length=0.146)
    add_fern_frond((cx + 0.104, -0.008, z_p), yaw=math.radians(-14), pitch_deg=50, length=0.150)
    add_fern_frond((cx + 0.098,  0.028, z_p), yaw=math.radians(24),  pitch_deg=46, length=0.136)
    add_clover((cx + 0.036,  0.056, z_p), yaw=0.4, scale=1.15)
    add_clover((cx - 0.034, -0.056, z_p), yaw=1.8, scale=1.22)
    add_clover((cx + 0.120,  0.038, z_p), yaw=2.7, scale=1.08)
    add_clover((cx - 0.048,  0.060, z_p), yaw=0.9, scale=1.12)
    finalize_mesh(bm, "P_planter_plants", ["M_foliage_stem", "M_foliage_leaf"], "B_torso", smooth_angle=65.0, uv_mode="box")


def build_pedestal_and_canopy():
    """Pass 3: smooth organic 16-seg Y-pedestal + high-res 24x16 aerospace curved 6-bay solar canopy."""
    cx = P_CANOPY_YAW.x; z_yaw = P_CANOPY_YAW.z; z_pit = P_CANOPY_PITCH.z

    # --- 1. Base Yaw Turret (B_canopy_yaw, twin outer ears strictly outside Y-fork tongue!) ---
    bm = bmesh.new()
    bm_add_cyl(bm, (cx, 0, z_yaw - 0.018), (cx, 0, z_yaw + 0.024), 0.046, 0.042, n=24, bev=0.003, mat_idx=0)
    for sy in (-1, 1):
        y_lo, y_hi = sorted((sy * 0.036, sy * 0.048))
        bm_add_box(bm, (cx - 0.024, y_lo, z_yaw + 0.014), (cx + 0.024, y_hi, z_pit + 0.010), bev=0.004, mat_idx=1)
    finalize_mesh(bm, "P_pedestal_turret", ["M_charcoal", "M_white_armor"], "B_canopy_yaw", uv_mode="box")

    # --- 2. Twin Machined Circular Pitch-Pivot Drums (B_canopy_pitch) ---
    bm = bmesh.new()
    bm_add_cyl(bm, (cx, -0.050, z_pit), (cx, 0.050, z_pit), 0.037, n=28, bev=0.003, mat_idx=0)
    for sy in (-1, 1):
        bm_add_cyl(bm, (cx, sy * 0.044, z_pit), (cx, sy * 0.050, z_pit), 0.036, n=28, bev=0.002, mat_idx=2)
        bm_add_cyl(bm, (cx, sy * 0.048, z_pit), (cx, sy * 0.055, z_pit), 0.025, n=24, bev=0.002, mat_idx=1)
        for k in range(4):
            ang = math.radians(45 + 90 * k)
            bm_add_bolt(bm, (cx + 0.030 * math.cos(ang), sy * 0.050, z_pit + 0.030 * math.sin(ang)), (0, sy, 0), r=0.0024, h=0.0018, mat_idx=2)
    finalize_mesh(bm, "P_pedestal_drums", ["M_charcoal", "M_lime_accent", "M_machined_alum"], "B_canopy_pitch", uv_mode="box")

    # --- 3. Smooth Organic 16-Seg Sculpted Y-Forked Pedestal Arm (B_canopy_pitch) ---
    bm = bmesh.new()
    uv_lay = bm.loops.layers.uv.new("UVMap")

    def smooth_ring_z(x, y, z, rx, ry, n=16):
        pts = []
        for i in range(n):
            a = 2.0 * math.pi * i / n
            # Squircle exponent 0.85 for sleek automotive/aerospace rounded-chamfer cross-section
            ca, sa = math.cos(a), math.sin(a)
            px = math.copysign(abs(ca) ** 0.82, ca) * rx
            py = math.copysign(abs(sa) ** 0.82, sa) * ry
            pts.append((x + px, y + py, z))
        return pts

    bm_add_loft(bm, [
        smooth_ring_z(cx, 0.0, z_pit + 0.022, 0.034, 0.033),
        smooth_ring_z(cx, 0.0, z_pit + 0.040, 0.035, 0.034),
        smooth_ring_z(cx, 0.0, z_pit + 0.058, 0.039, 0.032),
        smooth_ring_z(cx, 0.0, z_pit + 0.072, 0.046, 0.030),
    ], True, True, mat_idx=0)
    # Recessed dark cooling vent louver on front/rear stem base (closeup_canopy_planter!)
    bm_add_box(bm, (cx + 0.032, -0.020, z_pit + 0.018), (cx + 0.041, 0.020, z_pit + 0.048), bev=0.002, mat_idx=2)
    bm_add_box(bm, (cx - 0.041, -0.020, z_pit + 0.018), (cx - 0.032, 0.020, z_pit + 0.048), bev=0.002, mat_idx=2)

    for sx in (+1, -1):
        pts = eval_bezier(
            (cx + sx * 0.018, 0.0, z_pit + 0.052),
            (cx + sx * 0.062, 0.0, z_pit + 0.095),
            (cx + sx * 0.080, 0.0, z_pit + 0.140),
            (cx + sx * 0.074, 0.0, z_pit + 0.166 + sx * 0.014),
            steps=14
        )
        bm_add_loft(bm, [smooth_ring_z(p.x, 0.0, p.z, 0.021 - 0.005 * (i / 14.0), 0.026 - 0.005 * (i / 14.0)) for i, p in enumerate(pts)], True, True, mat_idx=0)
        # Soft luminous lime inner liner curving smoothly inside the Y-fork throat!
        bm_add_loft(bm, [smooth_ring_z(p.x - sx * 0.012, 0.0, p.z, 0.009, 0.019, n=12) for p in pts[:-1]], True, True, mat_idx=5)

    bm_add_cyl(bm, (cx - 0.020, 0, z_pit + 0.068), (cx + 0.020, 0, z_pit + 0.068), 0.018, n=16, mat_idx=5)
    # Upper 6-bolt circular canopy mount flange
    can_xf = Matrix.Translation((cx + 0.012, 0.0, 0.950)) @ Matrix.Rotation(math.radians(-11.5), 4, 'Y')
    bm_add_cyl(bm, can_xf @ V((0, 0, -0.016)), can_xf @ V((0, 0, 0.006)), 0.056, 0.060, n=28, bev=0.002, mat_idx=2)
    for k in range(6):
        ang = k * math.pi / 3.0
        bp = can_xf @ V((0.043 * math.cos(ang), 0.043 * math.sin(ang), -0.016))
        bn = can_xf.to_3x3() @ V((0, 0, -1))
        bm_add_bolt(bm, bp, bn, r=0.0038, h=0.0026, mat_idx=3)

    # Charming twin-leaf mini sprout clinging off the Y-stalk!
    sp0 = V((cx + 0.034, 0.022, z_pit + 0.106))
    sp1 = V((cx + 0.080, 0.038, z_pit + 0.126))
    bm_add_cyl(bm, sp0, sp1, 0.0024, 0.0014, n=6, mat_idx=4)
    # Two cupped veined mini leaves at sprout tip
    for l_off, l_dir, l_sz in (
        (sp1, V((0.75, 0.45, 0.30)), 0.030),
        (sp0.lerp(sp1, 0.65), V((0.65, 0.65, -0.15)), 0.022),
    ):
        d = l_dir.normalized(); side = d.cross(V((0, 0, 1))).normalized(); u = side.cross(d).normalized()
        rows = []
        for s, wp in ((0.0, 0.1), (0.35, 0.9), (0.75, 0.8), (1.0, 0.08)):
            c = l_off + d * (s * l_sz) - u * (0.18 * l_sz * s * s)
            hw = 0.5 * l_sz * 0.58 * wp
            rows.append((bm.verts.new(c + side * hw + u * 0.002), bm.verts.new(c), bm.verts.new(c - side * hw + u * 0.002)))
        for idx_r, (r0, r1) in enumerate(zip(rows, rows[1:])):
            v0, v1 = idx_r / 3.0, (idx_r + 1) / 3.0
            f1 = bm.faces.new((r0[0], r0[1], r1[1], r1[0])); f1.material_index = 4
            f2 = bm.faces.new((r0[1], r0[2], r1[2], r1[1])); f2.material_index = 4
            for lp, uv in zip(f1.loops, [(0.0, v0), (0.5, v0), (0.5, v1), (0.0, v1)]): lp[uv_lay].uv = uv
            for lp, uv in zip(f2.loops, [(0.5, v0), (1.0, v0), (1.0, v1), (0.5, v1)]): lp[uv_lay].uv = uv

    # Fill box UVs for non-leaf faces
    for f in bm.faces:
        if f.material_index != 4:
            n = f.normal; ax = max(range(3), key=lambda k: abs(n[k]))
            for lp in f.loops:
                co = lp.vert.co
                lp[uv_lay].uv = (co.y, co.z) if ax == 0 else ((co.x, co.z) if ax == 1 else (co.x, co.y))
    finalize_mesh(bm, "P_pedestal_yfork", ["M_white_armor", "M_lime_accent", "M_charcoal", "M_machined_alum", "M_foliage_leaf", "M_glow_soft_lime"], "B_canopy_pitch", smooth_angle=52.0, uv_mode="box")

    # --- 4. High-Res 24x16 Aerospace Curved Leaf Solar Canopy (crown exact Z = 1.009 m!) ---
    canopy_xf = Matrix.Translation((cx + 0.012, 0.0, 0.956)) @ Matrix.Rotation(math.radians(-11.5), 4, 'Y')
    Lx = 0.252
    nu, nv = 24, 16

    def canopy_hw(u):
        # Smooth organic rounded-leaf planform (no sharp rectangular corners!)
        return 0.164 * ((1.0 - 0.56 * (u * u)) ** 0.72) * (1.0 + 0.05 * u * (1.0 - u * u))

    def canopy_z_top(u, v):
        return 0.016 * (1.0 - u * u) - 0.044 * (v * v)

    bm_sh = bmesh.new()
    top_grid, bot_grid = [], []
    for iu in range(nu + 1):
        u = -1.0 + 2.0 * iu / nu; x = u * Lx; hw = canopy_hw(u)
        tr_, br_ = [], []
        for iv in range(nv + 1):
            v = -1.0 + 2.0 * iv / nv; y = v * hw; zt = canopy_z_top(u, v)
            thick = 0.009 + 0.018 * (1.0 - v * v) * (1.0 - 0.45 * u * u)
            tr_.append(bm_sh.verts.new(canopy_xf @ V((x, y, zt))))
            br_.append(bm_sh.verts.new(canopy_xf @ V((x, y, zt - thick))))
        top_grid.append(tr_); bot_grid.append(br_)

    for iu in range(nu):
        for iv in range(nv):
            bm_sh.faces.new((top_grid[iu][iv], top_grid[iu + 1][iv], top_grid[iu + 1][iv + 1], top_grid[iu][iv + 1])).material_index = 0
            f_b = bm_sh.faces.new((bot_grid[iu][iv], bot_grid[iu][iv + 1], bot_grid[iu + 1][iv + 1], bot_grid[iu + 1][iv]))
            f_b.material_index = 0 if (iu <= 1 or iu >= nu - 2 or iv <= 1 or iv >= nv - 2) else 1
    for iu in range(nu):
        bm_sh.faces.new((bot_grid[iu][0], bot_grid[iu + 1][0], top_grid[iu + 1][0], top_grid[iu][0])).material_index = 0
        bm_sh.faces.new((top_grid[iu][nv], top_grid[iu + 1][nv], bot_grid[iu + 1][nv], bot_grid[iu][nv])).material_index = 0
    for iv in range(nv):
        bm_sh.faces.new((top_grid[0][iv], top_grid[0][iv + 1], bot_grid[0][iv + 1], bot_grid[0][iv])).material_index = 0
        bm_sh.faces.new((bot_grid[nu][iv], bot_grid[nu][iv + 1], top_grid[nu][iv + 1], top_grid[nu][iv])).material_index = 0

    # 12 sculpted underside cooling heat-sink louver fins + dark recessed LED bezel frames!
    for sy in (-1, 1):
        for k in range(6):
            xk = -0.056 + k * 0.022
            bm_add_box(bm_sh, (xk, sy * 0.104, -0.032), (xk + 0.007, sy * 0.132, -0.020), bev=0.001, mat_idx=2, xf=canopy_xf)
    for sx in (+1, -1):
        for y_off in (-0.064, 0.0, 0.064):
            x_c = sx * 0.098
            z_u = canopy_z_top(x_c / Lx, y_off / 0.16) - 0.024
            bm_add_box(bm_sh, (x_c - 0.048, y_off - 0.024, z_u - 0.005), (x_c + 0.048, y_off + 0.024, z_u + 0.004), bev=0.002, mat_idx=2, xf=canopy_xf)
    finalize_mesh(bm_sh, "P_canopy_shell", ["M_lime_accent", "M_charcoal", "M_dark_rubber"], "B_canopy_pitch", smooth_angle=52.0, uv_mode="box")

    # 6 curved segmented deep cobalt-navy photovoltaic bays on canopy top
    bm_sol = bmesh.new(); uv_lay = bm_sol.loops.layers.uv.new("UVMap")
    for u0, u1 in [(-0.91, -0.34), (-0.30, 0.30), (0.34, 0.91)]:
        for v0, v1 in [(-0.89, -0.045), (0.045, 0.89)]:
            su, sv = 6, 5
            g_top, g_bot = [], []
            for iu in range(su + 1):
                u = u0 + (u1 - u0) * iu / su; x = u * Lx; hw = canopy_hw(u)
                rt, rb = [], []
                for iv in range(sv + 1):
                    v = v0 + (v1 - v0) * iv / sv; y = v * hw; zt = canopy_z_top(u, v)
                    rt.append(bm_sol.verts.new(canopy_xf @ V((x, y, zt + 0.0045))))
                    rb.append(bm_sol.verts.new(canopy_xf @ V((x, y, zt - 0.0010))))
                g_top.append(rt); g_bot.append(rb)
            for iu in range(su):
                for iv in range(sv):
                    f = bm_sol.faces.new((g_top[iu][iv], g_top[iu + 1][iv], g_top[iu + 1][iv + 1], g_top[iu][iv + 1]))
                    f.material_index = 0
                    for lp, uv in zip(f.loops, [(iu / su, iv / sv), ((iu + 1) / su, iv / sv), ((iu + 1) / su, (iv + 1) / sv), (iu / su, (iv + 1) / sv)]):
                        lp[uv_lay].uv = uv
            for iu in range(su):
                for side_iv, rev in ((0, False), (sv, True)):
                    vs = (g_bot[iu][side_iv], g_bot[iu + 1][side_iv], g_top[iu + 1][side_iv], g_top[iu][side_iv])
                    bm_sol.faces.new(tuple(reversed(vs)) if rev else vs).material_index = 1
            for iv in range(sv):
                for side_iu, rev in ((0, True), (su, False)):
                    vs = (g_bot[side_iu][iv], g_bot[side_iu][iv + 1], g_top[side_iu][iv + 1], g_top[side_iu][iv])
                    bm_sol.faces.new(tuple(reversed(vs)) if rev else vs).material_index = 1
    finalize_mesh(bm_sol, "P_canopy_solar", ["M_solar", "M_dark_rubber"], "B_canopy_pitch", smooth_angle=50.0, uv_mode="box")

    # 6 glowing yellow-lime LED grow-light diffuser pads + forward amber tip bar
    bm_led = bmesh.new()
    for sx in (+1, -1):
        for y_off in (-0.064, 0.0, 0.064):
            x_c = sx * 0.098
            z_u = canopy_z_top(x_c / Lx, y_off / 0.16) - 0.027
            bm_add_box(bm_led, (x_c - 0.042, y_off - 0.019, z_u - 0.003), (x_c + 0.042, y_off + 0.019, z_u + 0.003), bev=0.0018, mat_idx=0, xf=canopy_xf)
    z_tip = canopy_z_top(0.78, 0.0) - 0.020
    bm_add_box(bm_led, (0.172, -0.030, z_tip - 0.004), (0.210, 0.030, z_tip + 0.003), bev=0.002, mat_idx=1, xf=canopy_xf)
    finalize_mesh(bm_led, "P_canopy_leds", ["M_glow_grow", "M_glow_amber"], "B_canopy_pitch", uv_mode="box")


def build_neck_and_head():
    """Pass 3.5: True coaxial gimbal clearance at neck-root & neck-head joints + zero head-top z-fighting!"""
    # --- 1. Dark Ribbed Mechanical Gimbal Hubs (centered on B_neck=0.340 and B_head=0.468!) ---
    bm = bmesh.new()
    # Solid dark inner spine shaft bridging torso socket -> neck -> head gimbal
    bm_add_cyl(bm, (0.318, 0.0, 0.592), (0.494, 0.0, 0.580), 0.042, 0.038, n=24, bev=0.002, mat_idx=0)
    # Spherical/ribbed dark gimbal bellows at B_neck (X=0.340) so ±20 deg yaw/pitch NEVER shows a hollow gap or clips!
    for xk, rk in ((0.336, 0.050), (0.346, 0.052), (0.356, 0.050)):
        bm_add_cyl(bm, (xk - 0.004, 0.0, 0.592), (xk + 0.004, 0.0, 0.592), rk, n=24, bev=0.0015, mat_idx=1)
    # Spherical/ribbed dark gimbal bellows at B_head (X=0.468) bridging the 38 mm clearance gap cleanly!
    for xk, rk in ((0.456, 0.046), (0.468, 0.049), (0.480, 0.046)):
        bm_add_cyl(bm, (xk - 0.004, 0.0, 0.580), (xk + 0.004, 0.0, 0.580), rk, n=24, bev=0.0015, mat_idx=1)
    # Twin lower neck linkage struts tucked cleanly inside belly throat
    for sy in (-1, 1):
        bm_add_cyl(bm, (0.344, sy * 0.026, 0.550), (0.460, sy * 0.024, 0.542), 0.0085, n=12, mat_idx=1)
    finalize_mesh(bm, "P_neck_collar", ["M_charcoal", "M_dark_rubber"], "B_neck", uv_mode="box")

    # --- 2. Tapered Faceted Neck Shell (X = 0.362..0.448 -> 26mm rear + 20mm front gimbal clearance!) ---
    bm = bmesh.new()
    neck_rings = [
        oct_ring_yz(0.362, 0.0, 0.594, 0.068, 0.048, 0.36, 0.34),
        oct_ring_yz(0.405, 0.0, 0.589, 0.065, 0.050, 0.32, 0.30),
        oct_ring_yz(0.448, 0.0, 0.584, 0.063, 0.049, 0.32, 0.30),
    ]
    bm_add_loft(bm, neck_rings, True, True, mat_idx=0)
    for sy in (-1, 1):
        bm_add_bolt(bm, (0.405, sy * 0.065, 0.594), (0, sy, 0), r=0.0032, h=0.0022, mat_idx=2)
    finalize_mesh(bm, "P_neck_shell", ["M_white_armor", "M_dark_rubber", "M_machined_alum"], "B_neck", uv_mode="box")

    # --- 3. Sculpted Canine Sensor Head Casing (starts cleanly at X=0.486 -> 38mm clearance to neck shell!) ---
    bm = bmesh.new()
    head_rings = [
        oct_ring_yz(0.486, 0.0, 0.579, 0.066, 0.052, 0.30, 0.28),
        oct_ring_yz(0.556, 0.0, 0.574, 0.072, 0.056, 0.26, 0.24),
        oct_ring_yz(0.616, 0.0, 0.568, 0.068, 0.054, 0.24, 0.24),
    ]
    bm_add_loft(bm, head_rings, True, True, mat_idx=0)
    # Sloped dark visor brow cap cleanly raised +4mm ABOVE the sloped head roof (ZERO z-fighting!)
    brow_xf = Matrix.Translation((0.570, 0.0, 0.629)) @ Matrix.Rotation(math.radians(5.0), 4, 'Y')
    bm_add_box(bm, (-0.042, -0.044, -0.003), (0.042, 0.044, 0.007), bev=0.003, mat_idx=1, xf=brow_xf)
    # Side white cheek armor pods cleanly proud outside head_rings (zero coplanar overlap!)
    for sy in (-1, 1):
        y_lo, y_hi = sorted((sy * 0.065, sy * 0.076))
        bm_add_box(bm, (0.564, y_lo, 0.522), (0.614, y_hi, 0.616), bev=0.004, mat_idx=0)
        bm_add_bolt(bm, (0.532, sy * 0.070, 0.592), (0, sy, 0), r=0.0032, h=0.0022, mat_idx=2)
        bm_add_bolt(bm, (0.532, sy * 0.070, 0.550), (0, sy, 0), r=0.0032, h=0.0022, mat_idx=2)
    finalize_mesh(bm, "P_head_shell", ["M_white_armor", "M_charcoal", "M_machined_alum"], "B_head", uv_mode="box")

    # Dark Front Optical Bezel & Side Optical Frames (recessed cleanly behind optics at X=0.619 -> ZERO buried eyes!)
    bm = bmesh.new()
    bm_add_box(bm, (0.592, -0.054, 0.514), (0.618, 0.054, 0.622), bev=0.005, mat_idx=0)
    bm_add_box(bm, (0.612, -0.043, 0.522), (0.620, 0.043, 0.614), bev=0.0018, mat_idx=1)
    for sy in (-1, 1):
        y_lo, y_hi = sorted((sy * 0.073, sy * 0.080))
        bm_add_box(bm, (0.578, y_lo, 0.532), (0.606, y_hi, 0.604), bev=0.002, mat_idx=1)
    finalize_mesh(bm, "P_head_bezel", ["M_charcoal", "M_dark_rubber"], "B_head", uv_mode="box")

    # Machined Lens Barrels, Glowing Emerald Ring Optic, Reflective Dark Glass, Mint Dome & Amber Sensors
    # All proudly mounted +4..6mm IN FRONT of the X=0.620 black recessed bezel face (ZERO clipping/burying!)
    bm = bmesh.new()
    bm_add_cyl(bm, (0.618, 0.0, 0.586), (0.6245, 0.0, 0.586), 0.0195, 0.0185, n=24, bev=0.001, mat_idx=4)
    bm_add_cyl(bm, (0.621, 0.0, 0.586), (0.6260, 0.0, 0.586), 0.0168, n=24, mat_idx=0)
    bm_add_cyl(bm, (0.623, 0.0, 0.586), (0.6266, 0.0, 0.586), 0.0108, n=24, mat_idx=3)
    bm_add_cyl(bm, (0.618, 0.0, 0.544), (0.6240, 0.0, 0.544), 0.0175, 0.0168, n=24, bev=0.001, mat_idx=4)
    bm_add_cyl(bm, (0.621, 0.0, 0.544), (0.6258, 0.0, 0.544), 0.0148, n=24, mat_idx=1)
    for sy in (-1, 1):
        bm_add_box(bm, (0.619, sy * 0.033 - 0.0038, 0.572), (0.6245, sy * 0.033 + 0.0038, 0.600), bev=0.001, mat_idx=2)
        y_lo, y_hi = sorted((sy * 0.077, sy * 0.082))
        bm_add_box(bm, (0.586, y_lo, 0.544), (0.598, y_hi, 0.594), bev=0.001, mat_idx=2)
    finalize_mesh(bm, "P_head_optics", ["M_glow_lime", "M_glow_mint", "M_glow_amber", "M_lens_glass", "M_machined_alum"], "B_head", uv_mode="box")

    # Protruding Faceted Lime-Green & White Chin Bumper Skid
    bm = bmesh.new()
    bm_add_box(bm, (0.535, -0.044, 0.500), (0.595, 0.044, 0.516), bev=0.003, mat_idx=2)
    chin_xf = Matrix.Translation((0.578, 0.0, 0.494)) @ Matrix.Rotation(math.radians(-10), 4, 'Y')
    bm_add_box(bm, (-0.050, -0.058, -0.010), (0.044, 0.058, 0.008), bev=0.004, mat_idx=0, xf=chin_xf)
    bm_add_box(bm, (-0.040, -0.048, -0.016), (0.042, 0.048, -0.004), bev=0.003, mat_idx=1, xf=chin_xf)
    finalize_mesh(bm, "P_head_chin", ["M_white_armor", "M_lime_accent", "M_charcoal"], "B_head", uv_mode="box")


def build_rear_antennae():
    for sy, tag in ((+1, "L"), (-1, "R")):
        piv = V((P_ANT_L.x, sy * P_ANT_L.y, P_ANT_L.z))
        ant_xf = Matrix.Translation(piv) @ Matrix.Rotation(math.radians(-38.0), 4, 'Y')

        def loc_box_ring(z, hx, hy):
            return [ant_xf @ V((px, py, z)) for px, py in [
                (hx, hy * 0.7), (hx * 0.7, hy), (-hx * 0.7, hy), (-hx, hy * 0.7),
                (-hx, -hy * 0.7), (-hx * 0.7, -hy), (hx * 0.7, -hy), (hx, -hy * 0.7),
            ]]

        bm_v = bmesh.new()
        bm_add_cyl(bm_v, (piv.x, piv.y - 0.017, piv.z), (piv.x, piv.y + 0.017, piv.z), 0.016, n=18, bev=0.002, mat_idx=1)
        bm_add_bolt(bm_v, (piv.x, piv.y + sy * 0.017, piv.z), (0, sy, 0), r=0.0045, h=0.0025, mat_idx=1)
        bm_add_box(bm_v, (-0.020, -0.013, -0.008), (0.020, 0.013, 0.032), bev=0.003, mat_idx=0, xf=ant_xf)
        bm_add_loft(bm_v, [loc_box_ring(0.020, 0.019, 0.012), loc_box_ring(0.110, 0.016, 0.010), loc_box_ring(0.192, 0.012, 0.009)], True, True, mat_idx=0)
        bm_add_box(bm_v, (-0.005, -0.013, 0.040), (0.005, 0.013, 0.175), bev=0.001, mat_idx=1, xf=ant_xf)
        finalize_mesh(bm_v, f"P_ant_vane_{tag}", ["M_charcoal", "M_machined_alum"], f"B_ant_{tag}", uv_mode="box")

        bm_t = bmesh.new()
        bm_add_loft(bm_t, [loc_box_ring(0.192, 0.0125, 0.0092), loc_box_ring(0.228, 0.0105, 0.0078), loc_box_ring(0.238, 0.0065, 0.0052)], True, True, mat_idx=0)
        finalize_mesh(bm_t, f"P_ant_tip_{tag}", "M_glow_lime", f"B_ant_{tag}", uv_mode="box")


def build_paw_assembly(side_tag, leg_prefix, sy, wrist_pos, paw_pos, bone_name):
    bm_a = bmesh.new()
    w = V((wrist_pos.x, sy * Y_LEG, wrist_pos.z))
    p = V((paw_pos.x, sy * Y_LEG, 0.032))
    # Twin inner clevis cheeks fitting cleanly inside forearm wrist fork (outer 0.0185 < inner fork 0.021!)
    for sg in (-1, 1):
        bm_add_cyl(bm_a, w + V((0, sg * 0.010, 0)), p + V((0, sg * 0.010, 0.004)), 0.0082, 0.0082, n=14, mat_idx=0)
    bm_add_box(bm_a, (p.x - 0.030, p.y - 0.020, 0.026), (p.x + 0.026, p.y + 0.020, min(0.050, w.z - 0.022)), bev=0.004, mat_idx=0)
    bm_add_cyl(bm_a, (p.x - 0.014, p.y - 0.027, 0.044), (p.x - 0.014, p.y + 0.027, 0.044), 0.0065, n=12, mat_idx=1)
    bm_add_bolt(bm_a, (p.x - 0.014, p.y + sy * 0.027, 0.044), (0, sy, 0), r=0.0038, h=0.0022, mat_idx=1)
    finalize_mesh(bm_a, f"P_{leg_prefix}{side_tag}_paw_ankle", ["M_charcoal", "M_machined_alum"], bone_name, uv_mode="box")

    bm_p = bmesh.new()
    px, py = paw_pos.x, sy * Y_LEG
    bm_add_box(bm_p, (px - 0.050, py - 0.028, 0.011), (px + 0.052, py + 0.028, 0.032), bev=0.004, mat_idx=0)
    # 7 crisp sculpted transverse traction tread ribs strictly coplanar at Z = 0.000 m!
    for k in range(7):
        xk = (px - 0.047) + k * 0.0142
        bm_add_box(bm_p, (xk, py - 0.026, 0.000), (xk + 0.0098, py + 0.026, 0.013), bev=0.0014, mat_idx=1)
    # Chamfered lime-green toe bumper clip with black central latch!
    bm_add_box(bm_p, (px + 0.045, py - 0.021, 0.007), (px + 0.056, py + 0.021, 0.029), bev=0.0025, mat_idx=2)
    bm_add_box(bm_p, (px + 0.048, py - 0.009, 0.006), (px + 0.058, py + 0.009, 0.028), bev=0.0015, mat_idx=1)
    finalize_mesh(bm_p, f"P_{leg_prefix}{side_tag}_paw_pad", ["M_charcoal", "M_dark_rubber", "M_lime_accent"], bone_name, uv_mode="box")


def build_front_legs():
    """Pass 3: 3D-crowned swept shoulder cowls w/ hex bolts, CNC-milled forearms, banjo-fitted hydraulic actuators."""
    for sy, tag in ((+1, "L"), (-1, "R")):
        sh_p = V((FL_SH.x, sy * Y_LEG, FL_SH.z))
        el_p = V((FL_EL.x, sy * Y_LEG, FL_EL.z))
        wr_p = V((FL_WR.x, sy * Y_LEG, FL_WR.z))
        pw_p = V((FL_PAW.x, sy * Y_LEG, 0.000))

        def seg_ring(p, u, n, hn, hy):
            c_n, c_y = hn * 0.72, hy * 0.72
            return [
                p + n * hn + V((0, c_y, 0)), p + n * c_n + V((0, hy, 0)),
                p - n * c_n + V((0, hy, 0)), p - n * hn + V((0, c_y, 0)),
                p - n * hn - V((0, c_y, 0)), p - n * c_n - V((0, hy, 0)),
                p + n * c_n - V((0, hy, 0)), p + n * hn - V((0, c_y, 0)),
            ]

        bm = bmesh.new()
        y0, y1 = sorted((sy * (Y_AB - 0.016), sy * (Y_LEG - 0.026)))
        bm_add_cyl(bm, (sh_p.x, y0, sh_p.z), (sh_p.x, y1, sh_p.z), 0.048, 0.044, n=22, bev=0.003, mat_idx=0)
        bm_add_cyl(bm, (sh_p.x, sy * (Y_AB + 0.006), sh_p.z), (sh_p.x, sy * (Y_AB + 0.018), sh_p.z), 0.052, n=22, bev=0.002, mat_idx=1)
        finalize_mesh(bm, f"P_F{tag}_shoulder_mount", ["M_charcoal", "M_machined_alum"], f"B_F{tag}_ab", uv_mode="box")

        bm = bmesh.new()
        bm_add_rotary_drum(bm, sh_p, 0.056, 0.052, side_sign=sy, mat_alum=0, mat_dark=1, bolts=True)
        finalize_mesh(bm, f"P_F{tag}_shoulder_drum", ["M_machined_alum", "M_charcoal"], f"B_F{tag}_upper", uv_mode="box")

        # 3D-Crowned Swept Faceted Matte-White Shoulder Cowl (cleanly clears elbow collar at max flexion!)
        bm_cowl = bmesh.new(); bm_vent = bmesh.new()
        u_ua = (el_p - sh_p).normalized(); n_ua = V((-u_ua.z, 0.0, u_ua.x))
        cowl_base = [
            (sh_p.x + 0.095, sh_p.z + 0.025), (sh_p.x + 0.032, sh_p.z + 0.080),
            (sh_p.x - 0.072, sh_p.z + 0.052), (el_p.x - 0.034, el_p.z + 0.098),
            (el_p.x + 0.028, el_p.z + 0.070), (sh_p.x + 0.088, sh_p.z - 0.060),
        ]
        cx_c = sum(p[0] for p in cowl_base) / len(cowl_base)
        cz_c = sum(p[1] for p in cowl_base) / len(cowl_base)
        cowl_crown = [(cx_c + (px - cx_c) * 0.78, cz_c + (pz - cz_c) * 0.78) for px, pz in cowl_base]
        r_in  = [(px, sy * 0.166, pz) for px, pz in cowl_base]
        r_mid = [(px, sy * 0.200, pz) for px, pz in cowl_base]
        r_out = [(px, sy * 0.213, pz) for px, pz in cowl_crown]
        if sy < 0:
            r_in, r_mid, r_out = list(reversed(r_in)), list(reversed(r_mid)), list(reversed(r_out))
        bm_add_loft(bm_cowl, [r_in, r_mid, r_out], True, True, mat_idx=0)
        bm_add_box(bm_cowl, (sh_p.x - 0.058, min(sy * 0.145, sy * 0.200), sh_p.z + 0.040),
                            (sh_p.x + 0.056, max(sy * 0.145, sy * 0.200), sh_p.z + 0.074), bev=0.007, mat_idx=0)

        # Recessed diagonal amber louver pocket + central vertical metallic fin + 4 corner cowl bolts!
        vent_ctr = sh_p.lerp(el_p, 0.36) + V((0.026, sy * 0.039, 0.005))
        vent_ang = sag_angle(el_p - sh_p) + math.radians(12.0)
        vent_xf = Matrix.Translation(vent_ctr) @ Matrix.Rotation(vent_ang, 4, 'Y')
        bm_add_box(bm_cowl, (-0.028, -0.0065, -0.068), (0.028, 0.0065, 0.068), bev=0.003, mat_idx=1, xf=vent_xf)
        bm_add_box(bm_cowl, (-0.0028, -0.0078, -0.060), (0.0028, 0.0078, 0.060), bev=0.0008, mat_idx=2, xf=vent_xf)
        for sx_b in (-0.023, 0.023):
            for sz_b in (-0.061, 0.061):
                bp = vent_xf @ V((sx_b, sy * 0.0068, sz_b))
                bm_add_bolt(bm_cowl, bp, (0, sy, 0), r=0.0025, h=0.0018, mat_idx=2)
        for k in range(7):
            zk = -0.052 + k * 0.0165
            bm_add_box(bm_vent, (-0.019, sy * 0.0046 - 0.0040, zk), (0.019, sy * 0.0046 + 0.0040, zk + 0.0070), bev=0.001, mat_idx=0, xf=vent_xf)
        bm_add_box(bm_vent, (-0.030, sy * 0.0042 - 0.0040, -0.084), (0.024, sy * 0.0042 + 0.0040, -0.070), bev=0.0015, mat_idx=1, xf=vent_xf)
        finalize_mesh(bm_cowl, f"P_F{tag}_shoulder_cowl", ["M_white_armor", "M_dark_rubber", "M_machined_alum"], f"B_F{tag}_upper", uv_mode="box")
        finalize_mesh(bm_vent, f"P_F{tag}_shoulder_vents", ["M_glow_amber", "M_lime_accent"], f"B_F{tag}_upper", uv_mode="box")

        # Upper arm + coaxial elbow stator fork (stops 38mm above elbow pin so elbow collar NEVER clips!)
        bm_ua = bmesh.new()
        bm_add_loft(bm_ua, [
            seg_ring(sh_p, u_ua, n_ua, 0.042, 0.027),
            seg_ring(sh_p.lerp(el_p, 0.52), u_ua, n_ua, 0.036, 0.024),
            seg_ring(el_p - u_ua * 0.038, u_ua, n_ua, 0.028, 0.021),
        ], True, True, mat_idx=0)
        # Coaxial inner clevis arm reaching to elbow axle cleanly inside drum width
        bm_add_cyl(bm_ua, el_p - u_ua * 0.042, el_p, 0.019, 0.019, n=14, mat_idx=0)
        a_anc = V((HYD["a_world_L"].x, sy * Y_LEG, HYD["a_world_L"].z))
        bm_add_cyl(bm_ua, el_p, a_anc, 0.015, 0.013, n=12, mat_idx=0)
        for sg in (-1, 1):
            bm_add_cyl(bm_ua, a_anc + V((0, sg * 0.014, 0)), a_anc + V((0, sg * 0.020, 0)), 0.013, n=12, mat_idx=1)
        bm_add_cyl(bm_ua, a_anc + V((0, -0.023, 0)), a_anc + V((0, 0.023, 0)), 0.006, n=12, mat_idx=1)
        finalize_mesh(bm_ua, f"P_F{tag}_upper_arm", ["M_charcoal", "M_machined_alum"], f"B_F{tag}_upper", uv_mode="box")

        # Elbow harmonic drum + bolted clamshell lime wrap collar (strictly on forearm side -> ZERO upper-arm clip!)
        bm_ed = bmesh.new()
        bm_add_rotary_drum(bm_ed, el_p, 0.054, 0.042, side_sign=sy, mat_alum=0, mat_dark=1, bolts=True)
        finalize_mesh(bm_ed, f"P_F{tag}_elbow_drum", ["M_machined_alum", "M_charcoal"], f"B_F{tag}_lower", uv_mode="box")

        bm_ec = bmesh.new()
        u_fa = (wr_p - el_p).normalized(); n_fa = V((-u_fa.z, 0.0, u_fa.x))
        # Starts cleanly at +0.049 along forearm (LITERAL 0 upper-arm clip across ALL 8 actions incl. full Trot!)
        bm_add_loft(bm_ec, [
            seg_ring(el_p + n_fa * 0.028 + u_fa * 0.049, u_fa, n_fa, 0.016, 0.029),
            seg_ring(el_p + n_fa * 0.027 + u_fa * 0.074, u_fa, n_fa, 0.017, 0.029),
            seg_ring(el_p + n_fa * 0.022 + u_fa * 0.102, u_fa, n_fa, 0.013, 0.025),
        ], True, True, mat_idx=0)
        for sg in (-1, 1):
            bm_add_bolt(bm_ec, el_p + n_fa * 0.027 + u_fa * 0.076 + V((0, sg * 0.029, 0)), (0, sg, 0), r=0.0036, h=0.0022, mat_idx=1)
        finalize_mesh(bm_ec, f"P_F{tag}_elbow_collar", ["M_lime_accent", "M_machined_alum"], f"B_F{tag}_lower", uv_mode="box")

        # CNC-milled tapered forearm with non-coplanar side pocket, lime trim & forged wrist fork
        bm_fa = bmesh.new()
        bm_add_loft(bm_fa, [
            seg_ring(el_p + n_fa * 0.008 + u_fa * 0.032, u_fa, n_fa, 0.022, 0.023),
            seg_ring(el_p + n_fa * 0.010 + u_fa * (L_F2 * 0.45), u_fa, n_fa, 0.019, 0.021),
            seg_ring(el_p + n_fa * 0.008 + u_fa * (L_F2 * 0.86), u_fa, n_fa, 0.017, 0.019),
            seg_ring(wr_p - u_fa * 0.028, u_fa, n_fa, 0.015, 0.018),
        ], True, True, mat_idx=0)
        # Side dark structural channel proudly offset +2mm outside forearm flank (ZERO z-fighting!)
        fa_mid = el_p + n_fa * 0.009 + u_fa * (L_F2 * 0.50)
        fa_xf = Matrix.Translation(fa_mid + V((0, sy * 0.022, 0))) @ Matrix.Rotation(sag_angle(wr_p - el_p), 4, 'Y')
        bm_add_box(bm_fa, (-0.007, -0.0025, -0.082), (0.007, 0.0025, 0.082), bev=0.0012, mat_idx=3, xf=fa_xf)
        bm_add_cyl(bm_fa, el_p + u_fa * 0.095 + V((0, sy * 0.022, 0)),
                          el_p + u_fa * 0.220 + V((0, sy * 0.021, 0)), 0.0046, 0.0038, n=8, mat_idx=2)
        b_anc = V((HYD["b_world_L"].x, sy * Y_LEG, HYD["b_world_L"].z))
        b_root = el_p + u_fa * (b_anc - el_p).dot(u_fa) + n_fa * 0.006
        bm_add_cyl(bm_fa, b_root, b_anc, 0.013, 0.011, n=10, mat_idx=0)
        bm_add_cyl(bm_fa, b_anc + V((0, -0.021, 0)), b_anc + V((0, 0.021, 0)), 0.006, n=12, mat_idx=1)
        for sg in (-1, 1):
            y_lo, y_hi = sorted((sg * 0.021, sg * 0.027))
            wr_mid = wr_p - u_fa * 0.022
            wr_xf = Matrix.Translation(wr_mid) @ Matrix.Rotation(sag_angle(wr_p - el_p), 4, 'Y')
            bm_add_box(bm_fa, (-0.012, y_lo, -0.018), (0.012, y_hi, 0.014), bev=0.002, mat_idx=0, xf=wr_xf)
        finalize_mesh(bm_fa, f"P_F{tag}_forearm", ["M_charcoal", "M_machined_alum", "M_lime_accent", "M_dark_rubber"], f"B_F{tag}_lower", uv_mode="box")

        # Working Two-Part Aiming Hydraulic Actuator w/ Banjo Ports, Wiper Gland & Mirror Chrome Rod!
        u_hyd = (b_anc - a_anc).normalized(); n_hyd = V((-u_hyd.z, 0.0, u_hyd.x))
        bm_hc = bmesh.new()
        p_c0, p_c1 = a_anc, a_anc + u_hyd * HYD["L_cyl"]
        bm_add_cyl(bm_hc, p_c0 + V((0, -0.012, 0)), p_c0 + V((0, 0.012, 0)), 0.013, n=18, bev=0.0015, mat_idx=1)
        bm_add_cyl(bm_hc, p_c0 + u_hyd * 0.012, p_c1 - u_hyd * 0.014, 0.013, n=24, bev=0.002, mat_idx=0)
        # Twin hydraulic fluid banjo port collars near cylinder ends
        for s_p in (0.026, HYD["L_cyl"] - 0.026):
            bp = p_c0 + u_hyd * s_p
            bm_add_cyl(bm_hc, bp - u_hyd * 0.006, bp + u_hyd * 0.006, 0.0144, n=20, mat_idx=1)
            bm_add_cyl(bm_hc, bp, bp + V((0, -sy * 0.017, 0)), 0.0048, n=6, mat_idx=3)
        # Chamfered wiper seal gland nut at cylinder mouth
        bm_add_cyl(bm_hc, p_c1 - u_hyd * 0.015, p_c1, 0.0148, 0.0122, n=24, bev=0.0015, mat_idx=1)
        bm_add_cyl(bm_hc, p_c0 + u_hyd * 0.025 - n_hyd * 0.013, p_c1 - u_hyd * 0.020 - n_hyd * 0.013, 0.0038, n=8, mat_idx=2)
        finalize_mesh(bm_hc, f"P_F{tag}_hyd_barrel", ["M_machined_alum", "M_charcoal", "M_lime_accent", "M_brass"], f"B_F{tag}_hyd_cyl", uv_mode="box")

        bm_hr = bmesh.new()
        p_r0, p_r1 = b_anc, b_anc - u_hyd * HYD["L_rod"]
        bm_add_cyl(bm_hr, p_r0 + V((0, -0.011, 0)), p_r0 + V((0, 0.011, 0)), 0.012, n=18, bev=0.0015, mat_idx=1)
        bm_add_cyl(bm_hr, p_r0 - u_hyd * 0.010, p_r1, 0.0074, n=20, mat_idx=0)
        bm_add_cyl(bm_hr, p_r1, p_r1 + u_hyd * 0.010, 0.010, n=16, mat_idx=1)
        finalize_mesh(bm_hr, f"P_F{tag}_hyd_rod", ["M_chrome", "M_charcoal"], f"B_F{tag}_hyd_rod", uv_mode="box")

        bm_wd = bmesh.new()
        bm_add_rotary_drum(bm_wd, wr_p, 0.044, 0.029, side_sign=sy, mat_alum=0, mat_dark=1, bolts=False)
        finalize_mesh(bm_wd, f"P_F{tag}_wrist_drum", ["M_machined_alum", "M_charcoal"], f"B_F{tag}_paw", uv_mode="box")
        build_paw_assembly(tag, "F", sy, wr_p, pw_p, f"B_F{tag}_paw")


def build_rear_legs():
    """Pass 3: 3D-crowned hip cowls, CNC-milled thighs & shins, bolted lime knee guards & hex-crimped flex hoses."""
    for sy, tag in ((+1, "L"), (-1, "R")):
        hip_p = V((RL_HIP.x, sy * Y_LEG, RL_HIP.z))
        kne_p = V((RL_KNEE.x, sy * Y_LEG, RL_KNEE.z))
        hck_p = V((RL_HOCK.x, sy * Y_LEG, RL_HOCK.z))
        ank_p = V((RL_ANK.x, sy * Y_LEG, RL_ANK.z))
        pw_p  = V((RL_PAW.x, sy * Y_LEG, 0.000))

        def seg_ring(p, u, n, hn, hy):
            c_n, c_y = hn * 0.72, hy * 0.72
            return [
                p + n * hn + V((0, c_y, 0)), p + n * c_n + V((0, hy, 0)),
                p - n * c_n + V((0, hy, 0)), p - n * hn + V((0, c_y, 0)),
                p - n * hn - V((0, c_y, 0)), p - n * c_n - V((0, hy, 0)),
                p + n * c_n - V((0, hy, 0)), p + n * hn - V((0, c_y, 0)),
            ]

        bm = bmesh.new()
        y0, y1 = sorted((sy * (Y_AB - 0.016), sy * (Y_LEG - 0.026)))
        bm_add_cyl(bm, (hip_p.x, y0, hip_p.z), (hip_p.x, y1, hip_p.z), 0.048, 0.044, n=22, bev=0.003, mat_idx=0)
        bm_add_cyl(bm, (hip_p.x, sy * (Y_AB + 0.006), hip_p.z), (hip_p.x, sy * (Y_AB + 0.018), hip_p.z), 0.052, n=22, bev=0.002, mat_idx=1)
        finalize_mesh(bm, f"P_R{tag}_hip_mount", ["M_charcoal", "M_machined_alum"], f"B_R{tag}_ab", uv_mode="box")

        bm = bmesh.new()
        bm_add_rotary_drum(bm, hip_p, 0.054, 0.052, side_sign=sy, mat_alum=0, mat_dark=1, bolts=True)
        finalize_mesh(bm, f"P_R{tag}_hip_drum", ["M_machined_alum", "M_charcoal"], f"B_R{tag}_thigh", uv_mode="box")

        # 3D-Crowned Faceted Matte-White Hip Cowl w/ corner bolts
        bm = bmesh.new()
        hip_base = [
            (hip_p.x + 0.072, hip_p.z + 0.030), (hip_p.x + 0.012, hip_p.z + 0.072),
            (hip_p.x - 0.062, hip_p.z + 0.052), (hip_p.x - 0.068, hip_p.z - 0.024),
            (hip_p.x - 0.012, hip_p.z - 0.064), (hip_p.x + 0.060, hip_p.z - 0.020),
        ]
        hx_c = sum(p[0] for p in hip_base) / len(hip_base)
        hz_c = sum(p[1] for p in hip_base) / len(hip_base)
        hip_cr = [(hx_c + (px - hx_c) * 0.76, hz_c + (pz - hz_c) * 0.76) for px, pz in hip_base]
        ri = [(px, sy * 0.166, pz) for px, pz in hip_base]
        rm = [(px, sy * 0.200, pz) for px, pz in hip_base]
        ro = [(px, sy * 0.214, pz) for px, pz in hip_cr]
        if sy < 0: ri, rm, ro = list(reversed(ri)), list(reversed(rm)), list(reversed(ro))
        bm_add_loft(bm, [ri, rm, ro], True, True, mat_idx=0)
        bm_add_box(bm, (hip_p.x - 0.048, min(sy * 0.156, sy * 0.205), hip_p.z + 0.038),
                       (hip_p.x + 0.044, max(sy * 0.156, sy * 0.205), hip_p.z + 0.068), bev=0.006, mat_idx=0)
        bm_add_bolt(bm, (hip_p.x + 0.024, sy * 0.214, hip_p.z + 0.022), (0, sy, 0), r=0.0032, h=0.002, mat_idx=1)
        bm_add_bolt(bm, (hip_p.x - 0.028, sy * 0.214, hip_p.z - 0.018), (0, sy, 0), r=0.0032, h=0.002, mat_idx=1)
        finalize_mesh(bm, f"P_R{tag}_hip_cowl", ["M_white_armor", "M_machined_alum"], f"B_R{tag}_thigh", uv_mode="box")

        # CNC-milled thigh w/ coaxial knee clearance (stops 38mm above knee pin -> ZERO knee collar clip!)
        bm = bmesh.new()
        u_th = (kne_p - hip_p).normalized(); n_th = V((-u_th.z, 0.0, u_th.x))
        bm_add_loft(bm, [
            seg_ring(hip_p + u_th * 0.014, u_th, n_th, 0.044, 0.027),
            seg_ring(hip_p.lerp(kne_p, 0.52), u_th, n_th, 0.037, 0.024),
            seg_ring(kne_p - u_th * 0.038, u_th, n_th, 0.028, 0.021),
        ], True, True, mat_idx=0)
        bm_add_cyl(bm, kne_p - u_th * 0.042, kne_p, 0.019, 0.019, n=14, mat_idx=0)
        th_xf = Matrix.Translation(hip_p.lerp(kne_p, 0.52) + V((0, sy * 0.025, 0))) @ Matrix.Rotation(sag_angle(kne_p - hip_p), 4, 'Y')
        bm_add_box(bm, (-0.013, -0.0025, -0.038), (0.013, 0.0025, 0.038), bev=0.0015, mat_idx=2, xf=th_xf)
        boss_p = hip_p.lerp(kne_p, 0.22) - n_th * 0.043
        bm_add_cyl(bm, boss_p + V((0, 0, 0.014)), boss_p - V((0, 0, 0.016)), 0.010, 0.009, n=12, mat_idx=1)
        finalize_mesh(bm, f"P_R{tag}_thigh", ["M_charcoal", "M_machined_alum", "M_dark_rubber"], f"B_R{tag}_thigh", uv_mode="box")

        # Harmonic knee drum + bolted lime wrap guard (wraps lower-front shin side -> ZERO thigh clip!)
        bm = bmesh.new()
        bm_add_rotary_drum(bm, kne_p, 0.054, 0.042, side_sign=sy, mat_alum=0, mat_dark=1, bolts=True)
        finalize_mesh(bm, f"P_R{tag}_knee_drum", ["M_machined_alum", "M_charcoal"], f"B_R{tag}_shin", uv_mode="box")

        bm = bmesh.new()
        bm_add_box(bm, (kne_p.x + 0.026, kne_p.y - 0.031, kne_p.z - 0.048),
                       (kne_p.x + 0.054, kne_p.y + 0.031, kne_p.z + 0.010), bev=0.006, mat_idx=0)
        bm_add_box(bm, (kne_p.x + 0.004, kne_p.y - 0.028, kne_p.z - 0.054),
                       (kne_p.x + 0.044, kne_p.y + 0.028, kne_p.z - 0.022), bev=0.005, mat_idx=0)
        for sg in (-1, 1):
            bm_add_bolt(bm, (kne_p.x + 0.053, kne_p.y + sg * 0.015, kne_p.z - 0.032), (1, 0, 0), r=0.0038, h=0.0024, mat_idx=1)
            bm_add_bolt(bm, (kne_p.x + 0.053, kne_p.y + sg * 0.015, kne_p.z - 0.006), (1, 0, 0), r=0.0035, h=0.0022, mat_idx=1)
        finalize_mesh(bm, f"P_R{tag}_knee_collar", ["M_lime_accent", "M_machined_alum"], f"B_R{tag}_shin", uv_mode="box")

        # CNC-milled shin w/ non-coplanar side pocket, coaxial hock clearance, lime strip & rear hydraulic ram
        bm = bmesh.new()
        u_sh = (hck_p - kne_p).normalized(); n_sh = V((-u_sh.z, 0.0, u_sh.x))
        bm_add_loft(bm, [
            seg_ring(kne_p + u_sh * 0.032, u_sh, n_sh, 0.030, 0.023),
            seg_ring(kne_p.lerp(hck_p, 0.48), u_sh, n_sh, 0.025, 0.021),
            seg_ring(hck_p - u_sh * 0.030, u_sh, n_sh, 0.018, 0.018),
        ], True, True, mat_idx=0)
        sh_xf = Matrix.Translation(kne_p.lerp(hck_p, 0.52) + V((0, sy * 0.022, 0))) @ Matrix.Rotation(sag_angle(hck_p - kne_p), 4, 'Y')
        bm_add_box(bm, (-0.009, -0.0025, -0.052), (0.009, 0.0025, 0.052), bev=0.0012, mat_idx=3, xf=sh_xf)
        bm_add_cyl(bm, kne_p.lerp(hck_p, 0.14) + V((0, sy * 0.022, 0)),
                       kne_p.lerp(hck_p, 0.48) + V((0, sy * 0.021, 0)), 0.0068, 0.0055, n=8, mat_idx=2)
        ram0 = kne_p.lerp(hck_p, 0.46) - n_sh * 0.025
        ram1 = kne_p.lerp(hck_p, 0.88) - n_sh * 0.020
        bm_add_cyl(bm, ram0, ram1, 0.010, 0.009, n=14, bev=0.001, mat_idx=1)
        # Coaxial machined clevis fork ears at hock (inner gap ±0.019 -> 4mm clearance around metatarsal tongue!)
        for sg in (-1, 1):
            y_lo, y_hi = sorted((sg * 0.019, sg * 0.026))
            hk_mid = hck_p - u_sh * 0.020
            hk_xf = Matrix.Translation(hk_mid) @ Matrix.Rotation(sag_angle(hck_p - kne_p), 4, 'Y')
            bm_add_box(bm, (-0.013, y_lo, -0.020), (0.013, y_hi, 0.016), bev=0.002, mat_idx=0, xf=hk_xf)
        finalize_mesh(bm, f"P_R{tag}_shin", ["M_charcoal", "M_machined_alum", "M_lime_accent", "M_dark_rubber"], f"B_R{tag}_shin", uv_mode="box")

        bm_hd = bmesh.new()
        bm_add_rotary_drum(bm_hd, hck_p, 0.044, 0.029, side_sign=sy, mat_alum=0, mat_dark=1, bolts=False)
        finalize_mesh(bm_hd, f"P_R{tag}_hock_drum", ["M_machined_alum", "M_charcoal"], f"B_R{tag}_hock", uv_mode="box")

        bm_mt = bmesh.new()
        u_mt = (ank_p - hck_p).normalized(); n_mt = V((-u_mt.z, 0.0, u_mt.x))
        # Metatarsal fits cleanly between hock fork ears (±0.015 < ±0.019 -> ZERO hock clipping!)
        bm_add_loft(bm_mt, [
            seg_ring(hck_p + u_mt * 0.032, u_mt, n_mt, 0.017, 0.015),
            seg_ring(hck_p.lerp(ank_p, 0.58), u_mt, n_mt, 0.016, 0.015),
            seg_ring(ank_p - u_mt * 0.014, u_mt, n_mt, 0.015, 0.015),
        ], True, True, mat_idx=0)
        bm_add_cyl(bm_mt, hck_p + u_mt * 0.004, hck_p + u_mt * 0.034, 0.012, 0.013, n=12, mat_idx=0)
        finalize_mesh(bm_mt, f"P_R{tag}_metatarsal", "M_charcoal", f"B_R{tag}_hock", uv_mode="box")

        build_paw_assembly(tag, "R", sy, ank_p, pw_p, f"B_R{tag}_paw")

        # Flexibly skinned braided yellow hose w/ hex crimp nuts
        bm_h = bmesh.new(); uv_lay = bm_h.loops.layers.uv.new("UVMap")
        p0 = boss_p - V((0, 0, 0.012)); p3 = ram0
        pts = eval_bezier(p0, p0 + V((-0.028, 0.0, -0.070)), p3 + V((-0.024, 0.0, 0.066)), p3, steps=22)
        bm_add_tube(bm_h, pts, 0.0066, n=14, mat_idx=0, uv_layer=uv_lay)
        bm_add_cyl(bm_h, pts[0], pts[2], 0.0094, n=12, mat_idx=1)
        bm_add_cyl(bm_h, pts[1], pts[3], 0.0108, n=6, mat_idx=1)
        bm_add_cyl(bm_h, pts[-3], pts[-1], 0.0094, n=12, mat_idx=1)
        bm_add_cyl(bm_h, pts[-4], pts[-2], 0.0108, n=6, mat_idx=1)
        finalize_mesh(bm_h, f"P_R{tag}_hose_flex", ["M_yellow_braid", "M_machined_alum"], f"B_R{tag}_thigh", uv_mode="box",
                      flex_bones=(f"B_R{tag}_thigh", f"B_R{tag}_shin", p0, p3))


# ==============================================================================
# 7. ARMATURE, SKINNING & 5 ACTIONS
# ==============================================================================
def build_armature():
    arm_data = bpy.data.armatures.new("FloraQuad_Armature")
    arm_obj = bpy.data.objects.new("FloraQuad_Rig", arm_data)
    bpy.context.scene.collection.objects.link(arm_obj)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm_data.edit_bones

    def add_bone(name, head, tail, parent=None, roll_vec=(0, 1, 0)):
        b = eb.new(name); b.head = V(head); b.tail = V(tail)
        if parent: b.parent = eb[parent]
        if roll_vec is not None: b.align_roll(V(roll_vec))
        return b

    add_bone("B_root", (0, 0, 0), (0.25, 0, 0), None, (0, 0, 1))
    add_bone("B_torso", P_TORSO, P_TORSO + V((0.25, 0, 0)), "B_root", (0, 0, 1))
    add_bone("B_neck", P_NECK, P_HEAD, "B_torso", (0, 1, 0))
    add_bone("B_head", P_HEAD, P_HEAD + V((0.15, 0, 0)), "B_neck", (0, 1, 0))
    add_bone("B_canopy_yaw", P_CANOPY_YAW, P_CANOPY_PITCH, "B_torso", (0, 1, 0))
    add_bone("B_canopy_pitch", P_CANOPY_PITCH, P_CANOPY_PITCH + V((0.0, 0.0, 0.18)), "B_canopy_yaw", (0, 1, 0))

    for sy, tag in ((+1, "L"), (-1, "R")):
        p = V((P_ANT_L.x, sy * P_ANT_L.y, P_ANT_L.z))
        add_bone(f"B_ant_{tag}", p, p + V((-0.145, 0.0, 0.185)), "B_torso", (0, 1, 0))

    for sy, tag in ((+1, "L"), (-1, "R")):
        ab = V((FL_AB.x, sy * Y_AB, FL_AB.z)); sh = V((FL_SH.x, sy * Y_LEG, FL_SH.z))
        el = V((FL_EL.x, sy * Y_LEG, FL_EL.z)); wr = V((FL_WR.x, sy * Y_LEG, FL_WR.z))
        pw = V((FL_PAW.x, sy * Y_LEG, 0.000))
        a_anc = V((HYD["a_world_L"].x, sy * Y_LEG, HYD["a_world_L"].z))
        b_anc = V((HYD["b_world_L"].x, sy * Y_LEG, HYD["b_world_L"].z))
        add_bone(f"B_F{tag}_ab", ab, sh, "B_torso", (0, 0, 1))
        add_bone(f"B_F{tag}_upper", sh, el, f"B_F{tag}_ab", (0, 1, 0))
        add_bone(f"B_F{tag}_lower", el, wr, f"B_F{tag}_upper", (0, 1, 0))
        add_bone(f"B_F{tag}_paw", wr, pw + V((0.06, 0, 0)), f"B_F{tag}_lower", (0, 1, 0))
        add_bone(f"B_F{tag}_hyd_cyl", a_anc, b_anc, f"B_F{tag}_upper", (0, 1, 0))
        add_bone(f"B_F{tag}_hyd_rod", b_anc, a_anc, f"B_F{tag}_lower", (0, 1, 0))

    for sy, tag in ((+1, "L"), (-1, "R")):
        ab = V((RL_AB.x, sy * Y_AB, RL_AB.z)); hp = V((RL_HIP.x, sy * Y_LEG, RL_HIP.z))
        kn = V((RL_KNEE.x, sy * Y_LEG, RL_KNEE.z)); hk = V((RL_HOCK.x, sy * Y_LEG, RL_HOCK.z))
        an = V((RL_ANK.x, sy * Y_LEG, RL_ANK.z)); pw = V((RL_PAW.x, sy * Y_LEG, 0.000))
        add_bone(f"B_R{tag}_ab", ab, hp, "B_torso", (0, 0, 1))
        add_bone(f"B_R{tag}_thigh", hp, kn, f"B_R{tag}_ab", (0, 1, 0))
        add_bone(f"B_R{tag}_shin", kn, hk, f"B_R{tag}_thigh", (0, 1, 0))
        add_bone(f"B_R{tag}_hock", hk, an, f"B_R{tag}_shin", (0, 1, 0))
        add_bone(f"B_R{tag}_paw", an, pw + V((0.06, 0, 0)), f"B_R{tag}_hock", (0, 1, 0))

    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in arm_obj.pose.bones: pb.rotation_mode = "XYZ"

    assert not (set(arm_data.bones.keys()) & {e["obj"].name for e in PART_REGISTRY})
    print(f"ARMATURE OK: {len(arm_data.bones)} bones, {len(PART_REGISTRY)} mesh parts, 0 name collisions")
    return arm_obj


def skin_parts_to_armature(arm_obj):
    for entry in PART_REGISTRY:
        obj, bone_name, flex = entry["obj"], entry["bone"], entry["flex_bones"]
        obj.parent = arm_obj
        mod = obj.modifiers.new("Armature", "ARMATURE"); mod.object = arm_obj
        if flex is None:
            vg = obj.vertex_groups.new(name=bone_name)
            vg.add(list(range(len(obj.data.vertices))), 1.0, "REPLACE")
        else:
            b0, b1, p0, p3 = flex
            vg0 = obj.vertex_groups.new(name=b0); vg1 = obj.vertex_groups.new(name=b1)
            axis = p3 - p0; L2 = max(1e-6, axis.length_squared)
            for v in obj.data.vertices:
                t = max(0.0, min(1.0, (v.co - p0).dot(axis) / L2))
                w1 = t * t * (3.0 - 2.0 * t); w0 = 1.0 - w1
                if w0 > 1e-4: vg0.add([v.index], w0, "REPLACE")
                if w1 > 1e-4: vg1.add([v.index], w1, "REPLACE")


def compute_hyd_aim_deltas(d_el):
    a_rel, b_rel0 = HYD["a_rel"], HYD["b_rel"]
    b_rel = Matrix.Rotation(d_el, 3, 'Y') @ b_rel0
    v_rest, v_now = b_rel0 - a_rel, b_rel - a_rel
    phi = math.atan2(v_rest.z * v_now.x - v_rest.x * v_now.z, v_rest.x * v_now.x + v_rest.z * v_now.z)
    return phi, phi - d_el, v_now.length


def build_actions(arm_obj):
    bpy.context.scene.render.fps = 24
    arm_obj.animation_data_create()
    worst_eng, worst_exp = 1e9, 1e9
    M_torso_inv = arm_obj.data.bones["B_torso"].matrix_local.to_3x3().inverted()

    for act_name in ACTION_NAMES:
        act = bpy.data.actions.new(name=act_name)
        arm_obj.animation_data.action = act
        frames = ALL_ACTIONS[act_name]

        def set_rot(bname, euler_xyz, fr):
            pb = arm_obj.pose.bones[bname]; pb.rotation_euler = euler_xyz; pb.keyframe_insert("rotation_euler", frame=fr)

        def set_loc(bname, loc_xyz, fr):
            pb = arm_obj.pose.bones[bname]; pb.location = loc_xyz; pb.keyframe_insert("location", frame=fr)

        for fd in frames:
            fr = fd["frame"]
            set_loc("B_torso", M_torso_inv @ fd["torso_loc"], fr)
            R_w = Euler(fd["torso_rot"], "XYZ").to_matrix()
            set_rot("B_torso", (M_torso_inv @ R_w @ M_torso_inv.inverted()).to_euler("XYZ"), fr)

            for bname, w_rot in (("B_neck", fd["neck"]), ("B_head", fd["head"])):
                Mb = arm_obj.data.bones[bname].matrix_local.to_3x3()
                set_rot(bname, (Mb.inverted() @ Euler(w_rot, "XYZ").to_matrix() @ Mb).to_euler("XYZ"), fr)

            set_rot("B_canopy_yaw", (0.0, fd["canopy_yaw"], 0.0), fr)
            set_rot("B_canopy_pitch", (0.0, 0.0, fd["canopy_pitch"]), fr)
            set_rot("B_ant_L", (0.0, 0.0, fd["ant_L"]), fr)
            set_rot("B_ant_R", (0.0, 0.0, fd["ant_R"]), fr)

            for idx, bname in enumerate(("B_FL_ab", "B_FR_ab", "B_RL_ab", "B_RR_ab")):
                Mb = arm_obj.data.bones[bname].matrix_local.to_3x3()
                set_rot(bname, (Mb.inverted() @ Matrix.Rotation(fd["ab"][idx], 3, 'X') @ Mb).to_euler("XYZ"), fr)

            for tag, key in (("L", "FL"), ("R", "FR")):
                d_sh, d_el, d_wr = fd[key]
                set_rot(f"B_F{tag}_upper", (0.0, 0.0, d_sh), fr)
                set_rot(f"B_F{tag}_lower", (0.0, 0.0, d_el), fr)
                set_rot(f"B_F{tag}_paw", (0.0, 0.0, d_wr), fr)
                d_cyl, d_rod, dist_now = compute_hyd_aim_deltas(d_el)
                set_rot(f"B_F{tag}_hyd_cyl", (0.0, 0.0, d_cyl), fr)
                set_rot(f"B_F{tag}_hyd_rod", (0.0, 0.0, d_rod), fr)
                worst_eng = min(worst_eng, HYD["L_cyl"] + HYD["L_rod"] - dist_now)
                worst_exp = min(worst_exp, dist_now - HYD["L_cyl"])

            for tag, key in (("L", "RL"), ("R", "RR")):
                d_hp, d_kn, d_hk, d_pw = fd[key]
                set_rot(f"B_R{tag}_thigh", (0.0, 0.0, d_hp), fr)
                set_rot(f"B_R{tag}_shin", (0.0, 0.0, d_kn), fr)
                set_rot(f"B_R{tag}_hock", (0.0, 0.0, d_hk), fr)
                set_rot(f"B_R{tag}_paw", (0.0, 0.0, d_pw), fr)

        tr = arm_obj.animation_data.nla_tracks.new(); tr.name = act_name
        strip = tr.strips.new(act_name, 1, act)
        strip.action_frame_start = 1; strip.action_frame_end = len(frames)
        tr.mute = True

    assert worst_eng >= 0.035 and worst_exp >= 0.045
    arm_obj.animation_data.action = None
    for pb in arm_obj.pose.bones:
        pb.location = (0, 0, 0); pb.rotation_euler = (0, 0, 0); pb.scale = (1, 1, 1)
    print(f"ACTIONS OK ({len(ACTION_NAMES)}): {ACTION_NAMES} | hydraulic engage>={worst_eng*1000:.1f}mm exposed>={worst_exp*1000:.1f}mm")


# ==============================================================================
# 8. EXPANDED CYCLES CONTACT AMBIENT OCCLUSION BAKE (23 HERO PARTS!)
# ==============================================================================
def bake_cycles_ao_atlas():
    scn = bpy.context.scene
    scn.render.engine = "CYCLES"
    scn.cycles.device = "CPU"
    scn.cycles.samples = BAKE_SPP
    scn.cycles.use_denoising = False

    hero_targets = [
        "P_carapace_main", "P_chassis_spine", "P_rear_pods",
        "P_planter_collar", "P_pedestal_yfork", "P_canopy_shell",
        "P_head_shell", "P_neck_shell",
        "P_FL_shoulder_cowl", "P_FR_shoulder_cowl",
        "P_FL_forearm", "P_FR_forearm", "P_FL_elbow_collar", "P_FR_elbow_collar",
        "P_RL_hip_cowl", "P_RR_hip_cowl",
        "P_RL_thigh", "P_RR_thigh", "P_RL_shin", "P_RR_shin",
        "P_RL_knee_collar", "P_RR_knee_collar", "P_chest_grille",
    ]
    baked = []
    for obj_name in hero_targets:
        obj = bpy.data.objects.get(obj_name)
        if obj is None or obj.type != "MESH":
            continue
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True); bpy.context.view_layer.objects.active = obj
        uv_b = obj.data.uv_layers.new(name="BakeUV")
        obj.data.uv_layers.active = uv_b
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.02, correct_aspect=True)
        bpy.ops.object.mode_set(mode="OBJECT")

        # Main hero shells get full BAKE_SIZE/2 (512-1024px), smaller parts get 512px
        sz = BAKE_SIZE if obj_name in ("P_carapace_main", "P_canopy_shell", "P_pedestal_yfork") else max(256, BAKE_SIZE // 2)
        im_ao = bpy.data.images.new(f"ao_{obj_name}", sz, sz, alpha=False)
        im_ao.colorspace_settings.name = "Non-Color"
        temp_nodes = []
        for mat in obj.data.materials:
            if not mat: continue
            n = mat.node_tree.nodes.new("ShaderNodeTexImage"); n.image = im_ao
            mat.node_tree.nodes.active = n; temp_nodes.append((mat.node_tree, n))

        bpy.ops.object.bake(type="AO", margin=8, use_clear=True)
        ao_path = os.path.join(TEX_DIR, f"ao_{obj_name}.png")
        im_ao.filepath_raw = ao_path; im_ao.file_format = "PNG"; im_ao.save()
        for nt, n in temp_nodes: nt.nodes.remove(n)
        bpy.data.images.remove(im_ao)

        im_loaded = bpy.data.images.load(ao_path)
        im_loaded.colorspace_settings.name = "Non-Color"
        baked.append(ao_path)

        # Replace materials in-place (preserving exact per-polygon material_index!)
        for idx_m, mat in enumerate(list(obj.data.materials)):
            if mat and mat.name in ("M_white_armor", "M_charcoal", "M_lime_accent"):
                mc = mat.copy(); mc.name = f"{mat.name}_{obj_name}"
                nt = mc.node_tree
                bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
                uvn = nt.nodes.new("ShaderNodeUVMap"); uvn.uv_map = "BakeUV"
                taon = nt.nodes.new("ShaderNodeTexImage"); taon.image = im_loaded
                nt.links.new(uvn.outputs["UV"], taon.inputs["Vector"])
                for n in nt.nodes:
                    if n.type == "GROUP" and n.node_tree and n.node_tree.name == "glTF Material Output":
                        for l in list(n.inputs[0].links): nt.links.remove(l)
                        nt.links.new(taon.outputs["Color"], n.inputs[0])
                if bsdf.inputs["Base Color"].is_linked:
                    orig_sock = bsdf.inputs["Base Color"].links[0].from_socket
                    nt.links.remove(bsdf.inputs["Base Color"].links[0])
                    mr = nt.nodes.new("ShaderNodeMapRange")
                    mr.inputs["From Min"].default_value = 0.0; mr.inputs["From Max"].default_value = 1.0
                    mr.inputs["To Min"].default_value = 0.68; mr.inputs["To Max"].default_value = 1.00
                    nt.links.new(taon.outputs["Color"], mr.inputs["Value"])
                    mx = nt.nodes.new("ShaderNodeMix"); mx.data_type = "RGBA"; mx.blend_type = "MULTIPLY"
                    mx.inputs["Factor"].default_value = 1.0
                    nt.links.new(orig_sock, mx.inputs[6]); nt.links.new(mr.outputs["Result"], mx.inputs[7])
                    nt.links.new(mx.outputs[2], bsdf.inputs["Base Color"])
                obj.data.materials[idx_m] = mc
        obj.data.uv_layers.active = obj.data.uv_layers["UVMap"]
        print(f"  baked Cycles AO ({sz}px): {obj_name}", flush=True)

    assert len(baked) > 0
    print(f"CYCLES AO BAKE COMPLETE: {len(baked)} maps @ {BAKE_SPP} spp")


# ==============================================================================
# 9. STATS, VERIFICATION ASSERTIONS & EXPORT
# ==============================================================================
def compute_stats_and_assert(arm_obj):
    total_tris = total_quads = total_ngons = total_verts = 0
    lo = V((1e9, 1e9, 1e9)); hi = V((-1e9, -1e9, -1e9))
    part_info = []
    for e in PART_REGISTRY:
        o = e["obj"]; me = o.data; me.calc_loop_triangles()
        nt = len(me.loop_triangles); nq = sum(1 for p in me.polygons if len(p.vertices) == 4)
        ng = sum(1 for p in me.polygons if len(p.vertices) > 4)
        total_tris += nt; total_quads += nq; total_ngons += ng; total_verts += len(me.vertices)
        for v in me.vertices:
            w = o.matrix_world @ v.co
            lo = V((min(lo.x, w.x), min(lo.y, w.y), min(lo.z, w.z)))
            hi = V((max(hi.x, w.x), max(hi.y, w.y), max(hi.z, w.z)))
        part_info.append(dict(name=o.name, bone=e["bone"], tris=nt, verts=len(me.vertices)))

    dims = hi - lo
    assert total_ngons == 0, f"Found {total_ngons} n-gons!"
    assert abs(lo.z) < 0.001, f"Paws not grounded on Z=0! min_z={lo.z:.5f}"

    ref_dims = V((1.250, 0.440, 1.010))
    err_mm = max(abs(dims.x - ref_dims.x), abs(dims.y - ref_dims.y), abs(dims.z - ref_dims.z)) * 1000.0
    info = dict(
        name="flora_quad", pass_version="Pass 3 Hero Polish",
        parts=len(PART_REGISTRY), bones=len(arm_obj.data.bones), actions=ACTION_NAMES,
        tris=total_tris, quads=total_quads, ngons=total_ngons, verts=total_verts,
        bbox_min=[round(lo.x, 4), round(lo.y, 4), round(lo.z, 4)],
        bbox_max=[round(hi.x, 4), round(hi.y, 4), round(hi.z, 4)],
        dims_m=[round(dims.x, 4), round(dims.y, 4), round(dims.z, 4)],
        target_dims_m=[1.250, 0.440, 1.010], dim_err_mm=round(err_mm, 2),
        baked_cycles_ao=not NOBAKE, bake_size=BAKE_SIZE, bake_spp=BAKE_SPP,
        hydraulic=dict(
            d_rest_mm=round(HYD["d_rest"] * 1000, 2), d_min_mm=round(HYD["d_min"] * 1000, 2),
            d_max_mm=round(HYD["d_max"] * 1000, 2), stroke_mm=round(HYD["stroke"] * 1000, 2),
            L_cyl_mm=round(HYD["L_cyl"] * 1000, 2), L_rod_mm=round(HYD["L_rod"] * 1000, 2),
            min_engage_mm=round(HYD["eng_min"] * 1000, 2), min_exposed_mm=round(HYD["exp_min"] * 1000, 2),
            min_lever_mm=round(HYD["min_lever"] * 1000, 2),
        ),
        part_table=part_info,
    )
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "flora_quad_info.json"), "w") as fh:
        json.dump(info, fh, indent=2)
    print(f"STATS: tris={total_tris}, verts={total_verts}, ngons={total_ngons}, "
          f"dims={[round(v,4) for v in dims]} m (err={err_mm:.2f} mm), min_z={lo.z:.4f} m")
    assert err_mm < 5.0, f"Bounding box error {err_mm:.2f} mm >= 5.0 mm!"
    return info


def export_all(arm_obj):
    os.makedirs(OUT_DIR, exist_ok=True)
    glb_path = os.path.join(OUT_DIR, "flora_quad.glb")
    blend_path = os.path.join(OUT_DIR, "flora_quad.blend")

    bpy.ops.object.select_all(action="DESELECT")
    arm_obj.select_set(True)
    for e in PART_REGISTRY: e["obj"].select_set(True)
    bpy.context.view_layer.objects.active = arm_obj

    bpy.ops.export_scene.gltf(
        filepath=glb_path, export_format="GLB", use_selection=True,
        export_apply=False, export_yup=True, export_skins=True,
        export_animations=True, export_nla_strips=True, export_def_bones=False,
        export_tangents=True, export_materials="EXPORT",
    )
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    print(f"EXPORTED: {glb_path} ({os.path.getsize(glb_path)/1024:.1f} KB)")
    print(f"SAVED:    {blend_path} ({os.path.getsize(blend_path)/1024:.1f} KB)")


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    os.makedirs(TEX_DIR, exist_ok=True)

    build_materials()
    build_torso_and_carapace()
    build_planter_and_foliage()
    build_pedestal_and_canopy()
    build_neck_and_head()
    build_rear_antennae()
    build_front_legs()
    build_rear_legs()

    arm_obj = build_armature()
    skin_parts_to_armature(arm_obj)
    build_actions(arm_obj)

    if not NOBAKE:
        bake_cycles_ao_atlas()

    compute_stats_and_assert(arm_obj)
    export_all(arm_obj)


if __name__ == "__main__":
    main()
