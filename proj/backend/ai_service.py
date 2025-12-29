import json
from llm_client import llm_client

INGREDIENT_ANALYSIS_PROMPT = """You are a nutrition science expert. Analyze the following ingredients list and provide structured JSON output.

For each ingredient, determine:
1. Purpose (why it's in the product)
2. Health considerations (benefits/concerns)
3. Scientific certainty level: "High", "Medium", or "Low"

Ingredients: {ingredients}

Return ONLY valid JSON in this exact format:
{{
  "ingredients": [
    {{
      "name": "ingredient name",
      "purpose": "brief purpose",
      "health_considerations": "brief health impact",
      "confidence": "High|Medium|Low"
    }}
  ]
}}

Be concise. Each field should be 1-2 sentences max."""

def analyze_ingredients(ingredients_text: str) -> dict:
    try:
        messages = [{
            "role": "user",
            "content": INGREDIENT_ANALYSIS_PROMPT.format(ingredients=ingredients_text)
        }]
        
        response_text = llm_client.create_completion(
            messages=messages,
            max_tokens=2000,
            temperature=0.5
        )
        
        # Handle markdown code blocks
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        
        response_text = response_text.strip()
        
        parsed = json.loads(response_text)
        return parsed
        
    except json.JSONDecodeError as e:
        print(f"JSON Parse Error: {e}")
        print(f"Response was: {response_text}")
        return {"ingredients": [], "error": "Failed to parse AI response"}
    except Exception as e:
        print(f"AI Service Error: {e}")
        return {"ingredients": [], "error": str(e)}
