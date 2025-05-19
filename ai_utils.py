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


class ParsedMeals(BaseModel):
    items: List[FoodItem]


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
        "Return a JSON list called 'items' with the meal, food name "
        "and quantity in grams. If quantity missing assume a typical portion."
    ),
)


# ---------- 4.  Utility that the Streamlit app calls -------------
def extract_food_items(free_text: str) -> list[dict]:
    """Return list of dicts compatible with nutrition_items table."""
    parsed: ParsedMeals = meal_agent.run_sync(free_text)
    return [itm.model_dump() for itm in parsed.items]  # Pydantic v2 syntax
