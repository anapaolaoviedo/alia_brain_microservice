# nlp_pipeline.py - Updated version with vehicle info intent
import re
import spacy
import os
import time
import json
import openai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
print("🔐 OpenAI Key loaded:", os.getenv("OPENAI_API_KEY")[:8] + "...")

class NlpPipeline:
    """
    BRAIN's primary sensor with direct OpenAI integration and robust fallback.
    Simplified approach that bypasses spaCy-LLM configuration issues.
    """
    def __init__(self, use_llm=True, retry_delay=2.0):
        self.use_llm = use_llm
        self.retry_delay = retry_delay
        self.llm_failed_count = 0
        self.max_llm_failures = 3
        
        # Initialize OpenAI client
        if self.use_llm:
            try:
                openai.api_key = os.getenv("OPENAI_API_KEY")
                self.client = openai.OpenAI()
                print("NLP Pipeline initialized with direct OpenAI integration: Ready to perceive")
            except Exception as e:
                print(f"Error initializing OpenAI: {e}")
                print("Falling back to keyword/regex processing")
                self.client = None
        else:
            print("NLP Pipeline initialized in fallback mode (keyword/regex only)")
            self.client = None

        # Load basic spaCy model for text preprocessing
        try:
            self.nlp_basic = spacy.load("en_core_web_sm")
        except:
            print("Warning: spaCy model not found. Using basic text processing.")
            self.nlp_basic = None

    def process_message(self, text: str) -> dict:
        """Process a message and return intent and entities"""
        detected_intent = "Unknown"
        extracted_entities = {}

        if self.client and self.llm_failed_count < self.max_llm_failures:
            print(f"\n--- DEBUG: Processing with OpenAI LLM for text: '{text.strip()}' ---")
            try:
                # Direct OpenAI API call with improved system prompt
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": """You are an AI assistant for a car insurance company. 
                            
                            Classify the user's intent into ONE of: 
                            - RenovatePolicy: User wants to renew their insurance policy
                            - GetQuote: User asks for price/quote
                            - QueryPolicyDetails: User provides policy number or asks about policy
                            - ProvideVehicleInfo: User provides vehicle make, model, year (like "Honda Civic 2020", "es un VW Vento 2015")
                            - ProvideContactInfo: User provides name, email, phone
                            - CancelRenovation: User wants to cancel
                            - Greeting: Hello, good morning, etc.
                            - RequestSupport: User asks for help
                            - ConfirmRenovation: User confirms with "sí", "confirmo", "proceda", "adelante"
                            - Unknown: Cannot determine intent
                            
                            Extract entities for: POLICY_NUMBER, VEHICLE_MAKE, VEHICLE_MODEL, VEHICLE_YEAR, CUSTOMER_NAME, EMAIL, PHONE_NUMBER, VIN.
                            
                            IMPORTANT CONTEXT RULES:
                            - If user says "es un [brand] [model] [year]" = ProvideVehicleInfo
                            - If user says "sí", "confirmo", "proceda", "adelante" after discussing renovation = ConfirmRenovation
                            - "renovar", "renovación" = RenovatePolicy
                            - Always preserve and extract policy numbers, names, emails, vehicle info
                            
                            Examples:
                            - "Es un auto Honda Civic 2020" → ProvideVehicleInfo
                            - "Mi carro es un VW Vento 2015" → ProvideVehicleInfo
                            - "Tengo un Toyota Corolla del 2018" → ProvideVehicleInfo
                            
                            Respond ONLY with valid JSON:
                            {"intent": "IntentName", "entities": {"entity_type": "value"}}"""
                        },
                        {
                            "role": "user", 
                            "content": text
                        }
                    ],
                    temperature=0.1,
                    max_tokens=300
                )
                
                # Parse the response
                content = response.choices[0].message.content.strip()
                
                # Clean JSON response (remove markdown if present)
                if content.startswith("```json"):
                    content = content.replace("```json", "").replace("```", "").strip()
                
                parsed_output = json.loads(content)
                detected_intent = parsed_output.get("intent", "Unknown")
                extracted_entities = parsed_output.get("entities", {})

                print(f"--- DEBUG: LLM Intent: {detected_intent}")
                print(f"--- DEBUG: LLM Entities: {extracted_entities}")

                # Reset failure count on success
                self.llm_failed_count = 0
                
                # If LLM didn't find much, supplement with fallback
                if detected_intent == "Unknown" or not extracted_entities:
                    print("Supplementing with fallback processing...")
                    fallback_intent, fallback_entities = self._fallback_processing(text)
                    if detected_intent == "Unknown":
                        detected_intent = fallback_intent
                    # Normalize and merge entities
                    normalized_fallback = self._normalize_entities(fallback_entities)
                    normalized_extracted = self._normalize_entities(extracted_entities)
                    extracted_entities = {**normalized_fallback, **normalized_extracted}

            except json.JSONDecodeError as json_error:
                print(f"--- DEBUG: JSON parsing error: {json_error}")
                print(f"Raw response: {content if 'content' in locals() else 'No content'}")
                detected_intent, extracted_entities = self._fallback_processing(text)
                extracted_entities = self._normalize_entities(extracted_entities)
                
            except Exception as llm_error:
                self.llm_failed_count += 1
                print(f"--- DEBUG: Error during LLM processing: {llm_error}")
                
                if "429" in str(llm_error) or "rate_limit" in str(llm_error).lower():
                    print(f"Rate limited. Waiting {self.retry_delay}s before fallback...")
                    time.sleep(self.retry_delay)
                
                if self.llm_failed_count >= self.max_llm_failures:
                    print(f"Temporarily disabling LLM after {self.llm_failed_count} failures")
                
                print("Using fallback processing...")
                detected_intent, extracted_entities = self._fallback_processing(text)
                extracted_entities = self._normalize_entities(extracted_entities)

        else:
            reason = "disabled due to failures" if self.llm_failed_count >= self.max_llm_failures else "not initialized"
            print(f"--- DEBUG: Processing with fallback ({reason}) ---")
            detected_intent, extracted_entities = self._fallback_processing(text)
            extracted_entities = self._normalize_entities(extracted_entities)

        return {
            "intent": detected_intent,
            "entities": extracted_entities,
            "processing_method": "llm" if self.client and self.llm_failed_count < self.max_llm_failures else "fallback"
        }
    
    def _normalize_entities(self, entities: dict) -> dict:
        """Normalize entity keys to consistent format"""
        normalized = {}
        
        entity_mappings = {
            'vehicle_make': 'VEHICLE_MAKE',
            'vehicle_model': 'VEHICLE_MODEL', 
            'vehicle_year': 'VEHICLE_YEAR',
            'customer_name': 'CUSTOMER_NAME',
            'policy_number': 'POLICY_NUMBER',
            'email': 'EMAIL',
            'phone_number': 'PHONE_NUMBER',
            'vin': 'VIN'
        }
        
        for key, value in entities.items():
            # Use mapping if exists, otherwise keep original key
            standard_key = entity_mappings.get(key.lower(), key.upper())
            normalized[standard_key] = value
            
        return normalized
    
    def _fallback_processing(self, text: str) -> tuple:
        """Enhanced fallback processing with context awareness"""
        detected_intent = "Unknown"
        extracted_entities = {}
        normalized_text = text.lower()
        
        # Enhanced intent keywords with vehicle info detection
        intent_keywords = {
            "ConfirmRenovation": ["sí", "si", "confirmo", "confirmó", "proceda", "proceder", "adelante", "de acuerdo", "está bien", "ok", "yes", "confirm", "proceed"],
            "RenovatePolicy": ["renovar", "renovacion", "renovación", "renovar poliza", "renovar póliza", "renovarla", "renovarlo", "renew", "renewal", "extend policy"],
            "CancelRenovation": ["cancelar", "cancelarla", "cancelar renovacion", "cancelar renovación", "cancelar proceso", "cancel", "stop", "terminate", "no quiero"],
            "Greeting": ["hola", "que tal", "qué tal", "buenos dias", "buenos días", "buenas tardes", "hello", "hi", "hey", "good morning"],
            "RequestSupport": ["ayuda", "soporte", "asistencia", "help", "support", "assistance", "problema"],
            "GetQuote": ["precio", "cotizar", "cotizacion", "cotización", "costo", "quote", "price", "cost", "estimate"],
            "QueryPolicyDetails": ["poliza", "póliza", "detalles", "informacion", "información", "consultar", "policy", "details", "information", "status"],
            "ProvideVehicleInfo": ["es un", "tengo un", "mi carro", "mi auto", "mi vehículo", "it's a", "i have a", "my car"]
        }
        
        # Find intent with priority for confirmation words
        for intent, keywords in intent_keywords.items():
            if any(keyword in normalized_text for keyword in keywords):
                detected_intent = intent
                break

        # Enhanced entity extraction patterns
        patterns = {
            "policy_number": r'\b[A-Z]{2,4}\d{5,8}\b',
            "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            "phone_number": r'(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{4,6}',
            "vin": r'\b[A-HJ-NPR-Z0-9]{17}\b',
            "vehicle_year": r'\b(19[8-9]\d|20[0-4]\d)\b',
            "customer_id": r'\b(?:ID|id|Id)[-:\s]*([A-Z0-9]{4,12})\b'
        }
        
        for entity_type, pattern in patterns.items():
            flags = re.IGNORECASE if entity_type not in ["policy_number", "vin"] else 0
            search_text = text.upper() if entity_type in ["policy_number", "vin"] else text
            match = re.search(pattern, search_text, flags)
            if match:
                extracted_entities[entity_type] = match.group(1) if entity_type == "customer_id" else match.group(0)
        
        # Enhanced car make detection
        car_makes = {
            "Volkswagen": ["vw", "volkswagen"], "Honda": ["honda"], "Toyota": ["toyota"], 
            "Ford": ["ford"], "Audi": ["audi"], "Nissan": ["nissan"],
            "Chevrolet": ["chevrolet", "chevy"], "BMW": ["bmw"],
            "Mercedes": ["mercedes", "mercedes-benz", "benz"], "Hyundai": ["hyundai"],
            "Kia": ["kia"], "Mazda": ["mazda"], "Subaru": ["subaru"], "Jeep": ["jeep"]
        }
        
        for make, variants in car_makes.items():
            if any(variant in normalized_text for variant in variants):
                extracted_entities["vehicle_make"] = make
                break
        
        # Enhanced model detection
        common_models = {
            "vento": "Vento", "civic": "Civic", "accord": "Accord", "corolla": "Corolla", 
            "camry": "Camry", "focus": "Focus", "fiesta": "Fiesta", "sentra": "Sentra", 
            "altima": "Altima", "versa": "Versa", "jetta": "Jetta", "golf": "Golf"
        }
        
        for model_key, model_name in common_models.items():
            if model_key in normalized_text:
                extracted_entities["vehicle_model"] = model_name
                break
        
        # Enhanced name extraction with Spanish support
        name_patterns = [
            (r"my name is ([A-Za-zÀ-ÿ]+(?:\s+[A-Za-zÀ-ÿ]+)?)", 1),
            (r"me llamo ([A-Za-zÀ-ÿ]+(?:\s+[A-Za-zÀ-ÿ]+)?)", 1),
            (r"soy ([A-Za-zÀ-ÿ]+(?:\s+[A-Za-zÀ-ÿ]+)?)", 1),
            (r"nombre[:\s]+([A-Za-zÀ-ÿ]+(?:\s+[A-Za-zÀ-ÿ]+)?)", 1),
            (r"mi nombre es ([A-Za-zÀ-ÿ]+(?:\s+[A-Za-zÀ-ÿ]+)?)", 1)
        ]
        
        for pattern, group in name_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = match.group(group).strip().title()
                if len(name) > 1 and not any(char.isdigit() for char in name):
                    extracted_entities["customer_name"] = name
                    break
        
        print(f"🔧 Fallback results - Intent: {detected_intent}, Entities: {extracted_entities}")
        return detected_intent, extracted_entities
    
    def reset_llm_failures(self):
        """Reset LLM failure count to re-enable LLM processing"""
        self.llm_failed_count = 0
        print("LLM failure count reset. LLM processing re-enabled.")
    
    def get_status(self):
        """Get current pipeline status"""
        return {
            "llm_enabled": self.client is not None,
            "llm_failures": self.llm_failed_count,
            "llm_temp_disabled": self.llm_failed_count >= self.max_llm_failures,
            "processing_mode": "llm" if self.client and self.llm_failed_count < self.max_llm_failures else "fallback"
        }