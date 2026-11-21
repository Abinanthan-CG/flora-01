# run_render_all.py — Crash-proof resumable batch render orchestrator + final MP4 mastering.
# Runs Blender 5.2 in clean 160-frame GPU batches (fresh VRAM each batch, skipping existing frames),
# retries any transient driver hiccup, verifies all 1,344 frames, and runs compose_video.py!

import os
import sys
import json
import time
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
TL = json.load(open(os.path.join(HERE, "timeline.json"), "r"))
TOTAL = TL["total_frames"]
FRAMES_DIR = os.path.join(HERE, "frames")
BLENDER = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
RENDER_SCRIPT = os.path.join(HERE, "render_film.py")
COMPOSE_SCRIPT = os.path.join(HERE, "compose_video.py")
BATCH = 150


def missing_frames():
    return [
        f for f in range(1, TOTAL + 1)
        if not (os.path.exists(os.path.join(FRAMES_DIR, f"frame_{f:04d}.jpg"))
                and os.path.getsize(os.path.join(FRAMES_DIR, f"frame_{f:04d}.jpg")) > 10000)
    ]


def main():
    t_all = time.time()
    # Delete any half-written corrupt tiny frame files (< 10 KB) before starting
    for f in range(1, TOTAL + 1):
        p = os.path.join(FRAMES_DIR, f"frame_{f:04d}.jpg")
        if os.path.exists(p) and os.path.getsize(p) <= 10000:
            os.remove(p)

    for attempt in range(25):
        miss = missing_frames()
        if not miss:
            break
        f0 = miss[0]
        f1 = min(TOTAL, f0 + BATCH - 1)
        print(f"=== BATCH {attempt + 1}: rendering [{f0}..{f1}] ({len(miss)} frames remaining overall) ===", flush=True)
        cmd = [
            BLENDER, "-b", "--factory-startup", "-t", "4",
            "--python", RENDER_SCRIPT, "--", "--range", str(f0), str(f1),
        ]
        res = subprocess.run(cmd)
        if res.returncode != 0:
            print(f"  Batch [{f0}..{f1}] exited {res.returncode} — resuming cleanly from next missing frame...", flush=True)
            time.sleep(2.0)

    miss = missing_frames()
    assert not miss, f"Still missing {len(miss)} frames after retries: {miss[:10]}"
    print(f"ALL {TOTAL} FRAMES RENDERED in {(time.time() - t_all)/60:.1f} min! Running compose_video.py...", flush=True)

    res2 = subprocess.run([sys.executable, COMPOSE_SCRIPT], check=True)
    print(f"END-TO-END LAUNCH FILM PIPELINE COMPLETE in {(time.time() - t_all)/60:.1f} min!", flush=True)


if __name__ == "__main__":
    main()
