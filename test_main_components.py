# test_all_components.py
import os
import time
import psycopg2
import redis
import json
from dotenv import load_dotenv

# Load environment variables for the test script
load_dotenv()

# --- Configuration for testing (ensure these match your .env) ---
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))

PG_HOST = os.getenv('PG_HOST', 'localhost')
PG_DATABASE = os.getenv('PG_DATABASE', 'brain_memory')
PG_USER = os.getenv('PG_USER', 'postgres')
PG_PASSWORD = os.getenv('PG_PASSWORD', 'mysecretpassword')
PG_PORT = int(os.getenv('PG_PORT', 5432))

# Import your core BRAIN modules
from decision_engine import DecisionEngine
from memory_manager import MemoryManager # Needed for helper functions
from rule_engine import RuleEngine # Needed to verify rules
from policy_module import PolicyModule # Needed for placeholder behavior

# --- Helper Functions for Direct Database Checks (from test_memory_manager.py) ---
def check_redis_state(user_id: str):
    """Directly checks Redis for a user's session state."""
    try:
        r_test = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
        key = f"session:{user_id}"
        
        try:
            stored_data = r_test.json().get(key, '$')
            if stored_data and isinstance(stored_data, list) and len(stored_data) > 0:
                print(f"\n--- Redis Check for {user_id} (JSON): ---")
                print(json.dumps(stored_data[0], indent=2))
                return stored_data[0]
        except Exception:
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
            cur.execute("SELECT * FROM user_profiles WHERE user_id = %s;", (user_id,))
            profile = cur.fetchone()
            if profile:
                print(f"User Profile (user_id, customer_name, email, phone, vin, last_updated): {profile}")
            else:
                print("User Profile: Not found.")

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
    print("Starting all components integration tests...")

    # Initialize DecisionEngine (which initializes all other modules)
    decision_engine = DecisionEngine()

    test_user_id = "test_user_all_ana" # Unique ID for this full test

    # --- Cleanup from previous runs (optional) ---
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
            pg_conn_cleanup.commit()
        print(f"Cleared PostgreSQL data for {test_user_id}.")
        pg_conn_cleanup.close()
    except Exception as e:
        print(f"Could not connect to PostgreSQL for cleanup: {e}")
    time.sleep(0.5)

    # --- Test Scenario 1: User starts with full renovation request (should trigger Rule 1: Human Notify) ---
    print("\n--- Test Scenario 1: Full renovation request, should trigger human notification ---")
    message_1 = "Hola, me interesa renovar mi póliza ABC123456. Mi nombre es Ana Paola, mi correo es anapaola@example.com y mi carro es un VW Vento 2015."
    print(f"User: '{message_1}'")
    
    chosen_action_1 = decision_engine.decide(test_user_id, message_1)
    print(f"BRAIN's Action: {chosen_action_1}")
    assert chosen_action_1['action_type'] == 'notify_human_renovation_lead', "Test 1 Failed: Expected notify_human_renovation_lead action."
    print("Test 1 Passed: Correctly identified a hot lead and is ready to notify a human.")

    check_redis_state(test_user_id)
    check_postgres_data(test_user_id)
    time.sleep(1)

    # --- Test Scenario 2: User asks for renewal, but provides no info (should trigger Rule 6: Ask for Policy) ---
    print("\n--- Test Scenario 2: User only asks to renew, should trigger policy number request ---")
    # Cleanup from previous scenario to simulate a new conversation with a different user
    test_user_id_2 = "test_user_ask_policy"
    try:
        r_cleanup = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
        r_cleanup.delete(f"session:{test_user_id_2}")
        pg_conn_cleanup = psycopg2.connect(host=PG_HOST, database=PG_DATABASE, user=PG_USER, password=PG_PASSWORD, port=PG_PORT)
        with pg_conn_cleanup.cursor() as cur:
            cur.execute("DELETE FROM conversation_log WHERE user_id = %s;", (test_user_id_2,))
            cur.execute("DELETE FROM user_profiles WHERE user_id = %s;", (test_user_id_2,))
            pg_conn_cleanup.commit()
    except Exception as e:
        print(f"Cleanup failed for Test 2: {e}")
        
    message_2 = "Hola, quisiera renovar mi póliza."
    print(f"User: '{message_2}'")

    chosen_action_2 = decision_engine.decide(test_user_id_2, message_2)
    print(f"BRAIN's Action: {chosen_action_2}")
    assert chosen_action_2['action_type'] == 'ask_for_info', "Test 2 Failed: Expected ask_for_info action."
    assert 'póliza' in chosen_action_2['message'].lower(), "Test 2 Failed: Expected message to ask for policy number."
    print("Test 2 Passed: Correctly asked for missing policy number.")
    
    check_redis_state(test_user_id_2)
    check_postgres_data(test_user_id_2)
    time.sleep(1)

    # --- Test Scenario 3: Follow-up from Scenario 2 (user gives policy, should ask for car details) ---
    print("\n--- Test Scenario 3: User provides policy number, should ask for car details ---")
    message_3 = "Mi número de póliza es XYZ987654."
    print(f"User: '{message_3}'")

    chosen_action_3 = decision_engine.decide(test_user_id_2, message_3)
    print(f"BRAIN's Action: {chosen_action_3}")
    assert chosen_action_3['action_type'] == 'ask_for_info', "Test 3 Failed: Expected ask_for_info action."
    assert 'vehículo' in chosen_action_3['message'].lower(), "Test 3 Failed: Expected message to ask for vehicle details."
    print("Test 3 Passed: Correctly asked for missing vehicle details.")

    check_redis_state(test_user_id_2)
    check_postgres_data(test_user_id_2)
    time.sleep(1)

    # --- Test Scenario 4: User gives all details (should trigger Rule 8: Ready for Quote) ---
    print("\n--- Test Scenario 4: User provides vehicle details, should be ready for quote ---")
    message_4 = "Es un auto Honda Civic 2020."
    print(f"User: '{message_4}'")

    chosen_action_4 = decision_engine.decide(test_user_id_2, message_4)
    print(f"BRAIN's Action: {chosen_action_4}")
    assert chosen_action_4['action_type'] == 'generate_quote', "Test 4 Failed: Expected generate_quote action."
    assert 'cotización' in chosen_action_4['message'].lower(), "Test 4 Failed: Expected message to confirm quote generation."
    print("Test 4 Passed: Correctly identified all information is present and is ready to generate a quote.")

    check_redis_state(test_user_id_2)
    check_postgres_data(test_user_id_2)
    time.sleep(1)

    print("\nAll integration tests passed successfully!")
