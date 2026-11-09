"""Feature extraction for a panel pair (A, B).

Components:
  * Frozen OpenCLIP image encoder applied to each panel (letterboxed to a square, so the
    composition is kept). The pair is represented as [eA, eB, eA*eB, |eA-eB|, cos].
  * OpenCLIP text embeddings of the internally OCR'd text of each panel, plus their cosine.
  * Hand-crafted low-level similarity features (thumbnail correlation, colour-histogram distance,
    edge density, aspect ratio) that describe how much the picture changes.
  * OCR cue features (see ocr.py).
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageFile, ImageFilter, ImageOps

ImageFile.LOAD_TRUNCATED_IMAGES = True  # a few COMICS jpgs are truncated by a few bytes

from . import paths as _paths  # noqa: F401  (sets HF_HOME)
from .ocr import TEXT_FEATURE_NAMES, cue2_features, ocr_image, text_features

CLIP_ARCH = os.environ.get("CPT_CLIP_ARCH", "ViT-B-16")
CLIP_PRETRAINED = os.environ.get("CPT_CLIP_PRETRAINED", "laion2b_s34b_b88k")


def letterbox(img: Image.Image, fill=(255, 255, 255)) -> Image.Image:
    img = img.convert("RGB")
    s = max(img.size)
    canvas = Image.new("RGB", (s, s), fill)
    canvas.paste(img, ((s - img.width) // 2, (s - img.height) // 2))
    return canvas


def lowlevel_single(img: Image.Image) -> dict:
    rgb = img.convert("RGB")
    g = ImageOps.grayscale(rgb).resize((32, 32), Image.BILINEAR)
    thumb = np.asarray(g, dtype=np.float32).ravel()
    hsv = np.asarray(rgb.resize((64, 64)).convert("HSV"), dtype=np.float32)
    hist = np.concatenate([
        np.histogram(hsv[..., 0], bins=12, range=(0, 255))[0],
        np.histogram(hsv[..., 1], bins=6, range=(0, 255))[0],
        np.histogram(hsv[..., 2], bins=6, range=(0, 255))[0],
    ]).astype(np.float32)
    hist /= hist.sum() + 1e-6
    edges = np.asarray(ImageOps.grayscale(rgb).resize((128, 128)).filter(ImageFilter.FIND_EDGES), dtype=np.float32)
    return {"thumb": thumb, "hist": hist, "edge": float((edges > 40).mean()),
            "aspect": float(np.log(rgb.width / rgb.height)), "area": float(np.log(rgb.width * rgb.height))}


LOWLEVEL_NAMES = ["thumb_corr", "hist_l1", "edge_a", "edge_b", "edge_diff", "aspect_a", "aspect_b",
                  "aspect_diff", "area_ratio"]


def lowlevel_pair(a: dict, b: dict) -> np.ndarray:
    ta, tb = a["thumb"] - a["thumb"].mean(), b["thumb"] - b["thumb"].mean()
    corr = float((ta * tb).sum() / (np.linalg.norm(ta) * np.linalg.norm(tb) + 1e-6))
    return np.asarray([
        corr, float(np.abs(a["hist"] - b["hist"]).sum()), a["edge"], b["edge"], abs(a["edge"] - b["edge"]),
        a["aspect"], b["aspect"], abs(a["aspect"] - b["aspect"]), a["area"] - b["area"],
    ], dtype=np.float32)


class ClipEncoder:
    """Thin wrapper around a frozen OpenCLIP model (image + text towers)."""

    def __init__(self, device: str | None = None, arch: str = CLIP_ARCH, pretrained: str = CLIP_PRETRAINED):
        import open_clip
        import torch

        self.torch = torch
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device
        model, _, preprocess = open_clip.create_model_and_transforms(arch, pretrained=pretrained)
        model.eval()
        if device == "cuda":
            model = model.half()
        self.model = model.to(device)
        self.preprocess = preprocess
        self.tokenizer = open_clip.get_tokenizer(arch)
        self.dtype = torch.float16 if device == "cuda" else torch.float32

    def encode_images(self, imgs: list[Image.Image]) -> np.ndarray:
        t = self.torch
        x = t.stack([self.preprocess(letterbox(im)) for im in imgs]).to(self.device, self.dtype)
        with t.no_grad():
            e = self.model.encode_image(x).float()
        e = e / e.norm(dim=-1, keepdim=True)
        return e.cpu().numpy()

    def encode_texts(self, texts: list[str]) -> np.ndarray:
        t = self.torch
        tok = self.tokenizer([s[:300] if s else "" for s in texts]).to(self.device)
        with t.no_grad():
            e = self.model.encode_text(tok).float()
        e = e / e.norm(dim=-1, keepdim=True)
        return e.cpu().numpy()


class DinoEncoder:
    """Frozen DINOv2 ViT-B/14 (timm) at 224px -> CLS embedding + 16x16 patch tokens.

    DINOv2 features are good at instance-level correspondence (same character, same object, same
    background). Patch-to-patch matching between A and B measures how much visual content is shared
    and how far it moved, which is the core cue separating moment/action (same subject) from
    subject (new subject in the same scene) and from scene/non-sequitur (new everything).
    """

    def __init__(self, device: str | None = None, name: str = "vit_base_patch14_dinov2.lvd142m"):
        import timm
        import torch

        self.torch = torch
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        m = timm.create_model(name, pretrained=True, img_size=224, num_classes=0).eval()
        self.dtype = torch.float16 if self.device == "cuda" else torch.float32
        self.model = m.to(self.device, self.dtype)
        self.n_prefix = getattr(m, "num_prefix_tokens", 1)
        self.mean = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
        self.std = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)

    def encode(self, imgs: list[Image.Image]) -> tuple[np.ndarray, np.ndarray]:
        t = self.torch
        # Plain resize (no letterbox): white padding patches would create spurious matches.
        x = t.stack([t.from_numpy(np.asarray(im.convert("RGB").resize((224, 224), Image.BICUBIC), dtype=np.float32)
                                  .transpose(2, 0, 1) / 255.0) for im in imgs])
        x = ((x - self.mean) / self.std).to(self.device, self.dtype)
        with t.no_grad():
            tok = self.model.forward_features(x).float()
        cls = tok[:, 0]
        patches = tok[:, self.n_prefix:]
        cls = cls / cls.norm(dim=-1, keepdim=True)
        patches = patches / patches.norm(dim=-1, keepdim=True)
        return cls.cpu().numpy(), patches.cpu().numpy().astype(np.float16)


MATCH_NAMES = [f"{d}_{s}" for d in ("a2b", "b2a") for s in ("mean", "q25", "q50", "q75", "f60", "f75")] + [
    "mnn_frac", "mnn_disp_mean", "mnn_disp_std", "mnn_strong_frac"]


def patch_match(pa: np.ndarray, pb: np.ndarray) -> np.ndarray:
    pa, pb = pa.astype(np.float32), pb.astype(np.float32)
    S = pa @ pb.T
    a2b, b2a = S.max(1), S.max(0)
    f = []
    for v in (a2b, b2a):
        f += [v.mean(), *np.quantile(v, [0.25, 0.5, 0.75]), (v > 0.6).mean(), (v > 0.75).mean()]
    ia, ib = S.argmax(1), S.argmax(0)
    mnn = np.where(ib[ia] == np.arange(len(ia)))[0]
    g = int(round(np.sqrt(len(pa))))
    if len(mnn):
        ya, xa = np.divmod(mnn, g)
        yb, xb = np.divmod(ia[mnn], g)
        disp = np.hypot(ya - yb, xa - xb) / g
        strong = (S[mnn, ia[mnn]] > 0.6).mean()
        f += [len(mnn) / len(pa), disp.mean(), disp.std(), strong * len(mnn) / len(pa)]
    else:
        f += [0.0, 1.0, 0.0, 0.0]
    return np.asarray(f, dtype=np.float32)


@dataclass
class PanelRecord:
    """Everything we compute for a single panel (cacheable)."""
    img_emb: np.ndarray
    txt_emb: np.ndarray
    text: str
    low: dict
    dino_cls: np.ndarray | None = None
    dino_patches: np.ndarray | None = None


class PanelFeaturizer:
    """Computes PanelRecords with the encoders the deployed head needs."""

    def __init__(self, device: str | None = None, use_dino: bool = True):
        self.clip = ClipEncoder(device=device)
        self.dino = DinoEncoder(device=self.clip.device) if use_dino else None

    def record(self, img: Image.Image, text: str | None = None) -> PanelRecord:
        if text is None:
            text = ocr_image(img)
        rec = PanelRecord(self.clip.encode_images([img])[0], self.clip.encode_texts([text])[0], text, lowlevel_single(img))
        if self.dino is not None:
            c, p = self.dino.encode([img])
            rec.dino_cls, rec.dino_patches = c[0], p[0]
        return rec


# CLIP zero-shot "shot/content" attributes. Their text embeddings are computed once at training time and
# stored in the head (aux["zs"]), so inference needs no extra model call.
ZS_PROMPTS = [
    "a comic panel with a rectangular narration caption box", "a comic panel with only speech balloons",
    "a close-up of a face", "a wide establishing shot of a city", "a landscape with no people", "an interior room",
    "an outdoor street scene", "two people talking", "a fight scene with punches", "an explosion",
    "a car or vehicle", "a man running", "a title splash panel with large logo lettering", "a night scene",
    "a crowd of people", "a gun being fired", "a woman", "an airplane or ship", "a hand holding an object",
    "a silhouette",
]


def _ccos(x, y, mu):
    x, y = x - mu, y - mu
    return float(x @ y / (np.linalg.norm(x) * np.linalg.norm(y) + 1e-8))


def pair_groups(a: PanelRecord, b: PanelRecord, centers: dict | None = None) -> dict[str, np.ndarray]:
    """centers: corpus-mean embeddings {'clip': ..., 'dino': ...} computed from TRAINING panels and stored
    with the trained head. Raw CLIP/DINO cosines saturate on Golden Age art (everything looks alike);
    mean-centred cosines separate unrelated panels far better (see docs/model_design.md)."""
    ea, eb = a.img_emb, b.img_emb
    has_t = bool(a.text.strip()) and bool(b.text.strip())
    g = {
        "clip": np.concatenate([ea, eb, ea * eb, np.abs(ea - eb), [float(ea @ eb)]]),
        "clipdiff": np.concatenate([ea * eb, np.abs(ea - eb), [float(ea @ eb)]]),
        "text": np.concatenate([a.txt_emb - b.txt_emb if has_t else np.zeros_like(a.txt_emb),
                                [float(a.txt_emb @ b.txt_emb) if has_t else 0.0, float(has_t)]]),
        "low": lowlevel_pair(a.low, b.low),
        "cue": text_features(a.text, b.text),
        "cue2": cue2_features(a.text, b.text),
    }
    if a.dino_cls is not None and b.dino_cls is not None:
        da, db = a.dino_cls, b.dino_cls
        ma = a.dino_patches.astype(np.float32).mean(0)
        mb = b.dino_patches.astype(np.float32).mean(0)
        g["dino"] = np.concatenate([da * db, np.abs(da - db), [float(da @ db),
                                    float(ma @ mb / (np.linalg.norm(ma) * np.linalg.norm(mb) + 1e-6))]])
        g["match"] = patch_match(a.dino_patches, b.dino_patches)
    if centers is not None:
        cc = [_ccos(ea, eb, centers["clip"])]
        if a.dino_cls is not None and b.dino_cls is not None:
            cc.append(_ccos(a.dino_cls, b.dino_cls, centers["dino"]))
        g["cos_c"] = np.asarray(cc)
    if centers is not None and "zs" in centers:
        sa, sb = centers["zs"] @ ea, centers["zs"] @ eb
        g["zs"] = np.concatenate([sa, sb, sb - sa])
    return {k: v.astype(np.float32) for k, v in g.items()}


def pair_vector(a: PanelRecord, b: PanelRecord, groups: str, centers: dict | None = None) -> np.ndarray:
    """Concatenate the named feature groups, e.g. 'clip+low+cue' or 'dino+match+low+cue'."""
    g = pair_groups(a, b, centers)
    return np.concatenate([g[k] for k in groups.split("+")])


FEATURE_SUBSETS = (
    "clip+low+cue", "clip+text+low+cue", "clipdiff+low+cue",
    "match+low+cue", "dino+match+low+cue", "clipdiff+match+low+cue",
    "clipdiff+dino+match+low+cue", "clip+dino+match+text+low+cue",
    "cos_c+match+low+cue2", "cos_c+match+low+cue+cue2", "clipdiff+cos_c+match+low+cue2",
    "clip+dino+cos_c+match+text+low+cue+cue2",
    "zs+cos_c+match+low+cue2", "clipdiff+zs+cos_c+match+low+cue2", "clip+dino+zs+cos_c+match+text+low+cue+cue2",
)


def needs_centers(groups: str) -> bool:
    return bool({"cos_c", "zs"} & set(groups.split("+")))
