# nlp_pipeline.py
import re
import spacy
import os
import time
from dotenv import load_dotenv
from spacy.language import Language

# Load environment variables from .env file
load_dotenv()
# Print only first 8 chars of key for security
print("🔐 OpenAI Key loaded:", os.getenv("OPENAI_API_KEY")[:8] + "...")


class NlpPipeline:
    """
    BRAIN's primary sensor, now enhanced with Large Language Model capabilities
    via spaCy-LLM. This module processes raw text percepts, leveraging an LLM
    (like OpenAI) for advanced intent classification and entity extraction.
    """
    def __init__(self, use_llm=True, retry_delay=2.0):
        """
        Initializes the NLP pipeline with a base spaCy model and integrates
        spaCy-LLM components for LLM-powered text processing.
        
        Args:
            use_llm (bool): Whether to attempt LLM initialization
            retry_delay (float): Delay between retries in seconds
        """
        self.use_llm = use_llm
        self.retry_delay = retry_delay
        self.llm_failed_count = 0
        self.max_llm_failures = 3  # Temporarily disable LLM after 3 consecutive failures
        
        if self.use_llm:
            try:
                # 1. Load a base spaCy model (for tokenization, sentence segmentation, etc.)
                self.nlp = spacy.load("en_core_web_sm")

                # 2. Add separate LLM components for textcat and NER
                # Intent Classification Component
                self.nlp.add_pipe(
                    "llm_textcat",
                    name="intent_classifier",
                    config={
                        "model": {
                            "@llm_models": "spacy.GPT-4.v3", # CORRECTED FACTORY FOR GPT-4o-mini
                            "name": "gpt-4o-mini",          # UPDATED MODEL NAME
                            "config": {
                                "temperature": 0.1,
                                "max_tokens": 50
                            }
                        },
                        "task": {
                            "@llm_tasks": "spacy.TextCat.v3",
                            "labels": ["RenovatePolicy", "GetQuote", "QueryPolicyDetails", 
                                     "CancelRenovation", "Greeting", "RequestSupport", "Unknown"],
                            "template": """You are an AI assistant for a car insurance company.
Classify the user's intent from the following message.
Choose ONLY ONE of these labels: RenovatePolicy, GetQuote, QueryPolicyDetails, CancelRenovation, Greeting, RequestSupport, Unknown.

Rules:
- RenovatePolicy: user wants to renew/extend car insurance
- GetQuote: asking for price/estimate  
- QueryPolicyDetails: asking about existing policy details
- CancelRenovation: wants to cancel renovation/policy
- Greeting: general greeting (hola, hello, hi)
- RequestSupport: explicitly asks for help/support
- Unknown: anything else

Text: {{text}}
Intent:"""
                        }
                    }
                )

                # Named Entity Recognition Component  
                self.nlp.add_pipe(
                    "llm_ner",
                    name="entity_extractor", 
                    config={
                        "model": {
                            "@llm_models": "spacy.GPT-4.v3", # CORRECTED FACTORY FOR GPT-4o-mini
                            "name": "gpt-4o-mini",          # UPDATED MODEL NAME
                            "config": {
                                "temperature": 0.1,
                                "max_tokens": 200
                            }
                        },
                        "task": {
                            "@llm_tasks": "spacy.NER.v3",
                            "labels": ["POLICY_NUMBER", "VEHICLE_MAKE", "VEHICLE_MODEL", 
                                     "VEHICLE_YEAR", "RENOVATION_DATE", "CUSTOMER_NAME", 
                                     "EMAIL", "PHONE_NUMBER", "VIN", "CUSTOMER_ID"],
                            "template": """Extract entities from this car insurance message.
Only extract entities that are clearly present.

Types:
- POLICY_NUMBER: ABC123456, XYZ987654  
- VEHICLE_MAKE: Honda, Toyota, Ford
- VEHICLE_MODEL: Civic, Camry, Focus
- VEHICLE_YEAR: 2020, 2023
- RENOVATION_DATE: tomorrow, July 15th
- CUSTOMER_NAME: person's name
- EMAIL: email@domain.com
- PHONE_NUMBER: +5215548300145, 555-123-4567
- VIN: 17-character code
- CUSTOMER_ID: unique ID

Text: {{text}}
Entities:"""
                        }
                    },
                    last=True
                )
                
                print("NLP Pipeline initialized with spaCy-LLM (OpenAI): Ready to perceive")

            except Exception as e:
                print(f"Error initializing spaCy-LLM: {e}")
                print("Falling back to keyword/regex processing")
                self.nlp = None
        else:
            print("NLP Pipeline initialized in fallback mode (keyword/regex only)")
            self.nlp = None

    def process_message(self, text: str) -> dict:
        """Process a message and return intent and entities"""
        detected_intent = "Unknown"
        extracted_entities = {}

        # Check if we should try LLM (not disabled due to too many failures)
        if self.nlp and self.llm_failed_count < self.max_llm_failures:
            print(f"\nProcessing with LLM for text: '{text.strip()}'")
            try:
                doc = self.nlp(text)
                
                # Get intent from text classification
                if doc.cats:
                    detected_intent = max(doc.cats, key=doc.cats.get)
                    confidence = doc.cats[detected_intent]
                    print(f"LLM Intent: {detected_intent} (confidence: {confidence:.2f})")
                else:
                    print("No intent classification from LLM")

                # Extract entities
                for ent in doc.ents:
                    extracted_entities[ent.label_.lower()] = ent.text
                
                if doc.ents:
                    print(f"LLM Entities: {extracted_entities}")
                else:
                    print("No entities extracted by LLM")
                
                # Reset failure count on success
                self.llm_failed_count = 0
                
                # If LLM didn't find much, supplement with fallback
                if detected_intent == "Unknown" or not extracted_entities:
                    print("🔄 Supplementing with fallback processing...")
                    fallback_intent, fallback_entities = self._fallback_processing(text)
                    if detected_intent == "Unknown":
                        detected_intent = fallback_intent
                    extracted_entities.update({k: v for k, v in fallback_entities.items() 
                                             if k not in extracted_entities})

            except Exception as llm_error:
                self.llm_failed_count += 1
                print(f"LLM Error (attempt {self.llm_failed_count}): {llm_error}")
                
                if "429" in str(llm_error) or "Rate limit" in str(llm_error):
                    print(f"Rate limited. Waiting {self.retry_delay}s before fallback...")
                    time.sleep(self.retry_delay)
                
                if self.llm_failed_count >= self.max_llm_failures:
                    print(f"Temporarily disabling LLM after {self.max_llm_failures} failures")
                
                print("Using fallback processing...")
                detected_intent, extracted_entities = self._fallback_processing(text)

        else:
            reason = "disabled due to failures" if self.llm_failed_count >= self.max_llm_failures else "not initialized"
            print(f"Processing with fallback ({reason})")
            detected_intent, extracted_entities = self._fallback_processing(text)

        return {
            "intent": detected_intent,
            "entities": extracted_entities,
            "processing_method": "llm" if self.nlp and self.llm_failed_count < self.max_llm_failures else "fallback"
        }
    
    def _fallback_processing(self, text: str) -> tuple:
        """Enhanced fallback processing using regex and keyword matching"""
        detected_intent = "Unknown"
        extracted_entities = {}
        normalized_text = text.lower()
        
        # Intent Classification Fallback - More comprehensive
        intent_keywords = {
            "RenovatePolicy": ["renovar", "renovacion", "renovar poliza", "renovacion de poliza", 
                              "renovarla", "renovarlo", "renovar garantia", "renovacion de garantia",
                              "renew", "renewal", "extend policy"],
            "CancelRenovation": ["cancelar", "cancelarla", "cancelar renovacion", "cancelar proceso",
                               "cancel", "stop", "terminate"],
            "Greeting": ["hola", "que tal", "buenos dias", "buenas tardes", "hello", "hi", "hey", "good morning"],
            "RequestSupport": ["ayuda", "soporte", "asistencia", "help", "support", "assistance", "problema"],
            "GetQuote": ["precio", "cotizar", "cotizacion", "costo", "quote", "price", "cost", "estimate"],
            "QueryPolicyDetails": ["poliza", "detalles", "informacion", "consultar", "policy", "details", "information", "status"]
        }
        
        # Check for intent keywords
        for intent, keywords in intent_keywords.items():
            if any(keyword in normalized_text for keyword in keywords):
                detected_intent = intent
                break

        # Enhanced Entity Extraction with better patterns
        patterns = {
            "policy_number": r'\b[A-Z]{2,4}\d{5,8}\b',
            "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            "phone_number": r'(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{4,6}',
            "vin": r'\b[A-HJ-NPR-Z0-9]{17}\b',
            "vehicle_year": r'\b(19[8-9]\d|20[0-4]\d)\b',
            "customer_id": r'\b(?:ID|id|Id)[-:\s]*([A-Z0-9]{4,12})\b'
        }
        
        # Apply regex patterns
        for entity_type, pattern in patterns.items():
            flags = re.IGNORECASE if entity_type not in ["policy_number", "vin"] else 0
            search_text = text.upper() if entity_type in ["policy_number", "vin"] else text
            match = re.search(pattern, search_text, flags)
            if match:
                extracted_entities[entity_type] = match.group(1) if entity_type == "customer_id" else match.group(0)
        
        # Enhanced car makes detection
        car_makes = {
            "honda": ["honda"],
            "toyota": ["toyota"],
            "ford": ["ford"],
            "volkswagen": ["vw", "volkswagen"],
            "audi": ["audi"],
            "nissan": ["nissan"],
            "chevrolet": ["chevrolet", "chevy"],
            "bmw": ["bmw"],
            "mercedes": ["mercedes", "mercedes-benz", "benz"],
            "hyundai": ["hyundai"],
            "kia": ["kia"],
            "mazda": ["mazda"],
            "subaru": ["subaru"],
            "jeep": ["jeep"]
        }
        
        for make, variants in car_makes.items():
            if any(variant in normalized_text for variant in variants):
                extracted_entities["vehicle_make"] = make.capitalize()
                break
        
        # Enhanced model detection (basic patterns)
        common_models = ["civic", "accord", "corolla", "camry", "focus", "fiesta", "sentra", "altima",
                         "vento", "versa", "cr-v", "rav4", "f-150", "silverado", "jetta", "golf"]
        for model in common_models:
            if model in normalized_text:
                extracted_entities["vehicle_model"] = model.capitalize()
                break
        
        # Enhanced name extraction
        name_patterns = [
            (r"my name is ([A-Za-zÀ-ÿ]+(?:\s+[A-Za-zÀ-ÿ]+)?)", 1),
            (r"me llamo ([A-Za-zÀ-ÿ]+(?:\s+[A-Za-zÀ-ÿ]+)?)", 1),
            (r"soy ([A-Za-zÀ-ÿ]+(?:\s+[A-Za-zÀ-ÿ]+)?)", 1),
            (r"nombre[:\s]+([A-Za-zÀ-ÿ]+(?:\s+[A-Za-zÀ-ÿ]+)?)", 1)
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
        print("🔄 LLM failure count reset. LLM processing re-enabled.")
    
    def get_status(self):
        """Get current pipeline status"""
        return {
            "llm_enabled": self.nlp is not None,
            "llm_failures": self.llm_failed_count,
            "llm_temp_disabled": self.llm_failed_count >= self.max_llm_failures,
            "processing_mode": "llm" if self.nlp and self.llm_failed_count < self.max_llm_failures else "fallback"
        }
