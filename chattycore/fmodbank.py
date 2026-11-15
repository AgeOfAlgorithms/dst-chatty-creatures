"""Build a DST sound bank (FMOD Designer 4.44: <name>.fev + <name>.fsb) from a list of events and their .wav takes.

DST plays an event as "<name>/<group>/<event>" (the .fev's project name first). The mod loads it with
Asset("SOUNDPACKAGE", "sound/<name>.fev") and Asset("SOUND", "sound/<name>.fsb").

    build(name, group, events, out_dir, work_dir)
      events: {event: {"files": [wav, ...], "volume_db": 0, "pitch_rand": 0 (octaves), "volume_rand": 0 (dB),
                       "min": 3, "max": 30 (3D distances), "maxplaybacks": 4}}
      Several files: FMOD picks one at random (never the same twice in a row) each time it plays.
      3D, Linear rolloff, 3 to 30: what 4728 of DST's 6030 own events use (read from data/sound/*.fev, 2026-11-05).

It writes <work_dir>/<name>.fdp (the takes copied next to it) and runs the Mod Tools' fmod_designercl.exe, which
writes <out_dir>/<name>.fev and <name>.fsb.
"""
import os
import shutil
import subprocess
import uuid
from xml.sax.saxutils import escape

DESIGNERCL = (r"C:\Program Files (x86)\Steam\steamapps\common\Don't Starve Mod Tools\mod_tools\FMOD_Designer"
              r"\fmod_designercl.exe")


def _guid():
    return "{%s}" % uuid.uuid4()


def _tags(pairs):
    return "".join("<%s>%s</%s>\n" % (k, escape(str(v)), k) for k, v in pairs)


def _sounddef(name, waves, bank):
    out = "<sounddef>\n" + _tags([
        ("name", "/" + name), ("guid", _guid()), ("type", "randomnorepeat" if len(waves) > 1 else "sequential"),
        ("spawntime_min", 0), ("spawntime_max", 0), ("spawn_max", 1), ("mode", 0), ("pitch", 0),
        ("pitch_randmethod", 1), ("pitch_random_min", 0), ("pitch_random_max", 0), ("pitch_randomization", 0),
        ("pitch_recalculate", 0), ("volume_db", 0), ("volume_randmethod", 1), ("volume_random_min", 0),
        ("volume_random_max", 0), ("volume_randomization", 0), ("position_randomization", 0),
        ("trigger_delay_min", 0), ("trigger_delay_max", 0), ("notes", "")])
    for w in waves:
        out += "<waveform>\n" + _tags([("filename", w), ("soundbankname", bank), ("weight", 100),
                                      ("percentagelocked", 0)]) + "</waveform>\n"
    return out + "</sounddef>\n"


def _event(name, e):
    layer = "<layer>\n" + _tags([("name", "layer00"), ("height", 100), ("envelope_nextid", 0), ("mute", 0),
                                 ("solo", 0), ("soundlock", 0), ("envlock", 0), ("priority", -1)])
    layer += "<sound>\n" + _tags([
        ("name", "/" + name), ("x", 0), ("width", 1), ("startmode", 0), ("loopmode", 1), ("loopcount2", -1),
        ("autopitchenabled", 0), ("autopitchparameter", 0), ("autopitchreference", 0), ("autopitchatzero", 0),
        ("finetune", 0), ("volume", 1), ("fadeintype", 2), ("fadeouttype", 2)]) + "</sound>\n"
    layer += "<_PC_enable>1</_PC_enable>\n</layer>\n"
    return "<event>\n" + _tags([("name", name), ("guid", _guid()), ("parameter_nextid", 0),
                                ("layer_nextid", 1)]) + layer + _tags([
        ("car_rpm", 0), ("car_rpmsmooth", 0.075), ("car_loadsmooth", 0.05), ("car_loadscale", 6), ("car_dialog", 0),
        ("volume_db", e.get("volume_db", 0)), ("pitch", 0), ("pitch_units", "Octaves"),
        ("pitch_randomization", e.get("pitch_rand", 0)), ("pitch_randomization_units", "Octaves"),
        ("volume_randomization", e.get("volume_rand", 0)), ("priority", 128),
        ("maxplaybacks", e.get("maxplaybacks", 4)), ("maxplaybacks_behavior", "Steal_oldest"),
        ("stealpriority", 10000), ("mode", "x_3d"), ("ignoregeometry", "No"), ("rolloff", "Linear"),
        ("mindistance", e.get("min", 3)), ("maxdistance", e.get("max", 30)), ("headrelative", "World_relative"),
        ("oneshot", "Yes"), ("istemplate", "No"), ("usetemplate", ""), ("notes", ""), ("category", "sfx"),
        ("position_randomization", 0), ("speaker_l", 1), ("speaker_c", 0), ("speaker_r", 1), ("speaker_ls", 0),
        ("speaker_rs", 0), ("speaker_lb", 0), ("speaker_rb", 0), ("speaker_lfe", 0), ("speaker_config", 0),
        ("speaker_pan_r", 1), ("speaker_pan_theta", 0), ("cone_inside_angle", 360), ("cone_outside_angle", 360),
        ("cone_outside_volumedb", 0), ("doppler_scale", 1), ("reverbdrylevel_db", 0), ("reverblevel_db", 0),
        ("speaker_spread", 0), ("panlevel3d", 1), ("fadein_time", 0), ("fadeout_time", 0), ("spawn_intensity", 1),
        ("spawn_intensity_randomization", 0), ("_PC_enabled", 1)]) + "</event>\n"


def _bank(bank, waves):
    out = "<soundbank>\n" + _tags([
        ("name", bank), ("guid", _guid()), ("load_into_rsx", 0), ("disable_seeking", 0), ("enable_syncpoints", 1),
        ("hasbuiltwithsyncpoints", 0), ("_PC_banktype", "DecompressedSample"), ("notes", ""), ("rebuild", 1)])
    for w in waves:
        out += "<waveform>\n" + _tags([
            ("filename", w), ("guid", _guid()), ("mindistance", 1), ("maxdistance", 10000), ("deffreq", 44100),
            ("defvol", 1), ("defpan", 0), ("defpri", 128), ("xmafiltering", 0), ("channelmode", 0),
            ("quality_crossplatform", 0), ("quality", -1), ("optimisedratereduction", 100),
            ("enableratereduction", 1), ("notes", "")]) + "</waveform>\n"
    return out + _tags([("_PC_format", "ADPCM"), ("_PC_quality", 50), ("_PC_optimisesamplerate", 0),
                        ("_PC_forcesoftware", 1), ("_PC_maxstreams", 10)]) + "</soundbank>\n"


def project(name, group, events):
    """The .fdp text; events' files are paths relative to the .fdp."""
    allwaves = [w for e in events.values() for w in e["files"]]
    s = "<project>\n" + _tags([
        ("name", name), ("guid", _guid()), ("version", 4), ("eventgroup_nextid", 0), ("soundbank_nextid", 1),
        ("sounddef_nextid", 0), ("build_project", 1), ("build_headerfile", 0), ("build_banklists", 0),
        ("build_programmerreport", 0), ("build_applytemplate", 0), ("currentbank", name),
        ("currentlanguage", "default"), ("primarylanguage", "default"), ("language", "default"),
        ("templatefilename", ""), ("templatefileopen", 0)])
    s += "<eventcategory>\n" + _tags([("name", "sfx"), ("guid", _guid()), ("volume_db", 0), ("pitch", 0),
                                      ("maxplaybacks", 0), ("maxplaybacks_behavior", "Steal_oldest"),
                                      ("notes", ""), ("open", 0)]) + "</eventcategory>\n"
    s += "<sounddeffolder>\n" + _tags([("name", "master"), ("guid", _guid()), ("open", 0)])
    for ev, e in events.items():
        s += _sounddef(ev, e["files"], name)
    s += "</sounddeffolder>\n"
    s += "<eventgroup>\n" + _tags([("name", group), ("guid", _guid()), ("eventgroup_nextid", 0),
                                   ("event_nextid", 0), ("open", 0), ("notes", "")])
    for ev, e in events.items():
        s += _event(ev, e)
    s += "</eventgroup>\n"
    s += _bank(name, allwaves)
    s += _tags([("notes", ""), ("currentplatform", "PC"), ("_PC_encryptionkey", ""), ("_PC_builddirectory", ""),
                ("_PC_audiosourcedirectory", ""), ("_PC_prebuildcommands", ""), ("_PC_postbuildcommands", ""),
                ("_PC_buildinteractivemusic", "No"), ("presavecommands", ""), ("postsavecommands", ""),
                ("neweventusetemplate", 0), ("neweventlasttemplatename", "")])
    return s + "</project>\n"


def build(name, group, events, out_dir, work_dir):
    """Write work_dir/<name>.fdp with the takes copied beside it; build out_dir/<name>.fev and .fsb."""
    if os.path.isdir(work_dir):
        shutil.rmtree(work_dir)
    os.makedirs(os.path.join(work_dir, "wav"))
    rel = {}
    for ev, e in events.items():
        rel[ev] = dict(e, files=[])
        for i, src in enumerate(e["files"]):
            dst = "wav/%s_%d.wav" % (ev, i + 1)
            shutil.copyfile(src, os.path.join(work_dir, dst))
            rel[ev]["files"].append(dst)
    fdp = os.path.join(work_dir, name + ".fdp")
    with open(fdp, "w", encoding="utf-8", newline="\n") as f:
        f.write(project(name, group, rel))
    os.makedirs(out_dir, exist_ok=True)
    r = subprocess.run([DESIGNERCL, "-pc", "-r", "-b", os.path.abspath(out_dir), os.path.abspath(fdp)],
                       capture_output=True, text=True, cwd=work_dir)
    log = (r.stdout or "") + (r.stderr or "")
    fev, fsb = (os.path.join(out_dir, name + x) for x in (".fev", ".fsb"))
    if r.returncode != 0 or not (os.path.isfile(fev) and os.path.isfile(fsb)):
        raise RuntimeError("fmod_designercl failed (%d):\n%s" % (r.returncode, log))
    return fev, fsb, log
