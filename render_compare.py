# render_compare.py — Renders 6-view turnaround matching refs/turnaround.png, close-ups, action pose strips,
# and runs inter-bone BVH clash check + hydraulic tracking & ground-contact verification.
#
# Usage:
#   blender -b --factory-startup -t 4 --python render_compare.py -- [turn] [closeups] [actions] [check]

import bpy
import sys
import os
import json
import math
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
BLEND_PATH = os.path.join(HERE, "out", "flora_quad.blend")
REF_TURN = os.path.join(HERE, "refs", "turnaround.png")
RENDER_DIR = os.path.join(HERE, "renders")
os.makedirs(RENDER_DIR, exist_ok=True)

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODES = set(a for a in argv if a in ("turn", "closeups", "actions", "check", "beauty")) or {"turn", "closeups", "actions", "check"}


def setup_studio(scn):
    # Check valid render engines dynamically (Blender 5.2 safety!)
    scn.render.engine = "BLENDER_EEVEE"
    try:
        scn.eevee.taa_render_samples = 32
        scn.eevee.use_raytracing = True
    except Exception:
        pass
    scn.view_settings.view_transform = "AgX"
    scn.view_settings.exposure = 0.0
    scn.render.image_settings.file_format = "PNG"

    # Neutral mid-grey studio world matching refs/turnaround.png (#8a8a8a ~ 0.25 linear)
    w = bpy.data.worlds.new("StudioWorld")
    scn.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    lp = nt.nodes.new("ShaderNodeLightPath")
    bg_lit = nt.nodes.new("ShaderNodeBackground")
    bg_lit.inputs["Color"].default_value = (0.78, 0.80, 0.84, 1.0)
    bg_lit.inputs["Strength"].default_value = 0.85
    bg_cam = nt.nodes.new("ShaderNodeBackground")
    bg_cam.inputs["Color"].default_value = (0.25, 0.25, 0.25, 1.0)  # sRGB ~ #8a8a8a
    bg_cam.inputs["Strength"].default_value = 1.0
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs["Fac"])
    nt.links.new(bg_lit.outputs[0], mix.inputs[1])
    nt.links.new(bg_cam.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])

    # Clean 3-point soft studio lighting + canopy grow-light bounce
    def add_area(name, loc, target, energy, size, color=(1.0, 0.99, 0.97)):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy = energy
        ld.size = size
        ld.color = color
        lo = bpy.data.objects.new(name, ld)
        scn.collection.objects.link(lo)
        lo.location = Vector(loc)
        lo.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        return lo

    add_area("KeyLight", (2.4, -2.0, 2.8), (0.0, 0.0, 0.50), 220.0, 2.2, (1.0, 0.98, 0.95))
    add_area("FillLight", (-2.2, 2.4, 2.0), (0.0, 0.0, 0.50), 115.0, 2.8, (0.90, 0.95, 1.0))
    add_area("RimLight", (-2.0, -1.6, 2.4), (0.0, 0.0, 0.55), 95.0, 1.8, (0.98, 1.0, 0.95))
    # Subtle downward warm-lime area light inside canopy so moss & sprouts pick up real green grow-glow!
    grow = bpy.data.lights.new("CanopyGrowLight", "AREA")
    grow.energy = 1.8
    grow.size = 0.24
    grow.color = (0.85, 1.0, 0.35)
    go = bpy.data.objects.new("CanopyGrowLight", grow)
    scn.collection.objects.link(go)
    go.location = Vector((-0.02, 0.0, 0.91))
    go.rotation_euler = (0.0, 0.0, 0.0)

    # Subtle shadow-catcher floor disk (invisible shadow receiver or soft grey studio plane)
    bpy.ops.mesh.primitive_plane_add(size=8.0, location=(0, 0, -0.0005))
    floor = bpy.context.active_object
    floor.name = "_StudioFloor"
    fm = bpy.data.materials.new("_FloorMat")
    fm.use_nodes = True
    f_bsdf = next(n for n in fm.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    f_bsdf.inputs["Base Color"].default_value = (0.25, 0.25, 0.25, 1.0)
    f_bsdf.inputs["Roughness"].default_value = 0.95
    floor.data.materials.append(fm)

    cd = bpy.data.cameras.new("RenderCam")
    cd.clip_start, cd.clip_end = 0.02, 50.0
    cam = bpy.data.objects.new("RenderCam", cd)
    scn.collection.objects.link(cam)
    scn.camera = cam
    return cam, cd, floor


def reset_rest_pose(arm):
    if arm.animation_data:
        arm.animation_data.action = None
        for tr in arm.animation_data.nla_tracks:
            tr.mute = True
    for pb in arm.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_euler = (0, 0, 0)
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.scale = (1, 1, 1)
    bpy.context.view_layer.update()


def aim_cam(cam, cd, loc, target, ortho_scale=None, lens=55.0, up="Y"):
    cam.location = Vector(loc)
    vec = Vector(target) - Vector(loc)
    cam.rotation_euler = vec.to_track_quat("-Z", up).to_euler()
    if ortho_scale is not None:
        cd.type = "ORTHO"
        cd.ortho_scale = ortho_scale
    else:
        cd.type = "PERSP"
        cd.lens = lens


def render_to_array(scn, path, w, h):
    scn.render.resolution_x = w
    scn.render.resolution_y = h
    scn.render.filepath = path
    bpy.ops.render.render(write_still=True)
    im = bpy.data.images.load(path, check_existing=False)
    arr = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1]
    bpy.data.images.remove(im)
    return arr


def save_array_png(arr_rgba, path):
    h, w, _ = arr_rgba.shape
    im = bpy.data.images.new(os.path.basename(path), w, h, alpha=True)
    im.pixels.foreach_set(np.clip(arr_rgba[::-1], 0.0, 1.0).astype(np.float32).ravel())
    im.filepath_raw = path
    im.file_format = "PNG"
    im.save()
    bpy.data.images.remove(im)


def render_turnaround_sheet(scn, cam, cd, arm, floor):
    reset_rest_pose(arm)
    # Match refs/turnaround.png exact 3x2 grid:
    # Top row: FRONT (+X toward cam), LEFT SIDE (nose pointing left -> cam at +Y!), REAR (-X toward cam)
    # Bot row: RIGHT SIDE (nose pointing right -> cam at -Y!), TOP PLAN (nose pointing up -> cam at +Z, up=+X!), 3/4 front-left
    W, H = 480, 440
    ctr = Vector((0.0, 0.0, 0.505))
    os_val = 1.52
    views = [
        ("front", ( 3.0,  0.0, 0.505), ctr, os_val, 55, "Y", False),
        ("left",  ( 0.0,  3.0, 0.505), ctr, os_val, 55, "Y", False),
        ("rear",  (-3.0,  0.0, 0.505), ctr, os_val, 55, "Y", False),
        ("right", ( 0.0, -3.0, 0.505), ctr, os_val, 55, "Y", False),
        ("top",   ( 0.0,  0.0, 3.200), Vector((0.0, 0.0, 0.50)), os_val, 55, "X", True),
        ("3q",    ( 1.95, 1.55, 1.02), Vector((0.02, 0.0, 0.48)), None, 52, "Y", False),
    ]
    tiles = []
    for nm, loc, tgt, osc, lens, up, hide_floor in views:
        floor.hide_render = hide_floor
        aim_cam(cam, cd, loc, tgt, ortho_scale=osc, lens=lens, up=up)
        # Fix TOP view camera rotation so nose (+X) points straight UP on screen!
        if nm == "top":
            # Looking down -Z with +X up on screen => camera local +Y = +X, local +X = -Y, local -Z = -Z
            cam.rotation_euler = Matrix((
                ( 0,  1, 0),
                (-1,  0, 0),
                ( 0,  0, 1),
            )).to_euler()
        tmp = os.path.join(RENDER_DIR, f"_tile_{nm}.png")
        tiles.append(render_to_array(scn, tmp, W, H))
    floor.hide_render = False

    grid = np.zeros((H * 2, W * 3, 4), dtype=np.float32)
    for idx, t in enumerate(tiles):
        r, c = divmod(idx, 3)
        grid[r * H:(r + 1) * H, c * W:(c + 1) * W] = t
    out_model = os.path.join(RENDER_DIR, "model_turnaround.png")
    save_array_png(grid, out_model)
    print(f"SAVED {out_model}")

    # Also build stacked comparison image (Reference on top, 3D Model on bottom) for direct visual audit!
    if os.path.exists(REF_TURN):
        im_ref = bpy.data.images.load(REF_TURN, check_existing=False)
        rw, rh = im_ref.size
        ref_arr = np.array(im_ref.pixels[:], dtype=np.float32).reshape(rh, rw, 4)[::-1]
        bpy.data.images.remove(im_ref)
        # Resize ref_arr to match grid width (W*3) via simple bilinear/nearest numpy sample
        tw = W * 3
        th = int(round(rh * (tw / rw)))
        ys = np.clip((np.arange(th) * (rh / th)).astype(int), 0, rh - 1)
        xs = np.clip((np.arange(tw) * (rw / tw)).astype(int), 0, rw - 1)
        ref_res = ref_arr[ys[:, None], xs[None, :]]
        sep = np.full((12, tw, 4), (0.12, 0.12, 0.12, 1.0), dtype=np.float32)
        comp = np.vstack([ref_res, sep, grid])
        out_comp = os.path.join(RENDER_DIR, "compare_turnaround.png")
        save_array_png(comp, out_comp)
        print(f"SAVED {out_comp}")


def render_closeup_plates(scn, cam, cd, arm, floor):
    reset_rest_pose(arm)
    floor.hide_render = False
    W, H = 560, 420
    # 2x2 grid of hero close-up inspection views matching our reference plates:
    # 1. Front leg, shoulder amber vents, elbow drum & chrome hydraulic piston
    # 2. Rear leg, hip drum, yellow braided hoses, knee collar & rear battery pods
    # 3. Dorsal planter, moss/ferns/sprouts, Y-pedestal & arched solar canopy + underside LEDs
    # 4. Sensor head/neck optics, chin guard & rear antenna vanes (3/4 front-right hero shot)
    shots = [
        ("cu_front_leg", (0.58,  0.88, 0.34), ( 0.18, 0.16, 0.32), 62),
        ("cu_rear_leg",  (-0.78, 0.85, 0.38), (-0.42, 0.15, 0.34), 60),
        ("cu_canopy",    (0.38,  0.56, 0.84), (-0.02, 0.00, 0.82), 55),
        ("cu_hero_3q",   (1.22, -0.92, 0.72), ( 0.04, 0.00, 0.54), 52),
    ]
    tiles = []
    for nm, loc, tgt, lens in shots:
        aim_cam(cam, cd, loc, tgt, ortho_scale=None, lens=lens)
        tmp = os.path.join(RENDER_DIR, f"_tile_{nm}.png")
        tiles.append(render_to_array(scn, tmp, W, H))
    grid = np.zeros((H * 2, W * 2, 4), dtype=np.float32)
    for idx, t in enumerate(tiles):
        r, c = divmod(idx, 2)
        grid[r * H:(r + 1) * H, c * W:(c + 1) * W] = t
    out_cu = os.path.join(RENDER_DIR, "model_closeups.png")
    save_array_png(grid, out_cu)
    print(f"SAVED {out_cu}")


def render_action_strip(scn, cam, cd, arm, floor):
    floor.hide_render = False
    W, H = 480, 380
    poses = [
        ("Walk_Cycle",        18, (1.45,  1.35, 0.68), (0.00, 0.0, 0.48), 52),
        ("Trot_Cycle",         7, (1.45,  1.35, 0.68), (0.00, 0.0, 0.48), 52),
        ("Inspect_Plant",     48, (1.45,  1.25, 0.62), (0.05, 0.0, 0.44), 52),
        ("Sun_Bloom_Stretch", 48, (1.40, -1.25, 0.72), (0.04, 0.0, 0.50), 50),
    ]
    tiles = []
    for act_name, frame_num, loc, tgt, lens in poses:
        reset_rest_pose(arm)
        act = bpy.data.actions.get(act_name)
        if act:
            arm.animation_data.action = act
            scn.frame_set(frame_num)
            bpy.context.view_layer.update()
        aim_cam(cam, cd, loc, tgt, ortho_scale=None, lens=lens)
        tmp = os.path.join(RENDER_DIR, f"_tile_act_{act_name}.png")
        tiles.append(render_to_array(scn, tmp, W, H))
    grid = np.zeros((H * 2, W * 2, 4), dtype=np.float32)
    for idx, t in enumerate(tiles):
        r, c = divmod(idx, 2)
        grid[r * H:(r + 1) * H, c * W:(c + 1) * W] = t
    out_act = os.path.join(RENDER_DIR, "model_actions.png")
    save_array_png(grid, out_act)
    print(f"SAVED {out_act}")
    reset_rest_pose(arm)


def run_clash_and_rig_checks(scn, arm):
    """AnyMachine inter-bone BVH clash check + ground penetration & hydraulic alignment check across all actions."""
    deps = bpy.context.evaluated_depsgraph_get()
    meshes = [o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("P_")]

    # Map each mesh to its primary bone and bone ancestry
    mesh_bone = {}
    for o in meshes:
        if o.vertex_groups:
            mesh_bone[o.name] = o.vertex_groups[0].name
        else:
            mesh_bone[o.name] = "B_torso"

    parent_map = {b.name: (b.parent.name if b.parent else None) for b in arm.data.bones}

    def is_adjacent_or_same(b1, b2):
        if b1 == b2:
            return True
        if parent_map.get(b1) == b2 or parent_map.get(b2) == b1:
            return True
        # Hydraulic rod & barrel are concentric by design; exclude that pair
        if ("hyd_cyl" in b1 and "hyd_rod" in b2) or ("hyd_cyl" in b2 and "hyd_rod" in b1):
            return True
        if ("hyd_" in b1 and ("upper" in b2 or "lower" in b2)) or ("hyd_" in b2 and ("upper" in b1 or "lower" in b1)):
            return True
        # Ignore sibling children on same joint (e.g., ab & upper, canopy_yaw & torso)
        if parent_map.get(b1) == parent_map.get(b2):
            return True
        return False

    def eval_bvhs():
        bvhs = {}
        min_z_all = 1e9
        for o in meshes:
            # Skip flexible hose from rigid inter-bone overlap check
            if "hose_flex" in o.name:
                continue
            eo = o.evaluated_get(deps)
            me = eo.to_mesh()
            if len(me.polygons) == 0:
                eo.to_mesh_clear()
                continue
            M = eo.matrix_world
            verts = [M @ v.co for v in me.vertices]
            for v in verts:
                if v.z < min_z_all:
                    min_z_all = v.z
            me.calc_loop_triangles()
            polys = [tuple(t.vertices) for t in me.loop_triangles]
            bvhs[o.name] = BVHTree.FromPolygons(verts, polys, all_triangles=True)
            eo.to_mesh_clear()
        return bvhs, min_z_all

    # 1. Baseline rest-pose overlaps
    reset_rest_pose(arm)
    deps.update()
    rest_bvhs, rest_min_z = eval_bvhs()
    rest_pairs = set()
    names = sorted(rest_bvhs.keys())
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            n1, n2 = names[i], names[j]
            if is_adjacent_or_same(mesh_bone[n1], mesh_bone[n2]):
                continue
            if rest_bvhs[n1].overlap(rest_bvhs[n2]):
                rest_pairs.add((n1, n2))

    # 2. Sample every action across frames
    new_clashes = []
    worst_ground_pen = 0.0
    worst_hyd_misalign_mm = 0.0

    for act in bpy.data.actions:
        reset_rest_pose(arm)
        arm.animation_data.action = act
        f0, f1 = int(act.frame_range[0]), int(act.frame_range[1])
        step = max(1, (f1 - f0) // 10)
        sample_frames = sorted(set(list(range(f0, f1 + 1, step)) + [f1]))
        for fr in sample_frames:
            scn.frame_set(fr)
            deps.update()
            bvhs, min_z = eval_bvhs()
            if min_z < worst_ground_pen:
                worst_ground_pen = min_z
            for i in range(len(names)):
                for j in range(i + 1, len(names)):
                    n1, n2 = names[i], names[j]
                    if is_adjacent_or_same(mesh_bone[n1], mesh_bone[n2]):
                        continue
                    if (n1, n2) in rest_pairs:
                        continue
                    ov = bvhs[n1].overlap(bvhs[n2])
                    if ov:
                        new_clashes.append(dict(action=act.name, frame=fr, a=n1, b=n2, tris=len(ov)))

            # Verify hydraulic cylinder & rod colinearity (< 0.1 mm!)
            for tag in ("L", "R"):
                pb_c = arm.pose.bones[f"B_F{tag}_hyd_cyl"]
                pb_r = arm.pose.bones[f"B_F{tag}_hyd_rod"]
                c_head = arm.matrix_world @ pb_c.head
                c_tail = arm.matrix_world @ pb_c.tail
                r_head = arm.matrix_world @ pb_r.head
                r_tail = arm.pose.bones[f"B_F{tag}_hyd_rod"].tail
                r_tail = arm.matrix_world @ r_tail
                c_dir = (c_tail - c_head).normalized()
                r_dir = (r_tail - r_head).normalized()
                # Distance from r_head to line through c_head along c_dir
                v = r_head - c_head
                perp = (v - c_dir * v.dot(c_dir)).length * 1000.0
                # Opposite aiming check: c_dir + r_dir should be near 0
                ang_err = (c_dir + r_dir).length * 100.0
                worst_hyd_misalign_mm = max(worst_hyd_misalign_mm, perp, ang_err)

    report = dict(
        rest_min_z_mm=round(rest_min_z * 1000.0, 3),
        worst_ground_pen_mm=round(worst_ground_pen * 1000.0, 3),
        worst_hyd_misalign_mm=round(worst_hyd_misalign_mm, 4),
        rest_overlap_pairs=len(rest_pairs),
        new_action_clashes=len(new_clashes),
        clashes=new_clashes[:20],
    )
    out_chk = os.path.join(HERE, "out", "check.json")
    with open(out_chk, "w") as fh:
        json.dump(report, fh, indent=2)
    print("CHECK REPORT:", json.dumps(report, indent=2))
    reset_rest_pose(arm)
    return report


def render_cycles_beauty(scn, cam, cd, arm, floor):
    """Render a 1400x1050 Cycles path-traced studio beauty shot echoing the original concept image
    (with front-right paw gracefully lifted in Sun_Bloom_Stretch + real green grow-light bounce!)."""
    reset_rest_pose(arm)
    act = bpy.data.actions.get("Sun_Bloom_Stretch")
    if act:
        arm.animation_data.action = act
        scn.frame_set(48)
        bpy.context.view_layer.update()

    # Switch to Cycles CPU with OpenImageDenoise for genuine path-traced reflections & grow-light GI!
    scn.render.engine = "CYCLES"
    scn.cycles.device = "CPU"
    scn.cycles.samples = 48
    scn.cycles.use_adaptive_sampling = True
    scn.cycles.adaptive_threshold = 0.03
    scn.cycles.use_denoising = True
    scn.cycles.max_bounces = 6
    scn.cycles.diffuse_bounces = 3
    scn.cycles.glossy_bounces = 3

    # Warm clean cyclorama studio backdrop echoing concept.jpg
    nt = scn.world.node_tree
    for n in nt.nodes:
        if n.type == "BACKGROUND":
            if n.inputs["Strength"].default_value > 0.9:
                n.inputs["Color"].default_value = (0.76, 0.76, 0.74, 1.0)
            else:
                n.inputs["Color"].default_value = (0.82, 0.84, 0.86, 1.0)
                n.inputs["Strength"].default_value = 0.75
    floor.hide_render = False
    f_bsdf = next(n for n in floor.data.materials[0].node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    f_bsdf.inputs["Base Color"].default_value = (0.76, 0.76, 0.74, 1.0)
    f_bsdf.inputs["Roughness"].default_value = 0.88

    # Boost canopy grow-light slightly for real green path-traced bounce onto moss & ferns!
    gl = bpy.data.objects.get("CanopyGrowLight")
    if gl and gl.type == "LIGHT":
        gl.data.energy = 8.5
        gl.data.color = (0.85, 1.0, 0.25)

    # Classic studio 3/4 front-right camera framing the entire canopy & all four paws cleanly + subtle DoF
    aim_cam(cam, cd, (1.85, -1.72, 0.72), (0.03, 0.0, 0.50), ortho_scale=None, lens=48.0)
    cd.dof.use_dof = True
    cd.dof.focus_distance = (Vector((0.03, 0.0, 0.50)) - cam.location).length
    cd.dof.aperture_fstop = 8.0

    scn.render.resolution_x, scn.render.resolution_y = 1400, 1050
    out_beauty = os.path.join(RENDER_DIR, "hero_cycles_beauty.png")
    scn.render.filepath = out_beauty
    bpy.ops.render.render(write_still=True)
    cd.dof.use_dof = False
    print(f"SAVED {out_beauty}")
    reset_rest_pose(arm)


def main():
    bpy.ops.wm.open_mainfile(filepath=BLEND_PATH)
    scn = bpy.context.scene
    arm = bpy.data.objects["FloraQuad_Rig"]
    cam, cd, floor = setup_studio(scn)

    if "turn" in MODES:
        render_turnaround_sheet(scn, cam, cd, arm, floor)
    if "closeups" in MODES:
        render_closeup_plates(scn, cam, cd, arm, floor)
    if "actions" in MODES:
        render_action_strip(scn, cam, cd, arm, floor)
    if "check" in MODES:
        run_clash_and_rig_checks(scn, arm)
    if "beauty" in MODES:
        render_cycles_beauty(scn, cam, cd, arm, floor)


if __name__ == "__main__":
    main()
