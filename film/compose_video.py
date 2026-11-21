# compose_video.py — Generates crisp minimalist Apple/Rivian-grade 1080p RGBA typography & HUD overlays
# with Pillow, composites them onto the 1,344 rendered 1080p frames with smooth fade curves, adds subtle
# cinematic filmic grading + vignette, muxes & loudnorm-masters the stereo soundtrack + Gemini 3.8 TTS
# narration, and encodes X (Twitter)-optimized H.264 High@L4.1 MP4!
#
# Usage:
#   python compose_video.py

import os
import json
import math
import subprocess
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
TL = json.load(open(os.path.join(HERE, "timeline.json"), "r"))
W, H, FPS = TL["width"], TL["height"], TL["fps"]
FRAMES_DIR = os.path.join(HERE, "frames")
OV_DIR = os.path.join(HERE, "overlays")
AUDIO_WAV = os.path.join(HERE, "audio", "master_audio.wav")
OUT_MP4 = os.path.join(HERE, "FLORA-01_Launch_Film_1080p.mp4")
os.makedirs(OV_DIR, exist_ok=True)


def load_font(candidates, size):
    for name in candidates:
        p = os.path.join(r"C:\Windows\Fonts", name)
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


F_LIGHT_XL = load_font(["segoeuil.ttf", "segoeui.ttf"], 92)
F_SEMI_LG  = load_font(["seguisb.ttf", "segoeuib.ttf", "segoeui.ttf"], 34)
F_REG_MD   = load_font(["segoeui.ttf"], 26)
F_MONO_SM  = load_font(["consola.ttf"], 19)
F_MONO_XS  = load_font(["consola.ttf"], 16)
F_MONO_BD  = load_font(["consolab.ttf", "consola.ttf"], 21)

LIME   = (186, 232, 92, 255)
AMBER  = (245, 178, 72, 255)
WHITE  = (246, 248, 244, 255)
SOFT   = (216, 222, 214, 230)
MUTED  = (170, 178, 170, 215)
DARK_GLASS = (16, 20, 18, 152)
DARK_LINE  = (186, 232, 92, 130)


def draw_tracked_text(draw, xy, text, font, fill, tracking=0, anchor="la"):
    """Draw cleanly tracked uppercase/display text with subtle drop shadow for crisp legibility."""
    widths = [draw.textbbox((0, 0), ch, font=font)[2] for ch in text]
    total_w = sum(widths) + tracking * max(0, len(text) - 1)
    x, y = xy
    if anchor.startswith("m"):
        x -= total_w / 2.0
    elif anchor.startswith("r"):
        x -= total_w
    # Subtle soft shadow for contrast on both dark & bright backgrounds
    cx = x
    for ch, cw in zip(text, widths):
        draw.text((cx + 1, y + 2), ch, font=font, fill=(0, 0, 0, 120))
        draw.text((cx, y), ch, font=font, fill=fill)
        cx += cw + tracking


def draw_glass_pill(img, box, border_col=DARK_LINE, fill_col=DARK_GLASS, radius=10):
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    d.rounded_rectangle(box, radius=radius, fill=fill_col, outline=border_col, width=1)
    return Image.alpha_composite(img, overlay)


def make_ov_s1_hook():
    """S1 (0.8s..5.5s): Minimal obsidian opening micro-telemetry tag (top-left)."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    im = draw_glass_pill(im, (72, 62, 540, 108), border_col=(186, 232, 92, 95), fill_col=(10, 14, 12, 145), radius=8)
    d = ImageDraw.Draw(im)
    # Glowing emerald dot indicator
    d.ellipse((92, 79, 104, 91), fill=LIME)
    draw_tracked_text(d, (118, 75), "UNIT // FLORA-01  ·  SYSTEM WAKE", F_MONO_SM, SOFT, tracking=2)
    p = os.path.join(OV_DIR, "ov_s1.png")
    im.save(p)
    return p


def make_ov_s2_title():
    """S2 (7.2s..13.0s): Crisp Apple/Rivian keynote title card bottom-left over sweeping daylight reveal."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    # Subtle soft bottom-left readability gradient pill
    im = draw_glass_pill(im, (72, 826, 725, 1006), border_col=(255, 255, 255, 45), fill_col=(14, 18, 16, 148), radius=14)
    d = ImageDraw.Draw(im)
    draw_tracked_text(d, (104, 842), "FLORA-01", F_LIGHT_XL, WHITE, tracking=10)
    d.line([(104, 944), (685, 944)], fill=(186, 232, 92, 155), width=2)
    draw_tracked_text(d, (104, 958), "AUTONOMOUS BOTANICAL QUADRUPED  ·  BUILT IN CODE", F_MONO_SM, LIME, tracking=2)
    p = os.path.join(OV_DIR, "ov_s2.png")
    im.save(p)
    return p


def measure_tracked(draw, text, font, tracking=0):
    widths = [draw.textbbox((0, 0), ch, font=font)[2] for ch in text]
    return sum(widths) + tracking * max(0, len(text) - 1)


def make_ov_s3_garden():
    """S3 (14.8s..23.8s): Clean lower-left botanical & solar spec callout (auto-fitted pill!)."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d0 = ImageDraw.Draw(im)
    t1 = "DORSAL BIOME & SUN-TRACKING CANOPY"
    t2 = "6-BAY PHOTOVOLTAIC ARRAY  ·  6-NOZZLE BRASS DRIP RING"
    t3 = "2-AXIS ARTICULATED Y-PEDESTAL  ·  FULL-SPECTRUM LED GROW DECK"
    w_max = max(measure_tracked(d0, t1, F_MONO_BD, 2), measure_tracked(d0, t2, F_MONO_SM, 1), measure_tracked(d0, t3, F_MONO_XS, 1))
    im = draw_glass_pill(im, (72, 882, int(120 + w_max + 36), 1004), border_col=(186, 232, 92, 115), fill_col=(14, 18, 16, 165), radius=12)
    d = ImageDraw.Draw(im)
    d.rectangle((96, 906, 102, 980), fill=LIME)
    draw_tracked_text(d, (120, 904), t1, F_MONO_BD, WHITE, tracking=2)
    draw_tracked_text(d, (120, 938), t2, F_MONO_SM, SOFT, tracking=1)
    draw_tracked_text(d, (120, 966), t3, F_MONO_XS, LIME, tracking=1)
    p = os.path.join(OV_DIR, "ov_s3.png")
    im.save(p)
    return p


def make_ov_s4_mechanics():
    """S4 (25.2s..34.8s): Crisp lower-left precision mechanical engineering specs (auto-fitted pill!)."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d0 = ImageDraw.Draw(im)
    t1 = "MECHANICAL ARCHITECTURE · 30-BONE RIG"
    t2 = "4-BOLT HARMONIC DRUMS  ·  AIMING HYDRAULIC ACTUATORS"
    t3 = "SOLVED STROKE: 37.8 mm  ·  AIM ERR: 0.0001 mm  ·  FLEX HOSES"
    w_max = max(measure_tracked(d0, t1, F_MONO_BD, 2), measure_tracked(d0, t2, F_MONO_SM, 1), measure_tracked(d0, t3, F_MONO_XS, 1))
    im = draw_glass_pill(im, (72, 882, int(120 + w_max + 36), 1004), border_col=(245, 178, 72, 120), fill_col=(14, 18, 16, 168), radius=12)
    d = ImageDraw.Draw(im)
    d.rectangle((96, 906, 102, 980), fill=AMBER)
    draw_tracked_text(d, (120, 904), t1, F_MONO_BD, WHITE, tracking=2)
    draw_tracked_text(d, (120, 938), t2, F_MONO_SM, SOFT, tracking=1)
    draw_tracked_text(d, (120, 966), t3, F_MONO_XS, AMBER, tracking=1)
    p = os.path.join(OV_DIR, "ov_s4.png")
    im.save(p)
    return p


def make_ov_s5_motion():
    """S5 (36.0s..45.8s): Crisp lower-left verified kinematics telemetry (auto-fitted pill!)."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d0 = ImageDraw.Draw(im)
    t1 = "ANALYTICAL IK LOCOMOTION · WALK / TROT / INSPECT"
    t2 = "GROUND PENETRATION: 0.00 mm  ·  FOOT SLIP: 0.00 mm  ·  CLASHES: 0"
    w_max = max(measure_tracked(d0, t1, F_MONO_BD, 2), measure_tracked(d0, t2, F_MONO_SM, 1))
    im = draw_glass_pill(im, (72, 892, int(120 + w_max + 36), 1004), border_col=(186, 232, 92, 120), fill_col=(14, 18, 16, 168), radius=12)
    d = ImageDraw.Draw(im)
    d.rectangle((96, 914, 102, 982), fill=LIME)
    draw_tracked_text(d, (120, 912), t1, F_MONO_BD, WHITE, tracking=2)
    draw_tracked_text(d, (120, 948), t2, F_MONO_SM, LIME, tracking=1)
    p = os.path.join(OV_DIR, "ov_s5.png")
    im.save(p)
    return p


def make_ov_s6_finale():
    """S6 (49.5s..55.8s): Clean, unforgettable final product lockup at bottom-center with rich readability scrim."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    band = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(band)
    for y in range(690, H):
        a = int(225 * ((y - 690) / (H - 690)) ** 1.35)
        bd.line([(0, y), (W, y)], fill=(10, 14, 12, a))
    im = Image.alpha_composite(im, band)
    d = ImageDraw.Draw(im)

    draw_tracked_text(d, (W // 2, 814), "FLORA-01", F_LIGHT_XL, WHITE, tracking=16, anchor="ma")
    d.line([(W // 2 - 300, 922), (W // 2 + 300, 922)], fill=(186, 232, 92, 185), width=2)
    draw_tracked_text(d, (W // 2, 938), "GROWN IN LIGHT  ·  BUILT 100% IN PYTHON", F_SEMI_LG, LIME, tracking=4, anchor="ma")
    draw_tracked_text(d, (W // 2, 990), "54,910 TRIS  ·  80 PARTS  ·  30 BONES  ·  5 VERIFIED ACTIONS  ·  BLENDER 5.2 + GEMINI", F_MONO_SM, SOFT, tracking=2, anchor="ma")
    p = os.path.join(OV_DIR, "ov_s6.png")
    im.save(p)
    return p


def main():
    # Verify all 1,344 frames exist
    missing = [f for f in range(1, TL["total_frames"] + 1) if not os.path.exists(os.path.join(FRAMES_DIR, f"frame_{f:04d}.jpg"))]
    assert not missing, f"Missing {len(missing)} frames (first few: {missing[:10]})"
    assert os.path.exists(AUDIO_WAV), f"Missing {AUDIO_WAV}"

    ov1 = make_ov_s1_hook()
    ov2 = make_ov_s2_title()
    ov3 = make_ov_s3_garden()
    ov4 = make_ov_s4_mechanics()
    ov5 = make_ov_s5_motion()
    ov6 = make_ov_s6_finale()
    print("ALL 6 MINIMALIST MOTION-GRAPHICS OVERLAYS GENERATED!")

    # FFmpeg filtergraph:
    # - Input 0: 24 fps 1080p JPEG frame sequence
    # - Input 1: 48 kHz stereo mastered audio WAV
    # - Inputs 2..7: 6 crisp RGBA PNG overlays with smooth alpha fade-in / fade-out timed to voiceover beats!
    # - Plus subtle cinematic vignette, opening 0.6s fade-from-black, and closing 0.7s fade-to-black!
    def ov_chain(idx, t_in, t_out, fd=0.55):
        return (
            f"[{idx}:v]format=rgba,"
            f"fade=t=in:st={t_in:.2f}:d={fd:.2f}:alpha=1,"
            f"fade=t=out:st={t_out - fd:.2f}:d={fd:.2f}:alpha=1[o{idx}]"
        )

    fc = ";".join([
        # Subtle cinema grade (tiny warm highlights, crisp blacks, gentle optical vignette, fade in/out)
        "[0:v]format=rgba,eq=contrast=1.04:saturation=1.07:brightness=0.005,vignette=angle=0.32[base]",
        ov_chain(2,  0.70,  5.55, 0.50),
        ov_chain(3,  6.95, 13.40, 0.60),
        ov_chain(4, 14.70, 23.90, 0.55),
        ov_chain(5, 25.10, 34.90, 0.55),
        ov_chain(6, 36.00, 45.80, 0.55),
        ov_chain(7, 49.40, 55.60, 0.70),
        "[base][o2]overlay=0:0:shortest=1[v1]",
        "[v1][o3]overlay=0:0:shortest=1[v2]",
        "[v2][o4]overlay=0:0:shortest=1[v3]",
        "[v3][o5]overlay=0:0:shortest=1[v4]",
        "[v4][o6]overlay=0:0:shortest=1[v5]",
        "[v5][o7]overlay=0:0:shortest=1,"
        "fade=t=in:st=0.0:d=0.55,fade=t=out:st=55.20:d=0.80,"
        "scale=in_range=full:out_range=tv:out_color_matrix=bt709,format=yuv420p[vout]",
        # Broadcast loudness master (-15 LUFS, -1.5 dBTP true peak) for crystal-clear X playback!
        "[1:a]loudnorm=I=-15:TP=-1.5:LRA=9[aout]",
    ])

    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(FPS),
        "-i", os.path.join(FRAMES_DIR, "frame_%04d.jpg"),
        "-i", AUDIO_WAV,
        "-loop", "1", "-t", str(TL["duration_s"]), "-i", ov1,
        "-loop", "1", "-t", str(TL["duration_s"]), "-i", ov2,
        "-loop", "1", "-t", str(TL["duration_s"]), "-i", ov3,
        "-loop", "1", "-t", str(TL["duration_s"]), "-i", ov4,
        "-loop", "1", "-t", str(TL["duration_s"]), "-i", ov5,
        "-loop", "1", "-t", str(TL["duration_s"]), "-i", ov6,
        "-filter_complex", fc,
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "slow", "-crf", "16",
        "-profile:v", "high", "-level:v", "4.1", "-pix_fmt", "yuv420p",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
        "-r", str(FPS),
        "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart",
        "-shortest",
        OUT_MP4,
    ]
    print("RUNNING FFMPEG MASTER ENCODE...")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("FFMPEG STDERR:\n", res.stderr[-2500:])
        raise RuntimeError(f"FFmpeg failed with code {res.returncode}")
    mb = os.path.getsize(OUT_MP4) / (1024 * 1024)
    print(f"FINAL LAUNCH FILM READY: {OUT_MP4} ({mb:.2f} MB)")

    # Extract a 3x2 visual QA proof sheet straight from the FINAL encoded MP4!
    proof_p = os.path.join(HERE, "final_video_proof_sheet.png")
    cmd_q = [
        "ffmpeg", "-y", "-i", OUT_MP4,
        "-vf", "select='eq(n,60)+eq(n,230)+eq(n,440)+eq(n,660)+eq(n,920)+eq(n,1280)',scale=640:360,tile=3x2",
        "-frames:v", "1", proof_p,
    ]
    subprocess.run(cmd_q, check=True, capture_output=True)
    print(f"VIDEO PROOF SHEET SAVED: {proof_p}")


if __name__ == "__main__":
    main()
