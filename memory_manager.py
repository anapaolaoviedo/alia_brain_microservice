# memory_manager.py
import redis
import json
import psycopg2 # for postgres
import os # to read environmental variables for credentials
from dotenv import load_dotenv # for the .env file

load_dotenv()
    
class MemoryManager:
    '''
    Managing BRAIN memory using a hybrid approach:
    -Redis for short-term working memory
    -PostgreSQL for long-term user history and conversation logs
    '''
    
    def __init__(self): # CORRECTED: __init__ should have two underscores on each side
        #we start with REDIS configuration
        self.redis_host = os.getenv('REDIS_HOST', 'localhost')
        self.redis_port = int(os.getenv('REDIS_PORT', 6379))
        self.redis_db = int(os.getenv('REDIS_DB', 0))
        self.r = None
        self.redis_json_available = False
        self._in_memory_sessions = {} # Correctly initialized here
        
        try:
            self.r = redis.Redis(
                host = self.redis_host,
                port = self.redis_port,
                db = self.redis_db,
                decode_responses=True
            )
            self.r.ping() # testing connection
            print(f"Memory Manager: Connected to Redis at {self.redis_host}:{self.redis_port}")
            
            try:
                # literally try RedisJSON module availability.  requires the RedisJSON module to be loaded on the Redis server
                # if not available, fall back to storing JSON as simple strings
                self.r.json().set('test_key', '.', {'test': 'value'})
                self.r.json().delete('test_key') # Clean up test key
                self.r.delete('test_key') # Also delete the plain key if it was set
                self.redis_json_available = True
            except Exception as e:
                print(f"RedisJSON module not available or error: {e}. Falling back to JSON string storage in Redis.")

        except redis.exceptions.ConnectionError as e:
            print(f"ERROR: Could not connect to Redis at {self.redis_host}:{self.redis_port}. "
                  f"Please ensure Redis server is running. Error: {e}")
            print("Memory Manager will operate in IN-MEMORY ONLY mode for session state.")
            
        #we jump into PostgreSQL configuration
        self.pg_conn = None # PostgreSQL connection object
        self.pg_db_config = {
            "host": os.getenv('PG_HOST', 'localhost'),
            "database": os.getenv('PG_DATABASE', 'brain_memory'),
            "user": os.getenv('PG_USER', 'postgres'), # Default user for local docker
            "password": os.getenv('PG_PASSWORD', 'mysecretpassword'), # Default password for local docker
            "port": os.getenv('PG_PORT', 5432)
        }
        
        try:
            self.pg_conn = psycopg2.connect(**self.pg_db_config)
            self.pg_conn.autocommit = True # simplicity for mvp
            print(f"Memory Manager: Connected to PostgreSQL database '{self.pg_db_config['database']}'")
            self._create_tables_if_not_exists() # create table if ti doesnt exist
        except psycopg2.Error as e:
            print(f"ERROR: Could not connect to PostgreSQL database '{self.pg_db_config['database']}'. "
                  f"Please ensure PostgreSQL server is running and credentials are correct. Error: {e}")
            print("Memory Manager will NOT persist long-term data to PostgreSQL.")

        print("Memory Manager initialized: Ready to remember!")
        
    def _create_tables_if_not_exists(self):
        """
        Creates necessary PostgreSQL tables if they do not already exist.
        This method is called during initialization if a PG connection is successful.
        """
        if not self.pg_conn: # only works if PG is actually werking
            return

        try:
            with self.pg_conn.cursor() as cur:
                #okis we star with the long term memory queries
                #  mutable data like name, email, VIN
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
                # now a table for transcript of convos between brain and the client
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS conversation_log (
                        log_id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        role VARCHAR(10) NOT NULL, -- 'user' or 'agent'
                        message TEXT NOT NULL,
                        intent VARCHAR(255),
                        entities JSONB, -- JSONB for flexible storage of extracted entities
                        action_type VARCHAR(255),
                        FOREIGN KEY (user_id) REFERENCES user_profiles (user_id)
                    );
                """)
            print("PostgreSQL tables checked/created successfully.")
        except psycopg2.Error as e:
            print(f"ERROR: Failed to create PostgreSQL tables: {e}")
            
    # CORRECTED INDENTATION: These methods are part of the MemoryManager class, not _create_tables_if_not_exists
    def _get_redis_key(self, user_id: str) -> str:
        #mainlyyy to generate a consistent rediss key for like the user sessions
        return f"session:{user_id}"
        
    def get_session_state(self, user_id: str) -> dict: # CORRECTED: user_id:str -> user_id: str
        '''
        Here we check for the current session state for the given user.
        
        arguments: userd_id which is a string
        returns: a json structured dict of everything realted to that user
        '''
        default_state = {
            "session_id": user_id,
            "current_intent": None,
            "entities": {}, # stores extracted entities like policy_number, email, etcc
            "policy_number_provided": False,
            "vehicle_details_provided": False,
            "contact_info_provided": False,
            "quote_provided": False,
            "renovation_lead_notified": False, # the human team has been notified
            "status": "new_session", # rack the current stage of the renovation process
            "conversation_summary": "" # build a running summary for human handoff
        }
        
        if self.r: # if the Redis connection is active and onging
            redis_key = self._get_redis_key(user_id)
            try:
                if self.redis_json_available:
                # we dk if the resinJson is abaliable but if it is, must use that
                    stored_state = self.r.json().get(redis_key, '$')
                    if stored_state and isinstance(stored_state, list) and len(stored_state) > 0:
                        return stored_state[0] # returneturn the first (and ONLYY!!!) JSON document
                else:
                # hmm if redisjson doesntwork parse manually the json
                    stored_json_string = self.r.get(redis_key)
                    if stored_json_string:
                        return json.loads(stored_json_string)
            except Exception as e:
                print(f"Error retrieving state for {user_id} from Redis: {e}. Returning default state.")
            # show the error but it doesnr crash because the fallbacck parser is there

        # if redis is not connected, or an error occurred, or no state found, return default
        # also lets handle the case where self._in_memory_sessions might not be initialized if redi was the first posible oath
        if not self.r and hasattr(self, '_in_memory_sessions'):
            return self._in_memory_sessions.get(user_id, default_state).copy()
        
        return default_state.copy() # a copy of default if no state found in Redis or in-memory fallback
        
    def update_session_state(self, user_id: str, state: dict, user_message: str, chosen_action: dict = None):
        '''
        Mainly for updating the session state in Redis and just keep the long term relevant data into postgresql
        
        args: the users id, the state, the message from the user and the chosen action from the agent
        '''
        #update flags
        if state["entities"].get("email") or state["entities"].get("phone_number"):
            state["contact_info_provided"] = True
        if state["entities"].get("policy_number"):
            state["policy_number_provided"] = True
        if state["entities"].get("vehicle_make") and \
        state["entities"].get("vehicle_model") and \
        state["entities"].get("vehicle_year"):
            state["vehicle_details_provided"] = True
            
        #update convo summary for the state in redis
        #also for the convo summary thata gonne be sent to human scale
        if "conversation_summary" not in state:
            state["conversation_summary"] = ""
        
        # get the user message  message to the summary
        state["conversation_summary"] += f"User: {user_message} | "
        
        # get agents message to the summary
        if chosen_action and chosen_action.get("message_to_customer"):
            state["conversation_summary"] += f"Agent: {chosen_action['message_to_customer']} | "
        elif chosen_action and chosen_action.get("message"): # Fallback for generic 'message' key
            state["conversation_summary"] += f"Agent: {chosen_action['message']} | "
        
        # now lets get back to REDIS 
        if self.r: # If Redis connection is active
            redis_key = self._get_redis_key(user_id)
            try:
                if self.redis_json_available:
                # first checking redisnjson client to set the entire state dictionary
                    self.r.json().set(redis_key, '.', state)
                else:
                # again a fallcbkack serialize the dictionary to a JSON string and store it
                    self.r.set(redis_key, json.dumps(state))
                print(f"Session state updated for user {user_id} in Redis. Status: {state.get('status')}")
            except Exception as e:
                print(f"Error updating state for {user_id} in Redis: {e}. Data not persisted to Redis.")
                # or fallback to in-memory if Redis update fails
                if not hasattr(self, '_in_memory_sessions'): #
                    self._in_memory_sessions = {}
                self._in_memory_sessions[user_id] = state
        else:
        # if  Redis connection failed in __init__, use in-memory fallback
            if not hasattr(self, '_in_memory_sessions'): # Ensure fallback dict exists
                self._in_memory_sessions = {}
            self._in_memory_sessions[user_id] = state
            print(f"Session state updated for user {user_id} in-memory. Status: {state.get('status')}")

        # now persisten memory in postgresql
        if self.pg_conn: # if postgres is alive and connected 
            try:
                with self.pg_conn.cursor() as cur:
                    # 1. update or insert into user_profiles table (upsert)
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

                    # 2. put into conversation_log table (immutable record of this turn)
                    # log user's message
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
                            json.dumps(state.get("entities", {})), #  entities as JSONB
                            None # No action_type for user message
                        )
                    )
                    # log the agent action/message
                    if chosen_action:
                        cur.execute(
                            """
                            INSERT INTO conversation_log (user_id, role, message, intent, entities, action_type)
                            VALUES (%s, %s, %s, %s, %s, %s);
                            """,
                            (
                                user_id,
                                "agent", # role for the agent action/message
                                chosen_action.get("message_to_customer") or chosen_action.get("message"),
                                state.get("current_intent"), # agent action is based on current intent
                                json.dumps(state.get("entities", {})), # the entities relevant to aagent action
                                chosen_action.get("action_type")
                            )
                        )
                print(f"Long-term data updated for user {user_id} in PostgreSQL.")
            except psycopg2.Error as e:
                print(f"ERROR: Could not persist long-term data for {user_id} to PostgreSQL: {e}")
        else:
            print(f"PostgreSQL not connected. Long-term data for {user_id} not persisted.")
