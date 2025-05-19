# ai_utils.py
import os
from typing import Literal, List
from pydantic import BaseModel, conint
from pydantic_ai import Agent
from pydantic_ai.models import (
    OpenAIModel,
    AnthropicModel,
    GeminiModel,
    MistralModel,
    FallbackModel,
)


# ---------- 1.  Structured output -----------------
class FoodItem(BaseModel):
    meal: Literal["Breakfast", "Lunch", "Dinner", "Snack"]
    food: str
    quantity_g: conint(ge=1)
    calories: conint(ge=0)
    protein_g: conint(ge=0)


class ParsedMeals(BaseModel):
    items: List[FoodItem]
    total_calories: conint(ge=0)
    total_protein_g: conint(ge=0)


# ---------- 2.  Pick provider(s) ------------------
def _pick_model() -> "Model":
    """Return a ready-to-use PydanticAI model according to env vars."""
    provider = os.getenv("AI_PROVIDER", "openai")
    model_name = os.getenv("AI_MODEL")  # optional override

    if provider == "openai":
        return OpenAIModel(model=model_name or "gpt-4o-mini")
    if provider == "anthropic":
        return AnthropicModel(model=model_name or "claude-3-haiku-20240307")
    if provider == "mistral":
        return MistralModel(model=model_name or "mistral-small-latest")
    if provider == "gemini":
        return GeminiModel(model=model_name or "gemini-1.5-flash")
    raise ValueError(f"Unknown AI_PROVIDER={provider!r}")


PRIMARY_MODEL = _pick_model()

# Optional: automatic fallback to a local Ollama model
if os.getenv("ENABLE_FALLBACK") == "1":
    from pydantic_ai.models.ollama import OllamaModel

    fallback = OllamaModel(model="mixtral:8x7b")
    PRIMARY_MODEL = FallbackModel([PRIMARY_MODEL, fallback])

# ---------- 3.  Build the agent -------------------
meal_agent = Agent(
    model=PRIMARY_MODEL,
    output_model=ParsedMeals,
    system_prompt=(
        "You are a nutrition assistant. "
        "Return a JSON object with a list called 'items' and two top-level keys: "
        "'total_calories' and 'total_protein_g'. "
        "Each item in the 'items' list should detail the meal type (Breakfast, Lunch, Dinner, Snack), "
        "food name, quantity in grams, calories, and protein in grams. "
        "If quantity, calories, or protein are missing for an item, assume a typical portion and estimate them. "
        "Calculate 'total_calories' and 'total_protein_g' by summing the calories and protein_g from all items in the list."
    ),
)


# ---------- 4.  Utility that the Streamlit app calls -------------
def extract_meal_data(free_text: str) -> dict:
    """Return a dict representing the ParsedMeals object, including totals and items."""
    if not free_text or not free_text.strip():
        # Return a structure that indicates no data, matching ParsedMeals
        return ParsedMeals(items=[], total_calories=0, total_protein_g=0).model_dump()
    parsed: ParsedMeals = meal_agent.run_sync(free_text)
    return parsed.model_dump()  # Pydantic v2 syntax
