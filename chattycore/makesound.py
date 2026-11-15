"""The chatty creatures' voices: generate takes with MOSS-SoundEffect, pick, build the mod's FMOD bank.

A mod's tools/sound/voice.json lists its events (prompt, seconds, takes, volume_db, pitch_rand). Its picks
(tools/sound/picks.json: {event: [take, ...]}) are the takes that go in; several per event play at random.

    python chattycore/makesound.py jobs   <mod>   # writes the MOSS job list (raw takes: audio-gen/chatty_raw/<mod>/)
    <audiogen-moss python> audio-gen/gen_moss.py audio-gen/chatty_raw/<mod>/jobs.json --skip-existing
    <audiogen-moss python> chattycore/makesound.py review <mod>   # stats + auto picks (missing ones) + review.html
    <audiogen-moss python> chattycore/makesound.py build  <mod>   # picks -> tools/sound/wav/ -> <mod>/sound/*.fev/.fsb

review and build need numpy and soundfile (the audiogen-moss env has them). The game plays "<mod>/<group>/<event>"
(voice.json's name and group); modmain loads sound/<mod>.fev and sound/<mod>.fsb.
"""
import html
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RAW = r"C:\Users\seann\Projects\audio-gen\chatty_raw"
TAKES = 4
STEPS = 100


def load(mod):
    d = os.path.join(ROOT, mod, "tools", "sound")
    with open(os.path.join(d, "voice.json"), encoding="utf-8") as f:
        return d, json.load(f)


def raw_dir(mod):
    return os.path.join(RAW, mod)


def jobs(mod):
    d, v = load(mod)
    out = []
    for ev, e in v["events"].items():
        for seed in range(1, e.get("takes", TAKES) + 1):
            out.append({"prompt": e["prompt"] + " " + v["style"], "seed": seed, "out": "%s_%d.wav" % (ev, seed),
                        "seconds": e.get("seconds", 1.5) + 0.4, "steps": STEPS, "cfg_scale": 4.0})
    os.makedirs(raw_dir(mod), exist_ok=True)
    p = os.path.join(raw_dir(mod), "jobs.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print("%d jobs -> %s" % (len(out), p))


# ---- audio (numpy) ----

def read_mono(path):
    import numpy as np
    import soundfile as sf
    a, sr = sf.read(path, dtype="float32", always_2d=True)
    return a.mean(axis=1).astype(np.float32), sr


def trim(a, sr, floor_db=-40.0):
    """Cut leading/trailing quiet (below floor_db of the peak, in 10 ms windows); short fades."""
    import numpy as np
    win = max(1, sr // 100)
    n = len(a) // win
    if n == 0:
        return a
    rms = np.sqrt((a[:n * win].reshape(n, win) ** 2).mean(axis=1) + 1e-12)
    th = rms.max() * 10 ** (floor_db / 20)
    on = np.nonzero(rms > th)[0]
    if len(on) == 0:
        return a[:0]
    s, e = max(0, on[0] - 1) * win, min(len(a), (on[-1] + 3) * win)
    a = a[s:e].copy()
    fi, fo = min(len(a), sr // 200), min(len(a), sr // 25)
    if fi:
        a[:fi] *= np.linspace(0, 1, fi, dtype=np.float32)
    if fo:
        a[-fo:] *= np.linspace(1, 0, fo, dtype=np.float32)
    return a


def crop(a, sr, seconds):
    """Only its first seconds (a one-shot: one plop, not the train of them the model tends to make); a fade out."""
    import numpy as np
    if not seconds or len(a) <= int(seconds * sr):
        return a
    a = a[: int(seconds * sr)].copy()
    fo = int(len(a) * 0.3)
    a[-fo:] *= np.linspace(1, 0, fo, dtype=np.float32) ** 2
    return a


def prepared(path, e):
    """A take as it goes in the bank: mono, trimmed, cropped (voice.json's "crop"), at an even loudness."""
    import numpy as np
    a, sr = read_mono(path)
    a = crop(trim(a, sr), sr, e.get("crop"))
    if len(a):
        rms = float(np.sqrt((a ** 2).mean())) + 1e-9
        a = a * min(10 ** (-1 / 20) / max(1e-6, float(np.abs(a).max())), 10 ** (LEVEL_DB / 20) / rms)
    return a, sr


LEVEL_DB = -16        # (each take's loudness, RMS; its peak at most -1 dBFS)
CLIPPED = 0.001       # (more than 0.1 % of its samples at full scale: a clipped take)


def stats(path, e=None):
    import numpy as np
    a, sr = read_mono(path)
    clipped = float((np.abs(a) > 0.99).mean()) if len(a) else 0.0
    peak_raw = float(np.abs(a).max()) if len(a) else 0.0
    t = crop(trim(a, sr), sr, (e or {}).get("crop"))
    if len(t) < sr // 50:
        return {"dur": 0.0, "peak": peak_raw, "rms_db": -120.0, "flat": 1.0, "ok": False, "why": "silent"}
    spec = np.abs(np.fft.rfft(t[: sr * 3] * np.hanning(min(len(t), sr * 3)))) + 1e-9
    flat = float(np.exp(np.log(spec).mean()) / spec.mean())        # 0 tonal .. 1 noise
    rms_db = float(20 * np.log10(np.sqrt((t ** 2).mean()) + 1e-12))
    why = []
    if clipped > CLIPPED:
        why.append("clipped %.1f%%" % (clipped * 100))
    if rms_db < -45:
        why.append("very quiet")
    return {"dur": round(len(t) / sr, 2), "peak": round(peak_raw, 3), "rms_db": round(rms_db, 1),
            "flat": round(flat, 3), "ok": not why, "why": ", ".join(why)}


def review(mod):
    d, v = load(mod)
    pp = os.path.join(d, "picks.json")
    picks = json.load(open(pp, encoding="utf-8")) if os.path.isfile(pp) else {}
    rows, changed = [], False
    for ev, e in v["events"].items():
        n, want = e.get("crop") or e.get("seconds", 1.5), e.get("keep", 3)
        takes = []
        for seed in range(1, e.get("takes", TAKES) + 1):
            p = os.path.join(raw_dir(mod), "%s_%d.wav" % (ev, seed))
            if os.path.isfile(p):
                s = stats(p, e)
                import soundfile as sf      # (the page plays each take as it would go in the bank)
                a, sr = prepared(p, e)
                os.makedirs(os.path.join(raw_dir(mod), "prepared"), exist_ok=True)
                sf.write(os.path.join(raw_dir(mod), "prepared", os.path.basename(p)), a, sr, subtype="PCM_16")
                p = os.path.join(raw_dir(mod), "prepared", os.path.basename(p))
                # (closer to the length asked for, then the less noisy: a voice, not hiss)
                s["score"] = (abs(s["dur"] - n) / n) + s["flat"] if s["ok"] else 99
                takes.append((seed, p, s))
        if ev not in picks and takes:
            good = sorted((t for t in takes if t[2]["ok"]), key=lambda t: t[2]["score"])
            picks[ev] = sorted(t[0] for t in good[:want])
            changed = True
        rows.append((ev, e, takes))
    if changed:
        with open(pp, "w", encoding="utf-8") as f:
            json.dump(picks, f, indent=1)
    page = ["<!doctype html><meta charset=utf-8><title>%s voice takes</title>" % v["name"],
            "<style>body{font:14px system-ui;margin:16px;background:#fff;color:#222}td{padding:3px 8px}"
            "tr.pick{background:#e6f4e6}.bad{color:#b00}</style>",
            "<h1>%s takes</h1><p>Green rows are in tools/sound/picks.json.</p>" % html.escape(v["name"])]
    for ev, e, takes in rows:
        page.append("<h2>%s</h2><p>%s</p><table>" % (html.escape(ev), html.escape(e["prompt"])))
        for seed, p, s in takes:
            cls = "pick" if seed in picks.get(ev, []) else ""
            page.append("<tr class='%s'><td>take %d</td><td><audio controls preload=none src='file:///%s'></audio></td>"
                        "<td>%.2f s</td><td>%.1f dB</td><td>noise %.2f</td><td class=bad>%s</td></tr>"
                        % (cls, seed, p.replace("\\", "/"), s["dur"], s["rms_db"], s["flat"], html.escape(s["why"])))
        page.append("</table>")
    hp = os.path.join(raw_dir(mod), "review.html")
    with open(hp, "w", encoding="utf-8") as f:
        f.write("\n".join(page))
    for ev, e, takes in rows:
        print("%-13s picks %-12s %s" % (ev, picks.get(ev), "  ".join(
            "%d:%.2fs/%.0fdB/n%.2f%s" % (sd, s["dur"], s["rms_db"], s["flat"], "!" + s["why"] if s["why"] else "")
            for sd, _, s in takes)))
    print("review page:", hp)


def build(mod):
    import numpy as np
    import soundfile as sf
    sys.path.insert(0, HERE)
    import fmodbank
    d, v = load(mod)
    picks = json.load(open(os.path.join(d, "picks.json"), encoding="utf-8"))
    wav = os.path.join(d, "wav")
    os.makedirs(wav, exist_ok=True)
    for f in os.listdir(wav):
        if f.endswith(".wav"):
            os.remove(os.path.join(wav, f))
    events = {}
    for ev, e in v["events"].items():
        files = []
        for i, seed in enumerate(picks.get(ev, [])):
            a, sr = prepared(os.path.join(raw_dir(mod), "%s_%d.wav" % (ev, seed)), e)
            p = os.path.join(wav, "%s_%d.wav" % (ev, i + 1))
            sf.write(p, a.astype(np.float32), sr, subtype="PCM_16")
            files.append(p)
        if files:
            events[ev] = {"files": files, "volume_db": e.get("volume_db", 0), "pitch_rand": e.get("pitch_rand", 0),
                          "min": 3, "max": 30, "maxplaybacks": e.get("maxplaybacks", 4)}
    out = os.path.join(ROOT, mod, "sound")
    fev, fsb, log = fmodbank.build(v["name"], v["group"], events, out, os.path.join(raw_dir(mod), "fdp"))
    for junk in (".fsbcache",):
        p = os.path.join(out, junk)
        if os.path.isdir(p):
            import shutil
            shutil.rmtree(p)
    print("built %s (%d bytes), %s (%d bytes): %d events, %d takes" % (
        fev, os.path.getsize(fev), fsb, os.path.getsize(fsb), len(events), sum(len(e["files"]) for e in events.values())))


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("jobs", "review", "build"):
        sys.exit(__doc__)
    {"jobs": jobs, "review": review, "build": build}[sys.argv[1]](sys.argv[2])
