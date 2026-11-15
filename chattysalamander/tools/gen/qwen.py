"""Images from Qwen-Image-Edit 2511 on the local ComfyUI (127.0.0.1:8188, C:/Users/seann/ComfyUI; start_comfyui.bat
there): a prompt and up to 3 reference images (the game's own art, for its style) -> PNG.

    python tools/gen/qwen.py out.png "prompt" [--ref a.png --ref b.png] [--size 1024x1024] [--seed 1] [--steps 4]

As a module: generate(prompt, refs, out, size=(w, h), seed=, steps=). With the Lightning LoRA (4 steps, cfg 1) as
ComfyUI's own template for the model has it (comfyui_workflow_templates: image_qwen_image_edit_2511). With size, the
picture starts from an empty latent of that size (the references only guide it); without, from the first reference.
"""
import argparse
import json
import os
import random
import time
import urllib.parse
import urllib.request
import uuid

URL = "http://127.0.0.1:8188"
UNET = "qwen_image_edit_2511_fp8mixed.safetensors"
CLIP = "qwen_2.5_vl_7b_fp8_scaled.safetensors"
VAE = "qwen_image_vae.safetensors"
LORA = "Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors"


def _post(path, data, ctype="application/json"):
    req = urllib.request.Request(URL + path, data=data, headers={"Content-Type": ctype})
    return json.loads(urllib.request.urlopen(req).read())


def upload(path):
    name = f"{uuid.uuid4().hex[:8]}_{os.path.basename(path)}"
    boundary = uuid.uuid4().hex
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{name}\"\r\n"
            f"Content-Type: image/png\r\n\r\n").encode() + open(path, "rb").read() + \
        f"\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n--{boundary}--\r\n".encode()
    return _post("/upload/image", body, f"multipart/form-data; boundary={boundary}")["name"]


def workflow(prompt, refs, size, seed, steps, cfg, negative=""):
    g = {
        "unet": {"class_type": "UNETLoader", "inputs": {"unet_name": UNET, "weight_dtype": "default"}},
        "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": CLIP, "type": "qwen_image", "device": "default"}},
        "vae": {"class_type": "VAELoader", "inputs": {"vae_name": VAE}},
        "aura": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["unet", 0], "shift": 3.1}},
        "norm": {"class_type": "CFGNorm", "inputs": {"model": ["aura", 0], "strength": 1}},
    }
    model = ["norm", 0]
    if steps <= 8:
        g["lora"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": model, "lora_name": LORA, "strength_model": 1}}
        model = ["lora", 0]
    imgs = []
    for i, r in enumerate(refs):
        g[f"load{i}"] = {"class_type": "LoadImage", "inputs": {"image": r}}
        src = [f"load{i}", 0]
        if i == 0:
            g["scale0"] = {"class_type": "FluxKontextImageScale", "inputs": {"image": src}}
            src = ["scale0", 0]
        imgs.append(src)
    for key, text in (("pos", prompt), ("neg", negative)):
        inp = {"clip": ["clip", 0], "vae": ["vae", 0], "prompt": text}
        for i, im in enumerate(imgs):
            inp[f"image{i + 1}"] = im
        g[key] = {"class_type": "TextEncodeQwenImageEditPlus", "inputs": inp}
        g[key + "m"] = {"class_type": "FluxKontextMultiReferenceLatentMethod",
                        "inputs": {"conditioning": [key, 0], "reference_latents_method": "index_timestep_zero"}}
    if size or not imgs:
        w, h = size or (1024, 1024)
        g["lat"] = {"class_type": "EmptySD3LatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}}
    else:
        g["lat"] = {"class_type": "VAEEncode", "inputs": {"pixels": imgs[0], "vae": ["vae", 0]}}
    g["ks"] = {"class_type": "KSampler", "inputs": {
        "model": model, "positive": ["posm", 0], "negative": ["negm", 0], "latent_image": ["lat", 0], "seed": seed,
        "steps": steps, "cfg": cfg, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}}
    g["dec"] = {"class_type": "VAEDecode", "inputs": {"samples": ["ks", 0], "vae": ["vae", 0]}}
    g["save"] = {"class_type": "SaveImage", "inputs": {"images": ["dec", 0], "filename_prefix": "gen"}}
    return g


def generate(prompt, refs, out, size=None, seed=None, steps=4, cfg=None, negative=""):
    seed = random.randrange(2 ** 31) if seed is None else seed
    cfg = cfg if cfg is not None else (1.0 if steps <= 8 else 4.0)
    names = [upload(r) for r in refs]
    pid = _post("/prompt", json.dumps({"prompt": workflow(prompt, names, size, seed, steps, cfg, negative),
                                       "client_id": "gen"}).encode())["prompt_id"]
    t0 = time.time()
    while True:
        h = json.loads(urllib.request.urlopen(f"{URL}/history/{pid}").read())
        if pid in h:
            st = h[pid].get("status", {})
            if st.get("status_str") == "error":
                raise RuntimeError(json.dumps(st.get("messages"))[:2000])
            outs = h[pid]["outputs"]
            if outs:
                im = outs["save"]["images"][0]
                q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im["subfolder"], "type": im["type"]})
                os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
                open(out, "wb").write(urllib.request.urlopen(f"{URL}/view?{q}").read())
                return out, seed, time.time() - t0
        time.sleep(0.5)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("prompt")
    ap.add_argument("--ref", action="append", default=[])
    ap.add_argument("--size")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--steps", type=int, default=4)
    ap.add_argument("--neg", default="")
    a = ap.parse_args()
    size = tuple(int(v) for v in a.size.split("x")) if a.size else None
    out, seed, dt = generate(a.prompt, a.ref, a.out, size, a.seed, a.steps, negative=a.neg)
    print(out, "seed", seed, f"{dt:.1f}s")
