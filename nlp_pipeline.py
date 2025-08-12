# nlp_pipeline.py
"""
Improved NLP Pipeline - Robust Conversational Understanding
===========================================================

- Accent-insensitive matching (Spanish-safe)
- Stricter policy number extraction (no false positives like "HOLA")
- Plan selection extraction (e.g., "el de 12", "12 meses")
- Expired-policy detection via flags + entities (EXPIRY_DAYS, EXPIRY_DATE)
- Services-up-to-date detection (flags["services_ok"])
- Safer greeting detection (word boundaries)
- Better contact/vehicle extraction
- ProvideContactInfo intent when contact is given without other intent
- Optional LLM front-end with a tight JSON contract
"""

from __future__ import annotations
import re
import json
import unicodedata
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

try:
    import openai
except Exception:
    openai = None


# -------------------------
# Normalization utilities
# -------------------------
def _norm(s: str) -> str:
    """Lowercase + strip accents for robust keyword checks."""
    if not s:
        return ""
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn")


# -------------------------
# Compiled Regex / Constants
# -------------------------
GREETING_RE = re.compile(
    r"\b(hola|hello|hi|buen(?:os|as)\s+(?:dias|d[ií]as|tardes|noches))\b",
    re.IGNORECASE,
)

# Require 6–12 alnum, at least one digit (typical policy-like codes).
POLICY_CUE = r"(?:pol(?:i|í)za|poliza|policy|n(?:u|ú)mero|numero|folio|#)"
CODE_BODY = r"(?=[A-Z0-9]{6,12}\b)(?=.*\d)[A-Z0-9]+"
POLICY_WITH_CUE_RE = re.compile(rf"{POLICY_CUE}\s*[:\-]?\s*({CODE_BODY})", re.IGNORECASE)
POLICY_BARE_RE = re.compile(rf"^\s*({CODE_BODY})\s*$", re.IGNORECASE)

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(r"\b(?:\+?\d{1,3}\s*)?(?:\(?\d{2,4}\)?\s*)?\d{3,4}\s*\d{4}\b")
YEAR_RE  = re.compile(r"\b(19[8-9]\d|20[0-4]\d)\b")

# Simple brand lexicon (normalized keys -> display names)
BRANDS = {
    "toyota": "Toyota", "honda": "Honda", "nissan": "Nissan",
    "ford": "Ford", "vw": "Volkswagen", "volkswagen": "Volkswagen",
    "chevrolet": "Chevrolet", "audi": "Audi", "bmw": "BMW",
    "kia": "Kia", "hyundai": "Hyundai", "mazda": "Mazda",
    "mercedes": "Mercedes", "mercedes-benz": "Mercedes-Benz",
    "renault": "Renault", "seat": "SEAT", "fiat": "FIAT",
    "peugeot": "Peugeot", "jeep": "Jeep", "dodge": "Dodge",
    "ram": "RAM", "subaru": "Subaru", "mitsubishi": "Mitsubishi",
}

# Expired tokens (normalized)
EXPIRED_TOKENS = [
    "vencio", "vencida", "vencido", "vencimiento",
    "expirada", "expirado", "expiro", "expirio",   # expirió -> expirio (normalized)
    "caduca", "caducada", "caducado", "caducidad",
    "pasada", "ya paso", "se me paso", "ya vencio", "ya expiro",
]

# Plan selection tokens (normalized)
PLAN_RE_1 = re.compile(r"\b(12|24|36|48)\s*mes", re.IGNORECASE)
PLAN_RE_2 = re.compile(r"\b(?:el\s+de\s+)?(12|24|36|48)\b", re.IGNORECASE)

# Date patterns (common Spanish formats)
DATE_DDMMYYYY = re.compile(r'\b(0?[1-9]|[12]\d|3[01])[\/\-](0?[1-9]|1[0-2])[\/\-](\d{4})\b')
DATE_YYYYMMDD = re.compile(r'\b(\d{4})[\/\-](0?[1-9]|1[0-2])[\/\-](0?[1-9]|[12]\d|3[01])\b')
DATE_DD_DE_MES = re.compile(r'\b(0?[1-9]|[12]\d|3[01])\s+de\s+([a-záéíóú]+)\s+(\d{4})\b', re.I)
MESES = {
    "enero":1,"febrero":2,"marzo":3,"abril":4,"mayo":5,"junio":6,
    "julio":7,"agosto":8,"septiembre":9,"setiembre":9,"octubre":10,"noviembre":11,"diciembre":12
}


# -------------------------
# Feature detectors
# -------------------------
def _extract_policy(text: str) -> Optional[str]:
    """Extract policy number only when it's very likely a policy."""
    up = (text or "").upper()
    m = POLICY_WITH_CUE_RE.search(up)
    if m:
        return m.group(1)
    m2 = POLICY_BARE_RE.match(up)
    if m2:
        return m2.group(1)
    return None


def _expired_flag(text: str) -> bool:
    t = _norm(text)
    return any(tok in t for tok in EXPIRED_TOKENS)


def _detect_greeting(text: str) -> bool:
    return GREETING_RE.search(text or "") is not None


def _extract_plan_selection(text: str) -> Optional[int]:
    """Return 12/24/36/48 if present in typical phrasings."""
    t = text or ""
    n = _norm(t)
    m = PLAN_RE_1.search(n)
    if m:
        return int(m.group(1))
    m2 = PLAN_RE_2.search(n)
    if m2:
        return int(m2.group(1))
    return None


def _services_ok(text: str) -> bool:
    n = _norm(text)
    keys = [
        "servicios al dia", "tengo los servicios al dia", "servicios al corriente",
        "mantenimientos al dia", "si, al dia", "si al dia", "sí, al dia", "sí al dia",
        "todo al dia", "servicios al dia y al corriente", "servicios al dia ok"
    ]
    return any(k in n for k in keys)


def _extract_expiry_info(text: str) -> Dict[str, Any]:
    """Extract EXPIRY_DAYS and EXPIRY_DATE from text (ayer/hoy or explicit dates)."""
    out: Dict[str, Any] = {}
    if not text:
        return out

    n = _norm(text)
    today = datetime.utcnow().date()

    if "ayer" in n:
        out["EXPIRY_DAYS"] = 1
        out["EXPIRY_DATE"] = str(today - timedelta(days=1))
        return out
    if "hoy" in n:
        out["EXPIRY_DAYS"] = 0
        out["EXPIRY_DATE"] = str(today)
        return out

    m = DATE_YYYYMMDD.search(text) or DATE_DDMMYYYY.search(text)
    if m:
        try:
            if m.re is DATE_YYYYMMDD:
                y, mo, d = map(int, m.groups())
            else:
                d, mo, y = map(int, m.groups())
            dt = datetime(y, mo, d).date()
            out["EXPIRY_DAYS"] = (today - dt).days
            out["EXPIRY_DATE"] = str(dt)
            return out
        except Exception:
            pass

    m2 = DATE_DD_DE_MES.search(text)
    if m2:
        d, mes, y = m2.groups()
        mes_n = _norm(mes)
        if MESES.get(mes_n):
            try:
                dt = datetime(int(y), MESES[mes_n], int(d)).date()
                out["EXPIRY_DAYS"] = (today - dt).days
                out["EXPIRY_DATE"] = str(dt)
                return out
            except Exception:
                pass

    return out


def _entity_vehicle(text: str) -> Dict[str, str]:
    """Heuristic vehicle extraction: brand + (optional) model + year."""
    out: Dict[str, str] = {}

    t_raw = text or ""
    t_norm = _norm(t_raw)

    # Brand detection
    brand_key = None
    for k in BRANDS.keys():
        if re.search(rf"\b{k}\b", t_norm):
            brand_key = k
            break
    if brand_key:
        out["VEHICLE_MAKE"] = BRANDS[brand_key]

    # Year
    y = YEAR_RE.search(t_raw)
    if y:
        out["VEHICLE_YEAR"] = y.group(0)

    # Try model as the token(s) after brand, if any, before year
    if brand_key:
        m = re.search(
            rf"\b{brand_key}\b\s+([a-z0-9\-]+(?:\s+[a-z0-9\-]+)?)",
            t_norm,
        )
        if m:
            candidate = m.group(1).strip()
            # Avoid common filler words
            if not re.match(r"^(es|un|una|mi|tengo|modelo)$", candidate):
                if not YEAR_RE.search(candidate):
                    out["VEHICLE_MODEL"] = candidate.upper()

    # If phrased like "es un / tengo un / mi auto"
    if not out and re.search(r"\b(es un|tengo un|mi auto|mi carro|it's a)\b", t_norm):
        if y:
            out["VEHICLE_YEAR"] = y.group(0)

    return out


def _normalize_entities(entities: Dict[str, Any]) -> Dict[str, Any]:
    """Map to canonical uppercase keys used by the Rule Engine."""
    normalized: Dict[str, Any] = {}
    mappings = {
        "vehicle_make": "VEHICLE_MAKE",
        "vehicle_model": "VEHICLE_MODEL",
        "vehicle_year": "VEHICLE_YEAR",
        "customer_name": "CUSTOMER_NAME",
        "policy_number": "POLICY_NUMBER",
        "email": "EMAIL",
        "phone_number": "PHONE_NUMBER",
        "plan_selection": "PLAN_SELECTION",
        "expiry_days": "EXPIRY_DAYS",
        "expiry_date": "EXPIRY_DATE",
    }
    for k, v in entities.items():
        standard_key = mappings.get(k.lower(), k.upper())
        normalized[standard_key] = v
    return normalized


# -------------------------
# Pipeline
# -------------------------
class NlpPipeline:
    def __init__(self, use_llm: bool = True):
        self.use_llm = use_llm and (openai is not None)
        if self.use_llm:
            self.client = openai.OpenAI()
        else:
            self.client = None

    def process_message(self, text: str) -> Dict[str, Any]:
        """
        Returns:
            {
                "intent": str,
                "entities": { ... normalized ... },
                "flags": {"expired": bool, "services_ok": bool},
                "processing_method": "llm" | "fallback"
            }
        """
        if self.client:
            out = self._process_with_llm(text)
            if out is not None:
                # augment with local extractors (flags + expiry entities)
                flags = {
                    "expired": _expired_flag(text),
                    "services_ok": _services_ok(text),
                }
                # merge in expiry info if any
                extra = self._extract_entities_local(text)
                merged_entities = {**out.get("entities", {}), **extra}
                out["entities"] = _normalize_entities(merged_entities)
                out["flags"] = flags
                out["processing_method"] = "llm"

                # If Unknown but we clearly have contact, promote to ProvideContactInfo
                if out.get("intent") in (None, "", "Unknown"):
                    out = self._maybe_promote_contact_intent(text, out)
                return out

        # Fallback
        out_fb = self._enhanced_fallback_processing(text)
        out_fb["flags"] = {
            "expired": _expired_flag(text),
            "services_ok": _services_ok(text),
        }
        out_fb["processing_method"] = "fallback"
        return out_fb

    # -------------------------
    # LLM Front-End
    # -------------------------
    def _process_with_llm(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Calls GPT with a tight JSON contract. If parsing fails, return None to fallback.
        """
        try:
            resp = self.client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.1,
                max_tokens=260,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an NLP system for a conversational insurance agent. "
                            "Classify the user's message into EXACTLY ONE intent from this list:\n"
                            "RenovatePolicy, GetQuote, QueryPolicyDetails, ProvideVehicleInfo, "
                            "ProvideContactInfo, CancelRenovation, Greeting, RequestSupport, "
                            "ConfirmRenovation, AskForClarification, Disagreement, Confusion, Unknown.\n\n"
                            "Rules:\n"
                            "- 'ConfirmRenovation' only if it's an explicit affirmative to proceed (sí, claro, perfecto) in context.\n"
                            "- Do NOT infer 'ConfirmRenovation' from a bare 'ok' unless it clearly agrees to proceed.\n"
                            "- If the message is a single code-like token (6–12 alnum, at least one digit), treat as 'QueryPolicyDetails'.\n"
                            "- Extract entities: POLICY_NUMBER, VEHICLE_MAKE, VEHICLE_MODEL, VEHICLE_YEAR, "
                            "CUSTOMER_NAME, EMAIL, PHONE_NUMBER, PLAN_SELECTION (12/24/36/48 if present).\n"
                            "- Return ONLY valid JSON (no markdown) with keys: intent, entities (object)."
                        ),
                    },
                    {"role": "user", "content": text},
                ],
            )
            content = resp.choices[0].message.content.strip()
            # Some models wrap in ```json; strip safely
            if content.startswith("```"):
                content = content.strip("`")
                if content.lower().startswith("json"):
                    content = content[4:].strip()
            data = json.loads(content)

            intent = data.get("intent", "Unknown") or "Unknown"
            entities = data.get("entities", {}) or {}

            # Merge/override with local extractors
            entities_auto = self._extract_entities_local(text)
            entities = {**entities, **entities_auto}

            print(f"🤖 LLM Result: Intent={intent}, Entities={entities}")
            return {"intent": intent, "entities": _normalize_entities(entities)}
        except Exception as e:
            print(f"LLM failed: {e}")
            return None

    # -------------------------
    # Deterministic Fallback
    # -------------------------
    def _enhanced_fallback_processing(self, text: str) -> Dict[str, Any]:
        t = (text or "").strip()
        t_lower = t.lower()
        t_norm = _norm(t)

        detected_intent = "Unknown"
        extracted_entities: Dict[str, Any] = {}

        # 1) Exact conversational shortcuts
        if t_lower in {"?", "¿?", "???"}:
            detected_intent = "Confusion"
        elif t_lower in {"no", "no gracias", "no quiero", "nope"}:
            detected_intent = "Disagreement"
        elif t_lower in {"sí", "si", "yes", "claro", "está bien", "de acuerdo", "perfecto"}:
            detected_intent = "ConfirmRenovation"
        elif t_lower in {"con qué?", "con que?", "cómo?", "como?", "qué?", "que?", "explícame", "no entiendo"}:
            detected_intent = "AskForClarification"

        # 2) Greetings
        elif _detect_greeting(t):
            detected_intent = "Greeting"

        # 3) Domain intents (tokens)
        elif any(w in t_norm for w in ["renovar", "renovacion", "renovación", "renew"]):
            detected_intent = "RenovatePolicy"
        elif any(w in t_norm for w in ["precio", "costo", "cuanto", "cuánto", "quote", "cotizacion", "cotización"]):
            detected_intent = "GetQuote"
        elif any(w in t_norm for w in ["ayuda", "help", "soporte", "support"]):
            detected_intent = "RequestSupport"
        elif any(w in t_norm for w in ["cancelar", "cancel", "terminar"]):
            detected_intent = "CancelRenovation"

        # 4) Policy number detection (strict)
        if detected_intent == "Unknown":
            pol = _extract_policy(t)
            if pol:
                detected_intent = "QueryPolicyDetails"
                extracted_entities["policy_number"] = pol

        # 5) Entities (contact/vehicle/plan/expiry)
        ents = self._extract_entities_local(t)
        extracted_entities.update(ents)

        # 6) Promote to ProvideContactInfo if we got contact and nothing else
        if detected_intent == "Unknown":
            if any(k in extracted_entities for k in ("email", "phone_number", "customer_name")):
                detected_intent = "ProvideContactInfo"

        print(f"🔧 Fallback Result: Intent={detected_intent}, Entities={extracted_entities}")
        return {
            "intent": detected_intent,
            "entities": _normalize_entities(extracted_entities),
        }

    # -------------------------
    # Local entity extraction (shared)
    # -------------------------
    def _extract_entities_local(self, text: str) -> Dict[str, Any]:
        entities: Dict[str, Any] = {}

        # Policy
        pol = _extract_policy(text)
        if pol:
            entities["policy_number"] = pol

        # Email
        m = EMAIL_RE.search(text or "")
        if m:
            entities["email"] = m.group(0)

        # Phone
        m = PHONE_RE.search(text or "")
        if m:
            entities["phone_number"] = m.group(0)

        # Customer name (very light heuristic)
        t_lower = (text or "").lower()
        name_m = re.search(r"\b(me llamo|mi nombre es)\s+([a-záéíóúñ\s]{2,60})$", t_lower)
        if name_m:
            name = name_m.group(2).strip()
            entities["customer_name"] = " ".join(w.capitalize() for w in name.split())

        # Plan selection
        plan = _extract_plan_selection(text or "")
        if plan is not None:
            entities["plan_selection"] = int(plan)

        # Expiry info (days/date)
        entities.update(_extract_expiry_info(text or ""))

        # Vehicle
        entities.update(_entity_vehicle(text or ""))

        return entities

    def _maybe_promote_contact_intent(self, text: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """If we clearly have contact info but Unknown intent, promote to ProvideContactInfo."""
        ents = payload.get("entities", {})
        # entities might be normalized already; check both cases
        if any(k in ents for k in ("EMAIL", "PHONE_NUMBER", "CUSTOMER_NAME")) or \
           any(k in ents for k in ("email", "phone_number", "customer_name")):
            payload["intent"] = "ProvideContactInfo"
        return payload