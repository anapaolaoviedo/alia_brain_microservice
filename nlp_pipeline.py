    # nlp_pipeline.py
import re
import spacy
from spacy.language import Language
#rom spacy_llm.registry import registry
from spacy_llm.pipeline import SpacyLLM



class NlpPipeline:

        def __init__(self):
            try:
                self.nlp = spacy.load("en_core_web_sm")

                llm_component = SpacyLLM(
                    name="llm_text_processor",
                    model="gemini-2.0-flash",
                    api="gemini",
                    tasks={
                        "intent_classification": {
                            "task": "textcat",
                            "labels": ["RenovatePolicy", "GetQuote", "QueryPolicyDetails", "CancelRenovation", "Greeting", "RequestSupport", "Unknown"],
                            "prompt": """
                                You are an AI assistant for a car insurance company.
                                Classify the user's intent from the following message.
                                Choose one of these labels: RenovatePolicy, GetQuote, QueryPolicyDetails, CancelRenovation, Greeting, RequestSupport, Unknown.
                                If the user wants to renew or extend their car insurance, use 'RenovatePolicy'.
                                If they are asking for a price or estimate, use 'GetQuote'.
                                If they are asking about their existing policy details, use 'QueryPolicyDetails'.
                                If they want to cancel a renovation or policy, use 'CancelRenovation'.
                                If it's a general greeting, use 'Greeting'.
                                If they explicitly ask for help or support, use 'RequestSupport'.
                                Otherwise, use 'Unknown'.

                                Text: {text}
                                Intent:
                            """
                        },
                        "entity_extraction": {
                            "task": "ner",
                            "labels": ["POLICY_NUMBER", "VEHICLE_MAKE", "VEHICLE_MODEL", "VEHICLE_YEAR", "RENOVATION_DATE", "CUSTOMER_NAME", "EMAIL", "PHONE_NUMBER", "VIN" "CUSTOMER_ID"], # ADDED NEW LABELS HERE
                            "prompt": """
                                You are an AI assistant for a car insurance company.
                                Extract the following entities from the user's message related to car insurance renovation.
                                If an entity is not present, do not include it.

                                - POLICY_NUMBER: The alphanumeric policy identifier (e.g., ABC123456, XYZ987654).
                                - VEHICLE_MAKE: The manufacturer of the vehicle (e.g., Honda, Toyota).
                                - VEHICLE_MODEL: The specific model of the vehicle (e.g., Civic, Camry).
                                - VEHICLE_YEAR: The manufacturing year of the vehicle (e.g., 2020, 2023).
                                - RENOVATION_DATE: The desired date for policy renovation (e.g., tomorrow, July 15th, 2025).
                                - CUSTOMER_NAME: The name of the customer.
                                - EMAIL: The customer's email address (e.g., example@domain.com).
                                - PHONE_NUMBER: The customer's phone number, including country code if available (e.g., +5215548300145, 555-123-4567).
                                - VIN: The Vehicle Identification Number (a 17-character alphanumeric code).

                                Text: {text}
                                Entities:
                            """
                        }
                    }
                )
                self.nlp.add_pipe(llm_component, name="llm_processor", last=True)
                print("NLP Pipeline initialized with spaCy-LLM (Gemini): Ready to perceive")

            except Exception as e:
                print(f"Error initializing spaCy-LLM: {e}")
                print("Falling back to basic keyword matching and regex for NLP.")
                self.nlp = None

        def process_message(self, text: str) -> dict:
            #RULES BASED ON THE ENTITIES NEEDED 
            detected_intent = "Unknown"
            extracted_entities = {}

            if self.nlp:
                doc = self.nlp(text)
                if doc.cats:
                    detected_intent = max(doc.cats, key=doc.cats.get)
                for ent in doc.ents:
                    extracted_entities[ent.label_.lower()] = ent.text
            else:
                #in case that the LLM hallucinates 
                normalized_text = text.lower()
                
                if "renovate" in normalized_text or "renew" in normalized_text or \
                   "insurance" in normalized_text or "policy" in normalized_text:
                    detected_intent = "RenovatePolicy"
                
                if "cancelate" in normalized_text or "cancel" in normalized_text or \
                    "cancelate insurance" in normalized_text or "cancel policy" in normalized_text:
                        detected_intent = "CancelRenovation"
                

                # regex for policy number 
                policy_number_pattern = re.compile(r'\b[A-Z]{3}\d{6}\b')
                match = policy_number_pattern.search(text.upper())
                if match:
                    extracted_entities["policy_number"] = match.group(0)

                # regex for email
                email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
                match = email_pattern.search(text)
                if match:
                    extracted_entities["email"] = match.group(0)

                # regex for phone number 
                phone_pattern = re.compile(r'\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b')
                match = phone_pattern.search(text)
                if match:
                    extracted_entities["phone_number"] = match.group(0)
                
                # regex for vin
                vin_pattern = re.compile(r'\b[A-HJ-NPR-Z0-9]{17}\b')
                match = vin_pattern.search(text.upper())
                if match:
                    extracted_entities["vin"] = match.group(0)
                
                # regex for car brand 
                car_makes = ["honda", "toyota", "ford", "vw", "audi", "vento"] # <- might need to automate for the models 
                for make in car_makes:
                    if make in normalized_text:
                        extracted_entities["vehicle_make"] = make.capitalize()
                        break
                # regex for year of the car 
                year_pattern = re.compile(r'\b(19|20)\d{2}\b')
                match = year_pattern.search(text)
                if match:
                    extracted_entities["vehicle_year"] = match.group(0)
                
            #this must be returned to desicion_engine and possibly policy module, concrete on memory_manager too 
            return {
                "intent": detected_intent,
                "entities": extracted_entities
            }
    