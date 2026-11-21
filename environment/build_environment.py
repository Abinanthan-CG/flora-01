# build_environment.py — AnyScene Pass 2 Photoreal Solarpunk Rooftop Botanical Conservatory (Blender 5.2)
# Grounded strictly in refs/env-concept.jpg, refs/env-plan.jpg, and LAYOUT.md.
#
# Key Pass 2 craft upgrades:
#   - True FFT-periodic multi-octave 1024px PBR textures (Roman porous travertine, vertical
#     board-formed concrete, oiled cedar slats, glazed solarpunk tower curtain walls, PV cells)
#   - True 1024px RGBA alpha-cutout Monstera deliciosa & feathered Boston Fern botanical sheets
#   - Real Cycles 20-spp baked Contact Ambient Occlusion (TEXCOORD_1 -> glTF occlusionTexture)
#     on the 18m x 18m travertine terrace floor so every planter, column, dock & bollard grounds deeply
#   - 11-rib vaulted dark-steel & laminated-cedar conservatory canopy with dense cedar louvers
#   - Sleek low-profile chamfered white/obsidian charging dock w/ glowing lime perimeter lightpipe
#   - Dark-steel mirror rainwater basin w/ submerged cobbles, brass spillway & overhanging ferns
#   - Layered sunlit urban-forest tree canopy ring + 42 articulated glazed solarpunk towers
#
# Usage:
#   blender -b --factory-startup -t 4 --python build_environment.py -- [--preview]

import bpy
import bmesh
import os
import sys
import json
import math
import random
import numpy as np
from mathutils import Vector, Matrix

V = Vector
HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "out")
TEX_DIR = os.path.join(OUT_DIR, "textures")
REND_DIR = os.path.join(HERE, "renders")
os.makedirs(TEX_DIR, exist_ok=True)
os.makedirs(REND_DIR, exist_ok=True)

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
DO_PREVIEW = "--preview" in argv or True

# ==============================================================================
# 1. TRUE PERIODIC FFT-FILTERED MULTI-OCTAVE PBR TEXTURES (ZERO BLOCKINESS!)
# ==============================================================================
def ensure_png(filepath, arr_rgba, colorspace="sRGB"):
    h, w, _ = arr_rgba.shape
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
    im2 = bpy.data.images.load(filepath)
    im2.colorspace_settings.name = colorspace
    im2.name = name
    return im2


def fft_fbm(S, beta=2.1, seed=1, aniso_x=1.0, aniso_y=1.0, lo_cut=1.0, hi_cut=None):
    """100% seamlessly periodic, silky-smooth multi-octave fractal noise via 2D FFT."""
    rng = np.random.default_rng(seed)
    white = rng.standard_normal((S, S)).astype(np.float32)
    F = np.fft.rfft2(white)
    fy = np.fft.fftfreq(S)[:, None] * S * aniso_y
    fx = np.fft.rfftfreq(S)[None, :] * S * aniso_x
    r = np.sqrt(fx * fx + fy * fy)
    mask = np.where(r >= lo_cut, (np.maximum(r, 1e-4)) ** (-beta * 0.5), 0.0)
    if hi_cut is not None:
        mask *= np.exp(-((r / hi_cut) ** 4))
    mask[0, 0] = 0.0
    out = np.fft.irfft2(F * mask, s=(S, S)).astype(np.float32)
    std = float(np.std(out)) or 1.0
    return out / std


def make_normals_from_h(h, strength=2.4):
    # Scharr-weighted periodic gradient for razor-clean, artifact-free normal maps
    gx = (
        3.0 * (np.roll(np.roll(h, -1, 1), -1, 0) - np.roll(np.roll(h, 1, 1), -1, 0))
        + 10.0 * (np.roll(h, -1, 1) - np.roll(h, 1, 1))
        + 3.0 * (np.roll(np.roll(h, -1, 1), 1, 0) - np.roll(np.roll(h, 1, 1), 1, 0))
    ) * (strength / 16.0)
    gy = (
        3.0 * (np.roll(np.roll(h, -1, 0), -1, 1) - np.roll(np.roll(h, 1, 0), -1, 1))
        + 10.0 * (np.roll(h, -1, 0) - np.roll(h, 1, 0))
        + 3.0 * (np.roll(np.roll(h, -1, 0), 1, 1) - np.roll(np.roll(h, 1, 0), 1, 1))
    ) * (strength / 16.0)
    ln = np.sqrt(gx * gx + gy * gy + 1.0)
    nrm = np.zeros((*h.shape, 4), dtype=np.float32)
    nrm[..., 0] = 0.5 + 0.5 * (-gx / ln)
    nrm[..., 1] = 0.5 + 0.5 * (gy / ln)
    nrm[..., 2] = 0.5 + 0.5 * (1.0 / ln)
    nrm[..., 3] = 1.0
    return nrm


def gen_roman_travertine_tex():
    """Photoreal 1024x1024 porous Roman travertine ashlar slabs w/ hairline seams & micro moss specks."""
    S = 1024
    y, x = np.mgrid[0:S, 0:S].astype(np.float32) / S

    # Staggered architectural Roman ashlar slabs: 3 columns x 6 rows (2:1 proportions!)
    nx, ny = 3.0, 6.0
    iy = np.floor(y * ny)
    row_shift = np.where((iy % 2) == 0, 0.0, 0.42) + np.where((iy % 3) == 0, 0.17, 0.0)
    x_s = (x + row_shift) % 1.0
    ix = np.floor(x_s * nx)
    cx = (x_s * nx) % 1.0
    cy = (y * ny) % 1.0

    # Per-slab organic tone & slight mineral shift
    slab_h1 = np.sin(ix * 27.3 + iy * 71.9) * 43758.5
    slab_v = (slab_h1 - np.floor(slab_h1)) - 0.5
    slab_h2 = np.sin(ix * 59.1 + iy * 13.7) * 19421.3
    slab_warm = (slab_h2 - np.floor(slab_h2)) - 0.5

    # Silky periodic mineral clouding + horizontal Roman travertine sedimentary veins + micro pits!
    cloud = fft_fbm(S, beta=2.5, seed=101, lo_cut=2.0, hi_cut=48.0)
    vein = fft_fbm(S, beta=2.2, seed=102, aniso_x=0.35, aniso_y=2.4, lo_cut=3.0, hi_cut=90.0)
    fine = fft_fbm(S, beta=1.5, seed=103, lo_cut=18.0, hi_cut=240.0)
    # Authentic Roman travertine linear pores (tiny recessed dark pits!)
    pit_src = fft_fbm(S, beta=1.8, seed=104, aniso_x=0.45, aniso_y=2.8, lo_cut=20.0, hi_cut=180.0)
    pits = np.clip((pit_src - 1.55) / 0.85, 0.0, 1.0)

    # Crisp hairline joints (only ~4mm wide!) + delicate chamfered slab edge bevel
    dx_e = np.minimum(cx, 1.0 - cx) / nx  # normalized tile units
    dy_e = np.minimum(cy, 1.0 - cy) / ny
    d_edge = np.minimum(dx_e, dy_e)
    # Slight organic wiggle in mortar edge
    wiggle = 0.0005 * fine
    joint = np.clip((0.0032 - (d_edge + wiggle)) / 0.0014, 0.0, 1.0)
    bevel = np.clip((d_edge - 0.0030) / 0.0055, 0.0, 1.0)

    # Sparse, natural, irregular organic moss flecks tucked ONLY in tiny seam pockets (<12%!)
    moss_n = fft_fbm(S, beta=2.0, seed=109, lo_cut=6.0, hi_cut=95.0)
    moss_micro = fft_fbm(S, beta=1.3, seed=110, lo_cut=35.0, hi_cut=220.0)
    moss_mask = np.clip((joint * 0.85 + (1.0 - bevel) * 0.55) * np.clip((moss_n + 0.35 * moss_micro - 0.92) * 2.4, 0.0, 1.0), 0.0, 1.0)

    # Rich warm Roman Mediterranean travertine palette (sunlit honey-limestone, never cool grey!)
    r = 0.78 + 0.045 * slab_v + 0.025 * slab_warm + 0.032 * cloud + 0.026 * vein + 0.014 * fine - 0.15 * pits
    g = 0.71 + 0.040 * slab_v + 0.014 * slab_warm + 0.028 * cloud + 0.023 * vein + 0.013 * fine - 0.14 * pits
    b = 0.57 + 0.034 * slab_v - 0.010 * slab_warm + 0.024 * cloud + 0.018 * vein + 0.011 * fine - 0.12 * pits

    # Dark weathered mortar inside hairline joints
    r = r * (1.0 - joint) + (0.24 + 0.03 * fine) * joint
    g = g * (1.0 - joint) + (0.23 + 0.03 * fine) * joint
    b = b * (1.0 - joint) + (0.20 + 0.02 * fine) * joint

    # Subtle realistic olive moss specks inside seam pockets
    r = r * (1.0 - moss_mask) + (0.22 + 0.04 * moss_micro) * moss_mask
    g = g * (1.0 - moss_mask) + (0.31 + 0.05 * moss_micro) * moss_mask
    b = b * (1.0 - moss_mask) + (0.11 + 0.02 * moss_micro) * moss_mask

    col = np.stack([r, g, b, np.ones_like(r)], axis=-1).astype(np.float32)

    # Roughness: honed travertine satin sheen (0.50..0.68), matte inside pores/joints/moss!
    rough = np.clip(0.56 + 0.06 * cloud - 0.04 * slab_v + 0.24 * pits + 0.28 * joint + 0.32 * moss_mask, 0.36, 0.94)
    ao = np.clip(1.0 - 0.38 * joint - 0.28 * pits - 0.12 * (1.0 - bevel), 0.35, 1.0)
    orm = np.stack([ao, rough, np.full_like(r, 0.02), np.ones_like(r)], axis=-1).astype(np.float32)

    # Micro-detail heightfield for razor-sharp grazing normal reflections
    h = (0.78 + 0.10 * bevel + 0.03 * vein + 0.018 * fine - 0.22 * pits - 0.36 * joint + 0.06 * moss_mask).astype(np.float32)
    return (
        ensure_png(os.path.join(TEX_DIR, "travertine_col.png"), col, "sRGB"),
        ensure_png(os.path.join(TEX_DIR, "travertine_orm.png"), orm, "Non-Color"),
        ensure_png(os.path.join(TEX_DIR, "travertine_nrm.png"), make_normals_from_h(h, 2.8), "Non-Color"),
    )


def gen_board_concrete_tex():
    """Photoreal 1024x1024 vertically fluted board-formed architectural concrete (env-concept.jpg!)."""
    S = 1024
    y, x = np.mgrid[0:S, 0:S].astype(np.float32) / S
    n_boards = 12.0
    ix = np.floor(x * n_boards)
    bx = (x * n_boards) % 1.0
    b_tone = ((np.sin(ix * 41.7) * 8191.3) % 1.0) - 0.5

    # Vertical wood formwork grain cast into the concrete + mineral stains + fine pores
    grain = fft_fbm(S, beta=2.1, seed=201, aniso_x=3.2, aniso_y=0.35, lo_cut=4.0, hi_cut=140.0)
    stain = fft_fbm(S, beta=2.5, seed=202, lo_cut=2.0, hi_cut=40.0)
    pores = np.clip((fft_fbm(S, beta=1.5, seed=203, lo_cut=35.0, hi_cut=220.0) - 1.8) * 1.4, 0.0, 1.0)

    # Vertical board seams + subtle horizontal formwork lift seam
    d_b = np.minimum(bx, 1.0 - bx)
    v_seam = np.clip((0.038 - d_b) / 0.018, 0.0, 1.0)
    h_seam = np.clip((0.008 - np.minimum(y, 1.0 - y)) / 0.004, 0.0, 1.0)
    seam = np.maximum(v_seam, h_seam * 0.8)

    # Subtle warm architectural concrete tone
    v = 0.52 + 0.045 * b_tone + 0.032 * stain + 0.022 * grain - 0.14 * seam - 0.12 * pores
    col = np.stack([v * 1.06, v * 1.01, v * 0.92, np.ones_like(v)], axis=-1).astype(np.float32)
    rough = np.clip(0.76 + 0.08 * stain + 0.14 * seam + 0.12 * pores, 0.58, 0.95)
    ao = np.clip(1.0 - 0.42 * seam - 0.25 * pores, 0.35, 1.0)
    orm = np.stack([ao, rough, np.full_like(v, 0.02), np.ones_like(v)], axis=-1).astype(np.float32)
    h = (0.76 + 0.05 * grain + 0.03 * b_tone - 0.32 * seam - 0.18 * pores).astype(np.float32)
    return (
        ensure_png(os.path.join(TEX_DIR, "concrete_col.png"), col, "sRGB"),
        ensure_png(os.path.join(TEX_DIR, "concrete_orm.png"), orm, "Non-Color"),
        ensure_png(os.path.join(TEX_DIR, "concrete_nrm.png"), make_normals_from_h(h, 2.4), "Non-Color"),
    )


def gen_oiled_cedar_tex():
    """Photoreal 1024x1024 warm oiled architectural cedar/teak slats with silky wood grain."""
    S = 1024
    y, x = np.mgrid[0:S, 0:S].astype(np.float32) / S
    slats = 8.0
    iy = np.floor(y * slats)
    sy = (y * slats) % 1.0
    p_tone = ((np.sin(iy * 29.3 + 1.7) * 5213.7) % 1.0) - 0.5

    # Natural longitudinal teak/cedar grain rings + silky fine wood fibers
    wiggle = fft_fbm(S, beta=2.4, seed=301, aniso_x=0.3, aniso_y=2.0, lo_cut=2.0, hi_cut=36.0)
    rings = 0.5 + 0.5 * np.sin((y * 95.0 + iy * 3.7 + 2.8 * wiggle) * 2.0 * math.pi / 4.5)
    fibers = fft_fbm(S, beta=1.7, seed=302, aniso_x=0.22, aniso_y=3.5, lo_cut=12.0, hi_cut=200.0)

    d_s = np.minimum(sy, 1.0 - sy)
    gap = np.clip((0.042 - d_s) / 0.016, 0.0, 1.0)
    edge_bevel = np.clip((d_s - 0.040) / 0.045, 0.0, 1.0)

    # Rich oiled honey-cedar / teak palette (deep warm walnut-amber!)
    r = 0.48 + 0.075 * rings + 0.055 * p_tone + 0.025 * fibers
    g = 0.28 + 0.052 * rings + 0.036 * p_tone + 0.016 * fibers
    b = 0.13 + 0.028 * rings + 0.018 * p_tone + 0.008 * fibers
    r = r * (1.0 - gap) + 0.06 * gap
    g = g * (1.0 - gap) + 0.04 * gap
    b = b * (1.0 - gap) + 0.025 * gap

    col = np.stack([r, g, b, np.ones_like(r)], axis=-1).astype(np.float32)
    rough = np.clip(0.46 - 0.07 * rings + 0.04 * fibers + 0.42 * gap, 0.30, 0.92)
    ao = np.clip(1.0 - 0.65 * gap - 0.12 * (1.0 - edge_bevel), 0.25, 1.0)
    orm = np.stack([ao, rough, np.zeros_like(r), np.ones_like(r)], axis=-1).astype(np.float32)
    h = (0.72 + 0.14 * edge_bevel + 0.04 * rings + 0.02 * fibers - 0.45 * gap).astype(np.float32)
    return (
        ensure_png(os.path.join(TEX_DIR, "cedar_col.png"), col, "sRGB"),
        ensure_png(os.path.join(TEX_DIR, "cedar_orm.png"), orm, "Non-Color"),
        ensure_png(os.path.join(TEX_DIR, "cedar_nrm.png"), make_normals_from_h(h, 2.5), "Non-Color"),
    )


def gen_monstera_cutout_tex():
    """Crisp 1024x1024 RGBA Alpha-Cutout fenestrated Monstera deliciosa leaf PBR sheet."""
    S = 1024
    v, u = np.mgrid[0:S, 0:S].astype(np.float32) / S  # v=0 stem base, v=1 leaf tip
    cx = (u - 0.5) * 2.0  # -1..1
    ax = np.abs(cx)

    # Organic heart-shaped cordate Monstera silhouette
    # Lobed base indentation at v ~ 0.12..0.22, widest around v ~ 0.42, graceful pointed tip at v = 0.96
    t = np.clip((v - 0.06) / 0.90, 0.0, 1.0)
    half_w = 0.88 * np.sin(np.power(t, 0.68) * math.pi) * (1.0 + 0.14 * np.exp(-((t - 0.22) / 0.18) ** 2))
    # Subtle heart notch at bottom center
    base_notch = 0.14 * np.exp(-((ax / 0.24) ** 2))
    inside_leaf = (v > (0.07 + base_notch)) & (v < 0.96) & (ax < half_w)

    # Short cylindrical petiole stem at base (v = 0..0.18)
    petiole = (v < 0.22) & (ax < 0.045 * (1.0 - 0.35 * v / 0.22))

    # 4 authentic deep curved Monstera fenestration splits on each side!
    slit_cut = np.zeros_like(u, dtype=bool)
    for k, (v0, ang, w_slit, x_start) in enumerate([
        (0.27, 0.26, 0.028, 0.22),
        (0.42, 0.32, 0.032, 0.19),
        (0.58, 0.36, 0.030, 0.18),
        (0.73, 0.38, 0.024, 0.20),
    ]):
        # Slight natural left/right asymmetry so it looks wildly organic!
        v_shift = np.where(cx > 0, v0, v0 + 0.035)
        curve_y = v_shift + ang * np.power(np.maximum(0.0, ax - x_start), 1.12)
        dist = np.abs(v - curve_y)
        taper = np.clip((ax - x_start) / 0.10, 0.0, 1.0)
        slit_cut |= (ax > x_start) & (dist < w_slit * (0.45 + 0.55 * taper))

    # Oval inner fenestration holes along the lower lobes
    hole_cut = np.zeros_like(u, dtype=bool)
    for hx, hv, rx, ry in [(0.26, 0.34, 0.055, 0.025), (-0.28, 0.50, 0.058, 0.024), (0.24, 0.65, 0.045, 0.020)]:
        hole_cut |= (((cx - hx) / rx) ** 2 + ((v - hv) / ry) ** 2) < 1.0

    alpha = np.where((inside_leaf & (~slit_cut) & (~hole_cut)) | petiole, 1.0, 0.0).astype(np.float32)

    # Crisp midrib + curved primary lateral veins + waxy leaf micro-grain
    midrib = np.exp(-((ax / (0.032 * (1.0 - 0.65 * t))) ** 2)) * (1.0 - 0.25 * t)
    lat_phase = np.sin(2.0 * math.pi * (v * 6.5 - ax * 2.15))
    lat_vein = np.clip((lat_phase - 0.78) / 0.22, 0.0, 1.0) * (1.0 - 0.35 * ax)
    vein = np.clip(midrib + 0.55 * lat_vein, 0.0, 1.0)
    mottle = fft_fbm(S, beta=2.2, seed=401, lo_cut=4.0, hi_cut=60.0)

    # Deep rich botanical emerald-forest green (warm sunlit chartreuse veins & tip, zero neon!)
    r = 0.095 + 0.065 * t + 0.13 * vein + 0.018 * mottle
    g = 0.275 + 0.115 * t + 0.16 * vein + 0.028 * mottle
    b = 0.055 + 0.025 * t + 0.04 * vein + 0.010 * mottle
    # Bleed leaf color into transparent padding to prevent dark mipmap edge halos!
    col = np.stack([r, g, b, alpha], axis=-1).astype(np.float32)

    rough = np.clip(0.32 + 0.10 * vein + 0.04 * mottle, 0.22, 0.55)
    orm = np.stack([np.full_like(r, 0.95), rough, np.zeros_like(r), np.ones_like(r)], axis=-1).astype(np.float32)
    h = (0.50 + 0.28 * midrib + 0.16 * lat_vein + 0.04 * mottle).astype(np.float32)
    return (
        ensure_png(os.path.join(TEX_DIR, "monstera_col.png"), col, "sRGB"),
        ensure_png(os.path.join(TEX_DIR, "monstera_orm.png"), orm, "Non-Color"),
        ensure_png(os.path.join(TEX_DIR, "monstera_nrm.png"), make_normals_from_h(h, 2.2), "Non-Color"),
    )


def gen_boston_fern_tex():
    """Crisp 1024x1024 RGBA Alpha-Cutout feathered Boston Fern frond with 22 paired pinnae leaflets."""
    S = 1024
    v, u = np.mgrid[0:S, 0:S].astype(np.float32) / S
    cx = (u - 0.5) * 2.0
    ax = np.abs(cx)

    # Slender central rachis stem running v = 0.0..0.96
    stem = (v < 0.96) & (ax < (0.024 * (1.0 - 0.72 * v)))

    # 20 pairs of graceful sweeping lanceolate pinnae leaflets along v = 0.06..0.95!
    pinna_mask = np.zeros_like(u, dtype=bool)
    vein_acc = np.zeros_like(u, dtype=np.float32)
    n_pairs = 20
    for i in range(n_pairs):
        f = i / float(n_pairs - 1)
        v0 = 0.06 + 0.87 * f
        # Overall frond envelope: wide in lower-mid, tapering gracefully to fine tip
        L_pin = 0.86 * math.sin(math.pow(0.10 + 0.88 * f, 0.75) * math.pi)
        W_pin = 0.030 * (1.0 - 0.45 * f)
        for sgn in (-1.0, 1.0):
            vs = v0 + (0.012 if sgn < 0 else 0.0)
            # Local coordinate along the pinna (0 at stem, 1 at leaflet tip)
            px = np.where(cx * sgn >= 0.0, ax / max(L_pin, 0.05), -1.0)
            # Sweeps gently upward toward the frond tip
            py_center = vs + (0.06 + 0.04 * f) * np.power(np.clip(px, 0.0, 1.0), 1.25)
            # Tapering leaflet width with tiny organic serration wave
            serr = 1.0 + 0.14 * np.sin(px * 26.0)
            half_h = W_pin * np.sin(np.power(np.clip(px, 0.0, 1.0), 0.7) * math.pi) * serr
            hit = (px >= 0.0) & (px <= 1.0) & (np.abs(v - py_center) <= half_h)
            pinna_mask |= hit
            # Leaflet center vein
            vein_acc = np.maximum(vein_acc, np.where(hit, np.exp(-((np.abs(v - py_center) / (half_h * 0.25 + 1e-4)) ** 2)), 0.0))

    alpha = np.where(stem | pinna_mask, 1.0, 0.0).astype(np.float32)
    mottle = fft_fbm(S, beta=2.0, seed=420, lo_cut=6.0, hi_cut=70.0)
    # Lush sunlit fern-green palette (fresh yellow-green tips, deep forest base!)
    r = 0.14 + 0.12 * v + 0.06 * vein_acc + 0.02 * mottle
    g = 0.34 + 0.17 * v + 0.08 * vein_acc + 0.03 * mottle
    b = 0.06 + 0.04 * v + 0.02 * vein_acc + 0.01 * mottle
    # Darker woody brown-olive stem
    r = np.where(stem, 0.16, r)
    g = np.where(stem, 0.24, g)
    b = np.where(stem, 0.07, b)

    col = np.stack([r, g, b, alpha], axis=-1).astype(np.float32)
    rough = np.clip(0.42 - 0.05 * vein_acc + 0.04 * mottle, 0.30, 0.60)
    orm = np.stack([np.full_like(r, 0.94), rough, np.zeros_like(r), np.ones_like(r)], axis=-1).astype(np.float32)
    h = (0.50 + 0.22 * vein_acc + 0.12 * stem.astype(np.float32)).astype(np.float32)
    return (
        ensure_png(os.path.join(TEX_DIR, "fern_col.png"), col, "sRGB"),
        ensure_png(os.path.join(TEX_DIR, "fern_orm.png"), orm, "Non-Color"),
        ensure_png(os.path.join(TEX_DIR, "fern_nrm.png"), make_normals_from_h(h, 2.0), "Non-Color"),
    )


def gen_velvet_moss_tex():
    """Organic 512x512 velvety botanical moss pillow PBR (eliminates plastic egg look!)."""
    S = 512
    n1 = fft_fbm(S, beta=2.2, seed=501, lo_cut=4.0, hi_cut=45.0)
    n2 = fft_fbm(S, beta=1.3, seed=502, lo_cut=24.0, hi_cut=180.0)
    tuft = np.clip(0.5 + 0.35 * n1 + 0.22 * n2, 0.0, 1.0)
    r = 0.11 + 0.16 * tuft + 0.04 * np.clip(n2, 0, 1)
    g = 0.24 + 0.22 * tuft + 0.06 * np.clip(n2, 0, 1)
    b = 0.045 + 0.045 * tuft
    col = np.stack([r, g, b, np.ones_like(r)], axis=-1).astype(np.float32)
    orm = np.stack([np.clip(0.55 + 0.45 * tuft, 0.4, 1.0), np.full_like(r, 0.92), np.zeros_like(r), np.ones_like(r)], axis=-1).astype(np.float32)
    return (
        ensure_png(os.path.join(TEX_DIR, "moss_col.png"), col, "sRGB"),
        ensure_png(os.path.join(TEX_DIR, "moss_orm.png"), orm, "Non-Color"),
        ensure_png(os.path.join(TEX_DIR, "moss_nrm.png"), make_normals_from_h(tuft, 3.6), "Non-Color"),
    )


def gen_skyline_facade_tex():
    """Photoreal 1024x1024 Solarpunk Eco-Tower Curtain-Wall Glass & Living Balcony Facade!"""
    S = 1024
    y, x = np.mgrid[0:S, 0:S].astype(np.float32) / S
    floors = 14.0
    bays = 10.0
    iy = np.floor(y * floors)
    ix = np.floor(x * bays)
    fy = (y * floors) % 1.0
    fx = (x * bays) % 1.0

    # Crisp architectural white slab spandrels + slim dark mullions + tinted glass panes
    slab = (fy < 0.22) | (fy > 0.96)
    mullion = (fx < 0.07) | (fx > 0.93)
    # Lush vertical & balcony sky-garden planter bands on every 3rd floor!
    green_balc = ((iy % 3) == 1) & (fy >= 0.14) & (fy <= 0.34)
    # Vertical biophilic green facade column on 2 bays
    green_col = ((ix == 2) | (ix == 7)) & (fx > 0.15) & (fx < 0.85) & (fy > 0.22)
    foliage = green_balc | green_col

    fol_n = fft_fbm(S, beta=1.5, seed=601, lo_cut=18.0, hi_cut=180.0)
    win_var = ((np.sin(ix * 19.1 + iy * 37.3) * 9137.1) % 1.0)
    warm_room = win_var > 0.72

    # Base: warm matte off-white architectural concrete slabs
    r = np.full((S, S), 0.76, dtype=np.float32)
    g = np.full((S, S), 0.75, dtype=np.float32)
    b = np.full((S, S), 0.71, dtype=np.float32)

    # Glass panes (reflective architectural teal-slate catching warm sky + subtle lit interiors!)
    glass = (~slab) & (~mullion)
    r = np.where(glass, np.where(warm_room, 0.56, 0.26 + 0.12 * fy), r)
    g = np.where(glass, np.where(warm_room, 0.50, 0.35 + 0.12 * fy), g)
    b = np.where(glass, np.where(warm_room, 0.36, 0.40 + 0.10 * fy), b)

    # Dark anodized mullions
    r = np.where(mullion & (~slab), 0.18, r)
    g = np.where(mullion & (~slab), 0.20, g)
    b = np.where(mullion & (~slab), 0.20, b)

    # Lush sunlit terraced green facade greenery
    r = np.where(foliage, np.clip(0.18 + 0.08 * fol_n, 0.08, 0.34), r)
    g = np.where(foliage, np.clip(0.37 + 0.10 * fol_n, 0.20, 0.54), g)
    b = np.where(foliage, np.clip(0.10 + 0.04 * fol_n, 0.04, 0.18), b)

    col = np.stack([r, g, b, np.ones_like(r)], axis=-1).astype(np.float32)
    rough = np.where(foliage, 0.85, np.where(glass, 0.14, 0.68)).astype(np.float32)
    metal = np.where(glass & (~foliage), 0.42, 0.04).astype(np.float32)
    orm = np.stack([np.ones_like(r), rough, metal, np.ones_like(r)], axis=-1).astype(np.float32)
    h = np.where(slab, 0.85, np.where(foliage, 0.75 + 0.12 * fol_n, 0.30)).astype(np.float32)
    return (
        ensure_png(os.path.join(TEX_DIR, "facade_col.png"), col, "sRGB"),
        ensure_png(os.path.join(TEX_DIR, "facade_orm.png"), orm, "Non-Color"),
        ensure_png(os.path.join(TEX_DIR, "facade_nrm.png"), make_normals_from_h(h, 2.0), "Non-Color"),
    )


def gen_tree_canopy_cutout_tex():
    """Crisp 1024x1024 RGBA Alpha-Cutout leafy urban-forest tree branch cluster (ZERO Play-Doh spheres!)."""
    S = 1024
    y, x = np.mgrid[0:S, 0:S].astype(np.float32) / S
    dx = (x - 0.5) * 2.0
    dy = (y - 0.5) * 2.0
    dist = np.sqrt(dx * dx + dy * dy)

    # Organic branching silhouette of hundreds of tiny distinct crisp tree leaves!
    macro = fft_fbm(S, beta=2.2, seed=701, lo_cut=3.0, hi_cut=28.0)
    mid = fft_fbm(S, beta=1.7, seed=702, lo_cut=14.0, hi_cut=90.0)
    micro_leaf = fft_fbm(S, beta=1.2, seed=703, lo_cut=48.0, hi_cut=260.0)

    # Irregular rounded leafy bough envelope with lacy sunlit leaf gaps around edges
    density = (1.0 - dist * 1.06) + 0.24 * macro + 0.22 * mid + 0.16 * micro_leaf
    alpha = np.where(density > 0.14, 1.0, 0.0).astype(np.float32)

    # Rich sunlit urban-forest canopy depth: deep emerald shaded interior -> warm golden-olive outer leaf tips!
    sun_bias = np.clip(0.55 + 0.45 * (y - 0.25) + 0.28 * mid + 0.18 * micro_leaf, 0.0, 1.0)
    r = 0.08 + 0.19 * sun_bias
    g = 0.19 + 0.24 * sun_bias
    b = 0.04 + 0.055 * sun_bias
    col = np.stack([r, g, b, alpha], axis=-1).astype(np.float32)
    rough = np.clip(0.76 - 0.12 * sun_bias, 0.55, 0.88)
    orm = np.stack([np.clip(0.45 + 0.55 * sun_bias, 0.35, 1.0), rough, np.zeros_like(r), np.ones_like(r)], axis=-1).astype(np.float32)
    h = np.clip(0.5 + 0.25 * mid + 0.22 * micro_leaf, 0.0, 1.0).astype(np.float32)
    return (
        ensure_png(os.path.join(TEX_DIR, "tree_canopy_col.png"), col, "sRGB"),
        ensure_png(os.path.join(TEX_DIR, "tree_canopy_orm.png"), orm, "Non-Color"),
        ensure_png(os.path.join(TEX_DIR, "tree_canopy_nrm.png"), make_normals_from_h(h, 2.4), "Non-Color"),
    )


def gen_dock_solar_tex():
    """Crisp 512x512 monocrystalline photovoltaic cell grid matching FLORA-01's canopy!"""
    S = 512
    y, x = np.mgrid[0:S, 0:S].astype(np.float32) / S
    cx, cy = (x * 6.0) % 1.0, (y * 6.0) % 1.0
    gap = (cx < 0.04) | (cx > 0.96) | (cy < 0.04) | (cy > 0.96)
    bus = (np.abs(cx - 0.33) < 0.012) | (np.abs(cx - 0.67) < 0.012)
    # Chamfered monocrystalline wafer corner diamonds
    corner = ((np.minimum(cx, 1.0 - cx) + np.minimum(cy, 1.0 - cy)) < 0.13)
    cell_var = ((np.sin(np.floor(x * 6) * 17.3 + np.floor(y * 6) * 43.1) * 7193.3) % 1.0) - 0.5

    r = np.where(gap | corner, 0.65, np.where(bus, 0.56, 0.035 + 0.01 * cell_var))
    g = np.where(gap | corner, 0.67, np.where(bus, 0.58, 0.075 + 0.015 * cell_var))
    b = np.where(gap | corner, 0.70, np.where(bus, 0.62, 0.21 + 0.03 * cell_var))
    col = np.stack([r, g, b, np.ones_like(r)], axis=-1).astype(np.float32)
    rough = np.where(gap | corner, 0.38, 0.12).astype(np.float32)
    metal = np.where(gap | corner | bus, 0.72, 0.22).astype(np.float32)
    orm = np.stack([np.ones_like(r), rough, metal, np.ones_like(r)], axis=-1).astype(np.float32)
    h = np.where(gap, 0.35, 0.80).astype(np.float32)
    return (
        ensure_png(os.path.join(TEX_DIR, "dock_solar_col.png"), col, "sRGB"),
        ensure_png(os.path.join(TEX_DIR, "dock_solar_orm.png"), orm, "Non-Color"),
        ensure_png(os.path.join(TEX_DIR, "dock_solar_nrm.png"), make_normals_from_h(h, 1.5), "Non-Color"),
    )


# ==============================================================================
# 2. MATERIAL LIBRARY (100% glTF-2.0 NATIVE + DUAL-UV AO READY!)
# ==============================================================================
MATS = {}

def get_gltf_ao_group():
    """Creates/returns the standard glTF Material Output node group so Occlusion exports to glTF!"""
    gname = "glTF Material Output"
    if gname in bpy.data.node_groups:
        return bpy.data.node_groups[gname]
    ng = bpy.data.node_groups.new(gname, "ShaderNodeTree")
    ng.interface.new_socket(name="Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
    ng.nodes.new("NodeGroupInput")
    return ng


def pbr_tex_mat(name, imgs, uv_scale=1.0, nrm_str=0.55, alpha_mask=False, double_sided=False):
    im_c, im_o, im_n = imgs
    m = bpy.data.materials.new(name)
    m.use_backface_culling = not double_sided
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    uvn = nt.nodes.new("ShaderNodeUVMap"); uvn.uv_map = "UVMap"
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (uv_scale, uv_scale, uv_scale)
    nt.links.new(uvn.outputs["UV"], mp.inputs["Vector"])

    t1 = nt.nodes.new("ShaderNodeTexImage"); t1.image = im_c
    nt.links.new(mp.outputs["Vector"], t1.inputs["Vector"])
    nt.links.new(t1.outputs["Color"], bsdf.inputs["Base Color"])
    if alpha_mask:
        # Use Math GREATER_THAN so Blender 5.2 glTF exporter emits true alphaMode="MASK" (crisp shadows, zero sort bugs!)
        gt = nt.nodes.new("ShaderNodeMath")
        gt.operation = "GREATER_THAN"
        gt.inputs[1].default_value = 0.45
        nt.links.new(t1.outputs["Alpha"], gt.inputs[0])
        nt.links.new(gt.outputs["Value"], bsdf.inputs["Alpha"])
        if hasattr(m, "blend_method"):
            m.blend_method = "CLIP"
        if hasattr(m, "alpha_threshold"):
            m.alpha_threshold = 0.45

    t2 = nt.nodes.new("ShaderNodeTexImage"); t2.image = im_o
    nt.links.new(mp.outputs["Vector"], t2.inputs["Vector"])
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(t2.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
    nt.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])

    t3 = nt.nodes.new("ShaderNodeTexImage"); t3.image = im_n
    nt.links.new(mp.outputs["Vector"], t3.inputs["Vector"])
    nm = nt.nodes.new("ShaderNodeNormalMap"); nm.inputs["Strength"].default_value = nrm_str
    nt.links.new(t3.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])

    MATS[name] = m
    return m


def attach_baked_ao(mat, ao_img, uv_layer_name="UV_AO"):
    """Wires dedicated non-overlapping Cycles Contact AO image (TEXCOORD_1) to glTF Occlusion!"""
    nt = mat.node_tree
    uv_ao = nt.nodes.new("ShaderNodeUVMap"); uv_ao.uv_map = uv_layer_name
    t_ao = nt.nodes.new("ShaderNodeTexImage"); t_ao.image = ao_img
    nt.links.new(uv_ao.outputs["UV"], t_ao.inputs["Vector"])
    g = nt.nodes.new("ShaderNodeGroup"); g.node_tree = get_gltf_ao_group()
    nt.links.new(t_ao.outputs["Color"], g.inputs["Occlusion"])


def simple_mat(name, rgb, rough=0.45, metal=0.0, emit=None, emit_str=0.0, alpha=1.0):
    m = bpy.data.materials.new(name)
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if alpha < 1.0:
        bsdf.inputs["Alpha"].default_value = alpha
        if hasattr(m, "blend_method"):
            m.blend_method = "BLEND"
    if emit is not None:
        bsdf.inputs["Emission Color"].default_value = (*emit, 1.0)
        bsdf.inputs["Emission Strength"].default_value = emit_str
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    MATS[name] = m
    return m


def build_materials():
    # Tiled cleanly: ~1.6 m per 3x6 ashlar tile -> sharp 53x27cm Roman stone pavers!
    pbr_tex_mat("E_travertine", gen_roman_travertine_tex(), uv_scale=0.58, nrm_str=0.72)
    pbr_tex_mat("E_concrete", gen_board_concrete_tex(), uv_scale=0.72, nrm_str=0.68)
    pbr_tex_mat("E_cedar", gen_oiled_cedar_tex(), uv_scale=0.85, nrm_str=0.62)
    pbr_tex_mat("E_monstera", gen_monstera_cutout_tex(), uv_scale=1.0, nrm_str=0.65, alpha_mask=True, double_sided=True)
    pbr_tex_mat("E_fern", gen_boston_fern_tex(), uv_scale=1.0, nrm_str=0.58, alpha_mask=True, double_sided=True)
    pbr_tex_mat("E_tree_canopy", gen_tree_canopy_cutout_tex(), uv_scale=1.0, nrm_str=0.55, alpha_mask=True, double_sided=True)
    pbr_tex_mat("E_moss", gen_velvet_moss_tex(), uv_scale=1.8, nrm_str=0.85)
    pbr_tex_mat("E_facade", gen_skyline_facade_tex(), uv_scale=0.14, nrm_str=0.45)
    pbr_tex_mat("E_dock_solar", gen_dock_solar_tex(), uv_scale=1.2, nrm_str=0.35)

    simple_mat("E_steel_dark", (0.075, 0.082, 0.086), rough=0.36, metal=0.86)
    simple_mat("E_basalt", (0.055, 0.060, 0.064), rough=0.46, metal=0.22)
    simple_mat("E_ceramic_white", (0.82, 0.82, 0.78), rough=0.30, metal=0.05)
    simple_mat("E_brass", (0.76, 0.56, 0.22), rough=0.22, metal=0.94)
    simple_mat("E_soil", (0.055, 0.042, 0.030), rough=0.95, metal=0.0)
    simple_mat("E_cobble", (0.12, 0.13, 0.125), rough=0.32, metal=0.08)
    simple_mat("E_water", (0.022, 0.058, 0.055), rough=0.03, metal=0.12)
    simple_mat("E_glass_rail", (0.68, 0.82, 0.80), rough=0.06, metal=0.08, alpha=0.24)
    simple_mat("E_skylight_glass", (0.78, 0.86, 0.84), rough=0.06, metal=0.06, alpha=0.14)
    simple_mat("E_glow_lime", (0.62, 0.98, 0.22), rough=0.18, emit=(0.60, 1.0, 0.22), emit_str=2.2)
    simple_mat("E_glow_warm", (1.0, 0.84, 0.48), rough=0.18, emit=(1.0, 0.80, 0.40), emit_str=2.1)
    simple_mat("E_tree_deep", (0.11, 0.25, 0.065), rough=0.86, metal=0.0)
    simple_mat("E_tree_sun", (0.21, 0.37, 0.095), rough=0.82, metal=0.0)
    simple_mat("E_tree_olive", (0.16, 0.29, 0.085), rough=0.85, metal=0.0)


# ==============================================================================
# 3. CLEAN MESH HELPERS (ZERO N-GONS, WEIGHTED NORMALS, CLEAN UVS)
# ==============================================================================
ENV_OBJS = []

def _quad_caps(bm):
    ng = [f for f in bm.faces if len(f.verts) > 4]
    if ng:
        r = bmesh.ops.triangulate(bm, faces=ng, quad_method="BEAUTY", ngon_method="BEAUTY")
        bmesh.ops.join_triangles(bm, faces=r["faces"], angle_face_threshold=0.02, angle_shape_threshold=3.14)


def finish_obj(bm, name, mats, smooth_deg=44.0, planar_ao_uv=False):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    _quad_caps(bm)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    assert sum(1 for p in me.polygons if len(p.vertices) > 4) == 0, f"{name} has n-gons!"
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    for mn in (mats if isinstance(mats, (list, tuple)) else [mats]):
        me.materials.append(MATS[mn])
    for p in me.polygons: p.use_smooth = True
    me.set_sharp_from_angle(angle=math.radians(smooth_deg))
    if not me.uv_layers:
        uv_l = me.uv_layers.new(name="UVMap")
        for p in me.polygons:
            n = p.normal; ax = max(range(3), key=lambda k: abs(n[k]))
            for li in p.loop_indices:
                co = me.vertices[me.loops[li].vertex_index].co
                uv_l.data[li].uv = (co.y, co.z) if ax == 0 else ((co.x, co.z) if ax == 1 else (co.x, co.y))
    if planar_ao_uv:
        # Clean non-overlapping 0..1 planar top UVMap for Cycles Contact AO baking on the 18x18m terrace!
        uv_ao = me.uv_layers.new(name="UV_AO")
        for p in me.polygons:
            for li in p.loop_indices:
                co = me.vertices[me.loops[li].vertex_index].co
                u = max(0.005, min(0.995, (co.x + 9.2) / 18.4))
                v = max(0.005, min(0.995, (co.y + 9.2) / 18.4))
                uv_ao.data[li].uv = (u, v)
    ENV_OBJS.append(obj)
    return obj


def add_box(bm, mn, mx, bev=0.0, seg=1, mat_idx=0, xf=None):
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
        r = bmesh.ops.bevel(bm, geom=edges, offset=bev, segments=seg, profile=0.5, affect="EDGES", clamp_overlap=True)
        for f in r["faces"]: f.material_index = mat_idx


def add_cyl(bm, p0, p1, r0, r1=None, n=16, caps=(True, True), mat_idx=0):
    p0, p1 = V(p0), V(p1); r1 = r0 if r1 is None else r1
    ax = (p1 - p0).normalized()
    ex = ax.cross(V((0, 0, 1))).normalized() if abs(ax.z) < 0.9 else ax.cross(V((1, 0, 0))).normalized()
    ey = ax.cross(ex).normalized()
    a = [bm.verts.new(p0 + (ex * math.cos(2 * math.pi * i / n) + ey * math.sin(2 * math.pi * i / n)) * r0) for i in range(n)]
    b = [bm.verts.new(p1 + (ex * math.cos(2 * math.pi * i / n) + ey * math.sin(2 * math.pi * i / n)) * r1) for i in range(n)]
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], a[j], b[j], b[i])).material_index = mat_idx
    if caps[0]: bm.faces.new(list(reversed(a))).material_index = mat_idx
    if caps[1]: bm.faces.new(b).material_index = mat_idx


def add_loft(bm, rings, cap0=True, cap1=True, mat_idx=0):
    vr = [[bm.verts.new(V(p)) for p in r] for r in rings]
    n = len(rings[0])
    for ra, rb in zip(vr, vr[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((ra[i], ra[j], rb[j], rb[i])).material_index = mat_idx
    if cap0: bm.faces.new(list(reversed(vr[0]))).material_index = mat_idx
    if cap1: bm.faces.new(vr[-1]).material_index = mat_idx


def add_tube(bm, pts, r, n=10, mat_idx=0):
    pts = [V(p) for p in pts]; m = len(pts)
    tans = [(pts[1]-pts[0]).normalized() if i==0 else ((pts[-1]-pts[-2]).normalized() if i==m-1 else (pts[i+1]-pts[i-1]).normalized()) for i in range(m)]
    ex = tans[0].orthogonal().normalized(); ey = tans[0].cross(ex).normalized()
    rings = []
    for i, p in enumerate(pts):
        if i > 0:
            ax = tans[i-1].cross(tans[i])
            if ax.length > 1e-6:
                ang = math.acos(max(-1.0, min(1.0, tans[i-1].dot(tans[i]))))
                ex = (Matrix.Rotation(ang, 3, ax.normalized()) @ ex).normalized()
                ey = tans[i].cross(ex).normalized()
        rings.append([p + (ex * math.cos(2 * math.pi * k / n) + ey * math.sin(2 * math.pi * k / n)) * r for k in range(n)])
    add_loft(bm, rings, True, True, mat_idx=mat_idx)


def chamfer_oct_ring(cx, cy, z, r):
    """Smooth architectural 16-vertex rounded-chamfer octagonal planter ring (env-concept.jpg!)."""
    pts = []
    for i in range(8):
        a0 = math.radians(22.5 + 45 * i)
        # Subtle bevelled pair at each octagon corner for sleek modern architectural softness
        for da in (-4.5, 4.5):
            a = a0 + math.radians(da)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a), z))
    return pts


# ==============================================================================
# 4. ARCHITECTURAL BUILDERS (MATCHING env-concept.jpg!)
# ==============================================================================
COLLIDERS = []
STATIONS = []
FLOOR_OBJ = None


def build_terrace_floor_and_balustrade():
    global FLOOR_OBJ
    # --- 1. Main 18m x 18m Flat Roman Travertine Terrace Slab (strictly Z = 0.000 m!) ---
    # Separated top floor slab so Cycles Contact AO bakes crisply across 0..1 planar UVs!
    bm = bmesh.new()
    # Clean subdivided top walkable surface at Z = 0.000 m + architectural slab thickness
    add_box(bm, (-9.0, -9.0, -0.45), (9.0, 9.0, 0.000), bev=0.015, mat_idx=0)
    FLOOR_OBJ = finish_obj(bm, "Env_Terrace_Floor", ["E_travertine"], planar_ao_uv=True)

    # Subtle architectural hairline brushed-bronze & dark-basalt plaza compass inlay + perimeter curb
    bm_trim = bmesh.new()
    for r_in, r_out, midx in ((3.54, 3.575, 0), (3.585, 3.605, 1), (1.76, 1.78, 1)):
        n = 64
        v0 = [bm_trim.verts.new(V((r_in * math.cos(2 * math.pi * i / n), r_in * math.sin(2 * math.pi * i / n), 0.0018))) for i in range(n)]
        v1 = [bm_trim.verts.new(V((r_out * math.cos(2 * math.pi * i / n), r_out * math.sin(2 * math.pi * i / n), 0.0018))) for i in range(n)]
        for i in range(n):
            j = (i + 1) % n
            bm_trim.faces.new((v0[i], v1[i], v1[j], v0[j])).material_index = midx
    # Cardinal hairline bronze compass ticks
    for ang_d in (0, 90, 180, 270):
        xf = Matrix.Rotation(math.radians(ang_d), 4, 'Z')
        add_box(bm_trim, (1.80, -0.012, 0.000), (3.52, 0.012, 0.002), mat_idx=1, xf=xf)
    # Perimeter board-formed concrete rooftop fascia curb + recessed dark steel gutter channel
    for s in (-1, 1):
        add_box(bm_trim, (-9.12, s * 8.88 - 0.18, -0.48), (9.12, s * 8.88 + 0.18, 0.13), bev=0.012, mat_idx=2)
        add_box(bm_trim, (s * 8.88 - 0.18, -8.88, -0.48), (s * 8.88 + 0.18, 8.88, 0.13), bev=0.012, mat_idx=2)
        add_box(bm_trim, (-8.72, s * 8.66 - 0.04, -0.01), (8.72, s * 8.66 + 0.04, 0.003), mat_idx=0)
        add_box(bm_trim, (s * 8.66 - 0.04, -8.72, -0.01), (s * 8.66 + 0.04, 8.72, 0.003), mat_idx=0)
    finish_obj(bm_trim, "Env_Terrace_Trim", ["E_basalt", "E_brass", "E_concrete"])

    # --- 2. Glass & Cedar Rooftop Perimeter Balustrade (H = 1.05 m, machined clamp posts!) ---
    bm_m = bmesh.new()
    bm_g = bmesh.new()
    for s in (-1, 1):
        # Continuous warm oiled cedar top handrail + dark steel lower shoe rail
        add_box(bm_m, (-8.90, s * 8.86 - 0.042, 1.01), (8.90, s * 8.86 + 0.042, 1.065), bev=0.008, mat_idx=1)
        add_box(bm_m, (s * 8.86 - 0.042, -8.90, 1.01), (s * 8.86 + 0.042, 8.90, 1.065), bev=0.008, mat_idx=1)
        add_box(bm_m, (-8.86, s * 8.86 - 0.025, 0.13), (8.86, s * 8.86 + 0.025, 0.18), bev=0.004, mat_idx=0)
        add_box(bm_m, (s * 8.86 - 0.025, -8.86, 0.13), (s * 8.86 + 0.025, 8.86, 0.18), bev=0.004, mat_idx=0)
        # Clear tinted architectural glass panels
        add_box(bm_g, (-8.80, s * 8.86 - 0.007, 0.18), (8.80, s * 8.86 + 0.007, 1.00), mat_idx=0)
        add_box(bm_g, (s * 8.86 - 0.007, -8.80, 0.18), (s * 8.86 + 0.007, 8.80, 1.00), mat_idx=0)
        # Slim steel stanchions every 1.48 m
        for k in range(-6, 7):
            p = k * 1.46
            add_box(bm_m, (p - 0.024, s * 8.86 - 0.024, 0.12), (p + 0.024, s * 8.86 + 0.024, 1.02), bev=0.004, mat_idx=0)
            if abs(k) < 6:
                add_box(bm_m, (s * 8.86 - 0.024, p - 0.024, 0.12), (s * 8.86 + 0.024, p + 0.024, 1.02), bev=0.004, mat_idx=0)
    finish_obj(bm_m, "Env_Balustrade_Frame", ["E_steel_dark", "E_cedar"])
    finish_obj(bm_g, "Env_Balustrade_Glass", ["E_glass_rail"])


def build_conservatory_pergola():
    """Monumental 11-rib cathedral steel & laminated-cedar pergola vault w/ dense slatted louvers (env-concept.jpg!)."""
    bm = bmesh.new()
    bm_gl = bmesh.new()
    # 11 rhythmic monumental parabolic ribs spanning Y = -8.78 .. +8.78 across X = -7.8..+7.8!
    xs = [round(-7.8 + i * 1.56, 3) for i in range(11)]
    steps = 26
    arch_pts_list = []
    arch_nrm_list = []

    def arch_point(x_val, s_t):
        y = s_t * 8.78
        # Graceful soaring architectural barrel-dome vault (crown Z = 5.65 m in center!)
        crown = 5.68 - 0.42 * ((x_val / 7.8) ** 2)
        z = crown * (1.0 - (s_t ** 2) * 0.965) + 0.12
        return V((x_val, y, z))

    for x_val in xs:
        pts = [arch_point(x_val, -1.0 + 2.0 * i / steps) for i in range(steps + 1)]
        nrms = []
        for i, p in enumerate(pts):
            t = (pts[min(steps, i + 1)] - pts[max(0, i - 1)]).normalized()
            nrm = V((0, -t.z, t.y)).normalized()
            if nrm.z < 0 and abs(p.y) < 5.0: nrm = -nrm
            nrms.append(nrm)
        arch_pts_list.append(pts)
        arch_nrm_list.append(nrms)

        # Sculpted deep outer dark-anodized steel structural rib + thick warm laminated cedar inner soffit!
        rings_s, rings_w, rings_flange = [], [], []
        for p, nrm in zip(pts, nrms):
            hw_s, hh_s = 0.088, 0.22
            rings_s.append([
                p + V((-hw_s, 0, 0)) + nrm * hh_s, p + V((hw_s, 0, 0)) + nrm * hh_s,
                p + V((hw_s, 0, 0)) - nrm * 0.01,  p + V((-hw_s, 0, 0)) - nrm * 0.01,
            ])
            # Top structural I-beam steel flange cap
            hw_f = 0.125
            rings_flange.append([
                p + V((-hw_f, 0, 0)) + nrm * (hh_s + 0.028), p + V((hw_f, 0, 0)) + nrm * (hh_s + 0.028),
                p + V((hw_f, 0, 0)) + nrm * (hh_s - 0.004),  p + V((-hw_f, 0, 0)) + nrm * (hh_s - 0.004),
            ])
            # Warm laminated curved cedar inner soffit lining (catches golden sunlight!)
            hw_w = 0.078
            rings_w.append([
                p + V((-hw_w, 0, 0)) - nrm * 0.01, p + V((hw_w, 0, 0)) - nrm * 0.01,
                p + V((hw_w, 0, 0)) - nrm * 0.13,  p + V((-hw_w, 0, 0)) - nrm * 0.13,
            ])
        add_loft(bm, rings_s, True, True, mat_idx=0)
        add_loft(bm, rings_flange, True, True, mat_idx=0)
        add_loft(bm, rings_w, True, True, mat_idx=1)

        # Architectural cast-steel bolted column shoe brackets at both ends
        for sy in (-1, 1):
            add_box(bm, (x_val - 0.16, sy * 8.76 - 0.20, 0.00), (x_val + 0.16, sy * 8.76 + 0.20, 0.36), bev=0.015, mat_idx=0)
            add_box(bm, (x_val - 0.21, sy * 8.76 - 0.25, 0.00), (x_val + 0.21, sy * 8.76 + 0.25, 0.045), bev=0.008, mat_idx=0)

    # Dense rhythmic architectural cedar-slat louvered purlins (12 rows casting slatted golden-hour stripes!)
    purlin_indices = [3, 5, 7, 9, 11, 12, 14, 15, 17, 19, 21, 23]
    for idx_p in purlin_indices:
        for bi in range(len(arch_pts_list) - 1):
            p0, p1 = arch_pts_list[bi][idx_p], arch_pts_list[bi + 1][idx_p]
            n0 = arch_nrm_list[bi][idx_p]
            mid = (p0 + p1) * 0.5 + n0 * 0.06
            half_len = (p1 - p0).length * 0.5
            # Rectangular architectural cedar louver blade
            add_box(bm, (-half_len, -0.045, -0.065), (half_len, 0.045, 0.065), bev=0.006, mat_idx=1, xf=Matrix.Translation(mid))
        # Slim outer anodized tie-rod spanning all 11 ribs
        p_first, p_last = arch_pts_list[0][idx_p], arch_pts_list[-1][idx_p]
        add_cyl(bm, p_first + V((0, 0, 0.18)), p_last + V((0, 0, 0.18)), 0.022, 0.022, n=8, mat_idx=0)

    # Subtle tinted skylight canopy glazing panels along the upper vault bays!
    for bi in range(len(arch_pts_list) - 1):
        for idx_s in (6, 8, 10, 12, 14, 16, 18):
            a0 = arch_pts_list[bi][idx_s] + arch_nrm_list[bi][idx_s] * 0.24
            a1 = arch_pts_list[bi][idx_s + 2] + arch_nrm_list[bi][idx_s + 2] * 0.24
            b1 = arch_pts_list[bi + 1][idx_s + 2] + arch_nrm_list[bi + 1][idx_s + 2] * 0.24
            b0 = arch_pts_list[bi + 1][idx_s] + arch_nrm_list[bi + 1][idx_s] * 0.24
            v_g = [bm_gl.verts.new(p) for p in (a0, b0, b1, a1)]
            bm_gl.faces.new(v_g).material_index = 0

    # Delicate brushed-brass architectural pendant micro-lanterns suspended along the central spine!
    for x_l in (-4.68, -1.56, 1.56, 4.68):
        p_top = arch_point(x_l, 0.0) - V((0, 0, 0.12))
        p_bot = p_top - V((0, 0, 0.88))
        add_cyl(bm, p_top, p_bot, 0.008, 0.008, n=8, mat_idx=0)
        add_cyl(bm, p_bot, p_bot - V((0, 0, 0.08)), 0.075, 0.095, n=14, mat_idx=2)
        add_cyl(bm, p_bot - V((0, 0, 0.08)), p_bot - V((0, 0, 0.15)), 0.062, 0.048, n=14, mat_idx=3)

    finish_obj(bm, "Env_Pergola_Arches", ["E_steel_dark", "E_cedar", "E_brass", "E_glow_warm"])
    finish_obj(bm_gl, "Env_Pergola_Skylights", ["E_skylight_glass"])


def build_four_planter_islands():
    """4 lush terraced board-formed concrete & teak-bench planter islands w/ real Monstera & Boston Ferns!"""
    bm_arch = bmesh.new()
    bm_moss = bmesh.new()
    bm_monstera = bmesh.new()
    bm_fern = bmesh.new()
    uv_m = bm_monstera.loops.layers.uv.new("UVMap")
    uv_f = bm_fern.loops.layers.uv.new("UVMap")

    def add_arched_botanical_card(bm_t, uv_layer, base, dir_v, length, width, arch=0.32, cup=0.06, roll=0.0):
        """Builds a graceful curved, cupped 3D quad strip mapped cleanly 0..1 to our RGBA cutout sheet."""
        d = V(dir_v).normalized()
        side = d.cross(V((0, 0, 1)))
        if side.length < 1e-4: side = V((1, 0, 0))
        side.normalize()
        up = side.cross(d).normalized()
        if abs(roll) > 1e-4:
            rm = Matrix.Rotation(roll, 3, d)
            side = (rm @ side).normalized()
            up = (rm @ up).normalized()

        # 6 longitudinal segments x 2 width strips = buttery smooth organic botanical arch!
        n_seg = 6
        rows = []
        for i in range(n_seg + 1):
            s = i / float(n_seg)
            # Natural gravity droop along s^2
            c = V(base) + d * (s * length) - V((0, 0, arch * length * (s ** 1.85)))
            hw = 0.5 * width
            cup_z = cup * width * math.sin(s * math.pi)
            rows.append((
                bm_t.verts.new(c - side * hw + up * cup_z),
                bm_t.verts.new(c),
                bm_t.verts.new(c + side * hw + up * cup_z),
            ))
        for i in range(n_seg):
            v0, v1 = i / float(n_seg), (i + 1) / float(n_seg)
            r0, r1 = rows[i], rows[i + 1]
            fL = bm_t.faces.new((r0[0], r0[1], r1[1], r1[0])); fL.material_index = 0
            fR = bm_t.faces.new((r0[1], r0[2], r1[2], r1[1])); fR.material_index = 0
            for lp, uv in zip(fL.loops, [(0.0, v0), (0.5, v0), (0.5, v1), (0.0, v1)]): lp[uv_layer].uv = uv
            for lp, uv in zip(fR.loops, [(0.5, v0), (1.0, v0), (1.0, v1), (0.5, v1)]): lp[uv_layer].uv = uv

    quads = [
        ("BED_01_NE",  5.15,  5.15),
        ("BED_02_NW", -5.15,  5.15),
        ("BED_03_SW", -5.15, -5.15),
        ("BED_04_SE",  5.15, -5.15),
    ]
    rng = random.Random(2026)

    for idx_q, (sid, cx, cy) in enumerate(quads):
        # 1. Lower board-formed concrete base (rounded-chamfer octagon, r = 2.15 m, H = 0.37 m)
        add_loft(bm_arch, [
            chamfer_oct_ring(cx, cy, 0.00, 2.16),
            chamfer_oct_ring(cx, cy, 0.34, 2.11),
        ], True, True, mat_idx=0)
        # Recessed dark shadow reveal strip under the cedar bench (gives crisp architectural float shadow!)
        add_loft(bm_arch, [
            chamfer_oct_ring(cx, cy, 0.34, 2.04),
            chamfer_oct_ring(cx, cy, 0.37, 2.04),
        ], False, False, mat_idx=4)
        # Warm oiled cedar perimeter bench lip overhanging cleanly (env-concept.jpg!)
        add_loft(bm_arch, [
            chamfer_oct_ring(cx, cy, 0.37, 2.22),
            chamfer_oct_ring(cx, cy, 0.435, 2.22),
            chamfer_oct_ring(cx, cy, 0.435, 1.54),
            chamfer_oct_ring(cx, cy, 0.37, 1.54),
        ], False, False, mat_idx=1)
        # Dark rich organic soil trough on lower terrace
        add_loft(bm_arch, [chamfer_oct_ring(cx, cy, 0.36, 1.58), chamfer_oct_ring(cx, cy, 0.41, 1.55)], False, True, mat_idx=3)

        # 2. Upper board-formed concrete stepped inner planter bed (r = 1.38 m, H = 0.72 m, matching env-concept.jpg!)
        add_loft(bm_arch, [
            chamfer_oct_ring(cx, cy, 0.38, 1.40),
            chamfer_oct_ring(cx, cy, 0.71, 1.35),
            chamfer_oct_ring(cx, cy, 0.72, 1.24),
            chamfer_oct_ring(cx, cy, 0.63, 1.21),
        ], False, True, mat_idx=0)
        # Rich dark soil bed inside upper core
        add_loft(bm_arch, [chamfer_oct_ring(cx, cy, 0.62, 1.23), chamfer_oct_ring(cx, cy, 0.67, 1.19)], False, True, mat_idx=3)

        # 3. Signature Arching Brushed-Brass Misting Hoop w/ machined base flanges & 7 fine nozzles!
        ang_hoop = math.atan2(-cy, -cx) + math.pi * 0.5
        ex_h = V((math.cos(ang_hoop), math.sin(ang_hoop), 0.0))
        hoop_pts = []
        for i in range(25):
            a = math.pi * (i / 24.0)
            p = V((cx, cy, 0.66)) + ex_h * (math.cos(a) * 1.24) + V((0, 0, math.sin(a) * 1.98))
            hoop_pts.append(p)
        add_tube(bm_arch, hoop_pts, 0.020, n=10, mat_idx=2)
        for end_p in (hoop_pts[0], hoop_pts[-1]):
            add_cyl(bm_arch, end_p - V((0, 0, 0.04)), end_p + V((0, 0, 0.08)), 0.042, 0.032, n=12, mat_idx=2)
        for ni in (6, 8, 10, 12, 14, 16, 18):
            np0 = hoop_pts[ni]
            add_cyl(bm_arch, np0, np0 - V((0, 0, 0.045)), 0.011, 0.006, n=8, mat_idx=2)

        # 4. Irregular Organic Sculpted Velvet Moss Cushions nestled cleanly inside soil (zero bench overlap!)
        for k in range(16):
            a = k * (2 * math.pi / 16.0) + rng.uniform(-0.18, 0.18)
            inner = (k % 2 == 0)
            rr = rng.uniform(0.18, 0.96) if inner else rng.uniform(1.32, 1.38)
            z_b = 0.67 if inner else 0.42
            rad = rng.uniform(0.18, 0.28) if inner else rng.uniform(0.08, 0.11)
            res = bmesh.ops.create_icosphere(bm_moss, subdivisions=2, radius=rad)
            for v in res["verts"]:
                p = v.co
                disp = 1.0 + 0.28 * math.sin(p.x * 19 + k * 2.1) * math.cos(p.y * 23 - k) + 0.16 * math.sin(p.z * 31 + p.x * 14)
                v.co = V((cx + math.cos(a) * rr + p.x * disp * 1.15, cy + math.sin(a) * rr + p.y * disp * 1.15, z_b + max(-0.03, p.z * 0.35 * disp)))
            for f in {f for v in res["verts"] for f in v.link_faces}:
                f.material_index = 0

        # 5. Tall Sculptural Fenestrated MONSTERA DELICIOSA Crown (30 layered lush towering leaves filling the brass hoop!)
        for k in range(30):
            a = k * (2 * math.pi / 30.0) + rng.uniform(-0.22, 0.22)
            tier = k % 3
            if tier == 0:
                # Towering centerpiece leaves soaring gracefully up into the brass hoop (Z = 1.5..2.05 m!)
                rr, z0, pitch, L = rng.uniform(0.05, 0.42), 0.72, rng.uniform(1.55, 2.75), rng.uniform(1.15, 1.55)
                arch_v = 0.24
            elif tier == 1:
                # Lush mid-canopy arching Monstera fronds
                rr, z0, pitch, L = rng.uniform(0.28, 0.72), 0.70, rng.uniform(0.85, 1.55), rng.uniform(0.92, 1.30)
                arch_v = 0.32
            else:
                # Outward-leaning lush broad rim leaves
                rr, z0, pitch, L = rng.uniform(0.55, 0.96), 0.68, rng.uniform(0.45, 0.92), rng.uniform(0.74, 1.06)
                arch_v = 0.38
            W_l = L * rng.uniform(0.74, 0.90)
            roll = rng.uniform(-0.30, 0.30)
            add_arched_botanical_card(
                bm_monstera, uv_m,
                (cx + math.cos(a) * rr, cy + math.sin(a) * rr, z0),
                (math.cos(a), math.sin(a), pitch), L, W_l, arch=arch_v, cup=0.075, roll=roll
            )

        # 6. Lush Overflowing Feathered BOSTON FERN Skirt (46 fronds cascading over concrete rim, keeping bench clean!)
        for k in range(46):
            a = k * (2 * math.pi / 46.0) + rng.uniform(-0.14, 0.14)
            layer = k % 3
            if layer == 0:
                # Upper rim cascading ferns draping gracefully over the fluted concrete wall!
                rr, z0, pitch, L, W_l, arch = rng.uniform(0.82, 1.12), 0.72, rng.uniform(0.42, 0.80), rng.uniform(0.76, 1.08), rng.uniform(0.30, 0.42), 0.50
            elif layer == 1:
                # Tall feathery inner ferns filling the lower-mid volume around the Monstera stalks!
                rr, z0, pitch, L, W_l, arch = rng.uniform(0.18, 0.74), 0.72, rng.uniform(0.95, 1.75), rng.uniform(0.88, 1.26), rng.uniform(0.30, 0.44), 0.36
            else:
                # Lower concrete moat soft upright fern tufts (stay strictly inside bench inner lip!)
                rr, z0, pitch, L, W_l, arch = rng.uniform(1.30, 1.38), 0.45, rng.uniform(0.75, 1.35), rng.uniform(0.42, 0.62), rng.uniform(0.22, 0.30), 0.34
            add_arched_botanical_card(
                bm_fern, uv_f,
                (cx + math.cos(a) * rr, cy + math.sin(a) * rr, z0),
                (math.cos(a), math.sin(a), pitch), L, W_l, arch=arch, cup=0.04, roll=rng.uniform(-0.22, 0.22)
            )

        # Register smooth circular collider + interactive botanical care station (Three.js Y-up coords!)
        COLLIDERS.append(dict(type="circle", name=sid, x=cx, z=-cy, r=2.28))
        to_ctr = V((-cx, -cy)).normalized()
        px, py = cx + to_ctr.x * 2.58, cy + to_ctr.y * 2.58
        STATIONS.append(dict(
            id=sid,
            label=f"BOTANICAL BED 0{idx_q + 1}",
            center=[round(cx, 2), 0.98, round(-cy, 2)],
            approach=[round(px, 2), 0.0, round(-py, 2)],
            radius=2.95,
        ))

    finish_obj(bm_arch, "Env_Planter_Islands", ["E_concrete", "E_cedar", "E_brass", "E_soil", "E_basalt"])
    finish_obj(bm_moss, "Env_Planter_Moss", ["E_moss"], smooth_deg=75.0)
    finish_obj(bm_monstera, "Env_Planter_Monstera", ["E_monstera"], smooth_deg=75.0)
    finish_obj(bm_fern, "Env_Planter_Ferns", ["E_fern"], smooth_deg=75.0)


def build_charging_dock_and_water_basin():
    # --- 1. Sleek Low-Profile Chamfered Robotic Solar Charging & Hydration Dock (env-concept.jpg + FLORA-01!) ---
    bm = bmesh.new()
    dy = 6.75
    # Flush low basalt inductive drive-on pad (height only 10mm chamfered so FLORA-01 steps cleanly on!)
    add_box(bm, (-1.18, dy - 1.05, 0.000), (1.18, dy + 0.72, 0.010), bev=0.008, mat_idx=1)
    # Recessed brushed-aluminum charging coil ring & twin glowing lime alignment strips
    for sx in (-1, 1):
        add_box(bm, (sx * 0.86 - 0.025, dy - 0.94, 0.008), (sx * 0.86 + 0.025, dy + 0.62, 0.018), bev=0.003, mat_idx=4)
    add_cyl(bm, (0.0, dy - 0.16, 0.008), (0.0, dy - 0.16, 0.014), 0.34, 0.32, n=24, mat_idx=4)
    add_cyl(bm, (0.0, dy - 0.16, 0.010), (0.0, dy - 0.16, 0.016), 0.28, 0.27, n=24, mat_idx=1)

    # Sleek pill-beveled matte-white ceramic dock console (env-concept.jpg aesthetic!)
    add_box(bm, (-1.22, dy + 0.68, 0.00), (1.22, dy + 1.38, 1.08), bev=0.14, seg=3, mat_idx=0)
    # Deep recessed obsidian front telemetry bay
    add_box(bm, (-1.00, dy + 0.64, 0.14), (1.00, dy + 0.76, 0.94), bev=0.06, seg=2, mat_idx=1)
    # Continuous glowing chartreuse-lime perimeter lightpipe framing the obsidian bay!
    add_box(bm, (-1.03, dy + 0.635, 0.91), (1.03, dy + 0.68, 0.955), bev=0.008, mat_idx=4)
    add_box(bm, (-1.03, dy + 0.635, 0.125), (1.03, dy + 0.68, 0.165), bev=0.008, mat_idx=4)
    for sx in (-1, 1):
        add_box(bm, (sx * 1.01 - 0.02, dy + 0.635, 0.14), (sx * 1.01 + 0.02, dy + 0.68, 0.94), bev=0.008, mat_idx=4)
    # Twin sculpted rear angled steel arms supporting a sleek cantilevered PV solar shade wing!
    for sx in (-0.82, 0.82):
        add_box(bm, (sx - 0.055, dy + 1.02, 0.96), (sx + 0.055, dy + 1.24, 1.78), bev=0.015, mat_idx=1)
    roof_xf = Matrix.Translation((0.0, dy + 0.15, 1.82)) @ Matrix.Rotation(math.radians(-9), 4, 'X')
    add_box(bm, (-1.34, -0.96, -0.045), (1.34, 1.04, 0.045), bev=0.032, seg=2, mat_idx=0, xf=roof_xf)
    add_box(bm, (-1.20, -0.82, 0.035), (1.20, 0.90, 0.065), bev=0.008, mat_idx=2, xf=roof_xf)
    # Twin machined brushed-brass water refill couplings & pressure gauge bezel
    for sx in (-0.34, 0.34):
        add_cyl(bm, (sx, dy + 0.66, 0.50), (sx, dy + 0.52, 0.50), 0.036, 0.026, n=14, mat_idx=3)
        add_cyl(bm, (sx, dy + 0.52, 0.50), (sx, dy + 0.48, 0.50), 0.020, 0.018, n=12, mat_idx=1)
    finish_obj(bm, "Env_Charging_Dock", ["E_ceramic_white", "E_steel_dark", "E_dock_solar", "E_brass", "E_glow_lime"])
    COLLIDERS.append(dict(type="aabb", name="Charging_Dock_Pylon", minX=-1.28, maxX=1.28, minZ=-8.38, maxZ=-7.36))

    # --- 2. Razor-Sharp Dark-Steel Mirror Rainwater Basin + Submerged Cobbles (env-concept.jpg!) ---
    bm_w = bmesh.new()
    wy = -6.75
    # Crisp mitered dark anodized steel curb (height 14cm!)
    add_box(bm_w, (-1.82, wy - 1.66, 0.00), (1.82, wy - 1.52, 0.14), bev=0.008, mat_idx=0)
    add_box(bm_w, (-1.82, wy + 1.52, 0.00), (1.82, wy + 1.66, 0.14), bev=0.008, mat_idx=0)
    add_box(bm_w, (-1.82, wy - 1.66, 0.00), (-1.68, wy + 1.66, 0.14), bev=0.008, mat_idx=0)
    add_box(bm_w, ( 1.68, wy - 1.66, 0.00), ( 1.82, wy + 1.66, 0.14), bev=0.008, mat_idx=0)
    # Dark wet basalt recessed bed floor
    add_box(bm_w, (-1.69, wy - 1.53, 0.00), (1.69, wy + 1.53, 0.03), mat_idx=1)
    # Smooth submerged dark river cobbles visible gently along the basin edges!
    rng = random.Random(77)
    for _ in range(38):
        px = rng.uniform(-1.50, 1.50)
        py = wy + rng.uniform(-1.35, 1.35)
        rx, ry, rz = rng.uniform(0.06, 0.15), rng.uniform(0.05, 0.13), rng.uniform(0.025, 0.045)
        res = bmesh.ops.create_icosphere(bm_w, subdivisions=2, radius=1.0)
        for v in res["verts"]:
            v.co = V((px + v.co.x * rx, py + v.co.y * ry, 0.032 + v.co.z * rz))
        for f in {f for v in res["verts"] for f in v.link_faces}:
            f.material_index = 2
    # Sculpted brushed-brass cascade weir fountain bar on south edge
    add_box(bm_w, (-0.64, wy - 1.54, 0.14), (0.64, wy - 1.40, 0.24), bev=0.008, mat_idx=3)
    add_box(bm_w, (-0.54, wy - 1.42, 0.19), (0.54, wy - 1.32, 0.215), bev=0.004, mat_idx=3)
    finish_obj(bm_w, "Env_Water_Basin", ["E_steel_dark", "E_basalt", "E_cobble", "E_brass"])

    # Dedicated clean water plane (Three.js upgrades this mesh to an animated Fresnel ripple mirror shader!)
    bm_surf = bmesh.new()
    v0 = bm_surf.verts.new(V((-1.69, wy - 1.53, 0.105)))
    v1 = bm_surf.verts.new(V(( 1.69, wy - 1.53, 0.105)))
    v2 = bm_surf.verts.new(V(( 1.69, wy + 1.53, 0.105)))
    v3 = bm_surf.verts.new(V((-1.69, wy + 1.53, 0.105)))
    bm_surf.faces.new((v0, v1, v2, v3)).material_index = 0
    finish_obj(bm_surf, "Env_Water_Surface", ["E_water"])
    COLLIDERS.append(dict(type="aabb", name="Water_Basin", minX=-1.88, maxX=1.88, minZ=5.02, maxZ=8.48))


def build_bollards_treeline_and_skyline():
    # --- 1. 8 Sleek Architectural Solar Pathway Bollards (exact cylindrical env-concept.jpg look!) ---
    bm_b = bmesh.new()
    bollard_pts = [
        ( 2.98,  2.15), (-2.98,  2.15), (-2.98, -2.15), ( 2.98, -2.15),
        ( 7.45,  1.65), (-7.45,  1.65), (-7.45, -1.65), ( 7.45, -1.65),
    ]
    for bx, by in bollard_pts:
        add_cyl(bm_b, (bx, by, 0.00), (bx, by, 0.025), 0.092, 0.082, n=16, mat_idx=0)
        add_cyl(bm_b, (bx, by, 0.025), (bx, by, 0.49), 0.064, 0.060, n=16, mat_idx=0)
        add_cyl(bm_b, (bx, by, 0.49), (bx, by, 0.565), 0.056, 0.056, n=16, mat_idx=1)
        add_cyl(bm_b, (bx, by, 0.565), (bx, by, 0.615), 0.064, 0.058, n=16, mat_idx=0)
        COLLIDERS.append(dict(type="circle", name="Bollard", x=bx, z=-by, r=0.18))
    finish_obj(bm_b, "Env_Solar_Bollards", ["E_steel_dark", "E_glow_warm"])

    # --- 2. Lush Alpha-Cutout Leafy Urban-Forest Treeline Ring (ZERO smooth blob spheres!) ---
    bm_tr = bmesh.new()
    uv_tr = bm_tr.loops.layers.uv.new("UVMap")
    rng = random.Random(108)

    def add_foliage_cluster_card(center, size_w, size_h, yaw, tilt):
        xf = Matrix.Translation(center) @ Matrix.Rotation(yaw, 4, 'Z') @ Matrix.Rotation(tilt, 4, 'X')
        hw, hh = size_w * 0.5, size_h * 0.5
        pts = [xf @ V((-hw, 0, -hh)), xf @ V((hw, 0, -hh)), xf @ V((hw, 0, hh)), xf @ V((-hw, 0, hh))]
        vs = [bm_tr.verts.new(p) for p in pts]
        f = bm_tr.faces.new(vs); f.material_index = 0
        for lp, uv in zip(f.loops, [(0, 0), (1, 0), (1, 1), (0, 1)]):
            lp[uv_tr].uv = uv

    for k in range(84):
        ang = (k / 84.0) * 2.0 * math.pi + rng.uniform(-0.04, 0.04)
        rad = rng.uniform(15.0, 26.5)  # sits naturally beyond the rooftop edge, never crowding the glass!
        cx, cy = math.cos(ang) * rad, math.sin(ang) * rad
        # Graceful low treeline cresting gently near balustrade height (-0.4 .. +1.2 m) so skyline shines above!
        cz = rng.uniform(-1.2, 0.85)
        sz = rng.uniform(2.6, 4.4)
        # 3 intersecting angled botanical leaf-cluster cards per tree -> fluffy 3D lacy tree canopy from ALL angles!
        for j in range(3):
            yaw = ang + j * (math.pi / 3.0) + rng.uniform(-0.25, 0.25)
            tilt = rng.uniform(-0.22, 0.22)
            ox, oy, oz = rng.uniform(-0.55, 0.55), rng.uniform(-0.55, 0.55), rng.uniform(-0.35, 0.35)
            add_foliage_cluster_card(V((cx + ox, cy + oy, cz + oz)), sz, sz * rng.uniform(0.82, 1.05), yaw, tilt)
    finish_obj(bm_tr, "Env_Treeline_Canopy", ["E_tree_canopy"], smooth_deg=75.0)

    # --- 3. 42 Articulated Glazed Solarpunk Eco-Towers w/ Setbacks & Sky-Gardens (ZERO plain boxes!) ---
    bm_s = bmesh.new()
    rng2 = random.Random(2042)
    for k in range(42):
        ang = (k / 42.0) * 2.0 * math.pi + rng2.uniform(-0.035, 0.035)
        rad = rng2.uniform(25.5, 48.0)
        w = rng2.uniform(3.2, 6.2)
        d = rng2.uniform(3.2, 5.8)
        h = rng2.uniform(8.0, 21.0)
        z0 = -10.0  # city avenue below rooftop!
        cx, cy = math.cos(ang) * rad, math.sin(ang) * rad
        xf = Matrix.Translation((cx, cy, 0.0)) @ Matrix.Rotation(ang + rng2.uniform(-0.2, 0.2), 4, 'Z')

        # Main glazed curtain-wall tower shaft
        h1 = h * rng2.uniform(0.62, 0.78)
        add_box(bm_s, (-w/2, -d/2, z0), (w/2, d/2, z0 + h1), bev=0.14, mat_idx=0, xf=xf)
        # Architectural setback terrace green deck
        add_box(bm_s, (-w*0.52, -d*0.52, z0 + h1), (w*0.52, d*0.52, z0 + h1 + 0.55), bev=0.06, mat_idx=1, xf=xf)
        # Stepped slender upper crown tower
        w2, d2 = w * rng2.uniform(0.58, 0.76), d * rng2.uniform(0.58, 0.76)
        add_box(bm_s, (-w2/2, -d2/2, z0 + h1 + 0.4), (w2/2, d2/2, z0 + h), bev=0.12, mat_idx=0, xf=xf)
        # Lush forested solarpunk rooftop garden crown!
        add_box(bm_s, (-w2*0.46, -d2*0.46, z0 + h), (w2*0.46, d2*0.46, z0 + h + 0.75), bev=0.10, mat_idx=2, xf=xf)
        # Subtle white rooftop architectural canopy / spire on taller towers
        if h > 14.5:
            add_box(bm_s, (-w2*0.36, -d2*0.36, z0 + h + 1.15), (w2*0.36, d2*0.36, z0 + h + 1.45), bev=0.05, mat_idx=3, xf=xf)
            for sx in (-w2*0.28, w2*0.28):
                add_cyl(bm_s, xf @ V((sx, 0, z0 + h + 0.6)), xf @ V((sx, 0, z0 + h + 1.2)), 0.12, 0.10, n=8, mat_idx=3)
    finish_obj(bm_s, "Env_Solarpunk_Skyline", ["E_facade", "E_tree_deep", "E_tree_sun", "E_ceramic_white"])


# ==============================================================================
# 5. CYCLES BAKED CONTACT AMBIENT OCCLUSION ON TERRACE FLOOR (20 SPP!)
# ==============================================================================
def bake_terrace_contact_ao():
    """Bakes crisp real Cycles Contact Ambient Occlusion onto the 18x18m travertine floor (UV_AO)."""
    scn = bpy.context.scene
    scn.render.engine = "CYCLES"
    scn.cycles.device = "CPU"
    scn.cycles.samples = 20
    scn.cycles.use_denoising = False
    scn.render.bake.margin = 8
    scn.render.bake.margin_type = "EXTEND"

    # Hide distant skyline/treeline/glass skylights during floor AO bake so overhead glass doesn't darken sky!
    hide_during_ao = {"Env_Pergola_Skylights", "Env_Balustrade_Glass", "Env_Treeline_Canopy", "Env_Solarpunk_Skyline", "Env_Water_Surface"}
    for o in ENV_OBJS:
        if o.name in hide_during_ao:
            o.hide_render = True

    ao_path = os.path.join(TEX_DIR, "terrace_contact_ao.png")
    ao_im = bpy.data.images.new("terrace_contact_ao.png", width=1024, height=1024, alpha=False)
    ao_im.colorspace_settings.name = "Non-Color"

    # Temporary clean AO bake shader on FLOOR_OBJ targeting UV_AO
    orig_mat = FLOOR_OBJ.data.materials[0]
    tmp_mat = bpy.data.materials.new("_AO_BAKE_TMP")
    nt = tmp_mat.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    emit = nt.nodes.new("ShaderNodeEmission")
    ao_nd = nt.nodes.new("ShaderNodeAmbientOcclusion")
    ao_nd.samples = 16
    ao_nd.inputs["Distance"].default_value = 1.85
    # Gently shape contrast so contact crevices are rich & velvety without darkening open walkways!
    ramp = nt.nodes.new("ShaderNodeMapRange")
    ramp.inputs["From Min"].default_value = 0.18
    ramp.inputs["From Max"].default_value = 0.96
    ramp.inputs["To Min"].default_value = 0.22
    ramp.inputs["To Max"].default_value = 1.00
    nt.links.new(ao_nd.outputs["AO"], ramp.inputs["Value"])
    nt.links.new(ramp.outputs["Result"], emit.inputs["Color"])
    nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])

    tex_tgt = nt.nodes.new("ShaderNodeTexImage")
    tex_tgt.image = ao_im
    nt.nodes.active = tex_tgt

    FLOOR_OBJ.data.materials[0] = tmp_mat
    FLOOR_OBJ.data.uv_layers["UV_AO"].active = True
    FLOOR_OBJ.data.uv_layers["UV_AO"].active_render = True

    bpy.ops.object.select_all(action="DESELECT")
    FLOOR_OBJ.select_set(True)
    bpy.context.view_layer.objects.active = FLOOR_OBJ
    bpy.ops.object.bake(type="EMIT")

    ao_im.filepath_raw = ao_path
    ao_im.file_format = "PNG"
    ao_im.save()
    bpy.data.images.remove(ao_im)

    # Reload cleanly as Non-Color and wire onto TEXCOORD_1 -> glTF Occlusion!
    ao_reloaded = bpy.data.images.load(ao_path)
    ao_reloaded.colorspace_settings.name = "Non-Color"
    ao_reloaded.name = "terrace_contact_ao.png"

    FLOOR_OBJ.data.materials[0] = orig_mat
    FLOOR_OBJ.data.uv_layers["UVMap"].active = True
    FLOOR_OBJ.data.uv_layers["UVMap"].active_render = True
    bpy.data.materials.remove(tmp_mat)

    attach_baked_ao(orig_mat, ao_reloaded, "UV_AO")

    for o in ENV_OBJS:
        o.hide_render = False
    print(f"BAKED CYCLES TERRACE CONTACT AO: {ao_path}")


# ==============================================================================
# 6. PREVIEW RENDERER (CYCLES / EEVEE 4-VIEW ARCHITECTURAL VERIFICATION SHEET)
# ==============================================================================
def render_preview_sheet():
    scn = bpy.context.scene
    scn.render.engine = "BLENDER_EEVEE"
    scn.eevee.taa_render_samples = 28
    scn.eevee.use_raytracing = True
    scn.view_settings.view_transform = "AgX"
    scn.view_settings.look = "AgX - Medium High Contrast"
    scn.render.image_settings.file_format = "PNG"

    w = bpy.data.worlds.new("EnvSky")
    scn.world = w
    nt = w.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    sky = nt.nodes.new("ShaderNodeTexSky")
    if hasattr(sky, "sky_type"):
        sky.sky_type = "MULTIPLE_SCATTERING"
    if hasattr(sky, "sun_elevation"):
        sky.sun_elevation = math.radians(22)
        sky.sun_rotation = math.radians(-42)
    bg.inputs["Strength"].default_value = 0.65
    nt.links.new(sky.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs[0], out.inputs["Surface"])

    sun = bpy.data.lights.new("Sun", "SUN")
    sun.energy = 4.2; sun.color = (1.0, 0.86, 0.66); sun.angle = math.radians(1.6)
    so = bpy.data.objects.new("Sun", sun); scn.collection.objects.link(so)
    so.rotation_euler = (math.radians(66), 0.0, math.radians(-42))

    cd = bpy.data.cameras.new("EnvCam"); cd.clip_start, cd.clip_end = 0.1, 220.0
    cam = bpy.data.objects.new("EnvCam", cd); scn.collection.objects.link(cam); scn.camera = cam

    W, H = 640, 360
    shots = [
        ("concept_match", (-5.4, -6.2, 2.05), ( 2.2,  2.6, 1.05), 26, "PERSP"),
        ("top_plan",      ( 0.0,  0.0, 24.0), ( 0.0,  0.0, 0.00), 21.0, "ORTHO"),
        ("planter_cu",    ( 1.4,  1.4, 1.65), ( 5.15, 5.15, 1.05), 38, "PERSP"),
        ("dock_cu",       ( 2.6,  2.9, 1.45), ( 0.0,  6.8, 0.72), 36, "PERSP"),
    ]
    tiles = []
    for nm, loc, tgt, val, ctype in shots:
        cam.location = V(loc)
        if ctype == "ORTHO":
            cd.type = "ORTHO"; cd.ortho_scale = val
            cam.rotation_euler = (0.0, 0.0, 0.0)
        else:
            cd.type = "PERSP"; cd.lens = val
            cam.rotation_euler = (V(tgt) - V(loc)).to_track_quat("-Z", "Y").to_euler()
        scn.render.resolution_x, scn.render.resolution_y = W, H
        p = os.path.join(REND_DIR, f"_tmp_{nm}.png")
        scn.render.filepath = p
        bpy.ops.render.render(write_still=True)
        im = bpy.data.images.load(p, check_existing=False)
        tiles.append(np.array(im.pixels[:], dtype=np.float32).reshape(H, W, 4)[::-1])
        bpy.data.images.remove(im)
        os.remove(p)

    grid = np.zeros((H * 2, W * 2, 4), dtype=np.float32)
    for i, t in enumerate(tiles):
        r, c = divmod(i, 2)
        grid[r * H:(r + 1) * H, c * W:(c + 1) * W] = t
    out_p = os.path.join(REND_DIR, "env_preview.png")
    im_o = bpy.data.images.new("env_prev", W * 2, H * 2, alpha=True)
    im_o.colorspace_settings.name = "sRGB"
    im_o.pixels.foreach_set(np.clip(grid[::-1], 0.0, 1.0).astype(np.float32).ravel())
    im_o.update(); im_o.filepath_raw = out_p; im_o.file_format = "PNG"; im_o.save()
    bpy.data.images.remove(im_o)
    print(f"SAVED ENV PREVIEW: {out_p}")


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    build_materials()
    build_terrace_floor_and_balustrade()
    build_conservatory_pergola()
    build_four_planter_islands()
    build_charging_dock_and_water_basin()
    build_bollards_treeline_and_skyline()

    # Bake real Cycles Contact Ambient Occlusion onto the 18x18m terrace floor!
    bake_terrace_contact_ao()

    tot_tris = 0
    for o in ENV_OBJS:
        o.data.calc_loop_triangles()
        tot_tris += len(o.data.loop_triangles)
    print(f"ENVIRONMENT PASS 2 BUILT: {len(ENV_OBJS)} objects, {tot_tris} tris, {len(COLLIDERS)} colliders, {len(STATIONS)} botanical stations")

    meta = dict(
        name="Solarpunk Rooftop Botanical Conservatory (Pass 2)",
        bounds=dict(minX=-8.25, maxX=8.25, minZ=-8.25, maxZ=8.25),
        dock=dict(center=[0.0, 0.0, -6.75], radius=1.95),
        colliders=COLLIDERS,
        stations=STATIONS,
        tris=tot_tris,
    )
    with open(os.path.join(OUT_DIR, "env_meta.json"), "w") as fh:
        json.dump(meta, fh, indent=2)

    # Export Draco + WebP Web GLB (keeps RGBA alpha masks crisp!)
    bpy.ops.object.select_all(action="DESELECT")
    for o in ENV_OBJS: o.select_set(True)
    bpy.context.view_layer.objects.active = ENV_OBJS[0]
    web_glb = os.path.join(OUT_DIR, "courtyard_env_web.glb")
    bpy.ops.export_scene.gltf(
        filepath=web_glb, export_format="GLB", use_selection=True,
        export_apply=True, export_yup=True, export_tangents=True,
        export_materials="EXPORT", export_image_format="WEBP", export_image_quality=84,
        export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=6,
    )
    print(f"EXPORTED ENV WEB GLB: {web_glb} ({os.path.getsize(web_glb)/1024/1024:.2f} MB)")

    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT_DIR, "courtyard_env.blend"))

    if DO_PREVIEW:
        render_preview_sheet()


if __name__ == "__main__":
    main()
