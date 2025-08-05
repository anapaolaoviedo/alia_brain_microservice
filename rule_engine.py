"""
BRAIN Rule Engine - Strategic Decision-Making System
==================================================

This module implements BRAIN's "Strategic Decision-Making" capability through explicit
business rules and guardrails. It acts as the policy enforcement layer (π_R) that
ensures critical business actions are taken accurately and consistently.

Rule Architecture:
1. HIGH PRIORITY: Critical actions and immediate responses (notifications, escalations)
2. MEDIUM PRIORITY: Core conversation flow rules (information gathering)
3. LOW PRIORITY: General fallback responses (greetings, support)

Rules are evaluated in priority order, with the first matching rule's action being executed.
This ensures deterministic behavior for important business scenarios while allowing
flexibility for edge cases.

Key Business Rules:
- Automatic human agent notification when renovation intent + contact info detected
- FAQ responses for common questions (pricing, claims, payments)
- Guided conversation flow for policy renewals (collect policy #, vehicle info, generate quote)
- Fallback responses for general inquiries and support requests
"""

from typing import Optional # Import Optional for type hinting

class RuleEngine:
    '''
    BRAIN's rule-based policy component (π_R).
    
    This module contains explicit rules and guardrails for decision-making in the
    insurance domain. Rules encode business logic, compliance requirements, and
    best practices for customer interactions.
    
    Rules are evaluated in strict priority order to ensure consistent and predictable
    behavior for critical business scenarios.
    '''
    def __init__(self):
        """
        Initialize the rule engine with predefined business rules.
        
        Rules are hard-coded rather than loaded from external files to ensure
        reliability and prevent accidental rule modifications that could impact
        business operations.
        """
        print("Rule Engine initialized: Ready for explicit rules.")

    def evaluate_rules(self, state: dict) -> Optional[dict]:
        """
        Evaluate predefined business rules based on the current conversation state.
        
        This method implements BRAIN's strategic decision-making by checking the current
        conversation context against explicit business rules. Rules are ordered by
        business priority, with critical actions (like human notifications) taking
        precedence over informational responses.
        
        Processing Logic:
        1. Extract current intent and entities from conversation state
        2. Check rules in priority order (high → medium → low)
        3. Return action for first matching rule
        4. Return None if no rules match (triggers policy module fallback)

        Args:
            state (dict): Complete conversation state from MemoryManager including:
                - current_intent: What the customer wants to accomplish
                - entities: Extracted information (policy #, vehicle details, contact info)
                - conversation_summary: Running summary of the conversation
                - Various flags tracking conversation progress

        Returns:
            Optional[dict]: Action dictionary if a rule fires, otherwise None.
                Action structure: {
                    "action_type": "category_of_action",
                    "message_to_customer": "response_text",
                    "additional_data": {...}  # Action-specific metadata
                }
        """

        # ========================================================================
        # HIGH PRIORITY RULES - CRITICAL ACTIONS & IMMEDIATE RESPONSES
        # ========================================================================
        # These rules handle business-critical scenarios that require immediate
        # action and cannot be delayed or missed.

        # RULE 1: HUMAN AGENT NOTIFICATION - Business Critical
        # Triggers when we have sufficient information to notify a human sales agent
        # This is the most important rule as it directly impacts revenue generation
        if state.get("current_intent") == "RenovatePolicy" and \
           state.get("entities", {}).get("POLICY_NUMBER") and \
           (state.get("entities", {}).get("CUSTOMER_NAME") or state.get("entities", {}).get("EMAIL")) and \
           not state.get("renovation_lead_notified", False): # Ensure it only fires once per conversation
            
            # Extract all available customer data for the sales team
            entities = state.get("entities", {})
            customer_name = entities.get("CUSTOMER_NAME", "Usuario Desconocido")
            policy_number = entities.get("POLICY_NUMBER", "No Proporcionada")
            email = entities.get("EMAIL", "No Proporcionado")
            phone_number = entities.get("PHONE_NUMBER", state.get("session_id", "No Proporcionado"))
            vin = entities.get("VIN", "No Proporcionado")
            vehicle_make = entities.get("VEHICLE_MAKE", "No Proporcionado")
            vehicle_model = entities.get("VEHICLE_MODEL", "No Proporcionado")
            vehicle_year = entities.get("VEHICLE_YEAR", "No Proporcionado")
            conversation_summary = state.get("conversation_summary", "No hay resumen disponible.")

            # Mark notification as sent to prevent duplicate notifications
            state["renovation_lead_notified"] = True # This flag will be saved by DecisionEngine

            print(f"Rule Fired: Notify Human Renovation Lead for {customer_name}")
            return {
                "action_type": "notify_human_renovation_lead",
                "message_to_customer": f"Gracias {customer_name}. Hemos recibido su interés en renovar. Un agente se pondrá en contacto con usted en breve para ayudarle.",
                "notification_data": { # This data will be sent to Make.com for CRM integration
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

        # RULE 2: PRICING INFORMATION - Direct FAQ Response
        # Provides immediate pricing information when customers ask about costs
        # This reduces sales friction by providing transparent pricing upfront
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
        
        # RULE 3: CLAIMS REPORTING INFORMATION - Customer Service Critical
        # Provides warranty claim contact information - critical for customer satisfaction
        # Uses conversation context to detect claims-related queries
        if state.get("current_intent") == "QueryPolicyDetails" and \
           any(keyword in state.get("conversation_summary", "").lower() for keyword in ["reportar", "valida", "garantia"]):
            print("Rule Fired: Provide Warranty Claim Contact Info")
            return {
                "action_type": "provide_info",
                "message": "Para hacer válida su garantía, puede reportar a través de nuestro call center: 800 garanti (4272684) o WhatsApp 4432441212.",
                "message_to_customer": "Para hacer válida su garantía, puede reportar a través de nuestro call center: 800 garanti (4272684) o WhatsApp 4432441212."
            }

        # RULE 4: EXPIRED POLICY RENEWAL - Business Policy Clarification
        # Handles questions about renewing expired policies - important for revenue recovery
        # Uses conversation context to detect expiration-related concerns
        if state.get("current_intent") == "RenovatePolicy" and \
           any(keyword in state.get("conversation_summary", "").lower() for keyword in ["expiró", "vencida", "pasada"]):
            print("Rule Fired: Provide Expired Renewal Policy")
            return {
                "action_type": "provide_info",
                "message": "Sí, puede renovar si su garantía ya expiró, pero no debe exceder de 30 días posterior al fin de vigencia y haber cumplido con los servicios en tiempo y forma.",
                "message_to_customer": "Sí, puede renovar si su garantía ya expiró, pero no debe exceder de 30 días posterior al fin de vigencia y haber cumplido con los servicios en tiempo y forma."
            }
        
        # RULE 5: PAYMENT OPTIONS - Sales Support Information
        # Provides payment method information when customers ask about financing
        # Promotes the MSI (Months Without Interest) program to increase conversion
        if state.get("current_intent") == "GetQuote" and \
           any(keyword in state.get("conversation_summary", "").lower() for keyword in ["pago", "promociones", "msi"]):
            print("Rule Fired: Provide Payment Options")
            return {
                "action_type": "provide_info",
                "message": "El pago se realiza a través de transferencia o tarjeta. Actualmente contamos con la promoción de hasta 12 Meses Sin Intereses (MSI).",
                "message_to_customer": "El pago se realiza a través de transferencia o tarjeta. Actualmente contamos con la promoción de hasta 12 Meses Sin Intereses (MSI)."
            }

        # ========================================================================
        # MEDIUM PRIORITY RULES - CORE CONVERSATION FLOW GUIDANCE
        # ========================================================================
        # These rules guide the conversation flow to collect necessary information
        # for processing policy renewals in the correct sequence.

        # RULE 6: REQUEST POLICY NUMBER - Information Gathering
        # First step in the renewal process - must collect policy number to proceed
        # Only triggers for explicit renovation intent to avoid being too aggressive
        if state.get("current_intent") == "RenovatePolicy" and \
           not state.get("entities", {}).get("POLICY_NUMBER"):
            print("Rule Fired: Ask for Policy Number")
            return {
                "action_type": "ask_for_info",
                "message": "Para renovar su póliza, por favor, proporcione su número de póliza.",
                "message_to_customer": "Para renovar su póliza, por favor, proporcione su número de póliza."
            }

        # RULE 7: REQUEST VEHICLE DETAILS - Information Gathering (Renovation Flow)
        # Second step in renovation - collect vehicle information for accurate quoting
        # Triggers after policy number is provided but vehicle details are missing
        if state.get("current_intent") == "RenovatePolicy" and \
           state.get("entities", {}).get("POLICY_NUMBER") and \
           not (state.get("entities", {}).get("VEHICLE_MAKE") and 
                state.get("entities", {}).get("VEHICLE_MODEL")):
            print("Rule Fired: Ask for Vehicle Details")
            return {
                "action_type": "ask_for_info",
                "message": "¡Excelente! Ahora, ¿podría indicarme la marca, modelo y año de su vehículo?",
                "message_to_customer": "¡Excelente! Ahora, ¿podría indicarme la marca, modelo y año de su vehículo?"
            }

        # RULE 7B: REQUEST VEHICLE DETAILS - Information Gathering (Policy Query Flow)
        # Handles cases where customer provides policy number but NLP classifies as general query
        # Converts policy queries into renovation opportunities when appropriate
        if state.get("current_intent") == "QueryPolicyDetails" and \
           state.get("entities", {}).get("POLICY_NUMBER") and \
           not (state.get("entities", {}).get("VEHICLE_MAKE") and 
                state.get("entities", {}).get("VEHICLE_MODEL")) and \
           not any(keyword in state.get("conversation_summary", "").lower() for keyword in ["reportar", "valida", "garantia"]):
            print("Rule Fired: Ask for Vehicle Details (QueryPolicyDetails flow)")
            return {
                "action_type": "ask_for_info",
                "message": "Gracias por el número de póliza. Para continuar con su renovación, ¿podría indicarme la marca, modelo y año de su vehículo?",
                "message_to_customer": "Gracias por el número de póliza. Para continuar con su renovación, ¿podría indicarme la marca, modelo y año de su vehículo?"
            }
        
        # RULE 7C: ACKNOWLEDGE VEHICLE INFO - Conversation Flow Transition
        # Responds when customer provides vehicle information, moving conversation forward
        # This rule fills a gap in the conversation flow for better user experience
        if self._has_vehicle_info_in_entities(state.get("entities", {})) and \
           self._has_policy_number_in_state(state) and \
           not state.get("quote_provided", False):
            state["quote_provided"] = True # Mark quote as provided to prevent loops
            print("Rule Fired: Generate Quote After Vehicle Info Provided")
            return {
                "action_type": "generate_quote",
                "message": "Perfecto. Con la información de su póliza y vehículo, le generaré una cotización para la renovación.",
                "message_to_customer": "Perfecto. Con la información de su póliza y vehículo, le generaré una cotización para la renovación."
            }
        
        # RULE 8: GENERATE QUOTE - Business Process Completion
        # Final step when all required information is collected
        # Triggers quote generation process and prepares for human handoff
        if (state.get("current_intent") in ["RenovatePolicy", "QueryPolicyDetails"]) and \
           state.get("entities", {}).get("POLICY_NUMBER") and \
           state.get("entities", {}).get("VEHICLE_MAKE") and \
           state.get("entities", {}).get("VEHICLE_MODEL") and \
           not state.get("quote_provided", False): # Ensure quote hasn't been provided yet
            # In production, this would trigger an external quote generation API
            # For MVP, we simulate the quote generation process
            state["quote_provided"] = True # Mark quote as provided in state
            print("Rule Fired: Ready for Quote Generation")
            return {
                "action_type": "generate_quote",
                "message": "¡Perfecto! Con esta información, puedo generar una cotización para su renovación. Por favor, espere un momento.",
                "message_to_customer": "¡Perfecto! Con esta información, puedo generar una cotización para su renovación. Por favor, espere un momento."
            }

        # ========================================================================
        # LOW PRIORITY RULES - GENERAL FALLBACK RESPONSES
        # ========================================================================
        # These rules handle general interactions that don't require specific
        # business logic but still need appropriate responses.

        # RULE 9: GREETING RESPONSE - Customer Experience
        # Provides a warm, branded greeting that sets the tone for the interaction
        # Immediately explains BRAIN's purpose and invites engagement
        if state.get("current_intent") == "Greeting":
            print("Rule Fired: General Greeting")
            return {
                "action_type": "greet",
                "message": "¡Hola! Soy tu asistente de GarantiPLUS. ¿En qué puedo ayudarte hoy con la renovación de tu garantía extendida?",
                "message_to_customer": "¡Hola! Soy tu asistente de GarantiPLUS. ¿En qué puedo ayudarte hoy con la renovación de tu garantía extendida?"
            }

        # RULE 10: SUPPORT REQUEST - Human Escalation
        # Provides contact information for complex issues that require human assistance
        # Ensures customers can always reach human support when BRAIN cannot help
        if state.get("current_intent") == "RequestSupport":
            print("Rule Fired: Request Support")
            return {
                "action_type": "escalate_to_human",
                "message": "Entiendo que necesitas ayuda. Por favor, comunícate con nuestro centro de atención al cliente al 800 garanti (4272684) o por WhatsApp al 4432441212 para asistencia personalizada.",
                "message_to_customer": "Entiendo que necesitas ayuda. Por favor, comunícate con nuestro centro de atención al cliente al 800 garanti (4272684) o por WhatsApp al 4432441212 para asistencia personalizada."
            }

        # ========================================================================
        # NO RULE MATCHED - POLICY MODULE FALLBACK
        # ========================================================================
        # If no explicit rule matches, return None to trigger the policy module
        # This allows for learned behaviors and edge case handling
        print("No rule fired. Deferring to Policy Module.")
        return None

    def _has_vehicle_info_in_entities(self, entities: dict) -> bool:
        """
        Check if vehicle information is present in entities.
        
        This helper method handles the dual entity format that can result from
        different processing paths (LLM vs fallback processing).
        
        Args:
            entities: Dictionary of extracted entities
            
        Returns:
            bool: True if both vehicle make and model are present
        """
        # Check uppercase format (typically from LLM processing)
        has_uppercase = ('VEHICLE_MAKE' in entities and 'VEHICLE_MODEL' in entities)
        
        # Check lowercase format (typically from fallback processing)
        has_lowercase = ('vehicle_make' in entities and 'vehicle_model' in entities)
        
        return has_uppercase or has_lowercase

    def _has_policy_number_in_state(self, state: dict) -> bool:
        """
        Check if policy number exists anywhere in the conversation state.
        
        This method provides comprehensive policy number detection by checking:
        1. Current entities (both uppercase and lowercase formats)
        2. Conversation history (in case it was mentioned in previous turns)
        
        Args:
            state: Complete conversation state dictionary
            
        Returns:
            bool: True if policy number is found anywhere in the state
        """
        entities = state.get("entities", {})
        
        # Check in current entities (both formats from different processing methods)
        if 'POLICY_NUMBER' in entities or 'policy_number' in entities:
            return True
            
        # Check conversation history for policy number patterns
        # This catches cases where policy number was mentioned earlier but not
        # carried forward in current entity extraction
        conversation_summary = state.get("conversation_summary", "").upper()
        policy_pattern = r'\b[A-Z]{2,4}\d{5,8}\b'  # Standard policy number format
        import re
        if re.search(policy_pattern, conversation_summary):
            return True
            
        return False