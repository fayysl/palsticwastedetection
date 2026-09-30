"""Plastic detection through OpenRouter's free vision models.

Free models on OpenRouter come and go, and each one is rate-limited, so we:
  1. try any models set in OPENROUTER_MODEL (comma-separated),
  2. then free image-capable models discovered from OpenRouter's public model list,
  3. then a small built-in fallback list,
moving to the next model whenever one fails, is rate-limited or returns bad JSON.
"""

import base64
import io
import json
import logging
import os
import re
import time

import requests
from PIL import Image, ImageOps

log = logging.getLogger(__name__)

API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODELS_URL = "https://openrouter.ai/api/v1/models"

FALLBACK_MODELS = [
    "openrouter/free",
    "google/gemma-3-27b-it:free",
    "mistralai/mistral-small-3.2-24b-instruct:free",
    "qwen/qwen2.5-vl-72b-instruct:free",
    "meta-llama/llama-4-maverick:free",
]

CATEGORY_KEYS = "bottle, bag, food_container, packaging, cup, cutlery_straw, container_hdpe, other"

PROMPT = f"""You are a plastic waste detection system. Look at the image and identify every PLASTIC waste item.

Reply with ONLY a JSON object, no markdown, in exactly this shape:
{{
  "items": [
    {{
      "name": "short description, e.g. 'Clear water bottle'",
      "category": one of [{CATEGORY_KEYS}],
      "resin_code": integer 1-7 (your best guess of the recycling number),
      "count": integer,
      "confidence": number 0-1,
      "condition": "clean" | "dirty" | "damaged"
    }}
  ],
  "summary": "one sentence describing the waste in the image",
  "tips": ["up to 3 short, practical tips specific to this image"]
}}

Rules:
- Only list plastic items. Ignore paper, glass, metal and organic waste.
- If there is no plastic, return "items": [].
- Use "container_hdpe" for milk jugs, detergent/shampoo bottles; "bottle" for PET drink bottles.
"""

_discovered = {"models": [], "at": 0.0}


class AIError(Exception):
    pass


def prepare_image(raw_bytes, max_side=1024):
    """Normalise an upload: fix rotation, downscale, JPEG-encode.

    Returns (jpeg_bytes_for_ai, small_thumbnail_data_url).
    """
    try:
        img = Image.open(io.BytesIO(raw_bytes))
        img = ImageOps.exif_transpose(img).convert("RGB")
    except Exception as exc:
        raise AIError("That file is not a readable image.") from exc

    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)

    thumb = img.copy()
    thumb.thumbnail((320, 320))
    tbuf = io.BytesIO()
    thumb.save(tbuf, "JPEG", quality=70)
    thumb_url = "data:image/jpeg;base64," + base64.b64encode(tbuf.getvalue()).decode()
    return buf.getvalue(), thumb_url


def discover_free_vision_models(timeout=8):
    """Free, image-input models from OpenRouter's public list (cached 1 hour)."""
    if time.time() - _discovered["at"] < 3600:
        return _discovered["models"]
    models = []
    try:
        resp = requests.get(MODELS_URL, timeout=timeout)
        resp.raise_for_status()
        for m in resp.json().get("data", []):
            pricing = m.get("pricing") or {}
            modalities = (m.get("architecture") or {}).get("input_modalities") or []
            free = str(pricing.get("prompt")) == "0" and str(pricing.get("completion")) == "0"
            if free and "image" in modalities:
                models.append(m["id"])
    except Exception as exc:  # network trouble shouldn't break scanning
        log.warning("Could not list OpenRouter models: %s", exc)
    _discovered.update(models=models, at=time.time())
    return models


def candidate_models():
    configured = [m.strip() for m in os.getenv("OPENROUTER_MODEL", "").split(",") if m.strip()]
    ordered = []
    for m in configured + discover_free_vision_models() + FALLBACK_MODELS:
        if m not in ordered:
            ordered.append(m)
    return ordered


def parse_json(text):
    """Pull the first JSON object out of a model reply (handles ```json fences / chatter)."""
    if not text:
        raise ValueError("empty reply")
    text = re.sub(r"```(?:json)?", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("no JSON object in reply")
        return json.loads(text[start:end + 1])


def detect(jpeg_bytes, max_attempts=3, timeout=45):
    """Run detection. Returns (detection_dict, model_used)."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise AIError("OPENROUTER_API_KEY is not set.")

    image_url = "data:image/jpeg;base64," + base64.b64encode(jpeg_bytes).decode()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": os.getenv("APP_URL", "http://localhost:5000"),
        "X-Title": "EcoScan Plastic Detector",
    }
    errors = []
    for model in candidate_models()[:max_attempts]:
        body = {
            "model": model,
            "temperature": 0.1,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }],
        }
        try:
            resp = requests.post(API_URL, headers=headers, json=body, timeout=timeout)
            if resp.status_code != 200:
                errors.append(f"{model}: HTTP {resp.status_code}")
                log.warning("OpenRouter %s -> %s %s", model, resp.status_code, resp.text[:200])
                if resp.status_code in (401, 402):
                    break  # bad key / no credit: other models won't help
                continue
            data = resp.json()
            if data.get("error"):
                errors.append(f"{model}: {data['error'].get('message', 'error')}")
                continue
            content = data["choices"][0]["message"]["content"]
            if isinstance(content, list):  # some providers return content parts
                content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
            detection = parse_json(content)
            if not isinstance(detection, dict):
                raise ValueError("reply is not a JSON object")
            return detection, data.get("model") or model
        except (requests.RequestException, KeyError, IndexError, ValueError) as exc:
            errors.append(f"{model}: {exc}")
            log.warning("OpenRouter %s failed: %s", model, exc)

    raise AIError("All AI models failed (" + "; ".join(errors[:4]) + "). Please try again in a minute.")


DEMO_DETECTION = {
    "items": [
        {"name": "Clear water bottle", "category": "bottle", "resin_code": 1,
         "count": 2, "confidence": 0.93, "condition": "clean"},
        {"name": "Thin carry bag", "category": "bag", "resin_code": 4,
         "count": 1, "confidence": 0.88, "condition": "dirty"},
        {"name": "Takeaway food box", "category": "food_container", "resin_code": 5,
         "count": 1, "confidence": 0.8, "condition": "dirty"},
    ],
    "summary": "Demo result: two PET bottles, a carry bag and a takeaway container.",
    "tips": ["Set OPENROUTER_API_KEY to analyse your real photos."],
}
