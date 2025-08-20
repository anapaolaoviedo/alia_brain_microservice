# memory_manager.py
"""
BRAIN Memory Manager
====================

This module serves as BRAIN's "memory system" - both short-term working memory and long-term storage.
It implements a dual-layer memory architecture:

SHORT-TERM MEMORY (Redis):
- Stores active conversation sessions with automatic expiration
- Fast access for real-time decision making
- Handles temporary conversation state and context

LONG-TERM MEMORY (PostgreSQL): 
- Persistent storage of customer profiles and conversation history
- Enables learning from past interactions and customer relationship building
- Provides audit trail and analytics capabilities

KEY FEATURES:
- Redis (short-term) + PostgreSQL (long-term) dual storage
- Robust entity key normalization (UPPERCASE for consistency)
- Stable sessions with TTL (Time To Live) + status transitions
- Safe RedisJSON/string fallback for compatibility
- Bounded conversation summary to prevent memory bloat
- Graceful degradation when external systems are unavailable

BUSINESS VALUE:
- Customers don't have to repeat information within sessions
- Builds comprehensive customer profiles over time
- Enables personalized experiences based on interaction history
- Supports regulatory compliance through conversation logging
"""

# STANDARD LIBRARY IMPORTS
import os        # Environment variable access
import json      # JSON serialization for data storage
import redis     # Redis client for fast session storage
import psycopg2  # PostgreSQL client for persistent storage
from dotenv import load_dotenv          # Environment configuration management
from typing import Dict, Any, Optional  # Type hints for better code documentation

# LOAD ENVIRONMENT CONFIGURATION
# ==============================
# Load environment variables from .env file for configuration
# This allows different settings for development, staging, and production
load_dotenv()

# CONFIGURATION CONSTANTS
# =======================
# Session timeout: How long conversations stay in memory without activity
# Default 30 minutes (1800 seconds) - balances user experience with memory usage
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "1800"))  # 30 min

# Conversation summary limit: Prevents memory bloat from very long conversations
# Default ~4KB - enough for meaningful context without excessive storage
SUMMARY_MAX_CHARS = int(os.getenv("SUMMARY_MAX_CHARS", "4000"))      # ~4 KB

# ENTITY KEY NORMALIZATION
# ========================
# Standardizes entity keys to UPPERCASE for consistency across the system
# This prevents bugs caused by case-sensitive key mismatches
# Example: "vehicle_make", "Vehicle_Make", "VEHICLE_MAKE" all become "VEHICLE_MAKE"
#
# BUSINESS BENEFIT: Ensures data consistency regardless of how entities are extracted
# TECHNICAL BENEFIT: Prevents subtle bugs from case mismatches in rule conditions
UPPER_MAP = {
    'vehicle_make': 'VEHICLE_MAKE',       # Car manufacturer (Toyota, Honda, etc.)
    'vehicle_model': 'VEHICLE_MODEL',     # Car model (Camry, Civic, etc.)
    'vehicle_year': 'VEHICLE_YEAR',       # Model year (2020, 2021, etc.)
    'customer_name': 'CUSTOMER_NAME',     # Customer's full name
    'policy_number': 'POLICY_NUMBER',     # Insurance policy identifier
    'email': 'EMAIL',                     # Customer email address
    'phone_number': 'PHONE_NUMBER',       # Customer phone number
    'vin': 'VIN',                         # Vehicle Identification Number
    'plan_selection': 'PLAN_SELECTION',   # Selected insurance plan/coverage
}

def norm_entities_upper(entities: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalizes entity keys to uppercase for consistency.
    
    This function ensures all entity keys follow the same casing convention,
    preventing bugs caused by case-sensitive key lookups throughout the system.
    
    REAL-WORLD EXAMPLE:
    Input:  {"vehicle_make": "Toyota", "Vehicle_Model": "Camry", "VEHICLE_YEAR": "2020"}
    Output: {"VEHICLE_MAKE": "Toyota", "VEHICLE_MODEL": "Camry", "VEHICLE_YEAR": "2020"}
    
    Args:
        entities: Dictionary of extracted entities with potentially inconsistent casing
        
    Returns:
        Dictionary with normalized uppercase keys
        
    TECHNICAL NOTE: Uses UPPER_MAP for known entities, falls back to .upper() for others
    BUSINESS VALUE: Prevents data loss due to case mismatches in business rules
    """
    if not entities:
        return {}
    out = {}
    for k, v in entities.items():
        # Use predefined mapping if available, otherwise convert to uppercase
        std = UPPER_MAP.get(k.lower(), k.upper())
        out[std] = v
    return out

def coerce_bool(v: Any) -> bool:
    """
    Safely converts various data types to boolean values.
    
    This handles the fact that data from Redis, JSON, or other sources
    might represent boolean values as strings, integers, or other types.
    Essential for reliable boolean flag handling in business logic.
    
    EXAMPLES:
    - True, "true", "1", 1, "yes" → True
    - False, "false", "0", 0, "no", None → False
    
    Args:
        v: Value of any type that should be interpreted as boolean
        
    Returns:
        Boolean value based on standard truthiness rules
        
    TECHNICAL PURPOSE: Ensures consistent boolean handling across data sources
    BUSINESS PURPOSE: Prevents logic errors in rule evaluation due to data type issues
    """
    # Accept True, "true", "1", 1 as True; everything else False
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        return v != 0
    if isinstance(v, str):
        return v.strip().lower() in {"true", "1", "yes"}
    return bool(v)


class MemoryManager:
    """
    BRAIN's dual-layer memory system managing both short-term and long-term storage.
    
    ARCHITECTURE OVERVIEW:
    - SHORT-TERM: Redis for fast session data (conversation state, working memory)
    - LONG-TERM: PostgreSQL for persistent data (customer profiles, history)
    - FALLBACK: In-memory storage when external systems are unavailable
    
    MEMORY LAYERS EXPLAINED:
    
    1. WORKING MEMORY (Redis):
       - Active conversation sessions
       - Current intent and extracted entities  
       - Conversation flags and progress tracking
       - Automatic expiration after inactivity
       - Think: "What we're talking about right now"
    
    2. LONG-TERM MEMORY (PostgreSQL):
       - Customer profiles and contact information
       - Complete conversation history and patterns
       - Cross-session learning and analytics
       - Permanent audit trail
       - Think: "Everything we know about this customer"
    
    3. EMERGENCY MEMORY (In-Memory Dict):
       - Backup when Redis/PostgreSQL unavailable
       - Ensures BRAIN keeps working even with infrastructure issues
       - Limited to current server session only
       - Think: "Keep working no matter what"
    
    BUSINESS BENEFITS:
    - Seamless conversations without information repetition
    - Builds comprehensive customer relationships over time
    - Enables personalized service based on history
    - Supports compliance and audit requirements
    """
    
    def __init__(self):
        """
        Initialize BRAIN's memory system with dual-layer storage architecture.
        
        Sets up connections to:
        1. Redis for fast session storage (short-term memory)
        2. PostgreSQL for persistent data storage (long-term memory)  
        3. In-memory fallback for reliability
        
        Gracefully handles connection failures to ensure BRAIN remains operational
        even when external storage systems are unavailable.
        
        INITIALIZATION SEQUENCE:
        1. Configure Redis connection and detect RedisJSON capabilities
        2. Configure PostgreSQL connection and ensure required tables exist
        3. Set up in-memory fallback dictionary
        4. Test connections and log availability status
        """
        
        # REDIS CONFIGURATION (Short-term Memory)
        # ======================================
        # Redis serves as BRAIN's "working memory" for active conversations
        # Fast access times enable real-time decision making
        self.redis_host = os.getenv('REDIS_HOST', 'localhost')
        self.redis_port = int(os.getenv('REDIS_PORT', 6379))
        self.redis_db   = int(os.getenv('REDIS_DB', 0))
        self.r = None  # Will hold Redis connection object
        self.redis_json_available = False  # Flag for RedisJSON module availability
        
        # IN-MEMORY FALLBACK STORAGE
        # ==========================
        # Emergency storage when Redis is unavailable
        # Ensures BRAIN continues functioning during infrastructure issues
        # LIMITED: Only available during current server session
        self._in_memory_sessions: Dict[str, Dict[str, Any]] = {}

        # ATTEMPT REDIS CONNECTION
        # =======================
        try:
            # Establish Redis connection with configured parameters
            self.r = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=self.redis_db,
                decode_responses=True,  # Automatically decode bytes to strings
            )
            # Test connection by pinging Redis server
            self.r.ping()
            print(f"Memory Manager: Connected to Redis at {self.redis_host}:{self.redis_port}")

            # DETECT REDISJSON CAPABILITIES
            # ============================
            # RedisJSON provides native JSON storage and querying
            # Falls back to string storage if not available
            try:
                # Test RedisJSON by creating and deleting a test key
                self.r.json().set('mm_test_key', '.', {'ok': True})
                self.r.json().delete('mm_test_key')
                self.redis_json_available = True
                print("RedisJSON detected - using native JSON storage")
            except Exception as e:
                print(f"RedisJSON not available: {e}. Using string storage.")
        except redis.exceptions.ConnectionError as e:
            print(f"ERROR: Redis connect failed: {e}. Using in-memory fallback.")

        # POSTGRESQL CONFIGURATION (Long-term Memory)
        # ===========================================
        # PostgreSQL serves as BRAIN's "long-term memory" for persistent data
        # Stores customer profiles, conversation history, and analytics
        self.pg_conn = None  # Will hold PostgreSQL connection object
        self.pg_db_config = {
            "host": os.getenv('PG_HOST', 'localhost'),
            "database": os.getenv('PG_DATABASE', 'brain_memory'),
            "user": os.getenv('PG_USER', 'postgres'),
            "password": os.getenv('PG_PASSWORD', 'mysecretpassword'),
            "port": int(os.getenv('PG_PORT', 5432)),
        }
        
        # ATTEMPT POSTGRESQL CONNECTION
        # =============================
        try:
            # Establish PostgreSQL connection with configured parameters
            self.pg_conn = psycopg2.connect(**self.pg_db_config)
            self.pg_conn.autocommit = True  # Auto-commit for immediate persistence
            print(f"Memory Manager: Connected to PostgreSQL '{self.pg_db_config['database']}'")
            
            # Ensure required database tables exist
            self._create_tables_if_not_exists()
        except psycopg2.Error as e:
            print(f"ERROR: PostgreSQL connect failed: {e}. Long-term persistence disabled.")

        print("Memory Manager initialized.")

    # ---------- PostgreSQL Database Schema Management ----------
    def _create_tables_if_not_exists(self):
        """
        Create required database tables if they don't already exist.
        
        Sets up the long-term memory schema with two main tables:
        
        1. USER_PROFILES: Customer master data
           - Basic contact information and identifiers
           - Vehicle information (VIN)
           - Last interaction timestamp
        
        2. CONVERSATION_LOG: Complete interaction history
           - Every message and response with timestamps
           - Intent and entity extraction results
           - Action types taken by BRAIN
           - Links to user profiles for relationship tracking
        
        BUSINESS VALUE:
        - Enables comprehensive customer relationship management
        - Supports analytics and conversation pattern analysis
        - Provides regulatory compliance audit trail
        - Enables machine learning on conversation data
        
        TECHNICAL DESIGN:
        - Uses JSONB for flexible entity storage
        - Foreign key relationships for data integrity
        - Timestamp tracking for temporal analysis
        - Configurable field sizes for scalability
        """
        if not self.pg_conn:
            return
        try:
            with self.pg_conn.cursor() as cur:
                # USER_PROFILES TABLE: Customer master data storage
                # =================================================
                # Stores persistent customer information that accumulates over time
                # This is BRAIN's "customer relationship database"
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS user_profiles (
                        user_id VARCHAR(255) PRIMARY KEY,         -- Unique customer identifier (phone, email, etc.)
                        customer_name VARCHAR(255),               -- Customer's full name
                        email VARCHAR(255),                       -- Email address for communications
                        phone_number VARCHAR(255),                -- Phone number for contact
                        vin VARCHAR(17),                          -- Vehicle Identification Number (17 chars max)
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP  -- Track when profile was last modified
                    );
                """)
                
                # CONVERSATION_LOG TABLE: Complete interaction history
                # ===================================================
                # Records every message, response, and action for analysis and compliance
                # This is BRAIN's "conversation memory" and learning database
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS conversation_log (
                        log_id SERIAL PRIMARY KEY,               -- Auto-incrementing unique log entry ID
                        user_id VARCHAR(255) NOT NULL,           -- Links to user_profiles table
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- When this interaction occurred
                        role VARCHAR(10) NOT NULL,               -- "user" or "agent" - who said what
                        message TEXT NOT NULL,                   -- Actual message content
                        intent VARCHAR(255),                     -- Detected intent (get_quote, file_claim, etc.)
                        entities JSONB,                          -- Extracted entities in flexible JSON format
                        action_type VARCHAR(255),                -- Type of action BRAIN took
                        FOREIGN KEY (user_id) REFERENCES user_profiles (user_id)  -- Relationship integrity
                    );
                """)
            print("PostgreSQL tables ensured.")
        except psycopg2.Error as e:
            print(f"ERROR: Create tables failed: {e}")

    # ---------- Redis Key Management ----------
    def _get_redis_key(self, user_id: str) -> str:
        """
        Generate standardized Redis key for user sessions.
        
        Creates consistent key naming convention for Redis storage.
        Using prefixes helps organize data and prevents key collisions.
        
        Args:
            user_id: Unique identifier for the user/session
            
        Returns:
            Formatted Redis key string
            
        EXAMPLE: user_id="1234567890" → key="session:1234567890"
        
        TECHNICAL PURPOSE: Consistent key naming prevents conflicts and aids debugging
        BUSINESS PURPOSE: Organizes customer data for easy maintenance and monitoring
        """
        return f"session:{user_id}"

    # ---------- Session State Retrieval (Short-term Memory Access) ----------
    def get_session_state(self, user_id: str) -> dict:
        """
        Retrieve current conversation state for a user session.
        
        This is BRAIN's primary method for accessing "working memory" - the current
        context and state of an ongoing conversation with a customer.
        
        RETRIEVAL PRIORITY (graceful degradation):
        1. Redis (primary) - Fast access to active session data
        2. In-memory fallback - If Redis unavailable
        3. Default state - For completely new sessions
        
        The returned state includes:
        - Current conversation intent and extracted entities
        - Progress flags (has policy number, vehicle details, etc.)
        - Conversation metadata (turn count, status, summary)
        - Session management information
        
        REAL-WORLD EXAMPLE:
        Customer calls back after 10 minutes continuing previous conversation:
        → BRAIN retrieves: "This customer was getting a quote for 2020 Honda Civic"
        → Conversation continues seamlessly without re-asking for vehicle details
        
        Args:
            user_id: Unique identifier for the customer/session
            
        Returns:
            Dictionary containing complete session state with normalized data
            
        TECHNICAL FEATURES:
        - Automatic entity key normalization to prevent case-sensitivity issues
        - Boolean coercion for reliable flag handling
        - TTL renewal to keep active sessions alive
        - Graceful fallback when storage systems fail
        """
        
        # DEFAULT SESSION STATE TEMPLATE
        # =============================
        # This represents a completely new conversation with no prior context
        # All flags start as False, indicating no information has been collected yet
        default_state = {
            "session_id": user_id,                      # Unique session identifier
            "current_intent": None,                     # No intent detected yet
            "entities": {},                             # No entities extracted yet
            
            # BUSINESS LOGIC FLAGS - Track conversation progress
            "policy_number_provided": False,            # Has customer given policy number?
            "vehicle_details_provided": False,          # Do we have complete vehicle info?
            "contact_info_provided": False,             # Do we have email or phone?
            "quote_provided": False,                    # Have we given customer a quote?
            "renovation_lead_notified": False,          # Has renovation team been notified?
            "pricing_provided": False,                  # Have we provided pricing info?
            "pricing_confirmed": False,                 # Has customer confirmed pricing?
            
            # SESSION METADATA
            "conversation_turn": 0,                     # Number of exchanges in conversation
            "status": "new_session",                    # Session lifecycle status
            "conversation_summary": ""                  # Bounded summary of conversation
        }

        # STEP 1: ATTEMPT REDIS RETRIEVAL (Primary Storage)
        # =================================================
        # Redis provides the fastest access to active session data
        # Try both RedisJSON and string storage methods for compatibility
        if self.r:
            key = self._get_redis_key(user_id)
            try:
                data = None
                
                # Try RedisJSON first if available (native JSON operations)
                if self.redis_json_available:
                    data = self.r.json().get(key)  # no '$' → direct doc or None
                    
                # Fallback to string storage method
                if data is None:
                    # Try plain string storage with JSON parsing
                    raw = self.r.get(key)
                    if raw:
                        data = json.loads(raw)

                # PROCESS RETRIEVED DATA
                # =====================
                if data:
                    # Normalize entity keys to prevent case-sensitivity issues
                    # CRITICAL: This ensures consistent key access throughout BRAIN
                    data["entities"] = norm_entities_upper(data.get("entities", {}))
                    
                    # Coerce boolean flags to ensure reliable type handling
                    # CRITICAL: Prevents logic errors from string "false" being truthy
                    for f in ["policy_number_provided","vehicle_details_provided","contact_info_provided",
                              "quote_provided","renovation_lead_notified","pricing_provided","pricing_confirmed"]:
                        data[f] = coerce_bool(data.get(f, False))
                    
                    # REFRESH SESSION TTL (Sliding Window)
                    # ===================================
                    # Reset expiration timer since user is actively engaged
                    # This keeps active conversations alive while letting idle ones expire
                    try:
                        self.r.expire(key, SESSION_TTL_SECONDS)
                    except Exception:
                        pass  # Don't fail if TTL update fails
                        
                    return data
            except Exception as e:
                print(f"Redis read error for {user_id}: {e}. Using fallback/default.")

        # STEP 2: IN-MEMORY FALLBACK RETRIEVAL
        # ====================================
        # If Redis is unavailable, check our in-memory backup storage
        # This ensures BRAIN continues working during infrastructure issues
        if self._in_memory_sessions.get(user_id):
            data = self._in_memory_sessions[user_id].copy()
            # Apply same normalization as Redis data
            data["entities"] = norm_entities_upper(data.get("entities", {}))
            return data

        # STEP 3: RETURN DEFAULT STATE
        # ===========================
        # No existing session found - return fresh state for new conversation
        # This handles first-time customers or expired sessions
        return default_state.copy()

    # ---------- Session State Update (Short-term Memory Storage) ----------
    def update_session_state(self, user_id: str, state: dict, user_message: str, chosen_action: dict = None):
        """
        Update and persist the current conversation state across all memory layers.
        
        This is BRAIN's primary method for "remembering" information during and after
        each interaction. It updates both short-term working memory (Redis) and 
        long-term persistent storage (PostgreSQL).
        
        CRITICAL PROCESSING STEPS:
        1. Normalize entity keys for consistency
        2. Update derived business logic flags  
        3. Manage session status transitions
        4. Maintain bounded conversation summary
        5. Persist to both Redis and PostgreSQL
        6. Handle graceful degradation if storage fails
        
        REAL-WORLD EXAMPLE:
        Customer says: "My email is john@example.com and I drive a 2020 Honda Civic"
        → Extracts: EMAIL="john@example.com", VEHICLE_MAKE="Honda", etc.
        → Updates flags: contact_info_provided=True, vehicle_details_provided=True
        → Saves to Redis for immediate access
        → Logs to PostgreSQL for long-term relationship building
        
        Args:
            user_id: Unique identifier for the customer/session
            state: Complete updated session state dictionary
            user_message: The customer's message that triggered this update
            chosen_action: The action BRAIN decided to take in response
            
        TECHNICAL IMPORTANCE:
        - Must be called after every decision to maintain conversation continuity
        - Handles data normalization to prevent downstream bugs
        - Manages both working memory and permanent storage
        - Provides audit trail for compliance and debugging
        
        BUSINESS IMPORTANCE:
        - Enables seamless conversation flow without information repetition
        - Builds customer profiles for personalized service
        - Creates interaction history for relationship management
        - Supports regulatory compliance through complete audit trails
        """
        
        # STEP 1: ENTITY NORMALIZATION
        # ===========================
        # Normalize entities to UPPERCASE keys for consistency throughout system
        # CRITICAL: This prevents bugs from case-sensitive key mismatches in rules
        state["entities"] = norm_entities_upper(state.get("entities", {}))

        # STEP 2: DERIVED FLAG UPDATES
        # ===========================
        # Update business logic flags based on accumulated entity data
        # These flags make rule conditions much simpler and more readable
        # Using normalized UPPER keys for reliable entity access
        ents = state["entities"]
        
        # Contact information flag: Either email OR phone number is sufficient
        if ents.get("EMAIL") or ents.get("PHONE_NUMBER"):
            state["contact_info_provided"] = True
            
        # Policy number flag: Required for many business operations
        if ents.get("POLICY_NUMBER"):
            state["policy_number_provided"] = True
            
        # Vehicle details flag: All three components required for complete profile
        if ents.get("VEHICLE_MAKE") and ents.get("VEHICLE_MODEL") and ents.get("VEHICLE_YEAR"):
            state["vehicle_details_provided"] = True

        # STEP 3: BOOLEAN COERCION
        # =======================
        # Ensure all boolean flags are actual booleans, not strings or other types
        # CRITICAL: Prevents logic errors from string "false" being truthy in Python
        for f in ["policy_number_provided","vehicle_details_provided","contact_info_provided",
                  "quote_provided","renovation_lead_notified","pricing_provided","pricing_confirmed"]:
            state[f] = coerce_bool(state.get(f, False))

        # STEP 4: SESSION STATUS MANAGEMENT
        # ================================
        # Advance session status from "new_session" to "active_session" after first interaction
        # This helps track session lifecycle for analytics and business logic
        if state.get("status") == "new_session":
            state["status"] = "active_session"

        # STEP 5: CONVERSATION SUMMARY MAINTENANCE
        # =======================================
        # Maintain a bounded summary of the conversation for context preservation
        # Prevents memory bloat while keeping essential conversation flow
        if "conversation_summary" not in state:
            state["conversation_summary"] = ""
            
        # Add user message to summary
        if user_message:
            state["conversation_summary"] += f"User: {user_message} | "
            
        # Add agent response to summary
        if chosen_action:
            msg = chosen_action.get("message_to_customer") or chosen_action.get("message")
            if msg:
                state["conversation_summary"] += f"Agent: {msg} | "
                
        # Truncate summary if it gets too long (bounded memory)
        # Keeps most recent interactions while preventing unbounded growth
        if len(state["conversation_summary"]) > SUMMARY_MAX_CHARS:
            state["conversation_summary"] = state["conversation_summary"][-SUMMARY_MAX_CHARS:]

        # STEP 6: REDIS PERSISTENCE (Short-term Memory)
        # =============================================
        # Save updated state to Redis for fast retrieval in subsequent interactions
        # Uses RedisJSON if available, falls back to string storage for compatibility
        if self.r:
            key = self._get_redis_key(user_id)
            try:
                # Use native JSON storage if RedisJSON module is available
                if self.redis_json_available:
                    self.r.json().set(key, '.', state)
                else:
                    # Fallback to string storage with JSON serialization
                    self.r.set(key, json.dumps(state))
                    
                # SET SLIDING TTL (Time To Live)
                # =============================
                # Reset expiration timer to keep active sessions alive
                # Idle sessions will automatically expire to free memory
                try:
                    self.r.expire(key, SESSION_TTL_SECONDS)
                except Exception:
                    pass  # Don't fail entire operation if TTL setting fails
                    
                print(f"Session state updated for user {user_id} in Redis. Status: {state.get('status')}")
            except Exception as e:
                print(f"Redis write error for {user_id}: {e}. Using in-memory fallback.")
                # Graceful degradation: save to in-memory storage if Redis fails
                self._in_memory_sessions[user_id] = state
        else:
            # Redis not available - use in-memory fallback storage
            self._in_memory_sessions[user_id] = state
            print(f"Session state updated for user {user_id} in-memory. Status: {state.get('status')}")

        # STEP 7: POSTGRESQL PERSISTENCE (Long-term Memory)
        # ================================================
        # Save customer profile and conversation history for long-term relationship building
        # This data persists beyond session expiration for future interactions
        if self.pg_conn:
            try:
                with self.pg_conn.cursor() as cur:
                    # UPSERT CUSTOMER PROFILE
                    # ======================
                    # Update customer profile with any new information collected
                    # Uses PostgreSQL UPSERT to merge new data with existing profile
                    # COALESCE preserves existing data when new data is NULL
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
                    
                    # LOG USER MESSAGE
                    # ===============
                    # Record the customer's message for conversation history and analysis
                    # Includes extracted intent and entities for machine learning
                    cur.execute(
                        """
                        INSERT INTO conversation_log (user_id, role, message, intent, entities, action_type)
                        VALUES (%s, %s, %s, %s, %s, %s);
                        """,
                        (user_id, "user", user_message, state.get("current_intent"),
                         json.dumps(ents), None)
                    )
                    
                    # LOG AGENT ACTION
                    # ===============
                    # Record BRAIN's response/action for conversation history and learning
                    # Links action to conversation context for pattern analysis
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