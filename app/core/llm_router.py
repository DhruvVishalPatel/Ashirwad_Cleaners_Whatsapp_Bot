import os
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv
from app.core.logger import logger

# Configure API Key (ensure this is loaded from .env in production)
load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def classify_intent(user_text: str) -> tuple[str, str]:
    prompt = f"""
    You are an intent classification and language detection engine for 'Ashirwad Cleaners', a dry-cleaning business.
    Analyze the following user input, which may be in English, transliterated Hindi (Hinglish), or transliterated Gujarati (Gujlish) using Latin/English script.
    
    Map the input to EXACTLY ONE of the following intents:
    - INTENT_PICKUP: The user wants to schedule a pickup or drop off clothes.
    - INTENT_STATUS: The user is asking about the status of an existing order or tracking clothes.
    - INTENT_CANCEL_ORDER: The user wants to cancel an existing order (e.g. "cancel my order", "i want to cancel", "cancel order", "order cancel karna hai", "order radd karvo che", "cancel 1029").
    - INTENT_PRICING: The user is asking about prices, rates, or cost of services.
    - INTENT_GREETING: General greetings, hellos, start-of-conversation indicators (e.g. "hi", "hello", "hey", "kem cho", "namaste").
    - INTENT_QA: The user is asking questions about delivery times, business rules, service locations, specific items, or seeking help/complaining (e.g. "how much time for delivery", "carpet wash hota hai").
    - INTENT_CHANGE_LANGUAGE: The user explicitly wants to change language, switch language, or choose a different language to speak in (e.g. "change language", "language badlo", "switch to English", "gujarati select kar", "bhasha badlvi che").
    
    Also, detect the language style of the input:
    - ENGLISH: If the input is primarily standard English (e.g., "I want to schedule a pickup", "what is the price").
    - HINGLISH: If the input is Hindi transliterated in Latin script (e.g., "saree dry clean karwani hai", "mera kapda kab milega").
    - GUJLISH: If the input is Gujarati transliterated in Latin script (e.g., "kapda dhova aapva che", "bhav ketlo thase").
    
    CRITICAL CONSTRAINT FOR LANGUAGE:
    Generic, ambiguous, or extremely short greetings/inputs (such as "hi", "hello", "hey", "yes", "no") lack distinct linguistic markers. You MUST default them to "ENGLISH" or "HINGLISH" unless the message contains a distinct language marker (like "kem cho" or "karanu che" for GUJLISH, or "karna hai" or "bhav" for HINGLISH).
    
    User Input: "{user_text}"
    """

    # Enforce strict JSON output matching our schema
    model_name = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema={
                "type": "object",
                "properties": {
                    "intent": {
                        "type": "string",
                        "enum": ["INTENT_PICKUP", "INTENT_STATUS", "INTENT_CANCEL_ORDER", "INTENT_PRICING", "INTENT_GREETING", "INTENT_QA", "INTENT_CHANGE_LANGUAGE"]
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
        result = json.loads(response.text)
        intent = result.get("intent", "INTENT_QA")
        lang = result.get("detected_language", "ENGLISH")
        logger.info(f"Classify intent success. Input: '{user_text}' -> Intent: {intent}, Language: {lang}")
        return intent, lang
    except Exception as e:
        logger.error(f"Error classifying intent for input '{user_text}': {e}")
        return "INTENT_QA", "ENGLISH"


def answer_general_query(user_text: str, language: str = "ENGLISH") -> str:
    """Answers general customer questions (store hours, address, services, cancellation, turnaround, etc.)
    using verified store facts, strictly respecting the customer's preferred language.
    """
    lang = (language or "ENGLISH").upper()
    if lang == "HINGLISH":
        lang_instruction = (
            "CRITICAL LANGUAGE RULE: The customer's preferred language is HINGLISH. "
            "Formulate your entire response strictly in conversational Hindi written in the Latin (English) alphabet "
            '(e.g., "Humari shop Paldi mein hai..."). Do NOT respond in pure English or Gujarati.'
        )
    elif lang == "GUJLISH":
        lang_instruction = (
            "CRITICAL LANGUAGE RULE: The customer's preferred language is GUJLISH. "
            "Formulate your entire response strictly in conversational Gujarati written in the Latin (English) alphabet "
            '(e.g., "Amari shop Paldi ma che..."). Do NOT respond in pure English or Hindi.'
        )
    else:
        lang_instruction = (
            "CRITICAL LANGUAGE RULE: The customer's preferred language is ENGLISH. "
            "You MUST formulate your entire response STRICTLY in 100% standard, professional ENGLISH only. "
            "Under NO circumstances should you use any Hindi, Hinglish, or Gujarati words."
        )

    prompt = f"""
    You are an AI customer support assistant for Ashirwad Cleaners, a premium dry-cleaning and laundry service in Ahmedabad.
    
    Verified Store Facts:
    - Business Name: Ashirwad Cleaners
    - Shop Address: Raj Nagar complex, Rajnagar Society, Paldi, Ahmedabad, Gujarat 380007
    - Google Maps: https://maps.app.goo.gl/WFEzKEH5bHYWm6DRA
    - Service Area: Paldi area only for home pickup and delivery. Customers from other areas are welcome to drop off garments directly at the store.
    - Operating Hours: 9:00 AM to 8:30 PM (Open 7 days a week).
    - Services Offered: Premium Dry Cleaning, Washing, Steam Pressing, Petrol Wash, Stain Removal.
    - Turnaround Time: Typically 2 to 3 days.
    - Delivery Fee: ₹30 standard delivery fee (Waived for 4+ orders placed in a calendar month).
    - Loyalty Program: Earn 2 points per garment upon payment; redeemable at ₹1 per point once customer reaches 50+ points.
    - Order Cancellation: Customers can cancel orders while in 'Pending Pickup' status directly through WhatsApp. Orders already picked up or in-shop cannot be cancelled via chat.
    
    Customer Question: "{user_text}"
    
    {lang_instruction}
    
    Instructions:
    - Provide a polite, helpful, and concise response addressing the user's question using the verified store facts.
    - Do not invent services or locations not listed above.
    - Keep response under 3 sentences where possible.
    
    Respond in JSON format with key 'reply'.
    """

    model_name = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema={
                    "type": "object",
                    "properties": {"reply": {"type": "string"}},
                    "required": ["reply"]
                }
            )
        )
        data = json.loads(response.text)
        return data.get("reply", "")
    except Exception as e:
        logger.error(f"Error answering general query '{user_text}': {e}")
        return ""


def generate_estimate(user_text: str, language: str = "ENGLISH") -> dict:
    """Uses Gemini to match the user's clothes to the catalog across all services, then uses Python for perfectly accurate math."""
    from app.core.database import SessionLocal
    from app.models.schemas import CatalogItem

    all_valid_items = {}
    catalog_summary = {}
    
    try:
        with SessionLocal() as db:
            items = db.query(CatalogItem).all()
            for item in items:
                cat = item.service_type
                if cat not in all_valid_items:
                    all_valid_items[cat] = {}
                    catalog_summary[cat] = []
                all_valid_items[cat][item.item_name] = item.price
                catalog_summary[cat].append(item.item_name)
    except Exception as e:
        logger.error(f"Error querying catalog_items in generate_estimate: {e}")
        return {"is_question": False, "reply": "", "total_items_count": 0, "base_estimate": 0.0, "identified_services": ["Dry Clean"], "garments": []}

    lang = (language or "ENGLISH").upper()
    if lang == "HINGLISH":
        lang_rule = (
            "CRITICAL LANGUAGE RULE: The customer's preferred language is HINGLISH. "
            "Write the 'conversational_reply' strictly in conversational Hindi using Latin (English) script "
            '(e.g., "Aapka dry clean ka cost..."). Do NOT respond in pure English or Gujarati.'
        )
        unserviceable_ex = 'Sorry, Jackets ke liye Petrol Wash uplabdh nahi hai. Par Dry Cleaning ₹200 mein available hai. Kya aap dry clean karwana chahenge?'
        vague_ex = 'Kripya apne kapde aur unki service list karein, jaise: 2 shirts for washing, 1 saree for dry clean'
    elif lang == "GUJLISH":
        lang_rule = (
            "CRITICAL LANGUAGE RULE: The customer's preferred language is GUJLISH. "
            "Write the 'conversational_reply' strictly in conversational Gujarati using Latin (English) script "
            '(e.g., "Aapna dry clean no bhav..."). Do NOT respond in pure English or Hindi.'
        )
        unserviceable_ex = 'Maf karsho, Jacket mate Petrol Wash uplabdh nathi. Pan Jacket mate Dry Cleaning ₹200 ma uplabdh che. Shu tame dry clean karavva mango cho?'
        vague_ex = 'Kripya tamara kapda ane service list karo, jem ke: 2 shirts for washing, 1 saree for dry clean'
    else:
        lang_rule = (
            "CRITICAL LANGUAGE RULE: The customer's preferred language is ENGLISH. "
            "You MUST formulate 'conversational_reply' STRICTLY in 100% standard, professional ENGLISH only. "
            "Under NO circumstances should you use any Hindi, Hinglish, or Gujarati words."
        )
        unserviceable_ex = 'Sorry, we do not offer Petrol Wash for Jackets. However, we do offer Dry Cleaning for Jackets at ₹200. Would you like to dry clean your jacket instead?'
        vague_ex = 'Please list your garments and their desired service, e.g.: 2 shirts for washing, 1 saree for dry clean'

    prompt = f"""
    You are an AI assistant for Ashirwad Cleaners.
    The customer wants to schedule a pickup for their clothes. They may request multiple different services.
    
    Here are our available service categories and the ONLY valid item names for each:
    {json.dumps(catalog_summary, indent=2)}
    
    Customer Input: "{user_text}"
    
    Instructions:
    1. If the user is asking a question (e.g., about pricing, services, or general chat), OR if their input is vague/incomplete as described in step 6, set 'is_question_or_conversational' to true and provide a helpful 'conversational_reply' based on the price list provided.
       {lang_rule}
    2. If they are listing garments for pickup (e.g., "3 shirts for dry clean", "1 pant"), extract all garments into the 'garments' array. If quantity is not specified (e.g., "jacket", "saree"), DEFAULT quantity to 1!
    3. Determine which service category they want for each garment based on their input (e.g., 'washing', 'dry_clean', 'steam_press', 'petrol_wash'). If they don't explicitly specify, default to 'dry_clean'.
    4. Normalize each garment strictly to one of the valid item names in the chosen category. Handle synonyms (e.g., 'jeans' -> 'Pant', 'jacket' -> 'Jacket').
    5. UNSERVICEABLE ITEMS / CATEGORIES: If a user requests a service for an item that is NOT offered in that service category (e.g., requesting "jacket petrol wash" when Jacket is only available under dry_clean), set 'is_question_or_conversational' to true, keep 'garments' empty, and write a clear, polite 'conversational_reply' explaining that we do not offer that specific service for that item, but mention the service and price where the item IS available (e.g., "{unserviceable_ex}").
    6. If the user is trying to request a pickup but their request is too vague (e.g., they just say "laundry", "laundry karvana hai", "laundry dhoni hai", "laundry no order apo" without naming any garments at all), set 'is_question_or_conversational' to true, keep 'garments' empty, and write a polite 'conversational_reply' asking them to specify the clothes and services (e.g. "{vague_ex}").
    7. CRITICAL FOR ADDITIONS / REMOVALS / MODIFICATIONS: If the customer is adding, removing, or updating garments (e.g., "remove 4 pants from wash", "add 2 shirts", "nikal do 1 saree", "remove 1 shirt", "add 3 pants"), you MUST extract those garments and their quantities into the 'garments' array! Do NOT set 'is_question_or_conversational' to true for garment additions or removals.
    
    Output ONLY valid JSON matching the schema. Do not do any math.
    """

    model_name = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
    response = client.models.generate_content(
        model=model_name,
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
        
        # If garments exist, user is providing items, NOT asking a question!
        if garments:
            is_question = False
            
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
            qty = max(g.get("quantity", 1), 1)
            g["quantity"] = qty
            
            # Add to services used
            services_used.add(cat.replace("_", " ").title())
            
            # Lookup price
            category_prices = all_valid_items.get(cat, all_valid_items.get("dry_clean", {}))
            fallback_price = min(category_prices.values()) if category_prices else 50.0
            price = category_prices.get(name, fallback_price)
            
            total_count += qty
            total_estimate += (price * qty)
            
        identified_services = list(services_used) if services_used else ["Dry Clean"]
            
        logger.info(f"Generate estimate success. Input: '{user_text}' -> IsQuestion: {is_question}, Qty: {total_count}, Est: ₹{total_estimate}, Garments: {garments}")
        return {
            "is_question": is_question,
            "reply": reply,
            "total_items_count": total_count, 
            "base_estimate": total_estimate,
            "identified_services": identified_services,
            "garments": garments
        }
        
    except Exception as e:
        logger.error(f"Error generating estimate for input '{user_text}': {e}")
        return {"is_question": False, "reply": "", "total_items_count": 0, "base_estimate": 0.0, "identified_services": ["Dry Clean"], "garments": []}

