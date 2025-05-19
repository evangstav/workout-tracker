# ai_utils.py
import os
import json
from typing import Literal, List
from pydantic import BaseModel, conint
from pydantic_ai import Agent
from pydantic import BaseModel, conint, ConfigDict


# ---------- 1.  Structured output -----------------
class FoodItem(BaseModel):
    meal_type: Literal["Breakfast", "Lunch", "Dinner", "Snack"]
    food_name: str
    quantity_g: conint(ge=1)
    calories: conint(ge=0)
    protein_g: conint(ge=0)
    model_config = ConfigDict(extra="forbid")  # no stray keys per-item


class DaySummary(BaseModel):
    total_calories: conint(ge=0)
    total_protein_g: conint(ge=0)
    items: List[FoodItem]
    model_config = ConfigDict(extra="forbid")


model = os.getenv("PYDANTIC_AI_MODEL", "openai:gpt-4o-mini")
print(f"Using model: {model}")
# ---------- 3.  Build the agent -------------------
SYSTEM_MSG = """
You are a nutrition assistant.

Return ONE valid JSON object that matches exactly this schema:

{
  "total_calories": integer,          // day's kcal sum
  "total_protein_g": integer,         // day's protein g sum
  "items": [
    {
      "meal_type":   "Breakfast" | "Lunch" | "Dinner" | "Snack",
      "food_name":   string,
      "quantity_g":  integer,         // grams
      "calories":    integer,         // kcal
      "protein_g":   integer          // g
    }
  ]
}

Rules:
1. **No markdown, no code fences, no commentary** – JSON only.
2. Use the key names exactly as shown.
3. If quantity is missing, infer a realistic portion size before you calculate kcal/protein.
"""
meal_agent = Agent(
    model=model,
    output_type=DaySummary,  # latest API style
    system_prompt=SYSTEM_MSG,
    # JSON-only guard (ignored by vendors that don't support it)
    model_kwargs={"response_format": {"type": "json_object"}},
)


# ---------- 4.  Utility that the Streamlit app calls -------------
def extract_meal_data(free_text: str) -> DaySummary:
    """Return a DaySummary object, including totals and items."""
    if not free_text or not free_text.strip():
        # Return a structure that indicates no data, matching DaySummary
        return DaySummary(items=[], total_calories=0, total_protein_g=0)
    parsed: DaySummary = meal_agent.run_sync(free_text)
    return parsed.output  # Return the DaySummary Pydantic object itself
