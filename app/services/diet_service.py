"""
Diet Service — Clean Architecture, Single Responsibility Principle.
Responsabilidad: generar planes de dieta semanales usando Groq LLM.

Estrategia: genera cada plan en una llamada separada para evitar truncamiento
del JSON al llegar al límite de tokens del modelo.
"""
import json
import re
from typing import Any
from groq import Groq
from app.core.config import settings

client = Groq(api_key=settings.GROQ_API_KEY)

# ── Calculation helpers (Harris-Benedict) ──────────────────────────────────────

def _calculate_macros(profile: dict) -> dict:
    """Calcula TDEE y macros objetivo usando Harris-Benedict."""
    age    = profile.get("age", 25)
    height = profile.get("height", 170)
    weight = profile.get("weight", 70)
    gender = profile.get("gender", "male")
    goal   = profile.get("goal", "maintain")
    trains = profile.get("trains_strength", False)
    days   = profile.get("training_days", "1-2")

    bmr = (
        88.36 + 13.4 * weight + 4.8 * height - 5.7 * age
        if gender == "male"
        else 447.6 + 9.2 * weight + 3.1 * height - 4.3 * age
    )
    af_map = {"1-2": 1.375, "3-4": 1.55, "5-6": 1.725}
    af = af_map.get(str(days), 1.375) if trains else 1.2
    tdee = bmr * af

    if goal == "lose":   tdee -= 400
    elif goal == "gain": tdee += 300

    kcal    = round(tdee)
    protein = round(weight * 2)
    fat     = round((kcal * 0.25) / 9)
    carbs   = round((kcal - protein * 4 - fat * 9) / 4)

    return {"kcal": kcal, "protein": protein, "carbs": carbs, "fat": fat}


# ── Prompt builders ────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are an expert nutritionist. Create realistic meal plans in Spanish.
Rules:
- Use ONLY the foods listed as preferred (you may add minimal seasonings/oils).
- Hit the caloric and macro targets for EACH DAY as closely as possible.
- Vary meals across days — no repeating the same meal on consecutive days.
- Every ingredient must have a quantity (e.g. "Pollo — 200g", "Huevo — 3 und").
- Return ONLY raw compact JSON with no markdown, no code fences, no extra text.
- Macros must be integers (grams and kcal)."""


def _build_plan_prompt(profile: dict, macros: dict, plan_number: int) -> str:
    goal_map = {
        "lose":     "fat loss (caloric deficit)",
        "gain":     "muscle gain (caloric surplus)",
        "maintain": "weight maintenance",
    }
    diet_map = {
        "recommended":  "balanced and varied",
        "high-protein": "high-protein (prioritize protein in every meal)",
        "keto":         "ketogenic (very low carb, high fat, under 30g carbs/day)",
        "vegetarian":   "vegetarian (no meat or fish)",
    }

    goal      = goal_map.get(profile.get("goal", "maintain"), "maintenance")
    diet_type = diet_map.get(profile.get("diet_type", "recommended"), "balanced")
    meals_day = int(profile.get("meals_per_day") or 3)
    foods     = profile.get("favorite_foods") or ["pollo", "huevo", "arroz"]
    plan_fmt  = profile.get("plan_format", "step-by-step")

    meal_names_es = {1: "Desayuno", 2: "Comida", 3: "Cena", 4: "Snack 1", 5: "Snack 2"}
    meal_types = [meal_names_es[i+1] for i in range(min(meals_day, 5))]

    instructions_note = (
        'Each meal must have 2-3 short "instructions" steps in Spanish.'
        if plan_fmt == "step-by-step"
        else 'Set "instructions" to an empty array [] for all meals.'
    )

    style_note = "Prioritize high protein meals." if "high-protein" in diet_type else ""
    
    plan_names = {
        1: "Clásico y Variado",
        2: "Alternativo con Diferente Distribución"
    }
    plan_name = plan_names.get(plan_number, f"Plan {plan_number}")

    return f"""Create weekly meal plan "{plan_name}" (Plan {plan_number} of 2) for:
- Goal: {goal}
- Diet: {diet_type}. {style_note}
- Daily targets: {macros['kcal']} kcal | Protein {macros['protein']}g | Carbs {macros['carbs']}g | Fat {macros['fat']}g
- Meals per day: {meals_day} ({', '.join(meal_types)})
- Allowed foods: {', '.join(str(f) for f in foods)}
- {instructions_note}

Return ONLY this JSON (no markdown, compact, no spaces in arrays):
{{"plan_name":"Plan {plan_number} — {plan_name}","description":"One sentence about this plan","days":[{{"day":"Lunes","meals":[{{"meal_type":"Desayuno","name":"Meal name","ingredients":["Food — 200g"],"instructions":["Step 1","Step 2"],"calories":0,"protein":0,"carbs":0,"fat":0}}],"daily_totals":{{"calories":0,"protein":0,"carbs":0,"fat":0}}}}]}}

Include all 7 days: Lunes, Martes, Miércoles, Jueves, Viernes, Sábado, Domingo.
Each day must have exactly {meals_day} meals: {', '.join(meal_types)}.
Keep JSON compact and complete."""


# ── Internal helpers ───────────────────────────────────────────────────────────

def _call_groq_for_plan(prompt: str) -> dict | None:
    """Llama a Groq para generar UN plan semanal. Devuelve el dict o None si falla."""
    try:
        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            temperature=0.5,
            max_tokens=8192,
        )

        raw = response.choices[0].message.content.strip()
        print(f"[Diet AI] Tokens used approx: {len(raw.split())} words | Chars: {len(raw)}")

        # Strip markdown fences
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        raw = raw.strip()

        parsed = json.loads(raw)

        # Normalize: if the model returned a list instead of an object
        if isinstance(parsed, list):
            parsed = parsed[0] if parsed else {}

        # Recalculate daily_totals server-side to fix any model arithmetic errors
        for day in parsed.get("days", []):
            meals = day.get("meals", [])
            day["daily_totals"] = {
                "calories": sum(m.get("calories", 0) for m in meals),
                "protein":  sum(m.get("protein", 0)  for m in meals),
                "carbs":    sum(m.get("carbs", 0)    for m in meals),
                "fat":      sum(m.get("fat", 0)      for m in meals),
            }

        return parsed

    except json.JSONDecodeError as exc:
        print(f"[Diet JSON Error]: {exc} | Raw length: {len(raw) if 'raw' in dir() else 'N/A'}")
        return None
    except Exception as exc:
        print(f"[Diet Groq Error]: {type(exc).__name__}: {exc}")
        return None


def _default_plan(plan_number: int) -> dict:
    return {
        "plan_name": f"Plan {plan_number} — No generado",
        "description": "No se pudo generar este plan. Intenta de nuevo.",
        "days": [],
    }


# ── Public API ─────────────────────────────────────────────────────────────────

def generate_diet_plans(profile: dict) -> dict[str, Any]:
    """
    Genera 2 planes de dieta semanales personalizados para el perfil dado.
    Usa una llamada separada por plan para evitar truncamiento del JSON.
    """
    macros = _calculate_macros(profile)
    print(f"[Diet] Generating for profile: goal={profile.get('goal')}, "
          f"diet={profile.get('diet_type')}, meals={profile.get('meals_per_day')}, "
          f"macros={macros}")

    plans = []
    for plan_num in [1, 2]:
        print(f"[Diet] Generating Plan {plan_num}...")
        prompt = _build_plan_prompt(profile, macros, plan_num)
        plan = _call_groq_for_plan(prompt)
        plans.append(plan if plan else _default_plan(plan_num))

    return {"plans": plans, "macros": macros}
