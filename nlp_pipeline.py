# nlp_pipeline.py
import re
import spacy
import os
from dotenv import load_dotenv
from spacy.language import Language

# .env file
load_dotenv()
#making sure the connection is up 
print("🔐 OpenAI Key loaded:", os.getenv("OPENAI_API_KEY")[:8] + "...")


class NlpPipeline:
    """
    BRAIN's primary sensor, now enhanced with Large Language Model capabilities
    via spaCy-LLM. This module processes raw text percepts, leveraging an LLM
    (like OpenAI) for advanced intent classification and entity extraction.
    """
    def __init__(self):
        """
        Initializes the NLP pipeline with a base spaCy model and integrates
        spaCy-LLM components for LLM-powered text processing.
        """
        try:
            # 1. Load a base spaCy model (for tokenization, sentence segmentation, etc.)
            self.nlp = spacy.load("en_core_web_sm")

            # 2. Add a single spaCy-LLM component for text classification only
            # Note: We'll handle NER in the fallback for now to avoid complex multi-task setup
            
            self.nlp.add_pipe(
                "llm",
                name="llm_textcat",
                config={
                    "model": {
                        "@llm_models": "spacy.GPT-3-5.v1",
                        "name": "gpt-3.5-turbo"
                    },
                    "task": {
                        "@llm_tasks": "spacy.TextCat.v1",
                        "labels": "RenovatePolicy,GetQuote,QueryPolicyDetails,CancelRenovation,Greeting,RequestSupport,Unknown"
                    }
                },
                last=True
            )
            
            print("NLP Pipeline initialized with spaCy-LLM (OpenAI): Ready to perceive")

        except Exception as e:
            print(f"Error initializing spaCy-LLM: {e}")
            print("Falling back to basic keyword matching and regex for NLP.")
            self.nlp = None

    def process_message(self, text: str) -> dict:
        detected_intent = "Unknown"
        extracted_entities = {}

        if self.nlp:
            print(f"\n--- DEBUG: Processing with LLM for text: '{text}' ---")
            try:
                doc = self.nlp(text)
                print(f"--- DEBUG: Raw doc.cats: {doc.cats}")
                print(f"--- DEBUG: Raw doc.ents: {[(ent.text, ent.label_) for ent in doc.ents]}")

                if doc.cats:
                    detected_intent = max(doc.cats, key=doc.cats.get)
                else:
                    print("--- DEBUG: doc.cats is empty or None. LLM might not have classified intent.")

                for ent in doc.ents:
                    extracted_entities[ent.label_.lower()] = ent.text
                
                if not doc.ents:
                    print("--- DEBUG: doc.ents is empty. LLM might not have extracted entities.")

            except Exception as llm_error:
                print(f"--- DEBUG: Error during LLM processing: {llm_error}")
                print("--- DEBUG: Falling back to regex/keyword due to LLM error.")
                self.nlp = None # Disable LLM for subsequent calls if it fails once
                return self.process_message(text) # Recursive call to use fallback

        # This 'else' block (and the recursive call above) handles the fallback
        if not self.nlp: # This condition will be true if LLM failed or was never initialized
            print("--- DEBUG: Processing with Fallback (Keyword/Regex) ---")
            normalized_text = text.lower()
            
            # Intent Fallback
            if "renovar" in normalized_text or "renovacion" in normalized_text or \
               "renovar poliza" in normalized_text or "renovacion de poliza" in normalized_text or \
               "renovarla" in normalized_text or "renovarlo" in normalized_text or \
               "renovar garantia" in normalized_text or "renovacion de garantia" in normalized_text:
                detected_intent = "RenovatePolicy"
            elif "cancelar" in normalized_text or "cancelarla" in normalized_text or \
                 "cancelar renovacion" in normalized_text or "cancelar proceso" in normalized_text:
                detected_intent = "CancelRenovation"
            elif "hola" in normalized_text or "que tal" in normalized_text:
                detected_intent = "Greeting"
            elif "ayuda" in normalized_text or "soporte" in normalized_text:
                detected_intent = "RequestSupport"

            # Entity Fallback (Regex and keyword matching)
            policy_number_pattern = re.compile(r'\b[A-Z]{3}\d{6}\b')
            match = policy_number_pattern.search(text.upper())
            if match:
                extracted_entities["policy_number"] = match.group(0)

            email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
            match = email_pattern.search(text)
            if match:
                extracted_entities["email"] = match.group(0)

            phone_pattern = re.compile(r'\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b')
            match = phone_pattern.search(text)
            if match:
                extracted_entities["phone_number"] = match.group(0)
            
            vin_pattern = re.compile(r'\b[A-HJ-NPR-Z0-9]{17}\b')
            match = vin_pattern.search(text.upper())
            if match:
                extracted_entities["vin"] = match.group(0)
            
            car_makes = ["honda", "toyota", "ford", "vw", "audi", "vento", "nissan", "chevrolet"]
            for make in car_makes:
                if make in normalized_text:
                    extracted_entities["vehicle_make"] = make.capitalize()
                    break
            
            year_pattern = re.compile(r'\b(19|20)\d{2}\b')
            match = year_pattern.search(text)
            if match:
                extracted_entities["vehicle_year"] = match.group(0)
            
            if "my name is " in normalized_text:
                name_part = normalized_text.split("my name is ", 1)[1].split(" ")[0]
                if name_part:
                    extracted_entities["customer_name"] = name_part.capitalize()
            
        return {
            "intent": detected_intent,
            "entities": extracted_entities
        }