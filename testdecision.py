# test_decision_engine.py
import os
import time
import psycopg2
import redis
import json
from dotenv import load_dotenv

# Load environment variables for the test script
load_dotenv()

# --- Configuration (ensure these match your .env) ---
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
# Note: nlp_pipeline, rule_engine, policy_module are imported by DecisionEngine

# --- Helper Functions for Direct Database Checks (copied from test_memory_manager.py) ---
def check_redis_state(user_id: str):
    try:
        r_test = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
        key = f"session:{user_id}"
        try:
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
        else:
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
    print("Starting DecisionEngine integration tests...")

    # Initialize DecisionEngine (which initializes NLP, Memory, RuleEngine, PolicyModule)
    decision_engine = DecisionEngine()

    test_user_id = "test_user_integration_ana" # Unique ID for this test

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

    # --- Test Scenario 1: Initial Renovation Inquiry ---
    print("\n--- Test Scenario 1: Initial Renovation Inquiry ---")
    message_1 = "Hola, me interesa renovar mi póliza ABC123456. Mi nombre es Ana Paola, mi correo es anapaola@example.com y mi carro es un VW Vento 2015."
    print(f"User: '{message_1}'")
    
    # Call the decide method - this is the core integration test
    chosen_action_1 = decision_engine.decide(test_user_id, message_1)
    print(f"BRAIN's Action: {chosen_action_1}")

    # Verify state and logs after the first turn
    check_redis_state(test_user_id)
    check_postgres_data(test_user_id)
    time.sleep(1)

    # --- Test Scenario 2: Follow-up Message (Confirm Renovation) ---
    print("\n--- Test Scenario 2: Follow-up Message (Confirm Renovation) ---")
    message_2 = "Sí, confirmo la renovación. Proceda con el pago."
    print(f"User: '{message_2}'")

    # Call the decide method again - should use updated state from Redis
    chosen_action_2 = decision_engine.decide(test_user_id, message_2)
    print(f"BRAIN's Action: {chosen_action_2}")

    # Verify state and logs after the second turn
    check_redis_state(test_user_id)
    check_postgres_data(test_user_id)
    time.sleep(1)

    print("\nDecisionEngine integration tests finished.")
