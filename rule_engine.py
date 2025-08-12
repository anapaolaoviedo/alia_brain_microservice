# rule_engine.py
"""
BRAIN Rule Engine - Conversational + Business Policy (π_R)
==========================================================

Highlights
- Flow engine that advances, never repeats (expired/pricing/data collection)
- Accent-insensitive checks, robust synonyms
- Explicit step gates for expired policy (date + services) before proceeding
- Pricing loop prevention + plan selection (12/24/36/48)
- Flow-aware conversational rules (won't derail with Confusion/Clarification)
- Defensive state tracking: last_action_type, last_prompt, context, turn
- Clean human-notification trigger when info is sufficient
- Works with the corrected nlp_pipeline (UPPERCASE entities + flags)

Return shape:
    dict with keys like: action_type, message_to_customer, ... (plus any metadata)
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
# Helpers
# ---------------------------

def _coerce_bool(v: Any) -> bool:
    if isinstance(v, bool): return v
    if isinstance(v, int):  return v != 0
    if isinstance(v, str):  return v.strip().lower() in {"true","1","yes","si","sí"}
    return bool(v)

def _in_data_collection(state: Dict[str, Any]) -> bool:
    return (state.get("last_action_type") in {
        "ask_for_policy_number","ask_for_vehicle_info","request_contact_info",
        "ask_expiry_date","ask_services_status"
    } or state.get("context") in {"expired_policy_flow","pricing_flow","data_collection"})

def _expired_flag(summary_norm: str, nlp_flags: Dict[str, Any]) -> bool:
    if nlp_flags and nlp_flags.get("expired"): return True
    return any(tok in summary_norm for tok in EXPIRED_TOKENS)

def _services_ok(state: Dict[str, Any], nlp_flags: Dict[str, Any]) -> bool:
    return _coerce_bool(state.get("services_up_to_date")) or (nlp_flags and _coerce_bool(nlp_flags.get("services_ok")))

def _has_expiry_info(entities: Dict[str, Any], state: Dict[str, Any]) -> bool:
    return bool(entities.get("EXPIRY_DAYS") or entities.get("EXPIRY_DATE") or state.get("expiry_captured"))

def _ready_to_notify(entities: Dict[str, Any], state: Dict[str, Any]) -> bool:
    return (
        bool(entities.get("POLICY_NUMBER")) and
        bool(entities.get("CUSTOMER_NAME") or entities.get("EMAIL") or entities.get("PHONE_NUMBER")) and
        not _coerce_bool(state.get("renovation_lead_notified"))
    )

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

def _return(state: Dict[str, Any], action: Dict[str, Any], prompt: Optional[str] = None) -> Dict[str, Any]:
    if "action_type" in action:
        state["last_action_type"] = action["action_type"]
    if prompt:
        state["last_prompt"] = prompt
        action.setdefault("message_to_customer", prompt)
    return action

# ---------------------------
# Rule Engine
# ---------------------------

class RuleEngine:
    def __init__(self):
        print("Rule Engine initialized.")

    def evaluate_rules(self, state: dict) -> Optional[dict]:
        # ---- Extract & normalize ------------------------------------------------
        # Ensure booleans are real booleans
        for f in ("pricing_provided","pricing_confirmed","renovation_lead_notified",
                  "vehicle_info_acknowledged","plan_selected"):
            state[f] = _coerce_bool(state.get(f))

        current_intent = state.get("current_intent", "Unknown") or "Unknown"
        entities      = state.get("entities", {}) or {}
        raw_summary   = state.get("conversation_summary", "") or ""
        summary_norm  = _norm(raw_summary)
        last_action   = state.get("last_action_type", "") or ""
        nlp_flags     = state.get("nlp_flags", {}) or {}

        # increment turn
        state["conversation_turn"] = int(state.get("conversation_turn", 0)) + 1

        print("RULE DEBUG:",
              f"intent={current_intent}",
              f"last={last_action}",
              f"turn={state['conversation_turn']}",
              f"pricing_provided={state.get('pricing_provided')}",
              f"pricing_confirmed={state.get('pricing_confirmed')}",
              f"entities={list(entities.keys())}")

        # ---- GLOBAL OVERRIDES / LOOP PREVENTION --------------------------------

        # 0) If already ready, notify human immediately
        if _ready_to_notify(entities, state):
            state["renovation_lead_notified"] = True
            state["lead_generation_complete"] = True
            return _return(state, _build_lead_notification(state, entities))

        # 1) Pricing confirmation → move forward once, never re-price
        if (last_action == "provide_pricing_info" or state.get("pricing_provided")) \
           and current_intent in {"ConfirmRenovation","RenovatePolicy"} \
           and not state.get("pricing_confirmed"):
            state["pricing_confirmed"] = True
            state["context"] = "pricing_flow"
            return _return(state, {
                "action_type": "request_contact_info",
                "message_to_customer": (
                    "¡Perfecto! Para continuar con su cotización y que un agente se ponga en contacto, "
                    "¿cuál es su nombre completo y teléfono?"
                ),
                "information_requested": "contact_info"
            }, "¿Cuál es su nombre completo y teléfono?")

        # 2) Expired policy flow (stepwise; won't repeat)
        if _expired_flag(summary_norm, nlp_flags) or state.get("context") == "expired_policy_flow":
            state["context"] = "expired_policy_flow"

            # capture NLP signals once
            if nlp_flags.get("services_ok"): state["services_up_to_date"] = True
            if entities.get("EXPIRY_DAYS") or entities.get("EXPIRY_DATE"):
                state["expiry_captured"] = True
                state["expiry_days"] = entities.get("EXPIRY_DAYS")
                state["expiry_date"] = entities.get("EXPIRY_DATE")

            # ask only what's missing
            if not _has_expiry_info(entities, state):
                return _return(state, {
                    "action_type": "ask_expiry_date",
                    "message_to_customer": "¿En qué fecha venció su garantía? (por ejemplo, 2025-08-11 o 'ayer')",
                    "information_requested": "expiry_date"
                }, "¿En qué fecha venció su garantía?")
            if not _services_ok(state, nlp_flags):
                return _return(state, {
                    "action_type": "ask_services_status",
                    "message_to_customer": "¿Tiene los servicios de mantenimiento al día?",
                    "information_requested": "services_status"
                }, "¿Tiene los servicios de mantenimiento al día?")

            # ready to proceed with renewal data collection
            if not entities.get("POLICY_NUMBER"):
                prompt = "Perfecto. Para continuar con la renovación, ¿cuál es su número de póliza?"
                return _return(state, {
                    "action_type": "ask_for_policy_number",
                    "message_to_customer": prompt,
                    "information_requested": "policy_number"
                }, prompt)

            if not (entities.get("VEHICLE_MAKE") and entities.get("VEHICLE_MODEL")):
                prompt = "Gracias. Ahora, ¿cuál es la marca, modelo y año de su vehículo?"
                return _return(state, {
                    "action_type": "ask_for_vehicle_info",
                    "message_to_customer": prompt,
                    "information_requested": "vehicle_details"
                }, prompt)

            # contact (any) → notify human
            if _ready_to_notify(entities, state):
                state["renovation_lead_notified"] = True
                state["lead_generation_complete"] = True
                return _return(state, _build_lead_notification(state, entities))

        # ---- CONVERSATIONAL RULES (flow-aware; won't derail) -------------------

        if current_intent == "Disagreement":
            state["conversation_ended"] = True
            return _return(state, {
                "action_type": "end_conversation",
                "message_to_customer": (
                    "Entiendo. Si cambia de opinión sobre la renovación de su garantía, "
                    "estaré aquí para ayudarle. ¡Que tenga buen día!"
                ),
                "conversation_status": "ended_by_user"
            })

        if current_intent == "Confusion":
            if _in_data_collection(state):
                prompt = state.get("last_prompt") or "Para continuar, ¿cuál es su número de póliza?"
                return _return(state, {
                    "action_type": state.get("last_action_type") or "ask_for_policy_number",
                    "message_to_customer": prompt,
                    "clarification_provided": True
                }, prompt)
            else:
                return _return(state, {
                    "action_type": "explain",
                    "message_to_customer": (
                        "Soy su asistente para renovar garantías extendidas de autos. "
                        "¿Le puedo ayudar con la renovación de su garantía?"
                    ),
                    "explanation_provided": True
                })

        if current_intent == "AskForClarification":
            # If we are in pricing, guide to plan selection (no re-pricing)
            if state.get("context") == "pricing_flow" or last_action == "provide_pricing_info":
                prompt = "Tenemos coberturas de 12, 24, 36 y 48 meses. ¿Cuál prefiere?"
                detail = (
                    "Tenemos 4 coberturas: 12, 24, 36 y 48 meses. "
                    "La de 12 meses cuesta $9,900.00. ¿Cuál prefiere (12, 24, 36 o 48)?"
                )
                return _return(state, {
                    "action_type": "clarify_pricing_options",
                    "message_to_customer": detail
                }, prompt)
            if _in_data_collection(state):
                prompt = state.get("last_prompt") or "Para continuar, ¿cuál es su número de póliza?"
                return _return(state, {
                    "action_type": state.get("last_action_type") or "ask_for_policy_number",
                    "message_to_customer": prompt,
                    "detailed_explanation": True
                }, prompt)
            # general explanation
            if "renovacion" in summary_norm or "garantia" in summary_norm:
                return _return(state, {
                    "action_type": "explain",
                    "message_to_customer": (
                        "La renovación de garantía extendida protege su auto contra fallas mecánicas. "
                        "Necesito algunos datos para generar una cotización. ¿Le interesa?"
                    ),
                    "product_explanation": True
                })
            return _return(state, {
                "action_type": "explain",
                "message_to_customer": (
                    "Le ayudo con la renovación de su garantía extendida de auto. "
                    "Es sencillo: solo necesito algunos datos. ¿Le interesa renovar?"
                ),
                "general_explanation": True
            })

        if current_intent == "CancelRenovation":
            state["conversation_ended"] = True
            return _return(state, {
                "action_type": "cancel_process",
                "message_to_customer": (
                    "Entiendo que desea cancelar el proceso de renovación. El proceso ha sido cancelado. "
                    "Si necesita ayuda en el futuro, no dude en contactarnos."
                ),
                "cancellation_reason": "user_request"
            })

        if current_intent == "Greeting":
            # Reset state for fresh start (keep transcript but reset flow flags)
            for k in [
                "conversation_ended","renovation_lead_notified","lead_generation_complete",
                "vehicle_info_acknowledged","pricing_provided","pricing_confirmed",
                "plan_selected","context","last_action_type","last_prompt",
                "services_up_to_date","expiry_captured","expiry_days","expiry_date"
            ]:
                if isinstance(state.get(k), bool): state[k] = False
                else: state[k] = ""
            return _return(state, {
                "action_type": "greet_and_offer_service",
                "message_to_customer": (
                    "¡Hola! Soy su asistente de GarantiPLUS para renovaciones de garantía extendida. "
                    "¿Le ayudo con la renovación de su garantía?"
                ),
                "greeting_provided": True,
                "service_offered": True
            })

        # ---- BUSINESS CRITICAL: notify human when ready -------------------------
        if _ready_to_notify(entities, state):
            state["renovation_lead_notified"] = True
            state["lead_generation_complete"] = True
            return _return(state, _build_lead_notification(state, entities))

        # ---- INFORMATION GATHERING ---------------------------------------------

        # Plan selection after pricing (e.g., "el de 12")
        if (last_action == "provide_pricing_info" or state.get("pricing_provided")) \
           and entities.get("PLAN_SELECTION") and not state.get("plan_selected"):
            sel = entities.get("PLAN_SELECTION")
            state["plan_selected"] = True
            state["context"] = "pricing_flow"
            prompt = (
                f"¡Excelente elección! La cobertura de {sel} meses es una gran opción. "
                "Para continuar con su cotización y que un agente se ponga en contacto, "
                "¿cuál es su nombre completo y teléfono?"
            )
            return _return(state, {
                "action_type": "request_contact_info",
                "message_to_customer": prompt,
                "information_requested": "contact_info",
                "plan_selected": sel
            }, "¿Cuál es su nombre completo y teléfono?")

        # Start of renovation: ask policy number (only if not in pricing flow)
        if current_intent == "RenovatePolicy" and not entities.get("POLICY_NUMBER") and not state.get("pricing_provided"):
            state["context"] = "data_collection"
            prompt = "Perfecto, le ayudo con la renovación de su garantía. Para comenzar, ¿cuál es su número de póliza?"
            return _return(state, {
                "action_type": "ask_for_policy_number",
                "message_to_customer": prompt,
                "information_requested": "policy_number"
            }, prompt)

        # After policy number: ask vehicle info
        if (current_intent in {"RenovatePolicy","QueryPolicyDetails"} or entities.get("POLICY_NUMBER")) \
           and entities.get("POLICY_NUMBER") \
           and not (entities.get("VEHICLE_MAKE") and entities.get("VEHICLE_MODEL")) \
           and not state.get("pricing_provided"):
            state["context"] = "data_collection"
            policy = entities.get("POLICY_NUMBER")
            prompt = f"Excelente, tengo su póliza {policy}. Ahora necesito los datos de su vehículo: ¿cuál es la marca, modelo y año?"
            return _return(state, {
                "action_type": "ask_for_vehicle_info",
                "message_to_customer": prompt,
                "information_requested": "vehicle_details",
                "policy_acknowledged": True
            }, prompt)

        # Vehicle info acknowledged → ask contact name
        if (entities.get("VEHICLE_MAKE") or entities.get("VEHICLE_MODEL")) \
           and entities.get("POLICY_NUMBER") \
           and not state.get("vehicle_info_acknowledged") \
           and not state.get("pricing_provided"):
            state["vehicle_info_acknowledged"] = True
            parts = [entities.get("VEHICLE_MAKE",""), entities.get("VEHICLE_MODEL",""), entities.get("VEHICLE_YEAR","")]
            vehicle_description = " ".join([p for p in parts if p]).strip() or "su vehículo"
            state["context"] = "data_collection"
            prompt = f"Perfecto, {vehicle_description}. Para finalizar y que un agente se ponga en contacto con usted, ¿cuál es su nombre completo?"
            return _return(state, {
                "action_type": "request_contact_info",
                "message_to_customer": prompt,
                "information_requested": "customer_name",
                "vehicle_acknowledged": True
            }, prompt)

        # Confirmation handler (collect whatever is missing)
        if current_intent == "ConfirmRenovation":
            if (state.get("pricing_provided") and not state.get("pricing_confirmed")):
                state["pricing_confirmed"] = True
                state["context"] = "pricing_flow"
                return _return(state, {
                    "action_type": "request_contact_info",
                    "message_to_customer": (
                        "¡Perfecto! Para continuar con su cotización y que un agente se ponga en contacto, "
                        "¿cuál es su nombre completo y teléfono?"
                    ),
                    "information_requested": "contact_info",
                    "confirmation_received": True
                }, "¿Cuál es su nombre completo y teléfono?")
            if not entities.get("POLICY_NUMBER"):
                prompt = "Excelente. ¿Cuál es su número de póliza para proceder con la renovación?"
                return _return(state, {
                    "action_type": "ask_for_policy_number",
                    "message_to_customer": prompt,
                    "confirmation_received": True
                }, prompt)
            if not (entities.get("VEHICLE_MAKE") and entities.get("VEHICLE_MODEL")):
                prompt = "Perfecto. ¿Podría proporcionarme la marca, modelo y año de su vehículo?"
                return _return(state, {
                    "action_type": "ask_for_vehicle_info",
                    "message_to_customer": prompt,
                    "confirmation_received": True
                }, prompt)
            if not (entities.get("CUSTOMER_NAME") or entities.get("EMAIL") or entities.get("PHONE_NUMBER")):
                prompt = "Excelente. Para finalizar, ¿cuál es su nombre completo o un número de contacto?"
                return _return(state, {
                    "action_type": "request_contact_info",
                    "message_to_customer": prompt,
                    "confirmation_received": True
                }, prompt)
            if _ready_to_notify(entities, state):
                state["renovation_lead_notified"] = True
                state["lead_generation_complete"] = True
                return _return(state, _build_lead_notification(state, entities))

        # ---- FAQS (lower priority, loop-safe) ----------------------------------

        # Payment info: should not be blocked by pricing
        wants_pay = any(tok in summary_norm for tok in PAY_TOKENS)
        if (wants_pay or (current_intent == "GetQuote" and wants_pay)) and not _in_data_collection(state):
            return _return(state, {
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
        wants_price = (current_intent == "GetQuote") or any(tok in summary_norm for tok in PRICE_TOKENS)
        if wants_price and not state.get("pricing_provided") and not state.get("pricing_confirmed") \
           and not _in_data_collection(state) and last_action != "provide_pricing_info":
            state["pricing_provided"] = True
            state["context"] = "pricing_flow"
            return _return(state, {
                "action_type": "provide_pricing_info",
                "message_to_customer": PRICING_TEXT,
                "pricing_provided": True
            }, "¿Cuál le interesa (12, 24, 36 o 48)?")

        # Claims / hacer válida
        wants_claim = any(tok in summary_norm for tok in CLAIM_TOKENS)
        if (current_intent == "QueryPolicyDetails" and wants_claim) or any(k in summary_norm for k in ["reportar garantia","hacer valida","reclamacion","reclamación"]):
            return _return(state, {
                "action_type": "provide_claims_info",
                "message_to_customer": (
                    "Para hacer válida su garantía o reportar un problema:\n\n"
                    "Call Center: 800 GARANTI (4272684)\n"
                    "WhatsApp: 4432441212\n\n"
                    "Nuestro equipo de atención está disponible para ayudarle con cualquier reclamo."
                ),
                "claims_info_provided": True
            })

        # ---- EDGE CASES / UNKNOWN ----------------------------------------------

        if current_intent == "Unknown":
            if entities.get("POLICY_NUMBER") and not entities.get("VEHICLE_MAKE"):
                prompt = f"Veo que me proporcionó el número de póliza {entities.get('POLICY_NUMBER')}. Para ayudarle con la renovación, ¿cuál es la marca, modelo y año de su vehículo?"
                return _return(state, {
                    "action_type": "ask_for_vehicle_info",
                    "message_to_customer": prompt,
                    "intelligent_interpretation": True
                }, prompt)
            if (entities.get("VEHICLE_MAKE") or entities.get("VEHICLE_MODEL")) and not entities.get("POLICY_NUMBER"):
                prompt = "Veo que me proporcionó información del vehículo. Para la renovación de garantía, también necesito su número de póliza. ¿Cuál es?"
                return _return(state, {
                    "action_type": "ask_for_policy_number",
                    "message_to_customer": prompt,
                    "intelligent_interpretation": True
                }, prompt)
            return _return(state, {
                "action_type": "clarify_intent",
                "message_to_customer": (
                    "Soy especialista en renovaciones de garantía extendida. "
                    "¿Le interesa renovar su garantía o necesita información sobre nuestros servicios?"
                ),
                "clarification_requested": True
            })

        # ---- FALLBACK TO LEARNED POLICY ----------------------------------------
        print("No rule matched - Deferring to Policy Module")
        return None