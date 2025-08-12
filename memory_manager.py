# memory_manager.py
"""
BRAIN Memory Manager
- Redis (short-term) + PostgreSQL (long-term)
- Robust entity key normalization (UPPERCASE)
- Stable sessions with TTL + status transitions
- Safe RedisJSON/string fallback
- Bounded conversation summary
"""

import os
import json
import redis
import psycopg2
from dotenv import load_dotenv
from typing import Dict, Any, Optional

load_dotenv()

SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "1800"))  # 30 min
SUMMARY_MAX_CHARS = int(os.getenv("SUMMARY_MAX_CHARS", "4000"))      # ~4 KB

UPPER_MAP = {
    'vehicle_make': 'VEHICLE_MAKE',
    'vehicle_model': 'VEHICLE_MODEL',
    'vehicle_year': 'VEHICLE_YEAR',
    'customer_name': 'CUSTOMER_NAME',
    'policy_number': 'POLICY_NUMBER',
    'email': 'EMAIL',
    'phone_number': 'PHONE_NUMBER',
    'vin': 'VIN',
    'plan_selection': 'PLAN_SELECTION',
}

def norm_entities_upper(entities: Dict[str, Any]) -> Dict[str, Any]:
    if not entities:
        return {}
    out = {}
    for k, v in entities.items():
        std = UPPER_MAP.get(k.lower(), k.upper())
        out[std] = v
    return out

def coerce_bool(v: Any) -> bool:
    # Accept True, "true", "1", 1 as True; everything else False
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        return v != 0
    if isinstance(v, str):
        return v.strip().lower() in {"true", "1", "yes"}
    return bool(v)


class MemoryManager:
    def __init__(self):
        # Redis
        self.redis_host = os.getenv('REDIS_HOST', 'localhost')
        self.redis_port = int(os.getenv('REDIS_PORT', 6379))
        self.redis_db   = int(os.getenv('REDIS_DB', 0))
        self.r = None
        self.redis_json_available = False
        self._in_memory_sessions: Dict[str, Dict[str, Any]] = {}

        try:
            self.r = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=self.redis_db,
                decode_responses=True,
            )
            self.r.ping()
            print(f"Memory Manager: Connected to Redis at {self.redis_host}:{self.redis_port}")

            # Detect RedisJSON
            try:
                self.r.json().set('mm_test_key', '.', {'ok': True})
                self.r.json().delete('mm_test_key')
                self.redis_json_available = True
                print("RedisJSON detected - using native JSON storage")
            except Exception as e:
                print(f"RedisJSON not available: {e}. Using string storage.")
        except redis.exceptions.ConnectionError as e:
            print(f"ERROR: Redis connect failed: {e}. Using in-memory fallback.")

        # Postgres
        self.pg_conn = None
        self.pg_db_config = {
            "host": os.getenv('PG_HOST', 'localhost'),
            "database": os.getenv('PG_DATABASE', 'brain_memory'),
            "user": os.getenv('PG_USER', 'postgres'),
            "password": os.getenv('PG_PASSWORD', 'mysecretpassword'),
            "port": int(os.getenv('PG_PORT', 5432)),
        }
        try:
            self.pg_conn = psycopg2.connect(**self.pg_db_config)
            self.pg_conn.autocommit = True
            print(f"Memory Manager: Connected to PostgreSQL '{self.pg_db_config['database']}'")
            self._create_tables_if_not_exists()
        except psycopg2.Error as e:
            print(f"ERROR: PostgreSQL connect failed: {e}. Long-term persistence disabled.")

        print("Memory Manager initialized.")

    # ---------- Postgres DDL ----------
    def _create_tables_if_not_exists(self):
        if not self.pg_conn:
            return
        try:
            with self.pg_conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS user_profiles (
                        user_id VARCHAR(255) PRIMARY KEY,
                        customer_name VARCHAR(255),
                        email VARCHAR(255),
                        phone_number VARCHAR(255),
                        vin VARCHAR(17),
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS conversation_log (
                        log_id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        role VARCHAR(10) NOT NULL,
                        message TEXT NOT NULL,
                        intent VARCHAR(255),
                        entities JSONB,
                        action_type VARCHAR(255),
                        FOREIGN KEY (user_id) REFERENCES user_profiles (user_id)
                    );
                """)
            print("PostgreSQL tables ensured.")
        except psycopg2.Error as e:
            print(f"ERROR: Create tables failed: {e}")

    # ---------- Redis key ----------
    def _get_redis_key(self, user_id: str) -> str:
        return f"session:{user_id}"

    # ---------- Session read ----------
    def get_session_state(self, user_id: str) -> dict:
        default_state = {
            "session_id": user_id,
            "current_intent": None,
            "entities": {},
            "policy_number_provided": False,
            "vehicle_details_provided": False,
            "contact_info_provided": False,
            "quote_provided": False,
            "renovation_lead_notified": False,
            "pricing_provided": False,
            "pricing_confirmed": False,
            "conversation_turn": 0,
            "status": "new_session",
            "conversation_summary": ""
        }

        # Redis primary
        if self.r:
            key = self._get_redis_key(user_id)
            try:
                data = None
                if self.redis_json_available:
                    data = self.r.json().get(key)  # no '$' → direct doc or None
                if data is None:
                    # Try plain string
                    raw = self.r.get(key)
                    if raw:
                        data = json.loads(raw)

                if data:
                    # Normalize entities casing
                    data["entities"] = norm_entities_upper(data.get("entities", {}))
                    # Coerce booleans
                    for f in ["policy_number_provided","vehicle_details_provided","contact_info_provided",
                              "quote_provided","renovation_lead_notified","pricing_provided","pricing_confirmed"]:
                        data[f] = coerce_bool(data.get(f, False))
                    # Slide TTL
                    try:
                        self.r.expire(key, SESSION_TTL_SECONDS)
                    except Exception:
                        pass
                    return data
            except Exception as e:
                print(f"Redis read error for {user_id}: {e}. Using fallback/default.")

        # In-memory fallback
        if self._in_memory_sessions.get(user_id):
            data = self._in_memory_sessions[user_id].copy()
            data["entities"] = norm_entities_upper(data.get("entities", {}))
            return data

        return default_state.copy()

    # ---------- Session write ----------
    def update_session_state(self, user_id: str, state: dict, user_message: str, chosen_action: dict = None):
        # Normalize entities (UPPERCASE)
        state["entities"] = norm_entities_upper(state.get("entities", {}))

        # Derived flags (using UPPER keys)
        ents = state["entities"]
        if ents.get("EMAIL") or ents.get("PHONE_NUMBER"):
            state["contact_info_provided"] = True
        if ents.get("POLICY_NUMBER"):
            state["policy_number_provided"] = True
        if ents.get("VEHICLE_MAKE") and ents.get("VEHICLE_MODEL") and ents.get("VEHICLE_YEAR"):
            state["vehicle_details_provided"] = True

        # Coerce booleans
        for f in ["policy_number_provided","vehicle_details_provided","contact_info_provided",
                  "quote_provided","renovation_lead_notified","pricing_provided","pricing_confirmed"]:
            state[f] = coerce_bool(state.get(f, False))

        # Advance status from new_session → active_session
        if state.get("status") == "new_session":
            state["status"] = "active_session"

        # Bounded conversation summary
        if "conversation_summary" not in state:
            state["conversation_summary"] = ""
        if user_message:
            state["conversation_summary"] += f"User: {user_message} | "
        if chosen_action:
            msg = chosen_action.get("message_to_customer") or chosen_action.get("message")
            if msg:
                state["conversation_summary"] += f"Agent: {msg} | "
        if len(state["conversation_summary"]) > SUMMARY_MAX_CHARS:
            state["conversation_summary"] = state["conversation_summary"][-SUMMARY_MAX_CHARS:]

        # Persist to Redis (JSON if available)
        if self.r:
            key = self._get_redis_key(user_id)
            try:
                if self.redis_json_available:
                    self.r.json().set(key, '.', state)
                else:
                    self.r.set(key, json.dumps(state))
                # TTL (sliding)
                try:
                    self.r.expire(key, SESSION_TTL_SECONDS)
                except Exception:
                    pass
                print(f"Session state updated for user {user_id} in Redis. Status: {state.get('status')}")
            except Exception as e:
                print(f"Redis write error for {user_id}: {e}. Using in-memory fallback.")
                self._in_memory_sessions[user_id] = state
        else:
            self._in_memory_sessions[user_id] = state
            print(f"Session state updated for user {user_id} in-memory. Status: {state.get('status')}")

        # Long-term Postgres persistence
        if self.pg_conn:
            try:
                with self.pg_conn.cursor() as cur:
                    # Upsert profile
                    cur.execute(
                        """
                        INSERT INTO user_profiles (user_id, customer_name, email, phone_number, vin, last_updated)
                        VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (user_id) DO UPDATE SET
                            customer_name = COALESCE(EXCLUDED.customer_name, user_profiles.customer_name),
                            email = COALESCE(EXCLUDED.email, user_profiles.email),
                            phone_number = COALESCE(EXCLUDED.phone_number, user_profiles.phone_number),
                            vin = COALESCE(EXCLUDED.vin, user_profiles.vin),
                            last_updated = CURRENT_TIMESTAMP;
                        """,
                        (
                            user_id,
                            ents.get("CUSTOMER_NAME"),
                            ents.get("EMAIL"),
                            ents.get("PHONE_NUMBER"),
                            ents.get("VIN"),
                        )
                    )
                    # Log user message
                    cur.execute(
                        """
                        INSERT INTO conversation_log (user_id, role, message, intent, entities, action_type)
                        VALUES (%s, %s, %s, %s, %s, %s);
                        """,
                        (user_id, "user", user_message, state.get("current_intent"),
                         json.dumps(ents), None)
                    )
                    # Log agent action
                    if chosen_action:
                        cur.execute(
                            """
                            INSERT INTO conversation_log (user_id, role, message, intent, entities, action_type)
                            VALUES (%s, %s, %s, %s, %s, %s);
                            """,
                            (user_id, "agent",
                             chosen_action.get("message_to_customer") or chosen_action.get("message"),
                             state.get("current_intent"),
                             json.dumps(ents),
                             chosen_action.get("action_type"))
                        )
                print(f"Long-term data updated for user {user_id} in PostgreSQL.")
            except psycopg2.Error as e:
                print(f"ERROR: PostgreSQL persist failed for {user_id}: {e}")
        else:
            print(f"PostgreSQL not connected. Long-term data for {user_id} not persisted.")