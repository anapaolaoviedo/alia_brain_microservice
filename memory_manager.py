"""
BRAIN Memory Manager
===================

Implements BRAIN's memory system using a hybrid approach that mimics human memory:

1. Short-term Working Memory (Redis):
   - Active conversation state and context
   - Fast access for real-time decision making
   - Temporary storage that can be cleared/expired

2. Long-term Memory (PostgreSQL):
   - Persistent customer profiles and history
   - Complete conversation transcripts
   - Permanent storage for business intelligence

This dual-memory system allows BRAIN to maintain context during conversations
while building a comprehensive knowledge base about customers over time.
"""

import redis
import json
import psycopg2 # for postgres
import os # to read environmental variables for credentials
from dotenv import load_dotenv # for the .env file

# Load environment variables from .env file for database credentials
load_dotenv()
    
class MemoryManager:
    '''
    Managing BRAIN memory using a hybrid approach:
    -Redis for short-term working memory (active conversations)
    -PostgreSQL for long-term user history and conversation logs
    
    This architecture mirrors human cognition:
    - Working memory: What we're actively thinking about (Redis)
    - Long-term memory: Everything we've learned and experienced (PostgreSQL)
    '''
    
    def __init__(self): 
        """
        Initialize the dual-memory system with fallback mechanisms.
        
        If Redis fails: Falls back to in-memory dictionary (loses data on restart)
        If PostgreSQL fails: Continues without long-term persistence
        This ensures BRAIN can operate even with partial infrastructure failures.
        """
        
        # REDIS CONFIGURATION - Short-term working memory setup
        self.redis_host = os.getenv('REDIS_HOST', 'localhost')
        self.redis_port = int(os.getenv('REDIS_PORT', 6379))
        self.redis_db = int(os.getenv('REDIS_DB', 0))
        self.r = None
        self.redis_json_available = False
        self._in_memory_sessions = {} # Fallback storage if Redis is unavailable
        
        # Attempt to connect to Redis for working memory
        try:
            self.r = redis.Redis(
                host = self.redis_host,
                port = self.redis_port,
                db = self.redis_db,
                decode_responses=True  # Automatically decode bytes to strings
            )
            self.r.ping() # Test connection with a simple ping
            print(f"Memory Manager: Connected to Redis at {self.redis_host}:{self.redis_port}")
            
            # Test for RedisJSON module availability
            # RedisJSON provides native JSON storage and querying capabilities
            # If not available, we fall back to storing JSON as simple strings
            try:
                self.r.json().set('test_key', '.', {'test': 'value'})
                self.r.json().delete('test_key') # Clean up test key
                self.r.delete('test_key') # Also delete the plain key if it was set
                self.redis_json_available = True
                print("RedisJSON module detected - using native JSON storage")
            except Exception as e:
                print(f"RedisJSON module not available or error: {e}. Falling back to JSON string storage in Redis.")

        except redis.exceptions.ConnectionError as e:
            print(f"ERROR: Could not connect to Redis at {self.redis_host}:{self.redis_port}. "
                  f"Please ensure Redis server is running. Error: {e}")
            print("Memory Manager will operate in IN-MEMORY ONLY mode for session state.")
            
        # POSTGRESQL CONFIGURATION - Long-term persistent memory setup
        self.pg_conn = None # PostgreSQL connection object
        self.pg_db_config = {
            "host": os.getenv('PG_HOST', 'localhost'),
            "database": os.getenv('PG_DATABASE', 'brain_memory'),
            "user": os.getenv('PG_USER', 'postgres'), # Default user for local docker
            "password": os.getenv('PG_PASSWORD', 'mysecretpassword'), # Default password for local docker
            "port": os.getenv('PG_PORT', 5432)
        }
        
        # Attempt to connect to PostgreSQL for long-term memory
        try:
            self.pg_conn = psycopg2.connect(**self.pg_db_config)
            self.pg_conn.autocommit = True # Auto-commit for MVP simplicity
            print(f"Memory Manager: Connected to PostgreSQL database '{self.pg_db_config['database']}'")
            self._create_tables_if_not_exists() # Ensure required tables exist
        except psycopg2.Error as e:
            print(f"ERROR: Could not connect to PostgreSQL database '{self.pg_db_config['database']}'. "
                  f"Please ensure PostgreSQL server is running and credentials are correct. Error: {e}")
            print("Memory Manager will NOT persist long-term data to PostgreSQL.")

        print("Memory Manager initialized: Ready to remember!")
        
    def _create_tables_if_not_exists(self):
        """
        Creates necessary PostgreSQL tables if they do not already exist.
        
        Tables created:
        1. user_profiles: Mutable customer data (name, email, phone, VIN)
        2. conversation_log: Immutable conversation transcript with metadata
        
        This method is called during initialization if PostgreSQL connection succeeds.
        """
        if not self.pg_conn: # Only proceed if PostgreSQL is actually connected
            return

        try:
            with self.pg_conn.cursor() as cur:
                # Table 1: User Profiles - Stores mutable customer information
                # This is updated as we learn more about each customer
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS user_profiles (
                        user_id VARCHAR(255) PRIMARY KEY,
                        customer_name VARCHAR(255),
                        email VARCHAR(255),
                        phone_number VARCHAR(255),
                        vin VARCHAR(17),  -- Vehicle Identification Number (standardized 17 chars)
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                
                # Table 2: Conversation Log - Immutable transcript of all interactions
                # Provides complete history for analysis and customer service review
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS conversation_log (
                        log_id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        role VARCHAR(10) NOT NULL, -- 'user' or 'agent'
                        message TEXT NOT NULL,
                        intent VARCHAR(255),  -- What the user was trying to accomplish
                        entities JSONB, -- JSONB for flexible storage of extracted entities
                        action_type VARCHAR(255),  -- What action BRAIN took in response
                        FOREIGN KEY (user_id) REFERENCES user_profiles (user_id)
                    );
                """)
            print("PostgreSQL tables checked/created successfully.")
        except psycopg2.Error as e:
            print(f"ERROR: Failed to create PostgreSQL tables: {e}")
            
    def _get_redis_key(self, user_id: str) -> str:
        """
        Generate a consistent Redis key for user sessions.
        
        Uses a namespaced key pattern to avoid collisions and enable
        easy identification of session data in Redis.
        
        Args:
            user_id: Unique identifier for the user
            
        Returns:
            Formatted Redis key string
        """
        return f"session:{user_id}"
        
    def get_session_state(self, user_id: str) -> dict: # CORRECTED: user_id:str -> user_id: str
        '''
        Retrieve the current session state for the given user from working memory.
        
        This method implements BRAIN's short-term memory recall:
        1. First tries Redis (primary working memory)
        2. Falls back to in-memory dict if Redis unavailable
        3. Returns default state for new sessions
        
        Arguments: 
            user_id: String identifier for the user session
            
        Returns: 
            Dictionary containing complete session state and context
        '''
        
        # Default state structure for new sessions
        # This represents a "blank slate" when meeting a new customer
        default_state = {
            "session_id": user_id,
            "current_intent": None,  # What the customer wants (quote, renewal, question)
            "entities": {}, # Stores extracted entities like policy_number, email, etc
            
            # Convenience flags for business rules (derived from entities)
            "policy_number_provided": False,
            "vehicle_details_provided": False,
            "contact_info_provided": False,
            "quote_provided": False,
            "renovation_lead_notified": False, # Has the human team been notified?
            
            "status": "new_session", # Track the current stage of the process
            "conversation_summary": "" # Build a running summary for human handoff
        }
        
        # PRIMARY: Try to retrieve from Redis working memory
        if self.r: # If Redis connection is active and ongoing
            redis_key = self._get_redis_key(user_id)
            try:
                if self.redis_json_available:
                    # Use RedisJSON for native JSON operations
                    stored_state = self.r.json().get(redis_key, '$')
                    if stored_state and isinstance(stored_state, list) and len(stored_state) > 0:
                        return stored_state[0] # Return the first (and ONLY!) JSON document
                else:
                    # Fallback: Parse JSON manually from string storage
                    stored_json_string = self.r.get(redis_key)
                    if stored_json_string:
                        return json.loads(stored_json_string)
            except Exception as e:
                print(f"Error retrieving state for {user_id} from Redis: {e}. Returning default state.")
                # Log error but don't crash - fallback mechanisms handle this gracefully

        # SECONDARY: Fallback to in-memory storage if Redis failed
        if not self.r and hasattr(self, '_in_memory_sessions'):
            return self._in_memory_sessions.get(user_id, default_state).copy()
        
        # TERTIARY: Return fresh default state if no memory found anywhere
        return default_state.copy() # Always return a copy to prevent accidental mutations
        
    def update_session_state(self, user_id: str, state: dict, user_message: str, chosen_action: dict = None):
        '''
        Update session state in working memory and persist relevant data to long-term memory.
        
        This method implements BRAIN's memory consolidation process:
        1. Updates derived flags based on accumulated entities
        2. Builds conversation summary for human handoff
        3. Saves to Redis working memory (with fallback)
        4. Persists important data to PostgreSQL long-term memory
        
        Args:
            user_id: Unique identifier for the user session
            state: Complete session state dictionary to save
            user_message: The message the user just sent
            chosen_action: The action BRAIN decided to take (optional)
        '''
        
        # UPDATE DERIVED FLAGS - Set convenience flags based on accumulated entities
        # These flags make it easier for business rules to check information completeness
        
        # Flag: Do we have customer contact information?
        if state["entities"].get("email") or state["entities"].get("phone_number"):
            state["contact_info_provided"] = True
            
        # Flag: Do we have the customer's policy number?
        if state["entities"].get("policy_number"):
            state["policy_number_provided"] = True
            
        # Flag: Do we have complete vehicle information?
        if state["entities"].get("vehicle_make") and \
        state["entities"].get("vehicle_model") and \
        state["entities"].get("vehicle_year"):
            state["vehicle_details_provided"] = True
            
        # BUILD CONVERSATION SUMMARY - Create human-readable summary for handoff
        # This summary helps human agents quickly understand the conversation context
        if "conversation_summary" not in state:
            state["conversation_summary"] = ""
        
        # Add user message to the summary
        state["conversation_summary"] += f"User: {user_message} | "
        
        # Add agent response to the summary (if available)
        if chosen_action and chosen_action.get("message_to_customer"):
            state["conversation_summary"] += f"Agent: {chosen_action['message_to_customer']} | "
        elif chosen_action and chosen_action.get("message"): # Fallback for generic 'message' key
            state["conversation_summary"] += f"Agent: {chosen_action['message']} | "
        
        # SAVE TO WORKING MEMORY - Update Redis with current session state
        if self.r: # If Redis connection is active
            redis_key = self._get_redis_key(user_id)
            try:
                if self.redis_json_available:
                    # Use RedisJSON to set the entire state dictionary natively
                    self.r.json().set(redis_key, '.', state)
                else:
                    # Fallback: Serialize dictionary to JSON string and store
                    self.r.set(redis_key, json.dumps(state))
                print(f"Session state updated for user {user_id} in Redis. Status: {state.get('status')}")
            except Exception as e:
                print(f"Error updating state for {user_id} in Redis: {e}. Data not persisted to Redis.")
                # Fallback to in-memory if Redis update fails
                if not hasattr(self, '_in_memory_sessions'):
                    self._in_memory_sessions = {}
                self._in_memory_sessions[user_id] = state
        else:
            # If Redis connection failed in __init__, use in-memory fallback
            if not hasattr(self, '_in_memory_sessions'): # Ensure fallback dict exists
                self._in_memory_sessions = {}
            self._in_memory_sessions[user_id] = state
            print(f"Session state updated for user {user_id} in-memory. Status: {state.get('status')}")

        # SAVE TO LONG-TERM MEMORY - Persist important data to PostgreSQL
        if self.pg_conn: # If PostgreSQL is connected and available
            try:
                with self.pg_conn.cursor() as cur:
                    # 1. UPDATE USER PROFILE - Upsert customer information
                    # Uses COALESCE to preserve existing data when new data is null
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
                            state["entities"].get("customer_name"),
                            state["entities"].get("email"),
                            state["entities"].get("phone_number"),
                            state["entities"].get("vin")
                        )
                    )

                    # 2. LOG USER MESSAGE - Record what the customer said
                    cur.execute(
                        """
                        INSERT INTO conversation_log (user_id, role, message, intent, entities, action_type)
                        VALUES (%s, %s, %s, %s, %s, %s);
                        """,
                        (
                            user_id,
                            "user", 
                            user_message,
                            state.get("current_intent"),
                            json.dumps(state.get("entities", {})), # Store entities as JSONB
                            None # No action_type for user messages
                        )
                    )
                    
                    # 3. LOG AGENT ACTION - Record what BRAIN decided to do
                    if chosen_action:
                        cur.execute(
                            """
                            INSERT INTO conversation_log (user_id, role, message, intent, entities, action_type)
                            VALUES (%s, %s, %s, %s, %s, %s);
                            """,
                            (
                                user_id,
                                "agent", # Role identifier for BRAIN's responses
                                chosen_action.get("message_to_customer") or chosen_action.get("message"),
                                state.get("current_intent"), # Agent action is based on current intent
                                json.dumps(state.get("entities", {})), # Entities relevant to agent action
                                chosen_action.get("action_type")
                            )
                        )
                print(f"Long-term data updated for user {user_id} in PostgreSQL.")
            except psycopg2.Error as e:
                print(f"ERROR: Could not persist long-term data for {user_id} to PostgreSQL: {e}")
        else:
            print(f"PostgreSQL not connected. Long-term data for {user_id} not persisted.")