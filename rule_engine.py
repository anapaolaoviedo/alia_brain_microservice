# rule_engine.py
from typing import Optional # Import Optional for type hinting

class RuleEngine:
    '''
    BRAIN's rule-based policy component (pi_R).
    This module contains explicit rules and guardrails for decision-making.
    Rules are evaluated in order of priority.
    '''
    def __init__(self):
        print("Rule Engine initialized: Ready for explicit rules.")

    def evaluate_rules(self, state: dict) -> Optional[dict]:
        """
        Evaluates a set of predefined rules based on the current state.
        Rules are ordered by priority, with the first matching rule's action being returned.

        Args:
            state (dict): The current state of the conversation (from MemoryManager).

        Returns:
            Optional[dict]: An action dictionary if a rule fires, otherwise None.
        """

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

        # Rule 2: Answer "Cuánto cuesta renovar la garantía?" (GetQuote intent)
        # This is a direct answer from the FAQs.
        if state.get("current_intent") == "GetQuote":
            print("Rule Fired: Provide Renovation Cost Info")
            return {
                "action_type": "provide_info",
                "message": "Los costos de renovación de Garantía Extendida son:\n"
                           "Cobertura de 12 meses: $9,900.00\n"
                           "Cobertura de 24 meses: $14,900.00\n"
                           "Cobertura de 36 meses: $21,900.00\n"
                           "Cobertura de 48 meses: $28,900.00",
                "message_to_customer": "Los costos de renovación de Garantía Extendida son:\n"
                                       "Cobertura de 12 meses: $9,900.00\n"
                                       "Cobertura de 24 meses: $14,900.00\n"
                                       "Cobertura de 36 meses: $21,900.00\n"
                                       "Cobertura de 48 meses: $28,900.00"
            }
        
        # Rule 3: Answer "Dónde reportar para hacer válida la garantía?" (QueryPolicyDetails / RequestSupport)
        # This is a direct answer from the FAQs.
        if state.get("current_intent") == "QueryPolicyDetails" and \
           any(keyword in state.get("conversation_summary", "").lower() for keyword in ["reportar", "valida", "garantia"]):
           # Using conversation_summary for context if intent is general
            print("Rule Fired: Provide Warranty Claim Contact Info")
            return {
                "action_type": "provide_info",
                "message": "Para hacer válida su garantía, puede reportar a través de nuestro call center: 800 garanti (4272684) o WhatsApp 4432441212.",
                "message_to_customer": "Para hacer válida su garantía, puede reportar a través de nuestro call center: 800 garanti (4272684) o WhatsApp 4432441212."
            }

        # Rule 4: Answer "Puedo renovar si mi garantía ya expiró?" (RenovatePolicy / QueryExpiredRenewal)
        # This is a direct answer from the FAQs.
        if state.get("current_intent") == "RenovatePolicy" and \
           any(keyword in state.get("conversation_summary", "").lower() for keyword in ["expiró", "vencida", "pasada"]):
            print("Rule Fired: Provide Expired Renewal Policy")
            return {
                "action_type": "provide_info",
                "message": "Sí, puede renovar si su garantía ya expiró, pero no debe exceder de 30 días posterior al fin de vigencia y haber cumplido con los servicios en tiempo y forma.",
                "message_to_customer": "Sí, puede renovar si su garantía ya expiró, pero no debe exceder de 30 días posterior al fin de vigencia y haber cumplido con los servicios en tiempo y forma."
            }
        
        # Rule 5: Answer "Formas de pago o promociones?" (GetQuote / QueryPaymentOptions)
        if state.get("current_intent") == "GetQuote" and \
           any(keyword in state.get("conversation_summary", "").lower() for keyword in ["pago", "promociones", "msi"]):
            print("Rule Fired: Provide Payment Options")
            return {
                "action_type": "provide_info",
                "message": "El pago se realiza a través de transferencia o tarjeta. Actualmente contamos con la promoción de hasta 12 Meses Sin Intereses (MSI).",
                "message_to_customer": "El pago se realiza a través de transferencia o tarjeta. Actualmente contamos con la promoción de hasta 12 Meses Sin Intereses (MSI)."
            }

        # --- CORE RENOVATION FLOW RULES (GUIDING THE CONVERSATION) ---

        # Rule 6: Ask for Policy Number (if RenovatePolicy intent and no policy number)
        # This guides the user to provide necessary information for renovation.
        if state.get("current_intent") == "RenovatePolicy" and \
           not state.get("policy_number_provided", False):
            print("Rule Fired: Ask for Policy Number")
            return {
                "action_type": "ask_for_info",
                "message": "Para renovar su póliza, por favor, proporcione su número de póliza.",
                "message_to_customer": "Para renovar su póliza, por favor, proporcione su número de póliza."
            }

        # Rule 7: Ask for Vehicle Details (if policy number provided, but no vehicle details)
        # This guides the user to provide necessary information for renovation.
        if state.get("current_intent") == "RenovatePolicy" and \
           state.get("policy_number_provided", False) and \
           not state.get("vehicle_details_provided", False):
            print("Rule Fired: Ask for Vehicle Details")
            return {
                "action_type": "ask_for_info",
                "message": "¡Excelente! Ahora, ¿podría indicarme la marca, modelo y año de su vehículo?",
                "message_to_customer": "¡Excelente! Ahora, ¿podría indicarme la marca, modelo y año de su vehículo?"
            }
        
        # Rule 8: Ready for Quote (if all initial info collected and not yet quoted)
        # This is a transition rule to the next stage of the renovation process.
        if state.get("current_intent") == "RenovatePolicy" and \
           state.get("policy_number_provided", False) and \
           state.get("vehicle_details_provided", False) and \
           not state.get("quote_provided", False): # Ensure quote hasn't been provided yet
            # In a real scenario, you'd trigger an external quote generation API here.
            # For MVP, we'll simulate it.
            state["quote_provided"] = True # Mark quote as provided in state
            print("Rule Fired: Ready for Quote Generation")
            return {
                "action_type": "generate_quote",
                "message": "¡Perfecto! Con esta información, puedo generar una cotización para su renovación. Por favor, espere un momento.",
                "message_to_customer": "¡Perfecto! Con esta información, puedo generar una cotización para su renovación. Por favor, espere un momento."
            }

        # --- GENERAL FALLBACK RULES (LOWEST PRIORITY) ---

        # Rule 9: General Greeting Response
        if state.get("current_intent") == "Greeting":
            print("Rule Fired: General Greeting")
            return {
                "action_type": "greet",
                "message": "¡Hola! Soy tu asistente de GarantiPLUS. ¿En qué puedo ayudarte hoy con la renovación de tu garantía extendida?",
                "message_to_customer": "¡Hola! Soy tu asistente de GarantiPLUS. ¿En qué puedo ayudarte hoy con la renovación de tu garantía extendida?"
            }

        # Rule 10: Request Support Response
        if state.get("current_intent") == "RequestSupport":
            print("Rule Fired: Request Support")
            return {
                "action_type": "escalate_to_human",
                "message": "Entiendo que necesitas ayuda. Por favor, comunícate con nuestro centro de atención al cliente al 800 garanti (4272684) o por WhatsApp al 4432441212 para asistencia personalizada.",
                "message_to_customer": "Entiendo que necesitas ayuda. Por favor, comunícate con nuestro centro de atención al cliente al 800 garanti (4272684) o por WhatsApp al 4432441212 para asistencia personalizada."
            }

        # If no rule fires, return None, so the DecisionEngine can fall back to PolicyModule
        print("No rule fired. Deferring to Policy Module.")
        return None
