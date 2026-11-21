# render_film.py — Studio Cinematic Launch Film Renderer for FLORA-01 (Blender 5.2 EEVEE Raytraced)
#
# Modes:
#   --preview            Render 12 key storyboard frames (2 per shot) + 4x3 contact sheet for fast visual QA
#   --range START END    Render exact film frames [START..END] at 1920x1080 JPEG Q96 (supports parallel workers!)
#
# Usage:
#   blender -b --factory-startup -t 4 --python render_film.py -- --preview
#   blender -b --factory-startup -t 4 --python render_film.py -- --range 1 672

import bpy
import bmesh
import os
import sys
import json
import math
import time
import random
import numpy as np
from mathutils import Vector, Matrix

V = Vector
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BLEND_PATH = os.path.join(ROOT, "out", "flora_quad.blend")
FRAMES_DIR = os.path.join(HERE, "frames")
PREV_DIR = os.path.join(HERE, "preview")
os.makedirs(FRAMES_DIR, exist_ok=True)
os.makedirs(PREV_DIR, exist_ok=True)

TL = json.load(open(os.path.join(HERE, "timeline.json"), "r"))
FPS = TL["fps"]
TOTAL_FRAMES = TL["total_frames"]

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
PREVIEW = "--preview" in argv
if "--range" in argv:
    ri = argv.index("--range")
    F_START, F_END = int(argv[ri + 1]), int(argv[ri + 2])
else:
    F_START, F_END = 1, TOTAL_FRAMES


def sstep(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


def smoother(x):
    x = max(0.0, min(1.0, x))
    return x * x * x * (10.0 + x * (-15.0 + 6.0 * x))


def lerp(a, b, t):
    return a + (b - a) * t


def vlerp(a, b, t):
    return V(a).lerp(V(b), t)


# ==============================================================================
# 1. CINEMA STUDIO ENVIRONMENT (CURVED CYCLORAMA, PRECISION SCROLLING FLOOR,
#    SUNLIT POLLEN MOTES, WINDOW GOBO SHAFTS & BLENDER 5.2 COMPOSITOR BLOOM)
# ==============================================================================
def build_cinema_stage(scn):
    # EEVEE Raytraced + CPU Compositor Bloom (rock-solid across long Windows renders!) + AgX Punchy
    scn.render.engine = "BLENDER_EEVEE"
    scn.eevee.taa_render_samples = 12
    scn.eevee.use_raytracing = True
    try:
        scn.render.compositor_device = "CPU"
        scn.eevee.use_shadows = True
        scn.eevee.shadow_resolution_scale = 1.0
    except Exception:
        pass
    scn.view_settings.view_transform = "AgX"
    try:
        scn.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass
    scn.view_settings.exposure = 0.0

    # --- Blender 5.2 Compositor: Subtle Optical Bloom on Emissive Optics & Grow-Lights ---
    ng = bpy.data.node_groups.new("FloraFilmComp", "CompositorNodeTree")
    ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    rl = ng.nodes.new("CompositorNodeRLayers")
    gl = ng.nodes.new("CompositorNodeGlare")
    gl.inputs["Type"].default_value = "Bloom"
    gl.inputs["Threshold"].default_value = 1.05
    gl.inputs["Strength"].default_value = 0.34
    gl.inputs["Size"].default_value = 0.70
    out = ng.nodes.new("NodeGroupOutput")
    ng.links.new(rl.outputs["Image"], gl.inputs["Image"])
    ng.links.new(gl.outputs["Image"], out.inputs["Image"])
    scn.compositing_node_group = ng
    scn.render.use_compositing = True

    # --- World Shader (animated dynamically between Obsidian Dark & Golden Gallery) ---
    w = bpy.data.worlds.new("CinemaWorld")
    scn.world = w
    nt = w.node_tree
    nt.nodes.clear()
    w_out = nt.nodes.new("ShaderNodeOutputWorld")
    w_bg = nt.nodes.new("ShaderNodeBackground")
    w_bg.name = "WorldBG"
    w_bg.inputs["Color"].default_value = (0.015, 0.018, 0.022, 1.0)
    w_bg.inputs["Strength"].default_value = 0.15
    nt.links.new(w_bg.outputs[0], w_out.inputs["Surface"])

    # --- Seamless Curved Studio Cyclorama Dome (20 m wide, zero horizon seam!) ---
    bm = bmesh.new()
    # Flat floor disk (r = 12 m) smoothly curving up into an infinite architectural bowl!
    n_seg = 48
    prof = [
        (0.0, 0.0), (2.5, 0.0), (5.5, 0.0), (8.0, 0.0),
        (9.5, 0.25), (10.8, 0.95), (11.8, 2.2), (12.4, 4.2), (12.6, 7.5), (12.6, 12.0),
    ]
    rings = []
    for r, z in prof:
        if r < 1e-4:
            rings.append([bm.verts.new(V((0, 0, -0.0006)))])
        else:
            rings.append([bm.verts.new(V((r * math.cos(2 * math.pi * i / n_seg),
                                          r * math.sin(2 * math.pi * i / n_seg),
                                          z - 0.0006))) for i in range(n_seg)])
    for ra, rb in zip(rings, rings[1:]):
        for i in range(n_seg):
            j = (i + 1) % n_seg
            if len(ra) == 1:
                bm.faces.new((ra[0], rb[i], rb[j]))
            else:
                bm.faces.new((ra[i], rb[i], rb[j], ra[j]))
    me = bpy.data.meshes.new("Cyclorama")
    bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    cyc = bpy.data.objects.new("Cyclorama", me)
    scn.collection.objects.link(cyc)

    # Procedural Precision Architectural Micro-Grid Slate Floor Material!
    # Uses Object coordinates + Mapping X offset so floor tiles scroll seamlessly with ZERO foot slip!
    fm = bpy.data.materials.new("CinemaFloorMat")
    fnt = fm.node_tree; fnt.nodes.clear()
    f_out = fnt.nodes.new("ShaderNodeOutputMaterial")
    f_bsdf = fnt.nodes.new("ShaderNodeBsdfPrincipled")
    f_bsdf.name = "FloorBSDF"
    fnt.links.new(f_bsdf.outputs["BSDF"], f_out.inputs["Surface"])

    tc = fnt.nodes.new("ShaderNodeTexCoord")
    mp = fnt.nodes.new("ShaderNodeMapping")
    mp.name = "FloorScroll"
    fnt.links.new(tc.outputs["Object"], mp.inputs["Vector"])

    # Compute crisp 0.25 m architectural floor grid lines faded gracefully beyond r = 5.5 m
    sep = fnt.nodes.new("ShaderNodeSeparateXYZ")
    fnt.links.new(mp.outputs["Vector"], sep.inputs["Vector"])
    # Distance fade on original un-scrolled Object coords so grid fades cleanly into curved backdrop
    vlen = fnt.nodes.new("ShaderNodeVectorMath"); vlen.operation = "LENGTH"
    fnt.links.new(tc.outputs["Object"], vlen.inputs[0])
    fade = fnt.nodes.new("ShaderNodeMapRange")
    fade.clamp = True; fade.interpolation_type = "SMOOTHSTEP"
    fade.inputs["From Min"].default_value = 3.2; fade.inputs["From Max"].default_value = 7.0
    fade.inputs["To Min"].default_value = 1.0; fade.inputs["To Max"].default_value = 0.0
    fnt.links.new(vlen.outputs["Value"], fade.inputs["Value"])

    def axis_line(sock, spacing=0.25, thick=0.006):
        # pingpong/wrap mod spacing -> thin crisp line at 0
        m_mod = fnt.nodes.new("ShaderNodeMath"); m_mod.operation = "WRAP"
        fnt.links.new(sock, m_mod.inputs[0])
        m_mod.inputs[1].default_value = -spacing * 0.5
        m_mod.inputs[2].default_value = spacing * 0.5
        m_abs = fnt.nodes.new("ShaderNodeMath"); m_abs.operation = "ABSOLUTE"
        fnt.links.new(m_mod.outputs[0], m_abs.inputs[0])
        m_lt = fnt.nodes.new("ShaderNodeMapRange"); m_lt.clamp = True
        m_lt.inputs["From Min"].default_value = thick * 0.5; m_lt.inputs["From Max"].default_value = thick
        m_lt.inputs["To Min"].default_value = 1.0; m_lt.inputs["To Max"].default_value = 0.0
        fnt.links.new(m_abs.outputs[0], m_lt.inputs["Value"])
        return m_lt.outputs["Result"]

    gx = axis_line(sep.outputs["X"], 0.25, 0.0075)
    gy = axis_line(sep.outputs["Y"], 0.25, 0.0075)
    g_maj = axis_line(sep.outputs["X"], 1.00, 0.015)
    g_or = fnt.nodes.new("ShaderNodeMath"); g_or.operation = "MAXIMUM"
    fnt.links.new(gx, g_or.inputs[0]); fnt.links.new(gy, g_or.inputs[1])
    g_or2 = fnt.nodes.new("ShaderNodeMath"); g_or2.operation = "MAXIMUM"
    fnt.links.new(g_or.outputs[0], g_or2.inputs[0]); fnt.links.new(g_maj, g_or2.inputs[1])

    # Mask grid to flat floor only (Z < 0.05) and within distance radius
    sep0 = fnt.nodes.new("ShaderNodeSeparateXYZ")
    fnt.links.new(tc.outputs["Object"], sep0.inputs["Vector"])
    z_ok = fnt.nodes.new("ShaderNodeMath"); z_ok.operation = "LESS_THAN"
    fnt.links.new(sep0.outputs["Z"], z_ok.inputs[0]); z_ok.inputs[1].default_value = 0.05
    g_vis = fnt.nodes.new("ShaderNodeMath"); g_vis.operation = "MULTIPLY"
    fnt.links.new(g_or2.outputs[0], g_vis.inputs[0]); fnt.links.new(fade.outputs["Result"], g_vis.inputs[1])
    g_vis2 = fnt.nodes.new("ShaderNodeMath"); g_vis2.operation = "MULTIPLY"
    fnt.links.new(g_vis.outputs[0], g_vis2.inputs[0]); fnt.links.new(z_ok.outputs[0], g_vis2.inputs[1])

    # Subtle micro-concrete surface noise so floor reflects light organically!
    noi = fnt.nodes.new("ShaderNodeTexNoise")
    noi.inputs["Scale"].default_value = 4.5; noi.inputs["Detail"].default_value = 5.0
    fnt.links.new(mp.outputs["Vector"], noi.inputs["Vector"])
    r_map = fnt.nodes.new("ShaderNodeMapRange"); r_map.name = "FloorRoughMap"
    r_map.inputs["From Min"].default_value = 0.25; r_map.inputs["From Max"].default_value = 0.75
    r_map.inputs["To Min"].default_value = 0.28; r_map.inputs["To Max"].default_value = 0.42
    fnt.links.new(noi.outputs["Fac"], r_map.inputs["Value"])
    fnt.links.new(r_map.outputs["Result"], f_bsdf.inputs["Roughness"])

    # Mix Base Floor Color & Crisp Hairline Grid Color
    c_mix = fnt.nodes.new("ShaderNodeMix"); c_mix.name = "FloorColorMix"
    c_mix.data_type = "RGBA"
    c_mix.inputs[6].default_value = (0.04, 0.044, 0.050, 1.0)  # base floor (animated!)
    c_mix.inputs[7].default_value = (0.14, 0.18, 0.16, 1.0)    # grid line (animated!)
    g_str = fnt.nodes.new("ShaderNodeMath"); g_str.name = "GridStrength"; g_str.operation = "MULTIPLY"
    fnt.links.new(g_vis2.outputs[0], g_str.inputs[0]); g_str.inputs[1].default_value = 0.45
    fnt.links.new(g_str.outputs[0], c_mix.inputs["Factor"])
    fnt.links.new(c_mix.outputs[2], f_bsdf.inputs["Base Color"])
    cyc.data.materials.append(fm)

    # --- Studio & Golden-Hour Architectural Lighting Rig ---
    lights = {}
    def add_area(name, loc, tgt, energy, size, col=(1, 1, 1), size_y=None):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy = energy; ld.color = col
        if size_y is not None:
            ld.shape = "RECTANGLE"; ld.size = size; ld.size_y = size_y
        else:
            ld.size = size
        lo = bpy.data.objects.new(name, ld)
        scn.collection.objects.link(lo)
        lo.location = V(loc)
        lo.rotation_euler = (V(tgt) - V(loc)).to_track_quat("-Z", "Y").to_euler()
        lights[name] = (lo, ld)

    # Key golden-hour architectural sun softbox (upper front-right)
    add_area("KeySun", (2.8, -2.4, 2.9), (0.0, 0.0, 0.50), 260.0, 1.6, (1.0, 0.94, 0.84), size_y=2.6)
    # Soft sky gallery fill (upper left)
    add_area("SkyFill", (-2.2, 2.8, 2.5), (0.0, 0.0, 0.48), 115.0, 3.2, (0.86, 0.93, 1.0))
    # Sculpting dramatic obsidian/golden rim light (rear-top-left)
    add_area("RimSweep", (-2.1, 1.5, 1.85), (0.05, 0.0, 0.55), 140.0, 1.2, (1.0, 0.96, 0.86), size_y=2.2)
    # Crisp low metallic kicker (makes chrome hydraulic rod & 4-bolt drums gleam!)
    add_area("ChromeKick", (1.2, 1.8, 0.35), (0.15, 0.16, 0.25), 55.0, 0.9, (0.94, 0.98, 1.0))
    # Real warm-lime canopy grow-light bouncing down onto ferns & moss!
    add_area("GrowLight", (-0.02, 0.0, 0.92), (-0.02, 0.0, 0.68), 6.5, 0.26, (0.82, 1.0, 0.24))

    # --- Subtle Sunlit Floating Pollen / Dust Motes (adds magical sunlit depth!) ---
    mote_mat = bpy.data.materials.new("SunMoteMat")
    mnt = mote_mat.node_tree; mnt.nodes.clear()
    m_out = mnt.nodes.new("ShaderNodeOutputMaterial")
    m_bsdf = mnt.nodes.new("ShaderNodeBsdfPrincipled")
    m_bsdf.name = "MoteBSDF"
    m_bsdf.inputs["Base Color"].default_value = (1.0, 0.96, 0.78, 1.0)
    m_bsdf.inputs["Emission Color"].default_value = (1.0, 0.95, 0.65, 1.0)
    m_bsdf.inputs["Emission Strength"].default_value = 2.8
    mnt.links.new(m_bsdf.outputs["BSDF"], m_out.inputs["Surface"])

    rng = random.Random(77)
    motes = []
    bm_m = bmesh.new()
    bmesh.ops.create_icosphere(bm_m, subdivisions=1, radius=0.0015)
    me_m = bpy.data.meshes.new("MoteMesh")
    bm_m.to_mesh(me_m); bm_m.free()
    me_m.materials.append(mote_mat)
    for k in range(28):
        mo = bpy.data.objects.new(f"Mote_{k:02d}", me_m)
        scn.collection.objects.link(mo)
        ang_m = rng.uniform(0, 2 * math.pi)
        rad_m = rng.uniform(0.95, 2.20)
        base_pos = V((rad_m * math.cos(ang_m), rad_m * math.sin(ang_m), rng.uniform(0.28, 1.45)))
        mo.location = base_pos
        sc = rng.uniform(0.6, 1.2)
        mo.scale = (sc, sc, sc)
        motes.append((mo, base_pos, rng.uniform(0, 6.28), rng.uniform(0.014, 0.035)))

    # --- Cinema Camera ---
    cd = bpy.data.cameras.new("CinemaCam")
    cd.clip_start, cd.clip_end = 0.02, 50.0
    cd.sensor_width = 36.0
    cam = bpy.data.objects.new("CinemaCam", cd)
    scn.collection.objects.link(cam)
    scn.camera = cam

    # Cache base emissive strengths of robot's glowing materials so S1 can power them up smoothly!
    emissive_mats = []
    for m in bpy.data.materials:
        if m.name.startswith("M_glow_") and m.use_nodes:
            bsdf = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
            if bsdf:
                emissive_mats.append((bsdf, float(bsdf.inputs["Emission Strength"].default_value)))

    return dict(
        cam=cam, cd=cd, lights=lights, world_bg=w_bg,
        floor_scroll=mp, floor_mix=c_mix, floor_rough=r_map, grid_str=g_str,
        motes=motes, mote_bsdf=m_bsdf, emissive_mats=emissive_mats,
    )


# ==============================================================================
# 2. PER-FRAME DIRECTOR (CAMERA, LIGHTING ARC, ROBOT ACTION, ZERO-SLIP FLOOR)
# ==============================================================================
# Precompute cumulative floor scroll offset per film frame so Walk & Trot have 0.00 mm foot slip!
FLOOR_X = np.zeros(TOTAL_FRAMES + 2, dtype=np.float64)
V_WALK_PER_FR = 0.26 / (0.75 * 48.0)    # 0.0072222 m/frame (exact Walk_Cycle stance velocity!)
V_TROT_PER_FR = 0.34 / (0.56 * 28.0)    # 0.0216837 m/frame (exact Trot_Cycle stance velocity!)
for ff in range(1, TOTAL_FRAMES + 1):
    dx = 0.0
    if 721 <= ff <= 852:
        dx = V_WALK_PER_FR * 0.75   # S4b rear leg macro @ 0.75x walk speed
    elif 853 <= ff <= 948:
        dx = V_WALK_PER_FR          # S5a Walk @ 1.0x -> exact zero slip!
    elif 949 <= ff <= 1032:
        dx = V_TROT_PER_FR          # S5b Trot @ 1.0x -> exact zero slip!
    FLOOR_X[ff] = FLOOR_X[ff - 1] + dx


def eval_robot_pose(scn, arm, action_name, act_frame_float):
    """Evaluate exact fractional frame of named Blender action on the armature."""
    act = bpy.data.actions[action_name]
    if arm.animation_data is None:
        arm.animation_data_create()
    for tr in arm.animation_data.nla_tracks:
        tr.mute = True
    arm.animation_data.action = act
    f_int = int(math.floor(act_frame_float))
    sub = float(act_frame_float - f_int)
    scn.frame_set(f_int, subframe=sub)
    bpy.context.view_layer.update()


def set_stage_for_frame(scn, arm, st, f):
    """Master cinematographer: sets exact robot action, camera, lighting, floor, dust motes & glow for frame f."""
    cam, cd = st["cam"], st["cd"]
    lights = st["lights"]

    # Default bright sunlit studio parameters (overridden per shot below)
    daylight = 1.0       # 0 = dark obsidian awakening, 1 = luminous golden architectural gallery
    glow_mult = 1.0
    mote_vis = 1.0

    # --- SHOT 1: Obsidian Awakening (frames 1..144, 0.0s..6.0s) ---
    if f <= 144:
        u = (f - 1) / 143.0
        us = smoother(u)
        # Robot slowly wakes up in Idle_Scan (head turns gently toward lens!)
        eval_robot_pose(scn, arm, "Idle_Scan", 1.0 + u * 54.0)
        # Emissives power up gracefully over frames 14..78!
        glow_mult = 0.04 + 1.32 * sstep((f - 14) / 64.0)
        # Subtle creeping sunrise hint only in final 20 frames leading into S2
        daylight = 0.0 + 0.14 * sstep((f - 116) / 28.0)
        mote_vis = 0.25 + 0.55 * sstep((f - 30) / 80.0)

        # Slow dramatic macro dolly past emerald eye & amber shoulder vents
        c_loc = vlerp((1.18, -0.78, 0.56), (1.36, -1.04, 0.64), us)
        c_tgt = vlerp((0.46,  0.00, 0.57), (0.18,  0.00, 0.53), us)
        lens, fstop = lerp(82.0, 68.0, us), 2.4
        # Sweeping golden rim tracing silhouette in the dark
        rim_x = lerp(-1.2, -2.4, us)
        lights["RimSweep"][0].location = V((rim_x, 1.5, 1.65))
        lights["RimSweep"][0].rotation_euler = (V((0.15, 0, 0.56)) - lights["RimSweep"][0].location).to_track_quat("-Z", "Y").to_euler()

    # --- SHOT 2: Daylight Reveal (frames 145..336, 6.0s..14.0s) ---
    elif f <= 336:
        u = (f - 145) / 191.0
        us = smoother(u)
        eval_robot_pose(scn, arm, "Idle_Scan", 55.0 + u * 64.0)
        # THE MAGIC TRANSITION: Obsidian darkness blooms into warm architectural sunlit studio!
        daylight = 0.14 + 0.86 * smoother(min(1.0, (f - 145) / 72.0))
        glow_mult = lerp(1.30, 1.05, sstep((f - 145) / 60.0))
        mote_vis = 0.95

        # Majestic 115-degree sweeping hero crane arc framing FULL canopy & all 4 paws cleanly!
        ang = lerp(math.radians(52.0), math.radians(-48.0), us)
        rad = lerp(2.62, 2.84, us)
        cz = lerp(0.62, 0.86, us)
        c_loc = V((rad * math.cos(ang), rad * math.sin(ang), cz))
        c_tgt = vlerp((0.04, 0.0, 0.50), (0.02, 0.0, 0.50), us)
        lens, fstop = 46.0, 4.5

    # --- SHOT 3: Living Canopy Macro (frames 337..588, 14.0s..24.5s) ---
    elif f <= 588:
        u = (f - 337) / 251.0
        us = smoother(u)
        eval_robot_pose(scn, arm, "Sun_Bloom_Stretch", 1.0 + u * 86.0)
        daylight = 1.0
        glow_mult = 1.15
        mote_vis = 0.0  # razor-clean macro optics without foreground bokeh distraction!

        # Crisp showcase of octagonal planter, brass nozzles, moss, ferns, Y-pedestal & curved 6-bay PV canopy!
        if u < 0.52:
            u1 = smoother(u / 0.52)
            c_loc = vlerp((0.68, -0.74, 0.90), (0.56,  0.76, 0.96), u1)
            c_tgt = vlerp((-0.02, 0.00, 0.80), (-0.02, 0.00, 0.86), u1)
            lens, fstop = lerp(58.0, 54.0, u1), 3.8
        else:
            u2 = smoother((u - 0.52) / 0.48)
            c_loc = vlerp((0.56,  0.76, 0.96), (-0.54, 0.78, 1.24), u2)
            c_tgt = vlerp((-0.02, 0.00, 0.86), (-0.01, 0.00, 0.90), u2)
            lens, fstop = lerp(54.0, 50.0, u2), 4.0

    # --- SHOT 4: Precision Mechanics Macro (frames 589..852, 24.5s..35.5s) ---
    elif f <= 852:
        daylight = 1.0
        glow_mult = 1.05
        mote_vis = 0.0  # crystal-clear mechanical macro
        if f <= 720:
            # S4a: Tight crisp macro showcasing 4-bolt elbow drum, lime collar & FULL stroking chrome hydraulic actuator!
            u = (f - 589) / 131.0
            us = smoother(u)
            act_f = 1.0 + ((u * 1.15) % 1.0) * 95.0
            eval_robot_pose(scn, arm, "Inspect_Plant", act_f)
            c_loc = vlerp((0.64,  0.90, 0.26), (0.40,  0.86, 0.34), us)
            c_tgt = vlerp((0.20,  0.16, 0.22), (0.16,  0.16, 0.26), us)
            lens, fstop = 58.0, 3.6
        else:
            # S4b: Low macro on rear 4-bolt knee drum, bolted lime guard & flexing yellow braided hoses!
            u = (f - 721) / 131.0
            us = smoother(u)
            act_f = 1.0 + (((f - 721) * 0.75) % 48.0)
            eval_robot_pose(scn, arm, "Walk_Cycle", act_f)
            c_loc = vlerp((-0.24,  0.86, 0.34), (-0.82, 0.78, 0.38), us)
            c_tgt = vlerp((-0.38,  0.16, 0.32), (-0.42, 0.16, 0.35), us)
            lens, fstop = 62.0, 3.6

    # --- SHOT 5: Dynamic Locomotion — Walk -> Trot -> Inspect_Plant (frames 853..1116, 35.5s..46.5s) ---
    elif f <= 1116:
        daylight = 1.0
        glow_mult = 1.05
        mote_vis = 0.75
        if f <= 948:
            # S5a: Zero-slip Walk_Cycle (full canopy & rolling precision floor grid cleanly framed!)
            u = (f - 853) / 95.0
            us = smoother(u)
            eval_robot_pose(scn, arm, "Walk_Cycle", 1.0 + ((f - 853) % 48))
            c_loc = vlerp((1.88,  1.78, 0.56), (1.42,  2.14, 0.62), us)
            c_tgt = vlerp((0.02,  0.00, 0.48), (-0.02, 0.00, 0.48), us)
            lens, fstop = 42.0, 5.0
        elif f <= 1032:
            # S5b: Zero-slip brisk Trot_Cycle!
            u = (f - 949) / 83.0
            us = smoother(u)
            eval_robot_pose(scn, arm, "Trot_Cycle", 1.0 + ((f - 949) % 28))
            c_loc = vlerp((2.04, -1.64, 0.50), (1.58, -2.02, 0.58), us)
            c_tgt = vlerp((0.04,  0.00, 0.48), (0.00,  0.00, 0.48), us)
            lens, fstop = 40.0, 5.0
        else:
            # S5c: Graceful Inspect_Plant bow & curiosity scan!
            u = (f - 1033) / 83.0
            us = smoother(u)
            eval_robot_pose(scn, arm, "Inspect_Plant", 1.0 + u * 94.0)
            c_loc = vlerp((1.86,  1.56, 0.62), (1.72,  1.28, 0.52), us)
            c_tgt = vlerp((0.10,  0.00, 0.48), (0.18,  0.00, 0.44), us)
            lens, fstop = 44.0, 4.2

    # --- SHOT 6: Sun Bloom Finale & End Card Hold (frames 1117..1344, 46.5s..56.0s) ---
    else:
        u = (f - 1117) / 227.0
        us = smoother(u)
        if u < 0.52:
            act_f = 1.0 + smoother(u / 0.52) * 47.0
        else:
            u_h = (u - 0.52) / 0.48
            act_f = 48.0 + 3.5 * math.sin(math.pi * u_h)
        eval_robot_pose(scn, arm, "Sun_Bloom_Stretch", act_f)
        daylight = 1.0
        glow_mult = 1.15
        mote_vis = 1.0

        # Majestic slow hero pull-back into iconic portrait lockup with clean upper/lower margin for end card!
        c_loc = vlerp((1.84, -1.68, 0.62), (2.48, -2.22, 0.84), us)
        c_tgt = vlerp((0.04,  0.00, 0.50), (0.02,  0.00, 0.52), us)
        lens, fstop = lerp(46.0, 44.0, us), 4.5

    # --- Apply Camera Transform & Depth of Field ---
    cam.location = c_loc
    cam.rotation_euler = (c_tgt - c_loc).to_track_quat("-Z", "Y").to_euler()
    cd.lens = lens
    cd.dof.use_dof = True
    cd.dof.focus_distance = (c_tgt - c_loc).length
    cd.dof.aperture_fstop = fstop

    # --- Apply Lighting & Studio Cyclorama Transition (Obsidian -> Golden Architectural Gallery!) ---
    st["world_bg"].inputs["Color"].default_value = (
        lerp(0.012, 0.72, daylight), lerp(0.015, 0.74, daylight), lerp(0.020, 0.76, daylight), 1.0
    )
    st["world_bg"].inputs["Strength"].default_value = lerp(0.08, 0.72, daylight)

    lights["KeySun"][1].energy = lerp(4.0, 290.0, daylight)
    lights["SkyFill"][1].energy = lerp(2.0, 118.0, daylight)
    lights["RimSweep"][1].energy = lerp(95.0, 125.0, daylight)
    lights["ChromeKick"][1].energy = lerp(10.0, 72.0, daylight)
    lights["GrowLight"][1].energy = 10.5 * glow_mult

    # Track canopy GrowLight to robot's dorsal canopy center dynamically!
    pb_can = arm.pose.bones["B_canopy_pitch"]
    can_w = arm.matrix_world @ pb_can.tail
    lights["GrowLight"][0].location = can_w - V((0.0, 0.0, 0.02))

    # Architectural warm-stone slate floor with crisp visible precision grid lines (pops against white armor!)
    st["floor_mix"].inputs[6].default_value = (
        lerp(0.032, 0.34, daylight), lerp(0.036, 0.35, daylight), lerp(0.042, 0.34, daylight), 1.0
    )
    st["floor_mix"].inputs[7].default_value = (
        lerp(0.14, 0.17, daylight), lerp(0.22, 0.19, daylight), lerp(0.18, 0.17, daylight), 1.0
    )
    st["floor_rough"].inputs["To Min"].default_value = lerp(0.18, 0.36, daylight)
    st["floor_rough"].inputs["To Max"].default_value = lerp(0.30, 0.50, daylight)
    st["grid_str"].inputs[1].default_value = lerp(0.34, 0.72, daylight)
    # Positive Location.X in Mapping shifts texture features toward -X (backward beneath paws!)
    st["floor_scroll"].inputs["Location"].default_value = (float(FLOOR_X[f]), 0.0, 0.0)

    # Apply emissive power-up multiplier
    for bsdf, base_str in st["emissive_mats"]:
        bsdf.inputs["Emission Strength"].default_value = base_str * glow_mult

    # Animate gently drifting golden sunlit pollen motes
    t_sec = f / FPS
    st["mote_bsdf"].inputs["Emission Strength"].default_value = 2.6 * mote_vis
    for mo, bp, ph, spd in st["motes"]:
        mo.hide_render = (mote_vis < 0.05)
        mo.location = V((
            bp.x + 0.06 * math.sin(t_sec * 0.45 + ph),
            bp.y + 0.06 * math.cos(t_sec * 0.38 + ph * 1.3),
            bp.z + ((t_sec * spd + ph * 0.1) % 0.55) - 0.25,
        ))


def render_preview_storyboard(scn, arm, st):
    """Render 12 key storyboard frames (2 per shot) into a 4x3 visual QA contact sheet!"""
    key_frames = [
        (36,  "S1a_dark_ignite"),    (118, "S1b_eye_glow"),
        (170, "S2a_sunrise"),        (295, "S2b_daylight_hero"),
        (395, "S3a_garden_moss"),    (535, "S3b_pv_canopy"),
        (650, "S4a_hydraulic_piston"), (790, "S4b_rear_hoses"),
        (890, "S5a_walk_zeroslip"),  (985, "S5b_trot_zeroslip"),
        (1075,"S5c_inspect_bow"),    (1260,"S6_sun_bloom_finale"),
    ]
    W, H = 480, 270
    scn.render.resolution_x, scn.render.resolution_y = W, H
    scn.render.image_settings.file_format = "PNG"

    tiles = []
    for f, lbl in key_frames:
        set_stage_for_frame(scn, arm, st, f)
        p = os.path.join(PREV_DIR, f"prev_{f:04d}_{lbl}.png")
        scn.render.filepath = p
        bpy.ops.render.render(write_still=True)
        im = bpy.data.images.load(p, check_existing=False)
        arr = np.array(im.pixels[:], dtype=np.float32).reshape(H, W, 4)[::-1]
        bpy.data.images.remove(im)
        tiles.append(arr)
        print(f"  preview frame {f:4d} ({lbl}) OK", flush=True)

    grid = np.zeros((H * 3, W * 4, 4), dtype=np.float32)
    for idx, tile in enumerate(tiles):
        r, c = divmod(idx, 4)
        grid[r * H:(r + 1) * H, c * W:(c + 1) * W] = tile
    out_sheet = os.path.join(HERE, "storyboard_preview.png")
    im_out = bpy.data.images.new("sb_prev", W * 4, H * 3, alpha=True)
    im_out.pixels.foreach_set(np.clip(grid[::-1], 0.0, 1.0).astype(np.float32).ravel())
    im_out.filepath_raw = out_sheet; im_out.file_format = "PNG"; im_out.save()
    bpy.data.images.remove(im_out)
    print(f"STORYBOARD PREVIEW SAVED: {out_sheet}")


def render_frame_range(scn, arm, st, f0, f1):
    scn.render.resolution_x = TL["width"]
    scn.render.resolution_y = TL["height"]
    scn.render.image_settings.file_format = "JPEG"
    scn.render.image_settings.quality = 96

    t0 = time.time()
    todo = [f for f in range(f0, f1 + 1)
            if not (os.path.exists(os.path.join(FRAMES_DIR, f"frame_{f:04d}.jpg"))
                    and os.path.getsize(os.path.join(FRAMES_DIR, f"frame_{f:04d}.jpg")) > 10000)]
    count = len(todo)
    print(f"RANGE [{f0}..{f1}]: {count} frames to render (skipping {(f1 - f0 + 1) - count} already rendered)", flush=True)
    for i, f in enumerate(todo, 1):
        out_p = os.path.join(FRAMES_DIR, f"frame_{f:04d}.jpg")
        set_stage_for_frame(scn, arm, st, f)
        scn.render.filepath = out_p
        bpy.ops.render.render(write_still=True)
        if i % 48 == 0 or i == count:
            el = time.time() - t0
            fps_r = i / max(el, 0.01)
            eta = (count - i) / max(fps_r, 0.01)
            print(f"[{f0}-{f1}] {i}/{count} (frame {f}) | {fps_r:.2f} fr/s | elapsed {el:.0f}s | ETA {eta:.0f}s", flush=True)
    print(f"RANGE [{f0}..{f1}] COMPLETE in {time.time() - t0:.1f}s!")


def main():
    bpy.ops.wm.open_mainfile(filepath=BLEND_PATH)
    scn = bpy.context.scene
    arm = bpy.data.objects["FloraQuad_Rig"]
    st = build_cinema_stage(scn)
    if PREVIEW:
        render_preview_storyboard(scn, arm, st)
    else:
        render_frame_range(scn, arm, st, F_START, F_END)


if __name__ == "__main__":
    main()
