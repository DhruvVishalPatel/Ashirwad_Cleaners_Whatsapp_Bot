import os
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Configure API Key (ensure this is loaded from .env in production)
load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def classify_intent(user_text: str) -> tuple[str, str]:
    prompt = f"""
    You are an intent classification and language detection engine for 'Ashirwad Cleaners', a dry-cleaning business.
    Analyze the following user input, which may be in English, transliterated Hindi (Hinglish), or transliterated Gujarati (Gujlish) using Latin/English script.
    
    Map the input to EXACTLY ONE of the following intents:
    - INTENT_PICKUP: The user wants to schedule a pickup or drop off clothes.
    - INTENT_STATUS: The user is asking about the status of an existing order.
    - INTENT_PRICING: The user is asking about prices, rates, or cost of services.
    - INTENT_HUMAN: The user is complaining, asking complex questions, or greeting generally without a clear goal.
    
    Also, detect the language style of the input:
    - ENGLISH: If the input is primarily standard English (e.g., "I want to schedule a pickup", "what is the price").
    - HINGLISH: If the input is Hindi transliterated in Latin script (e.g., "saree dry clean karwani hai", "mera kapda kab milega").
    - GUJLISH: If the input is Gujarati transliterated in Latin script (e.g., "kapda dhova aapva che", "bhav ketlo thase").
    
    User Input: "{user_text}"
    """

    # Enforce strict JSON output matching our schema
    response = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema={
                "type": "object",
                "properties": {
                    "intent": {
                        "type": "string",
                        "enum": ["INTENT_PICKUP", "INTENT_STATUS", "INTENT_PRICING", "INTENT_HUMAN"]
                    },
                    "detected_language": {
                        "type": "string",
                        "enum": ["ENGLISH", "HINGLISH", "GUJLISH"]
                    }
                },
                "required": ["intent", "detected_language"]
            }
        )
    )
    
    try:
        # The output is guaranteed to be a JSON string matching the schema
        result = json.loads(response.text)
        return result.get("intent", "INTENT_HUMAN"), result.get("detected_language", "ENGLISH")
    except Exception:
        return "INTENT_HUMAN", "ENGLISH"


def generate_estimate(user_text: str, language: str = "ENGLISH") -> dict:
    """Uses Gemini to match the user's clothes to the catalog across all services, then uses Python for perfectly accurate math."""
    # Load price list
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    file_path = os.path.join(base_dir, "price_list.json")
    try:
        with open(file_path, "r") as f:
            price_list = json.load(f)
    except Exception:
        return {"is_question": False, "reply": "", "total_items_count": 0, "base_estimate": 0.0, "identified_services": ["Dry Clean"], "garments": []}

    all_valid_items = {}
    catalog_summary = {}
    
    for category_key, category_data in price_list.get("services", {}).items():
        items_dict = {item["item_name"]: item["base_price"] for item in category_data.get("items", [])}
        all_valid_items[category_key] = items_dict
        catalog_summary[category_key] = list(items_dict.keys())

    prompt = f"""
    You are an AI assistant for Ashirwad Cleaners.
    The customer wants to schedule a pickup for their clothes. They may request multiple different services.
    
    Here are our available service categories and the ONLY valid item names for each:
    {json.dumps(catalog_summary, indent=2)}
    
    Customer Input: "{user_text}"
    
    Instructions:
    1. If the user is asking a question (e.g., about pricing, services, or general chat), set 'is_question_or_conversational' to true and provide a helpful 'conversational_reply' based on the price list provided.
       CRITICAL: Write the 'conversational_reply' in {language} transliterated into the Latin (English) script. For example, if {language} is HINGLISH, write in Hindi using English letters (e.g., "Aapka dry clean ka cost..."). If {language} is GUJLISH, write in Gujarati using English letters (e.g., "Aapna dry clean no bhav...").
    2. If they are listing garments for pickup, extract all garments and their quantities into the 'garments' array.
    3. Determine which service category they want for each garment based on their input (e.g., 'washing', 'dry_clean', 'steam_press'). If they don't explicitly specify, default to 'dry_clean'.
    4. Normalize each garment strictly to one of the valid item names in the chosen category. Handle synonyms (e.g., 'jeans' -> 'Pant').
    5. If an item cannot be matched at all, just return it as 'Unknown'.
    
    Output ONLY valid JSON matching the schema. Do not do any math.
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema={
                "type": "object",
                "properties": {
                    "is_question_or_conversational": {"type": "boolean"},
                    "conversational_reply": {"type": "string"},
                    "garments": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "service_category": {"type": "string"},
                                "normalized_name": {"type": "string"},
                                "quantity": {"type": "integer"}
                            },
                            "required": ["service_category", "normalized_name", "quantity"]
                        }
                    }
                },
                "required": ["is_question_or_conversational", "conversational_reply", "garments"]
            }
        )
    )
    
    try:
        parsed = json.loads(response.text)
        is_question = parsed.get("is_question_or_conversational", False)
        reply = parsed.get("conversational_reply", "")
        garments = parsed.get("garments", [])
        
        if is_question and not garments:
            return {
                "is_question": True,
                "reply": reply,
                "total_items_count": 0, 
                "base_estimate": 0.0,
                "identified_services": [],
                "garments": []
            }
        
        total_count = 0
        total_estimate = 0.0
        services_used = set()
        
        for g in garments:
            cat = g.get("service_category", "dry_clean")
            name = g.get("normalized_name", "")
            qty = g.get("quantity", 0)
            
            # Add to services used
            services_used.add(cat.replace("_", " ").title())
            
            # Lookup price
            category_prices = all_valid_items.get(cat, all_valid_items.get("dry_clean", {}))
            fallback_price = min(category_prices.values()) if category_prices else 50.0
            price = category_prices.get(name, fallback_price)
            
            total_count += qty
            total_estimate += (price * qty)
            
        identified_services = list(services_used) if services_used else ["Dry Clean"]
            
        return {
            "is_question": is_question,
            "reply": reply,
            "total_items_count": total_count, 
            "base_estimate": total_estimate,
            "identified_services": identified_services,
            "garments": garments
        }
        
    except Exception:
        return {"is_question": False, "reply": "", "total_items_count": 0, "base_estimate": 0.0, "identified_services": ["Dry Clean"], "garments": []}

