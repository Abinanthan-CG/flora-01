# verify_glb.py — Independent binary GLB inspection + factory-empty Blender 5.2 re-import & render check
# Usage:
#   blender -b --factory-startup -t 4 --python verify_glb.py

import bpy
import os
import json
import struct
import math
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
GLB = os.path.join(HERE, "out", "flora_quad.glb")
OUTD = os.path.join(HERE, "renders")
os.makedirs(OUTD, exist_ok=True)

# 1. Raw GLB binary JSON inspection (independent of Blender's importer)
with open(GLB, "rb") as fh:
    magic, version, total_len = struct.unpack("<4sII", fh.read(12))
    assert magic == b"glTF" and version == 2, f"Bad GLB header: {magic} v{version}"
    chunk_len, chunk_type = struct.unpack("<II", fh.read(8))
    g = json.loads(fh.read(chunk_len))

n_imgs = len(g.get("images", []))
n_texs = len(g.get("textures", []))
n_mats = len(g.get("materials", []))
n_meshes = len(g.get("meshes", []))
n_joints = len(g["skins"][0]["joints"]) if g.get("skins") else 0
anims = [(a.get("name"), len(a.get("channels", []))) for a in g.get("animations", [])]

print(f"GLB HEADER OK: v{version}, {total_len/1024:.1f} KB")
print(f"  images={n_imgs}, textures={n_texs}, materials={n_mats}, meshes={n_meshes}, joints={n_joints}")
print(f"  animations={anims}")
for m in g.get("materials", []):
    p = m.get("pbrMetallicRoughness", {})
    em = [round(v, 2) for v in m.get("emissiveFactor", [0, 0, 0])]
    es = m.get("extensions", {}).get("KHR_materials_emissive_strength", {}).get("emissiveStrength", 1)
    if any(em) or "solar" in m["name"] or "white" in m["name"]:
        print(f"  mat {m['name']:32s} baseTex={'baseColorTexture' in p} mrTex={'metallicRoughnessTexture' in p} "
              f"nrm={'normalTexture' in m} occ={'occlusionTexture' in m} emit={em} x{es}")

assert n_meshes == 80, f"Expected 80 meshes, got {n_meshes}"
assert n_joints == 30, f"Expected 30 joints, got {n_joints}"
assert len(anims) == 8, f"Expected 8 animations, got {len(anims)}"

# 2. Re-import GLB into a factory-empty scene and verify geometry, rig, animations & visuals
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB)
scn = bpy.context.scene

meshes = [o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("P_")]
# Hide any internal glTF bone-shape helper object so it never appears in verification renders
for o in bpy.data.objects:
    if o.type == "MESH" and not o.name.startswith("P_"):
        o.hide_render = True
        o.hide_viewport = True
arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
loaded_imgs = [i.name for i in bpy.data.images if i.size[0] > 0]
actions = sorted(a.name for a in bpy.data.actions)

# Reset imported armature to rest pose to check resting bounding box
for arm in arms:
    if arm.animation_data:
        arm.animation_data.action = None
        for tr in arm.animation_data.nla_tracks:
            tr.mute = True
    for pb in arm.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.rotation_euler = (0, 0, 0)
        pb.scale = (1, 1, 1)
bpy.context.view_layer.update()

lo = Vector((1e9, 1e9, 1e9))
hi = Vector((-1e9, -1e9, -1e9))
total_tris = 0
for o in meshes:
    o.data.calc_loop_triangles()
    total_tris += len(o.data.loop_triangles)
    for v in o.data.vertices:
        w = o.matrix_world @ v.co
        lo = Vector((min(lo.x, w.x), min(lo.y, w.y), min(lo.z, w.z)))
        hi = Vector((max(hi.x, w.x), max(hi.y, w.y), max(hi.z, w.z)))

dims = hi - lo
print(f"RE-IMPORTED OK: meshes={len(meshes)}, tris={total_tris}, armatures={len(arms)}, "
      f"bones={len(arms[0].data.bones)}, actions={actions}, loaded_images={len(loaded_imgs)}")
print(f"  re-imported dims={[round(v,4) for v in dims]} m, min_z={lo.z:.4f} m")
assert len(meshes) == 80
assert len(arms) == 1 and len(arms[0].data.bones) == 30
assert len(actions) == 8
assert abs(lo.z) < 0.002, f"Re-imported min_z off: {lo.z}"

# 3. Render standalone verification still from the re-imported GLB data ONLY
scn.render.engine = "BLENDER_EEVEE"
try:
    scn.eevee.taa_render_samples = 32
    scn.eevee.use_raytracing = True
except Exception:
    pass
scn.view_settings.view_transform = "AgX"
scn.render.image_settings.file_format = "PNG"

w = bpy.data.worlds.new("VerifyWorld")
scn.world = w
nt = w.node_tree
nt.nodes.clear()
out = nt.nodes.new("ShaderNodeOutputWorld")
lp = nt.nodes.new("ShaderNodeLightPath")
bg1 = nt.nodes.new("ShaderNodeBackground")
bg1.inputs["Color"].default_value = (0.78, 0.80, 0.84, 1.0)
bg1.inputs["Strength"].default_value = 0.85
bg2 = nt.nodes.new("ShaderNodeBackground")
bg2.inputs["Color"].default_value = (0.82, 0.82, 0.80, 1.0)  # light clean studio backdrop like concept!
bg2.inputs["Strength"].default_value = 1.0
mix = nt.nodes.new("ShaderNodeMixShader")
nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs["Fac"])
nt.links.new(bg1.outputs[0], mix.inputs[1])
nt.links.new(bg2.outputs[0], mix.inputs[2])
nt.links.new(mix.outputs[0], out.inputs["Surface"])

def add_light(name, loc, tgt, energy, size, col=(1, 0.99, 0.96)):
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy, ld.size, ld.color = energy, size, col
    lo_ = bpy.data.objects.new(name, ld)
    scn.collection.objects.link(lo_)
    lo_.location = Vector(loc)
    lo_.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()

add_light("Key", (2.4, -2.0, 2.8), (0, 0, 0.50), 210, 2.2)
add_light("Fill", (-2.2, 2.2, 2.0), (0, 0, 0.50), 115, 2.6, (0.92, 0.96, 1.0))
add_light("Rim", (-1.8, -1.8, 2.4), (0, 0, 0.55), 95, 1.8, (0.98, 1.0, 0.94))

# Pose in Walk_Cycle frame 16 (graceful raised front-right paw echoing concept.png!)
arm = arms[0]
walk_act = next((a for a in bpy.data.actions if "Walk_Cycle" in a.name), None)
if walk_act:
    arm.animation_data_create()
    arm.animation_data.action = walk_act
    scn.frame_set(42)  # front-right paw lifted gracefully in mid-stride!
    bpy.context.view_layer.update()

bpy.ops.mesh.primitive_plane_add(size=10.0, location=(0, 0, -0.0005))
fl = bpy.context.active_object
fm = bpy.data.materials.new("CleanFloor")
bsdf = next(n for n in fm.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
bsdf.inputs["Base Color"].default_value = (0.78, 0.78, 0.76, 1.0)
bsdf.inputs["Roughness"].default_value = 0.92
fl.data.materials.append(fm)

cd = bpy.data.cameras.new("Cam")
cd.lens = 55.0
cam = bpy.data.objects.new("Cam", cd)
scn.collection.objects.link(cam)
scn.camera = cam
# Match original concept camera angle (front-right 3/4 framing full canopy & all four paws cleanly!)
cam.location = Vector((1.82, -1.70, 0.72))
cam.rotation_euler = (Vector((0.02, 0.0, 0.50)) - cam.location).to_track_quat("-Z", "Y").to_euler()
cd.lens = 48.0

scn.render.resolution_x, scn.render.resolution_y = 1200, 900
out_img = os.path.join(OUTD, "glb_reimport_hero.png")
scn.render.filepath = out_img
bpy.ops.render.render(write_still=True)

report = dict(
    glb_kb=round(total_len / 1024, 1),
    images=n_imgs, textures=n_texs, materials=n_mats,
    meshes=len(meshes), tris=total_tris, joints=n_joints,
    actions=actions, dims_m=[round(v, 4) for v in dims],
    min_z_m=round(lo.z, 4), hero_render=out_img,
)
with open(os.path.join(HERE, "out", "verify_glb.json"), "w") as fh:
    json.dump(report, fh, indent=2)
print("GLB VERIFIED:", json.dumps(report, indent=2))
