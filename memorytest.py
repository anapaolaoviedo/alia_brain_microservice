# test_memory_manager.py
import os
import time
import psycopg2
import redis
import json # Ensure json is imported for dumps/loads if RedisJSON isn't used
from dotenv import load_dotenv # Load .env for test script too

'''
Purely to test that the states and memory storage is working.
'''

# Load environment variables from .env file for the test script
load_dotenv()

# --- Configuration for testing (ensure these match your .env or defaults) ---
# For Redis
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))

# For PostgreSQL
PG_HOST = os.getenv('PG_HOST', 'localhost')
PG_DATABASE = os.getenv('PG_DATABASE', 'brain_memory') # IMPORTANT: Use 'brain_memory' or 'brain_db' as per your setup
PG_USER = os.getenv('PG_USER', 'postgres') # Or your macOS username, or 'brain_user'
PG_PASSWORD = os.getenv('PG_PASSWORD', 'mysecretpassword') # Or your actual password
PG_PORT = int(os.getenv('PG_PORT', 5432))

# Import your actual MemoryManager class
from memory_manager import MemoryManager 

# --- Helper Functions for Direct Database Checks (for verification) ---

def check_redis_state(user_id: str):
    """Directly checks Redis for a user's session state."""
    try:
        r_test = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
        key = f"session:{user_id}"
        
        # Try JSON get first, then fallback to plain string get
        try:
            # Check if RedisJSON module is available on the server for this connection
            # This is a basic way to check, a more robust way is to query MODULE LIST
            # but for testing, this is usually sufficient.
            test_json_key = "temp_json_check"
            r_test.json().set(test_json_key, '.', {'test': 'value'})
            r_test.json().delete(test_json_key)
            redis_json_available_for_test = True
        except Exception:
            redis_json_available_for_test = False

        if redis_json_available_for_test:
            stored_data = r_test.json().get(key, '$')
            if stored_data and isinstance(stored_data, list) and len(stored_data) > 0:
                print(f"\n--- Redis Check for {user_id} (JSON): ---")
                print(json.dumps(stored_data[0], indent=2))
                return stored_data[0]
        else: # Fallback to plain GET if JSON module not available or error
            stored_data = r_test.get(key)
            if stored_data:
                print(f"\n--- Redis Check for {user_id} (String): ---")
                print(json.dumps(json.loads(stored_data), indent=2))
                return json.loads(stored_data)
        
        print(f"\n--- Redis Check for {user_id}: No data found. ---")
        return None
    except Exception as e:
        print(f"\n--- Redis Check Error: Could not connect or retrieve from Redis: {e} ---")
        return None

def check_postgres_data(user_id: str):
    """Directly checks PostgreSQL for user profile and conversation log."""
    print(f"\n--- PostgreSQL Check for {user_id}: ---")
    try:
        pg_conn_test = psycopg2.connect(
            host=PG_HOST, database=PG_DATABASE, user=PG_USER, password=PG_PASSWORD, port=PG_PORT
        )
        with pg_conn_test.cursor() as cur:
            # Check user_profiles
            cur.execute("SELECT * FROM user_profiles WHERE user_id = %s;", (user_id,))
            profile = cur.fetchone()
            if profile:
                print(f"User Profile (user_id, customer_name, email, phone, vin, last_updated): {profile}")
            else:
                print("User Profile: Not found.")

            # Check conversation_log
            cur.execute("SELECT log_id, timestamp, role, message, intent, entities, action_type FROM conversation_log WHERE user_id = %s ORDER BY timestamp ASC;", (user_id,))
            logs = cur.fetchall()
            if logs:
                print("Conversation Log:")
                for log in logs:
                    print(f"  Log ID: {log[0]}, Timestamp: {log[1]}, Role: {log[2]}, Message: '{log[3][:50]}...', Intent: {log[4]}, Action: {log[6]}")
            else:
                print("Conversation Log: Empty.")
        pg_conn_test.close()
    except Exception as e:
        print(f"--- PostgreSQL Check Error: Could not connect or retrieve from PostgreSQL: {e} ---")

# --- Main Test Execution ---

if __name__ == "__main__":
    print("Starting MemoryManager tests...")

    # Initialize MemoryManager
    # It will attempt to connect to Redis and PostgreSQL based on .env
    memory_manager = MemoryManager()

    test_user_id = "test_user_123_ana" # Using a unique ID for easier testing

    # --- Cleanup from previous runs (optional, but good for fresh tests) ---
    print("\n--- Cleaning up previous test data (if any) ---")
    try:
        r_cleanup = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
        r_cleanup.delete(f"session:{test_user_id}")
        print(f"Cleared Redis session for {test_user_id}.")
    except Exception as e:
        print(f"Could not connect to Redis for cleanup: {e}")

    try:
        pg_conn_cleanup = psycopg2.connect(
            host=PG_HOST, database=PG_DATABASE, user=PG_USER, password=PG_PASSWORD, port=PG_PORT
        )
        with pg_conn_cleanup.cursor() as cur:
            cur.execute("DELETE FROM conversation_log WHERE user_id = %s;", (test_user_id,))
            cur.execute("DELETE FROM user_profiles WHERE user_id = %s;", (test_user_id,))
            pg_conn_cleanup.commit() # Commit deletions
        print(f"Cleared PostgreSQL data for {test_user_id}.")
        pg_conn_cleanup.close()
    except Exception as e:
        print(f"Could not connect to PostgreSQL for cleanup: {e}")
    time.sleep(0.5) # Give a moment for cleanup to settle

    # --- Test Case 1: New User, Initial Message with Renovation Intent and Entities ---
    print("\n--- Test Case 1: New User, Initial Renovation Inquiry ---")
    initial_user_message = "Hola, me interesa renovar mi póliza ABC123456. Mi nombre es Ana Paola, mi correo es anapaola@example.com y mi carro es un VW Vento 2015."
    
    # Simulate percept data from NLP pipeline for the initial message
    initial_percept_data = {
        "intent": "RenovatePolicy",
        "entities": {
            "policy_number": "ABC123456",
            "customer_name": "Ana Paola",
            "email": "anapaola@example.com",
            "vehicle_make": "VW",
            "vehicle_model": "Vento",
            "vehicle_year": "2015"
        }
    }
    
    # Get initial state (should be default for a new user)
    current_state_1 = memory_manager.get_session_state(test_user_id)
    print(f"1. Initial state retrieved (should be default): {current_state_1['status']}")

    # Manually update state based on percept (as DecisionEngine would do)
    current_state_1["current_intent"] = initial_percept_data["intent"]
    current_state_1["entities"].update(initial_percept_data["entities"])
    # Flags will be updated by memory_manager.update_session_state, but we can set expected status
    current_state_1["status"] = "awaiting_quote_confirmation" # Assume all info gathered

    # Simulate chosen action (e.g., from RuleEngine)
    chosen_action_1 = {
        "action_type": "generate_quote",
        "message_to_customer": "Gracias Ana Paola. He recibido su solicitud. Su cotización para la renovación de su póliza ABC123456 es de $5000 MXN. ¿Desea confirmar la renovación?"
    }

    # Update session state in MemoryManager
    memory_manager.update_session_state(test_user_id, current_state_1, initial_user_message, chosen_action_1)
    print(f"2. State after 1st turn updated. Status: {memory_manager.get_session_state(test_user_id)['status']}")

    # Verify directly in databases
    check_redis_state(test_user_id)
    check_postgres_data(test_user_id)
    time.sleep(1) # Give a moment for DB writes to ensure they are visible

    # --- Test Case 2: Existing User, Follow-up Message (Confirm Renovation) ---
    print("\n--- Test Case 2: Existing User, Follow-up Message (Confirm Renovation) ---")
    follow_up_user_message = "Sí, confirmo la renovación. Proceda con el pago."
    
    # Simulate percept data from NLP pipeline for the follow-up message
    follow_up_percept_data = {
        "intent": "ConfirmRenovation",
        "entities": {} # No new entities in this message
    }

    # Get current state (should retrieve from Redis, containing previous info)
    current_state_2 = memory_manager.get_session_state(test_user_id)
    print(f"3. State retrieved for 2nd turn: {current_state_2['status']}")

    # Manually update state based on percept
    current_state_2["current_intent"] = follow_up_percept_data["intent"]
    current_state_2["status"] = "renovation_confirmed_awaiting_payment" # Update status

    # Simulate chosen action
    chosen_action_2 = {
        "action_type": "process_payment",
        "message_to_customer": "¡Excelente! Su renovación ha sido confirmada. Le enviaremos un enlace de pago en breve."
    }

    # Update session state in MemoryManager
    memory_manager.update_session_state(test_user_id, current_state_2, follow_up_user_message, chosen_action_2)
    print(f"4. State after 2nd turn updated. Status: {memory_manager.get_session_state(test_user_id)['status']}")

    # Verify directly in databases
    check_redis_state(test_user_id)
    check_postgres_data(test_user_id)
    time.sleep(1)

    # --- Test Case 3: Verify Persistence Across Runs ---
    print("\n--- Test Case 3: Verify Persistence (simulating new app run) ---")
    print("Re-initializing MemoryManager to simulate a new application start.")
    memory_manager_reinit = MemoryManager()
    persisted_state = memory_manager_reinit.get_session_state(test_user_id)
    print(f"5. State retrieved after re-initialization: {persisted_state['status']}")
    assert persisted_state['status'] == "renovation_confirmed_awaiting_payment", "Persistence test failed!"
    print("Persistence test successful: State was correctly retrieved from Redis after re-initialization.")

    # --- Test Case 4: Verify Fallback (Optional, manual test) ---
    print("\n--- Test Case 4: Verify Fallback (Optional, requires manual action) ---")
    print("To test fallback, manually stop Redis and/or PostgreSQL servers and re-run this script.")
    print("You should see 'ERROR: Could not connect...' messages and 'in-memory' updates.")

    print("\nMemoryManager tests finished.")

