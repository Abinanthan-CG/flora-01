# build_soundtrack.py — Synthesizes the warm solarpunk analog ambient score, mechanical foley
# (power-up chime, sunrise swell, hydraulic hiss, servo ticks, synced paw footsteps), and masters
# the 6 Gemini 3.8 Flash TTS voiceover tracks with smooth sidechain ducking to 48 kHz stereo WAV.

import os
import json
import wave
import math
import numpy as np
from scipy import signal

HERE = os.path.dirname(os.path.abspath(__file__))
TL = json.load(open(os.path.join(HERE, "timeline.json"), "r"))
SR = 48000
DUR = TL["duration_s"]
N = int(round(DUR * SR))
T = np.arange(N, dtype=np.float32) / SR


def load_vo_trimmed(rel_path):
    p = os.path.join(HERE, rel_path)
    with wave.open(p, "rb") as w:
        sr_in = w.getframerate()
        ch = w.getnchannels()
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        pcm = pcm.reshape(-1, ch).mean(axis=1)
    # Trim leading/trailing dead silence with gentle 12 ms fades
    nz = np.where(np.abs(pcm) > 0.012)[0]
    if len(nz):
        i0 = max(0, nz[0] - int(0.03 * sr_in))
        i1 = min(len(pcm), nz[-1] + int(0.06 * sr_in))
        pcm = pcm[i0:i1]
    # Resample cleanly to 48 kHz
    n_out = int(round(len(pcm) * SR / sr_in))
    pcm48 = signal.resample_poly(pcm, SR // math.gcd(SR, sr_in), sr_in // math.gcd(SR, sr_in)).astype(np.float32)
    # High-pass 85 Hz rumble filter + subtle 3.2 kHz keynote vocal presence boost
    sos_hp = signal.butter(2, 85.0, btype="highpass", fs=SR, output="sos")
    pcm48 = signal.sosfilt(sos_hp, pcm48).astype(np.float32)
    sos_bp = signal.butter(2, [2400.0, 5200.0], btype="bandpass", fs=SR, output="sos")
    pcm48 = pcm48 + 0.16 * signal.sosfilt(sos_bp, pcm48).astype(np.float32)
    # Normalize RMS cleanly
    rms = float(np.sqrt(np.mean(pcm48 ** 2) + 1e-12))
    pcm48 = pcm48 * (0.17 / rms)
    # Smooth 15 ms edge fades
    fd = min(len(pcm48) // 4, int(0.015 * SR))
    if fd > 1:
        pcm48[:fd] *= np.linspace(0, 1, fd, dtype=np.float32)
        pcm48[-fd:] *= np.linspace(1, 0, fd, dtype=np.float32)
    return pcm48


def stereo_reverb(sig_st, wet=0.28, decay=0.45):
    """Lush stereo Schroeder multi-tap feedback comb + diffuser reverb."""
    out = np.zeros_like(sig_st)
    delays_ms_L = [29.7, 37.1, 41.9, 53.3, 67.1, 83.7]
    delays_ms_R = [31.3, 39.7, 44.3, 56.9, 71.3, 89.1]
    for ch, dlist in enumerate((delays_ms_L, delays_ms_R)):
        acc = np.zeros(len(sig_st), dtype=np.float32)
        x = sig_st[:, ch]
        for k, d_ms in enumerate(dlist):
            d = int(round(d_ms * SR / 1000.0))
            g = decay * (0.86 ** k)
            # 3-echo cascaded tap approximation (fast vectorized numpy!)
            y = np.zeros_like(x)
            for tap in range(1, 8):
                sh = d * tap
                if sh < len(x):
                    y[sh:] += (g ** tap) * x[:-sh]
            acc += y / len(dlist)
        # Warm low-pass on reverb tail (damps harsh highs like a wooden studio)
        sos = signal.butter(2, 3400.0, btype="lowpass", fs=SR, output="sos")
        out[:, ch] = signal.sosfilt(sos, acc).astype(np.float32)
    return sig_st * (1.0 - wet * 0.4) + out * wet


def midi_to_hz(m):
    return 440.0 * (2.0 ** ((m - 69.0) / 12.0))


def synth_warm_pad(freq, start_s, dur_s, amp=0.10, detune=0.0035, pan=0.0):
    """Warm analog Juno-style detuned polyphonic pad voice with gentle attack & release."""
    n_s = int(round(dur_s * SR))
    t = np.arange(n_s, dtype=np.float32) / SR
    # 3 detuned oscillators (rich fundamental + warm octave/2nd harmonic)
    v1 = np.sin(2 * math.pi * freq * t)
    v2 = np.sin(2 * math.pi * freq * (1.0 + detune) * t + 0.7) * 0.65
    v3 = np.sin(2 * math.pi * freq * (1.0 - detune) * t + 1.9) * 0.65
    v4 = np.sin(2 * math.pi * freq * 2.0 * t + 0.3) * 0.22
    v5 = np.sin(2 * math.pi * freq * 3.0 * t + 1.1) * 0.08
    sig = (v1 + v2 + v3 + v4 + v5) / 2.6
    # Gentle breathing LFO
    sig *= (1.0 + 0.08 * np.sin(2 * math.pi * 0.32 * t))
    # Smooth cosine envelope
    atk = min(n_s // 2, int(1.4 * SR))
    rel = min(n_s // 2, int(1.8 * SR))
    env = np.ones(n_s, dtype=np.float32)
    env[:atk] = 0.5 * (1.0 - np.cos(math.pi * np.linspace(0, 1, atk)))
    env[-rel:] = 0.5 * (1.0 + np.cos(math.pi * np.linspace(0, 1, rel)))
    sig *= env * amp
    gL = math.sqrt(0.5 * (1.0 - pan))
    gR = math.sqrt(0.5 * (1.0 + pan))
    return int(round(start_s * SR)), np.stack([sig * gL, sig * gR], axis=1)


def synth_glass_pluck(freq, start_s, amp=0.075, pan=0.0, decay_s=1.6):
    """Crystalline solarpunk glass-marimba / kalimba bell pluck."""
    n_s = int(round(decay_s * SR))
    t = np.arange(n_s, dtype=np.float32) / SR
    env = np.exp(-t / (decay_s * 0.28)) * (1.0 - np.exp(-t / 0.004))
    h1 = np.sin(2 * math.pi * freq * t)
    h2 = 0.28 * np.sin(2 * math.pi * freq * 2.0 * t) * np.exp(-t / 0.18)
    h3 = 0.14 * np.sin(2 * math.pi * freq * 3.98 * t) * np.exp(-t / 0.09)
    sig = (h1 + h2 + h3) * env * amp
    gL = math.sqrt(0.5 * (1.0 - pan))
    gR = math.sqrt(0.5 * (1.0 + pan))
    return int(round(start_s * SR)), np.stack([sig * gL, sig * gR], axis=1)


def add_stereo(buf, i0, clip):
    if i0 >= len(buf): return
    n_c = min(len(clip), len(buf) - i0)
    if n_c > 0:
        buf[i0:i0 + n_c] += clip[:n_c]


def build_music_score():
    """Warm optimistic solarpunk D-major9 / Bm9 / Gmaj9 / A6add9 cinematic ambient score."""
    music = np.zeros((N, 2), dtype=np.float32)

    # Chord progression timed cleanly to our 6 visual chapters:
    # S1 (0-6s):   D5 mystery drone (D2, A2, D3, F#3) — soft, atmospheric
    # S2 (6-14s):  Dmaj9 sunrise bloom (D2, A2, D3, F#3, A3, C#4, E4)
    # S3 (14-24.5): Gmaj9 -> Bm9 lush botanical wonder
    # S4 (24.5-35.5): A6add9 -> F#m7 kinetic precision pulse
    # S5 (35.5-46.5): Gmaj9 -> A9 -> Bm7 -> Dmaj9 kinetic momentum
    # S6 (46.5-56s):  Dmaj9 radiant orchestral bloom -> peaceful fadeout
    chords = [
        (0.0,  7.0,  [38, 45, 50, 57],             0.055),  # S1 D5 obsidian mystery
        (5.6,  9.2,  [38, 45, 50, 54, 57, 61, 64], 0.088),  # S2 Dmaj9 daylight bloom!
        (13.8, 6.2,  [43, 50, 55, 59, 62, 66],     0.085),  # S3a Gmaj9 garden wonder
        (19.2, 6.2,  [47, 54, 59, 62, 66, 69],     0.082),  # S3b Bm7/9 canopy
        (24.4, 6.2,  [45, 52, 57, 61, 64, 66],     0.082),  # S4a A6 mechanics
        (29.8, 6.4,  [42, 49, 54, 57, 61, 64],     0.080),  # S4b F#m7 precision
        (35.4, 5.8,  [43, 50, 55, 59, 62, 66],     0.088),  # S5a Gmaj9 walk
        (40.4, 6.6,  [45, 52, 57, 61, 64, 69],     0.090),  # S5b A9 trot->inspect
        (46.2, 9.8,  [38, 45, 50, 54, 57, 61, 64, 69], 0.095),  # S6 Dmaj9 radiant finale!
    ]
    for st, dur, notes, amp in chords:
        for k, m in enumerate(notes):
            pan = -0.45 + 0.90 * (k / max(1, len(notes) - 1))
            note_amp = amp * (1.25 if k == 0 else (0.90 if k < 3 else 0.62))
            i0, cl = synth_warm_pad(midi_to_hz(m), st, dur, amp=note_amp, pan=pan)
            add_stereo(music, i0, cl)

    # Crystalline pentatonic D-major arpeggio sparkles (S2 reveal, S3 garden, S5 motion, S6 finale!)
    arp_notes = [62, 66, 69, 73, 74, 76, 78, 81]  # D4, F#4, A4, C#5, D5, E5, F#5, A5
    # Delicate ascending sunrise motif at 6.1s
    for idx, m in enumerate([62, 66, 69, 73, 76, 81]):
        i0, cl = synth_glass_pluck(midi_to_hz(m), 6.05 + idx * 0.24, amp=0.055, pan=-0.5 + 0.2 * idx, decay_s=2.2)
        add_stereo(music, i0, cl)
    # Botanical garden crystalline shimmer pattern (14.2s..24.0s)
    pat_g = [66, 71, 74, 78, 74, 71, 69, 74, 78, 81, 78, 74]
    for k in range(28):
        tm = 14.2 + k * 0.34
        if tm < 24.0:
            m = pat_g[k % len(pat_g)]
            i0, cl = synth_glass_pluck(midi_to_hz(m), tm, amp=0.042, pan=0.45 * math.sin(k * 0.7), decay_s=1.8)
            add_stereo(music, i0, cl)
    # Kinetic subtle pulse & precision arpeggio (25.0s..45.5s)
    pat_m = [69, 73, 76, 73, 69, 74, 78, 74]
    for k in range(44):
        tm = 25.0 + k * 0.45
        if tm < 45.2:
            m = pat_m[k % len(pat_m)]
            i0, cl = synth_glass_pluck(midi_to_hz(m), tm, amp=0.036, pan=0.35 * math.cos(k * 0.9), decay_s=1.2)
            add_stereo(music, i0, cl)
            # Soft warm muted pulse kick on alternating beats during S4/S5
            if k % 2 == 0 and 25.5 < tm < 44.5:
                nk = int(0.18 * SR)
                tk = np.arange(nk, dtype=np.float32) / SR
                f_sweep = 95.0 * np.exp(-tk / 0.035) + 44.0
                ph = 2 * math.pi * np.cumsum(f_sweep) / SR
                kick = np.sin(ph) * np.exp(-tk / 0.055) * 0.13
                add_stereo(music, int(tm * SR), np.stack([kick, kick], axis=1))
    # Final radiant ascending chime at 46.8s & 52.8s
    for idx, m in enumerate([62, 66, 69, 73, 74, 78, 81, 86]):
        i0, cl = synth_glass_pluck(midi_to_hz(m), 46.7 + idx * 0.28, amp=0.052, pan=-0.55 + 0.15 * idx, decay_s=2.8)
        add_stereo(music, i0, cl)
    for idx, m in enumerate([74, 78, 81, 86]):
        i0, cl = synth_glass_pluck(midi_to_hz(m), 52.6 + idx * 0.32, amp=0.048, pan=-0.3 + 0.2 * idx, decay_s=3.2)
        add_stereo(music, i0, cl)

    # Evolving filter brightness: warm & dark in S1 (0-6s), blooms bright from 6s onward!
    sos_dark = signal.butter(2, 650.0, btype="lowpass", fs=SR, output="sos")
    dark_m = np.stack([signal.sosfilt(sos_dark, music[:, 0]), signal.sosfilt(sos_dark, music[:, 1])], axis=1).astype(np.float32)
    bright_mix = np.clip((T - 4.8) / 2.2, 0.0, 1.0)[:, None]
    music = dark_m * (1.0 - bright_mix) + music * bright_mix

    # Add lush stereo reverb
    music = stereo_reverb(music, wet=0.34, decay=0.48)

    # Clean fade-in (0.8s) and graceful finale fade-out (53.2s..56.0s)
    fi = int(0.8 * SR)
    fo = int(2.8 * SR)
    music[:fi] *= np.linspace(0, 1, fi, dtype=np.float32)[:, None]
    music[-fo:] *= (0.5 * (1.0 + np.cos(math.pi * np.linspace(0, 1, fo, dtype=np.float32))))[:, None]
    return music


def build_sfx():
    """Tactile mechanical & botanical foley synced to exact shots and paw strikes."""
    sfx = np.zeros((N, 2), dtype=np.float32)
    rng = np.random.default_rng(2026)

    def add_band_noise(start_s, dur_s, f_lo, f_hi, amp, pan=0.0, atk_frac=0.25):
        ns = int(round(dur_s * SR))
        noise = rng.normal(0, 1, ns).astype(np.float32)
        sos = signal.butter(3, [f_lo, f_hi], btype="bandpass", fs=SR, output="sos")
        y = signal.sosfilt(sos, noise).astype(np.float32)
        env = np.maximum(0.0, np.sin(math.pi * np.linspace(0, 1, ns, dtype=np.float32))) ** 1.3
        y = y * env * amp
        gL, gR = math.sqrt(0.5 * (1.0 - pan)), math.sqrt(0.5 * (1.0 + pan))
        add_stereo(sfx, int(start_s * SR), np.stack([y * gL, y * gR], axis=1))

    def add_servo_glide(start_s, dur_s, f0, f1, amp=0.025, pan=0.0):
        ns = int(round(dur_s * SR))
        t = np.arange(ns, dtype=np.float32) / SR
        freq = np.linspace(f0, f1, ns, dtype=np.float32)
        ph = 2 * math.pi * np.cumsum(freq) / SR
        y = (0.65 * np.sin(ph) + 0.25 * np.sin(2.0 * ph) + 0.10 * np.sin(3.0 * ph))
        env = np.maximum(0.0, np.sin(math.pi * np.linspace(0, 1, ns, dtype=np.float32))) ** 1.5
        y = y * env * amp
        gL, gR = math.sqrt(0.5 * (1.0 - pan)), math.sqrt(0.5 * (1.0 + pan))
        add_stereo(sfx, int(start_s * SR), np.stack([y * gL, y * gR], axis=1))

    def add_footstep(time_s, amp=0.075, pan=0.0):
        """Crisp rubber-paw floor tap + tiny harmonic servo click."""
        ns = int(0.095 * SR)
        t = np.arange(ns, dtype=np.float32) / SR
        thud = np.sin(2 * math.pi * (140.0 * np.exp(-t / 0.014) + 52.0) * t) * np.exp(-t / 0.022)
        click = rng.normal(0, 1, ns).astype(np.float32) * np.exp(-t / 0.008)
        sos = signal.butter(2, [800, 3200], btype="bandpass", fs=SR, output="sos")
        click = signal.sosfilt(sos, click).astype(np.float32)
        y = (0.72 * thud + 0.28 * click) * amp
        gL, gR = math.sqrt(0.5 * (1.0 - pan)), math.sqrt(0.5 * (1.0 + pan))
        add_stereo(sfx, int(time_s * SR), np.stack([y * gL, y * gR], axis=1))

    # S1 (0.4s): Subtle futuristic boot-up hum & optical lens focus chime
    add_servo_glide(0.45, 1.3, 180.0, 420.0, amp=0.022, pan=0.0)
    add_stereo(sfx, *synth_glass_pluck(midi_to_hz(74), 0.75, amp=0.045, pan=0.0, decay_s=1.4))

    # S2 (5.7s): Warm sunrise airy whoosh as studio illuminates
    add_band_noise(5.5, 1.8, 220, 1400, amp=0.032, pan=0.0)

    # S3 (15.2s & 19.5s): Soft canopy servo tilt + delicate misting nozzle shimmer
    add_servo_glide(15.2, 2.0, 260.0, 340.0, amp=0.014, pan=-0.15)
    add_band_noise(18.6, 1.2, 3200, 7800, amp=0.018, pan=0.1)

    # S4 (25.5s..34.8s): Macro hydraulic actuator strokes (soft pressurized whisper + precision servo)
    for t_h in (25.4, 27.6, 29.8, 32.0):
        add_servo_glide(t_h, 0.9, 310.0, 440.0, amp=0.018, pan=-0.2)
        add_band_noise(t_h + 0.1, 0.65, 1100, 3800, amp=0.020, pan=-0.2)

    # S5a Walk footsteps (35.5s..39.5s, 2.0s cycle, 4 paws offset by 0.50s -> RL, FL, RR, FR)
    for cyc in range(2):
        base = 35.5 + cyc * 2.0
        for p_off, pan in ((0.00, -0.25), (0.50, -0.22), (1.00, 0.25), (1.50, 0.22)):
            add_footstep(base + p_off, amp=0.068, pan=pan)

    # S5b Trot footsteps (39.5s..43.0s, 1.167s cycle, diagonal pairs every 0.583s)
    for step_i in range(6):
        tm = 39.5 + step_i * (28.0 / 24.0 / 2.0)
        add_footstep(tm, amp=0.088, pan=-0.18 if step_i % 2 == 0 else 0.18)

    # S5c Inspect bow servo glide (43.2s..46.0s)
    add_servo_glide(43.2, 1.5, 360.0, 220.0, amp=0.020, pan=0.0)
    add_servo_glide(44.9, 1.2, 220.0, 340.0, amp=0.018, pan=0.0)

    # S6 Sun Bloom Stretch regal hydraulic lift + canopy sweep
    add_servo_glide(47.0, 2.2, 240.0, 390.0, amp=0.016, pan=0.0)
    add_band_noise(47.4, 1.4, 900, 2800, amp=0.014, pan=0.1)

    return stereo_reverb(sfx, wet=0.18, decay=0.30)


def main():
    vo_bus = np.zeros((N, 2), dtype=np.float32)
    vo_env = np.zeros(N, dtype=np.float32)

    for sh in TL["shots"]:
        v = load_vo_trimmed(sh["vo_file"])
        i0 = int(round(sh["vo_start_s"] * SR))
        clip_st = np.stack([v, v], axis=1)
        add_stereo(vo_bus, i0, clip_st)
        # Voice envelope detector for smooth sidechain ducking
        n_c = min(len(v), N - i0)
        if n_c > 0:
            vo_env[i0:i0 + n_c] = np.maximum(vo_env[i0:i0 + n_c], np.abs(v[:n_c]))
        print(f"  placed {sh['vo_file']:24s} @ {sh['vo_start_s']:5.2f}s .. {sh['vo_start_s']+len(v)/SR:5.2f}s (shot ends {sh['end_s']:.2f}s)")

    # Light intimate studio room tail on voice
    vo_bus = stereo_reverb(vo_bus, wet=0.08, decay=0.22)

    # Smooth sidechain ducking envelope (smooth 180 ms release so music gently breathes around speech!)
    win = int(0.28 * SR)
    kernel = np.hanning(win).astype(np.float32)
    kernel /= kernel.sum()
    smooth_env = signal.fftconvolve(vo_env, kernel, mode="same").astype(np.float32)
    duck_mask = np.clip(smooth_env / 0.045, 0.0, 1.0)
    # Duck music down to 44% (-7.1 dB) during speech, 100% during open visual swells!
    music_gain = (1.0 - 0.56 * duck_mask)[:, None]

    music = build_music_score()
    sfx = build_sfx()

    master = vo_bus * 1.18 + music * music_gain * 0.85 + sfx * 0.90

    # Gentle broadcast mastering soft-limiter (tanh ceiling at -1.0 dBFS, zero digital clipping!)
    peak = float(np.max(np.abs(master)))
    if peak > 0.88:
        master = np.tanh(master * (0.95 / peak)) * 0.92
    else:
        master = master * (0.88 / max(peak, 1e-6))

    assert np.isfinite(master).all(), "Audio master contains NaN/Inf!"
    out_wav = os.path.join(HERE, "audio", "master_audio.wav")
    pcm16 = np.clip(master * 32767.0, -32768, 32767).astype(np.int16)
    rms_db = 20.0 * math.log10(float(np.sqrt(np.mean(master ** 2))) + 1e-12)
    peak_db = 20.0 * math.log10(float(np.max(np.abs(master))) + 1e-12)
    print(f"AUDIO METERS: RMS={rms_db:.1f} dBFS, Peak={peak_db:.1f} dBFS, 0 NaNs")
    with wave.open(out_wav, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm16.tobytes())
    print(f"MASTER AUDIO WRITTEN: {out_wav} ({os.path.getsize(out_wav)/1024:.1f} KB, {DUR:.2f}s @ {SR}Hz stereo)")


if __name__ == "__main__":
    main()
