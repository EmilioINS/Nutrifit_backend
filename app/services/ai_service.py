"""
AI Service — Clean Architecture, Single Responsibility Principle.
Responsabilidad: comunicarse con la API de visión de Groq y parsear resultados.
"""
import json
import re
from typing import Any
from groq import Groq
from app.core.config import settings

client = Groq(api_key=settings.GROQ_API_KEY)

# ── Prompts ────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are a professional nutritionist AI with expert food recognition capabilities.
When analyzing food images:
- READ ALL VISIBLE TEXT on packaging, labels, cans, or boxes — brand names and nutrition facts are your primary truth source.
- Identify EVERY distinct food item present in the image.
- Estimate nutritional values per item and provide a combined total.
- Use whole integers for all numerical nutritional values.
- Be specific: "StarKist Chunk Light Tuna in Water (185g can)" not just "tuna".
- Always respond with ONLY raw JSON, no markdown, no explanation text."""

_MULTI_ITEM_PROMPT = """Analyze this image and identify ALL food items visible.

For EACH food item return its macros. Also return a "total" row summing everything.

Return ONLY this JSON (no markdown, no extra text):
{
  "items": [
    {"food_name": "Product/dish name", "calories": 0, "protein": 0, "carbs": 0, "fat": 0, "portion_size": "~Xg"},
    {"food_name": "...", "calories": 0, "protein": 0, "carbs": 0, "fat": 0, "portion_size": "~Xg"}
  ],
  "total": {"calories": 0, "protein": 0, "carbs": 0, "fat": 0},
  "confidence": "85%"
}"""

# ── Private helpers ─────────────────────────────────────────────────────────────

def _normalize_base64(image: str) -> str:
    """Ensure the image string is a proper data URL."""
    if not image.startswith("data:image"):
        return f"data:image/jpeg;base64,{image}"
    return image


def _strip_markdown(text: str) -> str:
    """Remove code fences that the model may inject despite instructions."""
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _call_groq(image_data_url: str, prompt: str) -> str:
    """Low-level Groq API call. Returns raw text response."""
    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                ],
            },
        ],
        temperature=0.0,
        max_tokens=512,
    )
    return response.choices[0].message.content.strip()


def _defaults_item() -> dict:
    return {"food_name": "Alimento desconocido", "calories": 0,
            "protein": 0, "carbs": 0, "fat": 0, "portion_size": "N/A"}


# ── Public API ──────────────────────────────────────────────────────────────────

def analyze_food_image(base64_image: str) -> dict[str, Any]:
    """
    Analiza una imagen de comida y devuelve los macronutrientes desglosados
    por cada alimento detectado más un total consolidado.

    Returns:
        {
            "items": [...],
            "total": {...},
            "confidence": "85%"
        }
    """
    image_url = _normalize_base64(base64_image)

    try:
        raw = _call_groq(image_url, _MULTI_ITEM_PROMPT)
        print(f"[AI Raw Response]: {raw[:400]}")

        parsed: Any = json.loads(_strip_markdown(raw))

        # Normalise: model sometimes returns a plain object (single food) or array
        if isinstance(parsed, list):
            # Array of items with no wrapper — wrap it
            items = parsed
            total = {
                "calories": sum(i.get("calories", 0) for i in items),
                "protein":  sum(i.get("protein", 0)  for i in items),
                "carbs":    sum(i.get("carbs", 0)    for i in items),
                "fat":      sum(i.get("fat", 0)      for i in items),
            }
            result = {"items": items, "total": total, "confidence": "—"}

        elif isinstance(parsed, dict) and "items" in parsed:
            result = parsed
            # Recalculate total server-side to protect against model errors
            items = parsed.get("items", [])
            result["total"] = {
                "calories": sum(i.get("calories", 0) for i in items),
                "protein":  sum(i.get("protein", 0)  for i in items),
                "carbs":    sum(i.get("carbs", 0)    for i in items),
                "fat":      sum(i.get("fat", 0)      for i in items),
            }

        elif isinstance(parsed, dict):
            # Single-object fallback — wrap in items array
            item = {**_defaults_item(), **parsed}
            result = {
                "items": [item],
                "total": {k: item.get(k, 0) for k in ("calories", "protein", "carbs", "fat")},
                "confidence": parsed.get("confidence", "—"),
            }
        else:
            raise ValueError(f"Unexpected parsed type: {type(parsed)}")

        # Ensure items have all required keys
        result["items"] = [{**_defaults_item(), **item} for item in result["items"]]
        return result

    except json.JSONDecodeError as exc:
        print(f"[AI JSON Parse Error]: {exc}")
        return _error_response()
    except Exception as exc:
        print(f"[AI Service Error]: {type(exc).__name__}: {exc}")
        return _error_response()


def _error_response() -> dict:
    return {
        "items": [{**_defaults_item(), "food_name": "Error al analizar la imagen"}],
        "total": {"calories": 0, "protein": 0, "carbs": 0, "fat": 0},
        "confidence": "0%",
    }
