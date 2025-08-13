# rule_engine.py
"""
BRAIN Rule Engine - Conversational + Business Policy (π_R)
==========================================================

Fixed Issues:
- Better state transitions to prevent loops
- More precise intent handling with context awareness
- Proper action selection based on (processed_percept, current_state) → action
- Enhanced flow control with step gates
- Defensive state tracking with better memory management

Mathematical Model: A(p', m) → (action, new_state)
Where:
- p' = processed percept (NLP output)
- m = current memory/state
- A = action space
- Returns tuple of (action, updated_state)
"""

from __future__ import annotations
from typing import Optional, Dict, Any
import unicodedata

# ---------------------------
# Normalization & constants
# ---------------------------

def _norm(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn")

EXPIRED_TOKENS = {
    "vencio","vencida","vencido","vencimiento","expirada","expirado","expiro","expirio",
    "caduca","caducada","caducado","caducidad","pasada","ya paso","se me paso","ya vencio","ya expiro"
}
PRICE_TOKENS = {"precio","costo","cuanto","cuánto","cotizacion","cotización","cotizar","quote"}
PAY_TOKENS   = {"pago","financiamiento","msi","formas de pago","como pagar","promociones","pagos"}
CLAIM_TOKENS = {"reportar","reclamar","claim","garantia","garantía","hacer valida","hacer válida","valida","válida"}

PRICING_TEXT = (
    "Precios de renovación de Garantía Extendida:\n"
    "- 12 meses: $9,900.00\n"
    "- 24 meses: $14,900.00\n"
    "- 36 meses: $21,900.00\n"
    "- 48 meses: $28,900.00\n\n"
    "¿Cuál le interesa (12, 24, 36 o 48)?"
)

# ---------------------------
# State Management Helpers
# ---------------------------

def _coerce_bool(v: Any) -> bool:
    if isinstance(v, bool): return v
    if isinstance(v, int):  return v != 0
    if isinstance(v, str):  return v.strip().lower() in {"true","1","yes","si","sí"}
    return bool(v)

def _get_conversation_phase(state: Dict[str, Any]) -> str:
    """Determine current conversation phase to prevent loops"""
    if state.get("conversation_ended"): 
        return "ended"
    if state.get("lead_generation_complete"): 
        return "completed"
    
    context = state.get("context", "")
    if context == "expired_policy_flow":
        if not _has_expiry_info({}, state) or not _services_ok(state, {}):
            return "expired_verification"
        return "expired_data_collection"
    elif context == "expired_data_collection":
        return "expired_data_collection"
    elif context == "pricing_flow":
        if state.get("pricing_confirmed"):
            return "post_pricing_collection"
        return "pricing_discussion"
    
    if state.get("last_action_type") in {"ask_for_policy_number", "ask_for_vehicle_info", "request_contact_info"}:
        return "data_collection"
    return "initial"

def _in_data_collection(state: Dict[str, Any]) -> bool:
    phase = _get_conversation_phase(state)
    return phase in {"data_collection", "expired_data_collection", "post_pricing_collection"}

def _expired_flag(summary_norm: str, nlp_flags: Dict[str, Any]) -> bool:
    if nlp_flags and nlp_flags.get("expired"): return True
    return any(tok in summary_norm for tok in EXPIRED_TOKENS)

def _services_ok(state: Dict[str, Any], nlp_flags: Dict[str, Any]) -> bool:
    # Check state flag first
    if _coerce_bool(state.get("services_up_to_date")):
        return True
    
    # Check NLP flags
    if nlp_flags and _coerce_bool(nlp_flags.get("services_ok")):
        return True
    
    # If we're waiting for services confirmation and got "si", mark as ok
    if state.get("waiting_for") == "services_status":
        summary = state.get("conversation_summary", "").lower()
        last_words = summary.split()[-5:]  # Check last few words
        if any(word in ["si", "sí", "yes"] for word in last_words):
            return True
    
    return False

def _has_expiry_info(entities: Dict[str, Any], state: Dict[str, Any]) -> bool:
    return bool(entities.get("EXPIRY_DAYS") or entities.get("EXPIRY_DATE") or state.get("expiry_captured"))

def _ready_to_notify(entities: Dict[str, Any], state: Dict[str, Any]) -> bool:
    has_policy = bool(entities.get("POLICY_NUMBER"))
    has_contact = bool(entities.get("CUSTOMER_NAME") or entities.get("EMAIL") or entities.get("PHONE_NUMBER"))
    not_notified = not _coerce_bool(state.get("renovation_lead_notified"))
    return has_policy and has_contact and not_notified

def _get_missing_info(entities: Dict[str, Any], state: Dict[str, Any]) -> str:
    """Return what information is still needed"""
    if not entities.get("POLICY_NUMBER"):
        return "policy_number"
    if not (entities.get("VEHICLE_MAKE") and entities.get("VEHICLE_MODEL")):
        return "vehicle_info"
    if not (entities.get("CUSTOMER_NAME") or entities.get("EMAIL") or entities.get("PHONE_NUMBER")):
        return "contact_info"
    return "complete"

def _build_lead_notification(state: Dict[str, Any], entities: Dict[str, Any]) -> Dict[str, Any]:
    customer_name = entities.get("CUSTOMER_NAME", "Usuario")
    policy_number = entities.get("POLICY_NUMBER", "No Proporcionada")
    email = entities.get("EMAIL", "No Proporcionado")
    phone_number = entities.get("PHONE_NUMBER", "No Proporcionado")
    vin = entities.get("VIN", "No Proporcionado")
    vehicle_make = entities.get("VEHICLE_MAKE", "")
    vehicle_model = entities.get("VEHICLE_MODEL", "")
    vehicle_year = entities.get("VEHICLE_YEAR", "")
    auto_info = " ".join([p for p in [vehicle_make, vehicle_model, vehicle_year] if p]) or "No Proporcionado"
    return {
        "action_type": "notify_human_renovation_lead",
        "message_to_customer": (
            f"Perfecto, {customer_name}. Tengo toda la información necesaria. "
            "Un agente especializado se pondrá en contacto con usted muy pronto para finalizar su renovación."
        ),
        "notification_data": {
            "customer_name": customer_name,
            "policy_number": policy_number,
            "email": email,
            "phone_whatsapp": phone_number,
            "vin": vin,
            "auto": auto_info,
            "interest": "renovación de garantía extendida",
            "conversation_summary": state.get("conversation_summary", ""),
            "lead_quality": "high",
            "timestamp": state.get("timestamp"),
        },
        "business_outcome": "lead_generated",
    }

def _update_state_and_return(state: Dict[str, Any], action: Dict[str, Any], new_context: Optional[str] = None) -> Dict[str, Any]:
    """Update state and return action - implements A(p', m) → (action, new_state)"""
    if "action_type" in action:
        state["last_action_type"] = action["action_type"]
        state["last_action_turn"] = state.get("conversation_turn", 0)
    
    if new_context:
        state["context"] = new_context
    
    # Set prompt for data collection continuity
    if action.get("information_requested"):
        state["last_prompt"] = action.get("message_to_customer", "")
        state["waiting_for"] = action.get("information_requested")
    
    return action

# ---------------------------
# Enhanced Intent Classification
# ---------------------------

def _classify_intent_with_context(current_intent: str, entities: Dict[str, Any], 
                                state: Dict[str, Any], summary_norm: str) -> str:
    """More precise intent classification based on context"""
    
    # If we're waiting for specific info, classify accordingly
    waiting_for = state.get("waiting_for")
    if waiting_for and current_intent in {"Unknown", "ProvideVehicleInfo", "ProvideContactInfo", "QueryPolicyDetails"}:
        if waiting_for == "policy_number" and entities.get("POLICY_NUMBER"):
            return "QueryPolicyDetails"
        elif waiting_for == "vehicle_details" and (entities.get("VEHICLE_MAKE") or entities.get("VEHICLE_MODEL")):
            return "ProvideVehicleInfo"
        elif waiting_for == "contact_info" and (entities.get("CUSTOMER_NAME") or entities.get("EMAIL") or entities.get("PHONE_NUMBER")):
            return "ProvideContactInfo"
        elif waiting_for in {"expiry_date", "services_status"}:
            return "ExpiredPolicy"
    
    # Context-aware intent refinement
    phase = _get_conversation_phase(state)
    
    if phase == "pricing_discussion":
        if current_intent == "Unknown" and entities.get("PLAN_SELECTION"):
            return "ConfirmRenovation"
        elif current_intent in {"GetQuote", "RenovatePolicy"}:
            return "ConfirmRenovation"  # They already have pricing
    
    if phase == "data_collection" and current_intent == "Unknown":
        missing = _get_missing_info(entities, state)
        if missing == "policy_number" and entities.get("POLICY_NUMBER"):
            return "QueryPolicyDetails"
        elif missing == "vehicle_info" and (entities.get("VEHICLE_MAKE") or entities.get("VEHICLE_MODEL")):
            return "ProvideVehicleInfo"
        elif missing == "contact_info" and (entities.get("CUSTOMER_NAME") or entities.get("EMAIL") or entities.get("PHONE_NUMBER")):
            return "ProvideContactInfo"
    
    # Detect expired policy intent from keywords even if not classified
    if current_intent in {"Unknown", "QueryPolicyDetails"} and _expired_flag(summary_norm, {}):
        return "ExpiredPolicy"
    
    return current_intent

# ---------------------------
# Rule Engine
# ---------------------------

class RuleEngine:
    def __init__(self):
        print("Rule Engine initialized with enhanced state management.")

    def evaluate_rules(self, state: dict) -> Optional[dict]:
        """
        Mathematical Model: A(p', m) → (action, new_state)
        Where p' = processed percept, m = current memory state
        """
        
        # ---- NORMALIZE STATE (ensure proper types) -------------------------
        for f in ("pricing_provided","pricing_confirmed","renovation_lead_notified",
                  "vehicle_info_acknowledged","plan_selected","conversation_ended",
                  "lead_generation_complete","expiry_captured","services_up_to_date"):
            state[f] = _coerce_bool(state.get(f))

        # ---- EXTRACT PERCEPT DATA (p') ------------------------------------
        current_intent = state.get("current_intent", "Unknown") or "Unknown"
        entities = state.get("entities", {}) or {}
        raw_summary = state.get("conversation_summary", "") or ""
        summary_norm = _norm(raw_summary)
        nlp_flags = state.get("nlp_flags", {}) or {}
        
        # ---- STATE MANAGEMENT (m) -----------------------------------------
        state["conversation_turn"] = int(state.get("conversation_turn", 0)) + 1
        phase = _get_conversation_phase(state)
        
        # Enhanced intent classification with context
        refined_intent = _classify_intent_with_context(current_intent, entities, state, summary_norm)
        
        print(f"RULE DEBUG: turn={state['conversation_turn']}, phase={phase}, "
              f"intent={current_intent}→{refined_intent}, "
              f"entities={list(entities.keys())}, "
              f"waiting_for={state.get('waiting_for')}")

        # ---- TERMINAL STATES (prevent loops) ------------------------------
        
        if phase == "ended":
            return None  # Don't process further
        
        if phase == "completed":
            if refined_intent in {"ThankYou", "Bye"}:
                return _update_state_and_return(state, {
                    "action_type": "end_conversation_after_completion",
                    "message_to_customer": "¡Ha sido un placer ayudarle! ¡Que tenga excelente día!"
                })
            return None  # Conversation already complete

        # ---- CRITICAL: HUMAN NOTIFICATION (highest priority) -------------
        
        if _ready_to_notify(entities, state) and not state.get("renovation_lead_notified"):
            state["renovation_lead_notified"] = True
            state["lead_generation_complete"] = True
            return _update_state_and_return(state, _build_lead_notification(state, entities), "completed")

        # ---- CONVERSATIONAL INTENTS (flow-aware) -------------------------

        if refined_intent == "Bye":
            state["conversation_ended"] = True
            if entities.get("POLICY_NUMBER") or entities.get("CUSTOMER_NAME"):
                return _update_state_and_return(state, {
                    "action_type": "end_conversation_with_followup",
                    "message_to_customer": (
                        "¡Hasta pronto! Tengo guardada su información para cuando desee continuar "
                        "con la renovación. No dude en contactarnos cuando guste. ¡Que tenga buen día!"
                    ),
                    "conversation_status": "ended_by_user_with_data",
                    "data_preserved": True
                }, "ended")
            else:
                return _update_state_and_return(state, {
                    "action_type": "end_conversation",
                    "message_to_customer": (
                        "¡Hasta pronto! Si necesita ayuda con la renovación de su garantía extendida "
                        "en el futuro, estaré aquí para ayudarle. ¡Que tenga buen día!"
                    ),
                    "conversation_status": "ended_by_user"
                }, "ended")

        if refined_intent == "ThankYou":
            if phase == "completed":
                state["conversation_ended"] = True
                return _update_state_and_return(state, {
                    "action_type": "end_conversation_after_thanks",
                    "message_to_customer": (
                        "¡De nada! Ha sido un placer ayudarle. Un agente se pondrá en contacto "
                        "con usted muy pronto. ¡Que tenga excelente día!"
                    ),
                    "conversation_status": "ended_after_service_completion"
                }, "ended")
            elif _in_data_collection(state):
                prompt = state.get("last_prompt") or "Para continuar, ¿cuál es su número de póliza?"
                return _update_state_and_return(state, {
                    "action_type": state.get("last_action_type") or "ask_for_policy_number", 
                    "message_to_customer": f"¡De nada! {prompt}",
                    "thanks_acknowledged": True
                })
            else:
                return _update_state_and_return(state, {
                    "action_type": "acknowledge_thanks",
                    "message_to_customer": (
                        "¡De nada! Estoy aquí para ayudarle con la renovación de su garantía extendida. "
                        "¿En qué más le puedo asistir?"
                    ),
                    "thanks_acknowledged": True
                })

        if refined_intent == "Disagreement":
            state["conversation_ended"] = True
            return _update_state_and_return(state, {
                "action_type": "end_conversation",
                "message_to_customer": (
                    "Entiendo. Si cambia de opinión sobre la renovación de su garantía, "
                    "estaré aquí para ayudarle. ¡Que tenga buen día!"
                ),
                "conversation_status": "ended_by_user"
            }, "ended")

        if refined_intent == "CancelRenovation":
            state["conversation_ended"] = True
            return _update_state_and_return(state, {
                "action_type": "cancel_process",
                "message_to_customer": (
                    "Entiendo que desea cancelar el proceso de renovación. El proceso ha sido cancelado. "
                    "Si necesita ayuda en el futuro, no dude en contactarnos."
                ),
                "cancellation_reason": "user_request"
            }, "ended")

        if refined_intent == "Greeting":
            # Reset state for fresh start but preserve conversation history
            reset_keys = [
                "renovation_lead_notified","lead_generation_complete",
                "vehicle_info_acknowledged","pricing_provided","pricing_confirmed",
                "plan_selected","last_action_type","last_prompt","waiting_for",
                "services_up_to_date","expiry_captured","expiry_days","expiry_date"
            ]
            for k in reset_keys:
                if k in state:
                    if isinstance(state[k], bool): 
                        state[k] = False
                    else: 
                        state[k] = ""
            
            return _update_state_and_return(state, {
                "action_type": "greet_and_offer_service",
                "message_to_customer": (
                    "¡Hola! Soy su asistente de GarantiPLUS para renovaciones de garantía extendida. "
                    "¿Le ayudo con la renovación de su garantía?"
                ),
                "greeting_provided": True,
                "service_offered": True
            }, "initial")

        # ---- EXPIRED POLICY FLOW (stepwise, no loops) --------------------

        if refined_intent == "ExpiredPolicy" or _expired_flag(summary_norm, nlp_flags) or phase in ["expired_verification", "expired_data_collection"]:
            # Set context first
            if not state.get("context"):
                state["context"] = "expired_policy_flow"
            
            # Capture NLP signals and user confirmations
            if nlp_flags.get("services_ok"): 
                state["services_up_to_date"] = True
            
            # Handle "si" response when waiting for services confirmation
            if (state.get("waiting_for") == "services_status" and 
                (refined_intent == "ConfirmRenovation" or "si" in summary_norm.split() or "sí" in summary_norm.split())):
                state["services_up_to_date"] = True
                state["waiting_for"] = ""  # Clear waiting state
            
            if entities.get("EXPIRY_DAYS") is not None or entities.get("EXPIRY_DATE"):
                state["expiry_captured"] = True
                state["expiry_days"] = entities.get("EXPIRY_DAYS")
                state["expiry_date"] = entities.get("EXPIRY_DATE")
                if state.get("waiting_for") == "expiry_date":
                    state["waiting_for"] = ""  # Clear waiting state

            # Step 1: Expiry date verification
            if not _has_expiry_info(entities, state) and state.get("waiting_for") != "services_status":
                return _update_state_and_return(state, {
                    "action_type": "ask_expiry_date",
                    "message_to_customer": (
                        "Entiendo que su garantía ya venció. Para ayudarle con la renovación, "
                        "¿en qué fecha exacta venció? (por ejemplo, 2025-08-11 o 'ayer')"
                    ),
                    "information_requested": "expiry_date"
                }, "expired_policy_flow")
            
            # Step 2: Services verification (only if not already confirmed)
            if not _services_ok(state, nlp_flags) and state.get("waiting_for") != "expiry_date":
                return _update_state_and_return(state, {
                    "action_type": "ask_services_status",
                    "message_to_customer": (
                        "Perfecto. Para proceder con la renovación de una garantía vencida, "
                        "¿tiene los servicios de mantenimiento al día?"
                    ),
                    "information_requested": "services_status"
                }, "expired_policy_flow")

            # Step 3: Proceed to normal data collection (both conditions met)
            if _has_expiry_info(entities, state) and _services_ok(state, nlp_flags):
                state["context"] = "expired_data_collection"  # Update phase
                missing = _get_missing_info(entities, state)
                
                if missing == "policy_number":
                    return _update_state_and_return(state, {
                        "action_type": "ask_for_policy_number",
                        "message_to_customer": (
                            "Excelente, podemos proceder con la renovación. "
                            "¿Cuál es su número de póliza?"
                        ),
                        "information_requested": "policy_number"
                    }, "expired_data_collection")
                elif missing == "vehicle_info":
                    return _update_state_and_return(state, {
                        "action_type": "ask_for_vehicle_info",
                        "message_to_customer": "Gracias. Ahora, ¿cuál es la marca, modelo y año de su vehículo?",
                        "information_requested": "vehicle_details"
                    }, "expired_data_collection")
                elif missing == "contact_info":
                    return _update_state_and_return(state, {
                        "action_type": "request_contact_info",
                        "message_to_customer": "Perfecto. Para finalizar, ¿cuál es su nombre completo y teléfono?",
                        "information_requested": "contact_info"
                    }, "expired_data_collection")

        # ---- PRICING FLOW (prevent re-pricing loops) ---------------------

        if phase == "pricing_discussion":
            # Plan selection after pricing
            if entities.get("PLAN_SELECTION") and not state.get("plan_selected"):
                sel = entities.get("PLAN_SELECTION")
                state["plan_selected"] = True
                return _update_state_and_return(state, {
                    "action_type": "request_contact_info",
                    "message_to_customer": (
                        f"¡Excelente elección! La cobertura de {sel} meses es una gran opción. "
                        "Para continuar con su cotización y que un agente se ponga en contacto, "
                        "¿cuál es su nombre completo y teléfono?"
                    ),
                    "information_requested": "contact_info",
                    "plan_selected": sel
                }, "post_pricing_collection")
            
            # Confirmation to move forward
            if refined_intent == "ConfirmRenovation" and not state.get("pricing_confirmed"):
                state["pricing_confirmed"] = True
                return _update_state_and_return(state, {
                    "action_type": "request_contact_info",
                    "message_to_customer": (
                        "¡Perfecto! Para continuar con su cotización y que un agente se ponga en contacto, "
                        "¿cuál es su nombre completo y teléfono?"
                    ),
                    "information_requested": "contact_info"
                }, "post_pricing_collection")

        # ---- CLARIFICATION HANDLERS (context-aware) ----------------------

        if refined_intent == "Confusion":
            if _in_data_collection(state):
                prompt = state.get("last_prompt") or "Para continuar, ¿cuál es su número de póliza?"
                return _update_state_and_return(state, {
                    "action_type": state.get("last_action_type") or "ask_for_policy_number",
                    "message_to_customer": f"No se preocupe. {prompt}",
                    "clarification_provided": True
                })
            else:
                return _update_state_and_return(state, {
                    "action_type": "explain",
                    "message_to_customer": (
                        "Soy su asistente para renovar garantías extendidas de autos. "
                        "¿Le puedo ayudar con la renovación de su garantía?"
                    ),
                    "explanation_provided": True
                })

        if refined_intent == "AskForClarification":
            if phase == "pricing_discussion":
                return _update_state_and_return(state, {
                    "action_type": "clarify_pricing_options",
                    "message_to_customer": (
                        "Tenemos 4 coberturas: 12, 24, 36 y 48 meses. "
                        "La de 12 meses cuesta $9,900.00, la de 24 meses $14,900.00, "
                        "la de 36 meses $21,900.00 y la de 48 meses $28,900.00. "
                        "¿Cuál prefiere?"
                    )
                })
            elif _in_data_collection(state):
                prompt = state.get("last_prompt") or "Para continuar, ¿cuál es su número de póliza?"
                return _update_state_and_return(state, {
                    "action_type": state.get("last_action_type") or "ask_for_policy_number",
                    "message_to_customer": f"Con gusto le explico. {prompt}",
                    "detailed_explanation": True
                })
            else:
                return _update_state_and_return(state, {
                    "action_type": "explain",
                    "message_to_customer": (
                        "La renovación de garantía extendida protege su auto contra fallas mecánicas. "
                        "Necesito algunos datos para generar una cotización. ¿Le interesa?"
                    ),
                    "product_explanation": True
                })

        # ---- BUSINESS FLOW: INFORMATION GATHERING (step-by-step) ----------

        # Start renovation process
        if refined_intent == "RenovatePolicy":
            missing = _get_missing_info(entities, state)
            if missing == "policy_number":
                return _update_state_and_return(state, {
                    "action_type": "ask_for_policy_number",
                    "message_to_customer": "Perfecto, le ayudo con la renovación de su garantía. Para comenzar, ¿cuál es su número de póliza?",
                    "information_requested": "policy_number"
                }, "data_collection")
            elif missing == "vehicle_info":
                policy = entities.get("POLICY_NUMBER")
                return _update_state_and_return(state, {
                    "action_type": "ask_for_vehicle_info",
                    "message_to_customer": f"Excelente, tengo su póliza {policy}. Ahora necesito los datos de su vehículo: ¿cuál es la marca, modelo y año?",
                    "information_requested": "vehicle_details"
                }, "data_collection")
            elif missing == "contact_info":
                return _update_state_and_return(state, {
                    "action_type": "request_contact_info",
                    "message_to_customer": "Perfecto. Para finalizar y que un agente se ponga en contacto con usted, ¿cuál es su nombre completo?",
                    "information_requested": "contact_info"
                }, "data_collection")

        # Handle specific data provision
        if refined_intent == "QueryPolicyDetails" and entities.get("POLICY_NUMBER"):
            missing = _get_missing_info(entities, state)
            if missing == "vehicle_info":
                policy = entities.get("POLICY_NUMBER")
                return _update_state_and_return(state, {
                    "action_type": "ask_for_vehicle_info",
                    "message_to_customer": f"Excelente, tengo su póliza {policy}. Ahora necesito los datos de su vehículo: ¿cuál es la marca, modelo y año?",
                    "information_requested": "vehicle_details",
                    "policy_acknowledged": True
                }, "data_collection")

        if refined_intent == "ProvideVehicleInfo" and (entities.get("VEHICLE_MAKE") or entities.get("VEHICLE_MODEL")):
            if not state.get("vehicle_info_acknowledged"):
                state["vehicle_info_acknowledged"] = True
                parts = [entities.get("VEHICLE_MAKE",""), entities.get("VEHICLE_MODEL",""), entities.get("VEHICLE_YEAR","")]
                vehicle_description = " ".join([p for p in parts if p]).strip() or "su vehículo"
                
                missing = _get_missing_info(entities, state)
                if missing == "contact_info":
                    return _update_state_and_return(state, {
                        "action_type": "request_contact_info",
                        "message_to_customer": f"Perfecto, {vehicle_description}. Para finalizar y que un agente se ponga en contacto con usted, ¿cuál es su nombre completo?",
                        "information_requested": "customer_name",
                        "vehicle_acknowledged": True
                    }, "data_collection")

        if refined_intent == "ProvideContactInfo":
            # Contact provided - check if ready to notify
            if _ready_to_notify(entities, state):
                state["renovation_lead_notified"] = True
                state["lead_generation_complete"] = True
                return _update_state_and_return(state, _build_lead_notification(state, entities), "completed")

        # Confirmation handler (collect missing data)
        if refined_intent == "ConfirmRenovation":
            if phase not in {"pricing_discussion", "post_pricing_collection"}:
                missing = _get_missing_info(entities, state)
                if missing == "policy_number":
                    return _update_state_and_return(state, {
                        "action_type": "ask_for_policy_number",
                        "message_to_customer": "Excelente. ¿Cuál es su número de póliza para proceder con la renovación?",
                        "confirmation_received": True,
                        "information_requested": "policy_number"
                    }, "data_collection")
                elif missing == "vehicle_info":
                    return _update_state_and_return(state, {
                        "action_type": "ask_for_vehicle_info",
                        "message_to_customer": "Perfecto. ¿Podría proporcionarme la marca, modelo y año de su vehículo?",
                        "confirmation_received": True,
                        "information_requested": "vehicle_details"
                    }, "data_collection")
                elif missing == "contact_info":
                    return _update_state_and_return(state, {
                        "action_type": "request_contact_info",
                        "message_to_customer": "Excelente. Para finalizar, ¿cuál es su nombre completo o un número de contacto?",
                        "confirmation_received": True,
                        "information_requested": "contact_info"
                    }, "data_collection")

        # ---- FAQS AND INFORMATION REQUESTS (only when not collecting) ----

        # Payment info
        wants_pay = any(tok in summary_norm for tok in PAY_TOKENS)
        if wants_pay and not _in_data_collection(state):
            return _update_state_and_return(state, {
                "action_type": "provide_payment_info",
                "message_to_customer": (
                    "Las opciones de pago disponibles son:\n\n"
                    "• Tarjeta de crédito o débito\n"
                    "• Transferencia bancaria\n"
                    "• Promoción: hasta 12 Meses Sin Intereses (MSI)\n\n"
                    "¿Cuál prefiere?"
                ),
                "payment_info_provided": True
            })

        # Pricing: only once, never while collecting other info
        wants_price = (refined_intent == "GetQuote") or any(tok in summary_norm for tok in PRICE_TOKENS)
        if wants_price and not state.get("pricing_provided") and not state.get("pricing_confirmed") \
           and not _in_data_collection(state) and phase != "pricing_discussion":
            state["pricing_provided"] = True
            return _update_state_and_return(state, {
                "action_type": "provide_pricing_info",
                "message_to_customer": PRICING_TEXT,
                "pricing_provided": True
            }, "pricing_flow")

        # Claims / hacer válida
        wants_claim = any(tok in summary_norm for tok in CLAIM_TOKENS)
        if (refined_intent == "QueryPolicyDetails" and wants_claim) or any(k in summary_norm for k in ["reportar","hacer valida","reclamacion","reclamación"]):
            return _update_state_and_return(state, {
                "action_type": "provide_claims_info",
                "message_to_customer": (
                    "Para hacer válida su garantía o reportar un problema:\n\n"
                    "Call Center: 800 GARANTI (4272684)\n"
                    "WhatsApp: 4432441212\n\n"
                    "Nuestro equipo de atención está disponible para ayudarle con cualquier reclamo."
                ),
                "claims_info_provided": True
            })

        # ---- INTELLIGENT UNKNOWN HANDLING (context-aware) ----------------

        if refined_intent == "Unknown":
            # Smart interpretation based on provided entities
            if entities.get("POLICY_NUMBER") and not entities.get("VEHICLE_MAKE"):
                return _update_state_and_return(state, {
                    "action_type": "ask_for_vehicle_info",
                    "message_to_customer": f"Veo que me proporcionó el número de póliza {entities.get('POLICY_NUMBER')}. Para ayudarle con la renovación, ¿cuál es la marca, modelo y año de su vehículo?",
                    "intelligent_interpretation": True,
                    "information_requested": "vehicle_details"
                }, "data_collection")
            
            elif (entities.get("VEHICLE_MAKE") or entities.get("VEHICLE_MODEL")) and not entities.get("POLICY_NUMBER"):
                return _update_state_and_return(state, {
                    "action_type": "ask_for_policy_number",
                    "message_to_customer": "Veo que me proporcionó información del vehículo. Para la renovación de garantía, también necesito su número de póliza. ¿Cuál es?",
                    "intelligent_interpretation": True,
                    "information_requested": "policy_number"
                }, "data_collection")
            
            elif entities.get("CUSTOMER_NAME") or entities.get("EMAIL") or entities.get("PHONE_NUMBER"):
                # Contact provided but unclear intent
                missing = _get_missing_info(entities, state)
                if missing == "policy_number":
                    return _update_state_and_return(state, {
                        "action_type": "ask_for_policy_number",
                        "message_to_customer": "Gracias por su información de contacto. Para ayudarle con la renovación, ¿cuál es su número de póliza?",
                        "information_requested": "policy_number"
                    }, "data_collection")
                elif missing == "vehicle_info":
                    return _update_state_and_return(state, {
                        "action_type": "ask_for_vehicle_info",
                        "message_to_customer": "Perfecto. Ahora necesito los datos de su vehículo: ¿cuál es la marca, modelo y año?",
                        "information_requested": "vehicle_details"
                    }, "data_collection")
            
            # No clear entities - general clarification
            return _update_state_and_return(state, {
                "action_type": "clarify_intent",
                "message_to_customer": (
                    "Soy especialista en renovaciones de garantía extendida. "
                    "¿Le interesa renovar su garantía o necesita información sobre nuestros servicios?"
                ),
                "clarification_requested": True
            })

        # ---- FALLBACK TO POLICY MODULE ------------------------------------
        print(f"No rule matched for intent={refined_intent}, phase={phase} - Deferring to Policy Module")
        return None