# rule_engine.py
from typing import Optional # Import Optional for type hinting

class RuleEngine:
    '''
    Placeholder for BRAIN's rule-based policy component (pi_R).
    In future iterations, this module will contain explicit rules and guardrails.
    '''
    def __init__(self):
        print("Rule Engine initialized: Ready for explicit rules.")

    def evaluate_rules(self, state: dict) -> Optional[dict]: # CORRECTED: Use Optional[dict]
        """
        Evaluates a set of predefined rules based on the current state.
        For now, it always returns None, deferring to the PolicyModule.

        Args:
        state (dict): The current state of the conversation.

        Returns:
        Optional[dict]: An action dictionary if a rule fires, otherwise None.
        """
        # For today, we'll make this always return None so the DecisionEngine
        # falls back to the PolicyModule. SOOOONNN ->>>
        return None

        # --- HIGH PRIORITY RULES (CRITICAL ACTIONS & IMMEDIATE RESPONSES) ---

        # Rule 1: Immediate Notification for Renovation Interest (HIGHEST PRIORITY)
        # This rule fires as soon as the intent is detected and we have basic contact info.
        # It's for hot leads that need human attention quickly.
        if state.get("current_intent") == "RenovatePolicy" and \
           state.get("contact_info_provided", False) and \
           not state.get("renovation_lead_notified", False): # Ensure it only fires once
            
            # Extract all relevant data for the email notification
            customer_name = state["entities"].get("customer_name", "Usuario Desconocido")
            policy_number = state["entities"].get("policy_number", "No Proporcionada")
            email = state["entities"].get("email", "No Proporcionado")
            phone_number = state["entities"].get("phone_number", state["session_id"]) # Use WhatsApp ID if no phone provided
            vin = state["entities"].get("vin", "No Proporcionado")
            vehicle_make = state["entities"].get("vehicle_make", "No Proporcionado")
            vehicle_model = state["entities"].get("vehicle_model", "No Proporcionado")
            vehicle_year = state["entities"].get("vehicle_year", "No Proporcionado")
            conversation_summary = state.get("conversation_summary", "No hay resumen disponible.") # Summary from MemoryManager

            # Update the state to mark that the lead has been notified
            state["renovation_lead_notified"] = True # This flag will be saved by DecisionEngine

            print(f"Rule Fired: Notify Human Renovation Lead for {customer_name}")
            return {
                "action_type": "notify_human_renovation_lead",
                "message_to_customer": f"Gracias {customer_name}. Hemos recibido su interés en renovar. Un agente se pondrá en contacto con usted en breve para ayudarle.",
                "notification_data": { # This data will be sent to Make.com for the email
                    "customer_name": customer_name,
                    "policy_number": policy_number,
                    "email": email,
                    "phone_whatsapp": phone_number,
                    "vin": vin,
                    "auto": f"{vehicle_make} {vehicle_model} {vehicle_year}".strip(),
                    "interest": "renovación",
                    "conversation_summary": conversation_summary
                }
            }
    
