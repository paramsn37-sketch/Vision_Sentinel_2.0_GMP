"""Per-detection Grad-CAM and whole-frame EigenCAM for YOLO detectors (blueprint §7.1).

Grad-CAM here is computed on the detector's *raw* head output, before any NMS or top-k selection:
1. letterbox the frame exactly like inference and run the network with gradients enabled;
2. decode every anchor's box and pick the anchor that best explains the chosen detection
   (IoU with the detection × that anchor's score for the detection's class);
3. backpropagate that single class logit to the three feature maps feeding the head (strides 8/16/32);
4. Grad-CAM per map (ReLU of the gradient-weighted channel sum), upsample, and combine the maps weighted by their
   gradient energy; finally undo the letterbox so the heatmap lines up with the original frame.
The branch is the one the predictor uses (one-to-one for end-to-end YOLO26 exports, one-to-many otherwise),
so the explained anchor is the one that produced the detection.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np
import torch
import torch.nn.functional as F

from ..geometry import iou
from ..types import Box


@dataclass(slots=True)
class Explanation:
    method: str
    heatmap: np.ndarray  # float32 in [0, 1], original frame size
    target_class: str | None
    target_box: Box | None
    energy_in_box: float | None  # share of positive heat inside the target box
    peak_in_box: bool | None
    anchor_score: float | None
    ms: float
    layers: list[str] = field(default_factory=list)

    def meta(self) -> dict:
        return {
            "method": self.method,
            "target_class": self.target_class,
            "target_box": list(self.target_box) if self.target_box else None,
            "energy_in_box": None if self.energy_in_box is None else round(self.energy_in_box, 4),
            "peak_in_box": self.peak_in_box,
            "anchor_score": None if self.anchor_score is None else round(self.anchor_score, 4),
            "ms": round(self.ms, 1),
            "layers": self.layers,
        }


@dataclass(slots=True)
class _Letterbox:
    tensor: torch.Tensor
    ratio: float
    pad: tuple[float, float]  # (left, top)
    shape: tuple[int, int]  # original (h, w)
    size: tuple[int, int]  # letterboxed (h, w)


def letterbox(img: np.ndarray, imgsz: int, stride: int = 32) -> _Letterbox:
    h, w = img.shape[:2]
    r = min(imgsz / h, imgsz / w)
    nh, nw = round(h * r), round(w * r)
    th, tw = int(np.ceil(nh / stride) * stride), int(np.ceil(nw / stride) * stride)
    top, left = (th - nh) / 2, (tw - nw) / 2
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
    canvas = cv2.copyMakeBorder(
        resized, round(top - 0.1), round(th - nh - top + 0.1), round(left - 0.1),
        round(tw - nw - left + 0.1), cv2.BORDER_CONSTANT, value=(114, 114, 114),
    )  # fmt: skip
    t = torch.from_numpy(canvas[:, :, ::-1].copy()).permute(2, 0, 1).float().div(255).unsqueeze(0)
    return _Letterbox(t, r, (round(left - 0.1), round(top - 0.1)), (h, w), canvas.shape[:2])


def _unletterbox(cam: np.ndarray, lb: _Letterbox) -> np.ndarray:
    h, w = lb.shape
    left, top = lb.pad
    nh, nw = round(h * lb.ratio), round(w * lb.ratio)
    crop = cam[top : top + nh, left : left + nw]
    return cv2.resize(crop, (w, h), interpolation=cv2.INTER_LINEAR)


def _normalise(x: np.ndarray) -> np.ndarray:
    x = np.maximum(x, 0)
    m = x.max()
    return (x / m).astype(np.float32) if m > 0 else np.zeros_like(x, dtype=np.float32)


def box_stats(heat: np.ndarray, box: Box) -> tuple[float, bool]:
    h, w = heat.shape
    x1, y1 = max(0, int(box[0])), max(0, int(box[1]))
    x2, y2 = min(w, int(np.ceil(box[2]))), min(h, int(np.ceil(box[3])))
    total = float(heat.sum())
    inside = float(heat[y1:y2, x1:x2].sum()) if x2 > x1 and y2 > y1 else 0.0
    py, px = np.unravel_index(int(np.argmax(heat)), heat.shape)
    return (inside / total if total > 0 else 0.0), bool(x1 <= px < x2 and y1 <= py < y2)


class YoloCAM:
    """Wraps a YOLO `DetectionModel` (``YOLO(weights).model``). Not thread-safe; the XAI worker serialises calls."""

    def __init__(self, model: Any, class_names: dict[int, str], imgsz: int = 640) -> None:
        self.model = model.float().eval()
        for p in self.model.parameters():
            p.requires_grad_(False)
        self.head: Any = self.model.model[-1]
        self.names = class_names
        self.ids = {v: k for k, v in class_names.items()}
        self.imgsz = imgsz

    def _branch(self, preds: dict) -> dict:
        """The head branch the predictor actually uses: one-to-one when end-to-end (NMS-free), else one-to-many."""
        if "one2one" in preds:
            return preds["one2one"] if self.head.end2end else preds["one2many"]
        return preds

    def _forward(self, lb: _Letterbox) -> tuple[dict, list[torch.Tensor]]:
        x = lb.tensor.clone().requires_grad_(True)
        _, preds = self.model(x)
        branch = self._branch(preds)
        feats: list[torch.Tensor] = list(branch["feats"])
        for f in feats:
            f.retain_grad()
        return branch, feats

    def _decoded_boxes(self, branch: dict, lb: _Letterbox) -> np.ndarray:
        with torch.no_grad():
            db = self.head._get_decode_boxes(branch)[0].T.cpu().numpy()  # (N, 4) in letterbox pixels
        if not self.head.end2end and not getattr(self.head, "xyxy", False):  # xywh → xyxy
            db = np.concatenate([db[:, :2] - db[:, 2:] / 2, db[:, :2] + db[:, 2:] / 2], axis=1)
        left, top = lb.pad
        db[:, [0, 2]] = (db[:, [0, 2]] - left) / lb.ratio
        db[:, [1, 3]] = (db[:, [1, 3]] - top) / lb.ratio
        return db

    def gradcam(self, frame: np.ndarray, box: Box, cls: str, variant: str = "hirescam") -> Explanation:
        """`variant="gradcam"`: channel weights = spatially averaged gradients (Selvaraju et al. 2017).
        `variant="hirescam"` (default): element-wise gradient × activation (Draelos & Carin 2020). For a single
        detector anchor the gradient is spatially local, and averaging it away (classic Grad-CAM) spreads heat over
        every region with similar features; the element-wise form keeps it on the explained object. The XAI
        evaluation measures both.
        """
        t0 = time.perf_counter()
        lb = letterbox(frame, self.imgsz)
        with torch.enable_grad():
            branch, feats = self._forward(lb)
            scores = branch["scores"][0]  # (nc, N) logits
            cid = self.ids[cls]
            boxes = self._decoded_boxes(branch, lb)
            probs = scores[cid].detach().sigmoid().cpu().numpy()
            ious = np.array([iou(box, tuple(b)) for b in boxes])
            match = ious * probs
            anchor = int(np.argmax(match))
            target = scores[cid, anchor]
            self.model.zero_grad(set_to_none=True)
            target.backward()
        h, w = lb.size
        cams, energies, layers = [], [], []
        for i, f in enumerate(feats):
            g = f.grad
            if g is None:
                continue
            if variant == "gradcam":
                cam = F.relu((g.mean(dim=(2, 3), keepdim=True) * f).sum(dim=1, keepdim=True))
            else:
                cam = F.relu((g * f).sum(dim=1, keepdim=True))
            cam_np: np.ndarray = (
                F.interpolate(cam, size=(h, w), mode="bilinear", align_corners=False)[0, 0]
                .detach()
                .cpu()
                .numpy()
            )
            cams.append(_normalise(cam_np))
            energies.append(float(g.abs().sum()))
            layers.append(
                f"P{i + 3}/stride{int(self.head.stride[i]) if hasattr(self.head, 'stride') else '?'}"
            )
        total = sum(energies) or 1.0
        combined = (
            sum(c * (e / total) for c, e in zip(cams, energies, strict=True)) if cams else np.zeros((h, w))
        )
        heat = _normalise(_unletterbox(np.asarray(combined, dtype=np.float32), lb))
        energy, peak = box_stats(heat, box)
        return Explanation(variant, heat, cls, box, energy, peak, float(probs[anchor]),
                           (time.perf_counter() - t0) * 1000, layers)  # fmt: skip

    def eigencam(self, frame: np.ndarray, box: Box | None = None, cls: str | None = None) -> Explanation:
        """First principal component of each head-input feature map, averaged over scales. Gradient-free."""
        t0 = time.perf_counter()
        lb = letterbox(frame, self.imgsz)
        with torch.no_grad():
            _, preds = self.model(lb.tensor)
            feats = self._branch(preds)["feats"]
        h, w = lb.size
        cams = []
        for f in feats:
            a = f[0].cpu().numpy()  # (C, H, W)
            c, fh, fw = a.shape
            m = a.reshape(c, -1).T  # (HW, C)
            m = m - m.mean(axis=0)
            _, _, vt = np.linalg.svd(m, full_matrices=False)
            proj = (m @ vt[0]).reshape(fh, fw)
            if proj.max() < -proj.min():  # SVD sign is arbitrary: keep the dominant polarity positive
                proj = -proj
            cams.append(_normalise(cv2.resize(proj.astype(np.float32), (w, h))))
        heat = _normalise(_unletterbox(np.mean(cams, axis=0).astype(np.float32), lb))
        energy, peak = box_stats(heat, box) if box else (None, None)
        return Explanation("eigencam", heat, cls, box, energy, peak, None, (time.perf_counter() - t0) * 1000,
                           [f"P{i + 3}" for i in range(len(feats))])  # fmt: skip


def overlay(frame: np.ndarray, heat: np.ndarray, alpha: float = 0.45, box: Box | None = None) -> np.ndarray:
    colored = cv2.applyColorMap((heat * 255).astype(np.uint8), cv2.COLORMAP_TURBO)
    out = cv2.addWeighted(frame, 1 - alpha, colored, alpha, 0)
    if box is not None:
        x1, y1, x2, y2 = (int(v) for v in box)
        cv2.rectangle(out, (x1, y1), (x2, y2), (255, 255, 255), 2)
    return out
