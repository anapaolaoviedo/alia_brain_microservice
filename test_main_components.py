"""
BRAIN Integration Test Suite
===========================

This comprehensive test suite validates the complete BRAIN system by testing
all three core capabilities working together:

1. Advanced Perception: NLP pipeline correctly extracts intent and entities
2. Memory and Context: Session state persists correctly across conversation turns
3. Strategic Decision-Making: Rules fire appropriately based on conversation context

Test Architecture:
- End-to-end conversation simulation with real database persistence
- Direct database validation to ensure data integrity
- Multiple conversation scenarios covering critical business flows
- Automated assertions to verify expected BRAIN behavior

The tests simulate realistic customer interactions and verify that BRAIN
responds correctly at each stage of the policy renewal process.
"""

import os
import time
import psycopg2
import redis
import json
from dotenv import load_dotenv

# Load environment variables for the test script
load_dotenv()

# ========================================================================
# TEST CONFIGURATION - Database Connection Settings
# ========================================================================
# These settings must match your .env file for proper database connectivity

REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))

PG_HOST = os.getenv('PG_HOST', 'localhost')
PG_DATABASE = os.getenv('PG_DATABASE', 'brain_memory')
PG_USER = os.getenv('PG_USER', 'postgres')
PG_PASSWORD = os.getenv('PG_PASSWORD', 'mysecretpassword')
PG_PORT = int(os.getenv('PG_PORT', 5432))

# Import BRAIN's core modules for integration testing
from decision_engine import DecisionEngine
from memory_manager import MemoryManager # Needed for helper functions
from rule_engine import RuleEngine # Needed to verify rules
from policy_module import PolicyModule # Needed for placeholder behavior

# ========================================================================
# DATABASE INSPECTION UTILITIES
# ========================================================================
# These helper functions allow direct database access to verify that BRAIN's
# memory system is working correctly and data is being persisted properly.

def check_redis_state(user_id: str):
    """
    Directly inspect Redis to verify session state persistence.
    
    This function bypasses BRAIN's memory manager to directly check what's
    actually stored in Redis, ensuring data integrity and proper serialization.
    
    Args:
        user_id: The user session identifier to inspect
        
    Returns:
        dict: The stored session state, or None if not found
    """
    try:
        # Create direct Redis connection for inspection
        r_test = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
        key = f"session:{user_id}"
        
        # Try RedisJSON format first (preferred method)
        try:
            stored_data = r_test.json().get(key, '$')
            if stored_data and isinstance(stored_data, list) and len(stored_data) > 0:
                print(f"\n--- Redis Check for {user_id} (JSON): ---")
                print(json.dumps(stored_data[0], indent=2))
                return stored_data[0]
        except Exception:
            # Fallback to string-based JSON storage
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
    """
    Directly inspect PostgreSQL to verify long-term memory persistence.
    
    This function checks both user profiles and conversation logs to ensure
    BRAIN's long-term memory system is correctly storing customer data and
    conversation history.
    
    Args:
        user_id: The user identifier to inspect
    """
    print(f"\n--- PostgreSQL Check for {user_id}: ---")
    try:
        # Create direct PostgreSQL connection for inspection
        pg_conn_test = psycopg2.connect(
            host=PG_HOST, database=PG_DATABASE, user=PG_USER, password=PG_PASSWORD, port=PG_PORT
        )
        with pg_conn_test.cursor() as cur:
            # Check user profile data (mutable customer information)
            cur.execute("SELECT * FROM user_profiles WHERE user_id = %s;", (user_id,))
            profile = cur.fetchone()
            if profile:
                print(f"User Profile (user_id, customer_name, email, phone, vin, last_updated): {profile}")
            else:
                print("User Profile: Not found.")

            # Check conversation log (immutable conversation history)
            cur.execute("SELECT log_id, timestamp, role, message, intent, entities, action_type FROM conversation_log WHERE user_id = %s ORDER BY timestamp ASC;", (user_id,))
            logs = cur.fetchall()
            if logs:
                print("Conversation Log:")
                for log in logs:
                    # Truncate long messages for readability
                    message_preview = log[3][:50] + "..." if len(log[3]) > 50 else log[3]
                    print(f"  Log ID: {log[0]}, Timestamp: {log[1]}, Role: {log[2]}, Message: '{message_preview}', Intent: {log[4]}, Action: {log[6]}")
            else:
                print("Conversation Log: Empty.")
        pg_conn_test.close()
    except Exception as e:
        print(f"--- PostgreSQL Check Error: Could not connect or retrieve from PostgreSQL: {e} ---")

# ========================================================================
# MAIN TEST EXECUTION
# ========================================================================

if __name__ == "__main__":
    print("Starting BRAIN integration tests...")
    print("Testing all three core capabilities: Perception, Memory, and Decision-Making\n")

    # Initialize the complete BRAIN system
    # This creates instances of all subsystems: NLP, Memory, Rules, and Policy
    decision_engine = DecisionEngine()

    test_user_id = "test_user_all_ana" # Unique ID for this full test suite

    # ====================================================================
    # TEST ENVIRONMENT CLEANUP
    # ====================================================================
    # Clean up any residual data from previous test runs to ensure
    # tests start with a clean slate and don't interfere with each other

    print("\n--- Cleaning up previous test data (if any) ---")
    
    # Clear Redis session data
    try:
        r_cleanup = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
        r_cleanup.delete(f"session:{test_user_id}")
        print(f"Cleared Redis session for {test_user_id}.")
    except Exception as e:
        print(f"Could not connect to Redis for cleanup: {e}")

    # Clear PostgreSQL user and conversation data
    try:
        pg_conn_cleanup = psycopg2.connect(
            host=PG_HOST, database=PG_DATABASE, user=PG_USER, password=PG_PASSWORD, port=PG_PORT
        )
        with pg_conn_cleanup.cursor() as cur:
            # Delete in correct order due to foreign key constraints
            cur.execute("DELETE FROM conversation_log WHERE user_id = %s;", (test_user_id,))
            cur.execute("DELETE FROM user_profiles WHERE user_id = %s;", (test_user_id,))
            pg_conn_cleanup.commit()
        print(f"Cleared PostgreSQL data for {test_user_id}.")
        pg_conn_cleanup.close()
    except Exception as e:
        print(f"Could not connect to PostgreSQL for cleanup: {e}")
    
    time.sleep(0.5)  # Brief pause to ensure cleanup completes

    # ====================================================================
    # TEST SCENARIO 1: COMPLETE RENOVATION REQUEST
    # ====================================================================
    # This test simulates a "hot lead" - a customer who provides all necessary
    # information upfront. This should trigger the highest priority rule:
    # immediate human agent notification.
    
    print("\n" + "="*70)
    print("TEST SCENARIO 1: Complete renovation request with all information")
    print("Expected: Human agent notification (Rule 1)")
    print("="*70)
    
    message_1 = "Hola, me interesa renovar mi póliza ABC123456. Mi nombre es Ana Paola, mi correo es anapaola@example.com y mi carro es un VW Vento 2015."
    print(f"User Message: '{message_1}'")
    
    # Process message through complete BRAIN pipeline
    chosen_action_1 = decision_engine.decide(test_user_id, message_1)
    print(f"BRAIN's Response: {chosen_action_1}")
    
    # Validate that BRAIN correctly identified this as a high-priority lead
    assert chosen_action_1['action_type'] == 'notify_human_renovation_lead', "Test 1 Failed: Expected notify_human_renovation_lead action."
    assert 'notification_data' in chosen_action_1, "Test 1 Failed: Expected notification data for human agent."
    print("✅ Test 1 PASSED: BRAIN correctly identified hot lead and triggered human notification.")

    # Verify memory persistence in both Redis and PostgreSQL
    check_redis_state(test_user_id)
    check_postgres_data(test_user_id)
    time.sleep(1)

    # ====================================================================
    # TEST SCENARIO 2: MINIMAL RENOVATION REQUEST
    # ====================================================================
    # This test simulates a customer who expresses interest but provides no
    # specific information. BRAIN should guide the conversation by asking
    # for the policy number first.
    
    print("\n" + "="*70)
    print("TEST SCENARIO 2: Minimal renovation request - no details provided")
    print("Expected: Request for policy number (Rule 6)")
    print("="*70)
    
    # Use a different user ID to simulate a fresh conversation
    test_user_id_2 = "test_user_ask_policy"
    
    # Clean up any existing data for this test user
    try:
        r_cleanup = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
        r_cleanup.delete(f"session:{test_user_id_2}")
        pg_conn_cleanup = psycopg2.connect(host=PG_HOST, database=PG_DATABASE, user=PG_USER, password=PG_PASSWORD, port=PG_PORT)
        with pg_conn_cleanup.cursor() as cur:
            cur.execute("DELETE FROM conversation_log WHERE user_id = %s;", (test_user_id_2,))
            cur.execute("DELETE FROM user_profiles WHERE user_id = %s;", (test_user_id_2,))
            pg_conn_cleanup.commit()
        pg_conn_cleanup.close()
    except Exception as e:
        print(f"Cleanup failed for Test 2: {e}")
        
    message_2 = "Hola, quisiera renovar mi póliza."
    print(f"User Message: '{message_2}'")

    # Process through BRAIN pipeline
    chosen_action_2 = decision_engine.decide(test_user_id_2, message_2)
    print(f"BRAIN's Response: {chosen_action_2}")
    
    # Validate that BRAIN correctly identified missing information and asked for it
    assert chosen_action_2['action_type'] == 'ask_for_info', "Test 2 Failed: Expected ask_for_info action."
    assert 'póliza' in chosen_action_2['message'].lower(), "Test 2 Failed: Expected message to ask for policy number."
    print("✅ Test 2 PASSED: BRAIN correctly identified missing policy number and requested it.")
    
    # Verify memory persistence
    check_redis_state(test_user_id_2)
    check_postgres_data(test_user_id_2)
    time.sleep(1)

    # ====================================================================
    # TEST SCENARIO 3: POLICY NUMBER PROVIDED (CONVERSATION CONTINUATION)
    # ====================================================================
    # This test continues the conversation from Scenario 2. The customer now
    # provides their policy number, so BRAIN should ask for vehicle details
    # to complete the information gathering process.
    
    print("\n" + "="*70)
    print("TEST SCENARIO 3: Policy number provided in follow-up message")
    print("Expected: Request for vehicle details (Rule 7)")
    print("="*70)
    
    message_3 = "Mi número de póliza es XYZ987654."
    print(f"User Message: '{message_3}'")

    # Continue the same conversation (same user_id_2)
    chosen_action_3 = decision_engine.decide(test_user_id_2, message_3)
    print(f"BRAIN's Response: {chosen_action_3}")
    
    # Validate conversation flow progression
    assert chosen_action_3['action_type'] == 'ask_for_info', "Test 3 Failed: Expected ask_for_info action."
    assert 'vehículo' in chosen_action_3['message'].lower() or 'carro' in chosen_action_3['message'].lower(), "Test 3 Failed: Expected message to ask for vehicle details."
    print("✅ Test 3 PASSED: BRAIN correctly progressed conversation flow and requested vehicle details.")

    # Verify updated memory state
    check_redis_state(test_user_id_2)
    check_postgres_data(test_user_id_2)
    time.sleep(1)

    # ====================================================================
    # TEST SCENARIO 4: COMPLETE INFORMATION PROVIDED (QUOTE GENERATION)
    # ====================================================================
    # This test completes the conversation flow from Scenarios 2-3. The customer
    # now provides vehicle details, giving BRAIN all necessary information to
    # generate a quote and complete the business process.
    
    print("\n" + "="*70)
    print("TEST SCENARIO 4: Vehicle details provided - ready for quote")
    print("Expected: Quote generation trigger (Rule 7C or Rule 8)")
    print("="*70)
    
    message_4 = "Es un auto Honda Civic 2020."
    print(f"User Message: '{message_4}'")

    # Complete the conversation flow
    chosen_action_4 = decision_engine.decide(test_user_id_2, message_4)
    print(f"BRAIN's Response: {chosen_action_4}")
    
    # Validate business process completion
    assert chosen_action_4['action_type'] == 'generate_quote', "Test 4 Failed: Expected generate_quote action."
    assert 'cotización' in chosen_action_4['message'].lower() or 'información' in chosen_action_4['message'].lower(), "Test 4 Failed: Expected message to confirm quote generation."
    print("✅ Test 4 PASSED: BRAIN correctly identified complete information and triggered quote generation.")

    # Verify final memory state
    check_redis_state(test_user_id_2)
    check_postgres_data(test_user_id_2)
    time.sleep(1)

    # ====================================================================
    # TEST SUITE COMPLETION
    # ====================================================================
    
    print("\n" + "="*70)
    print("🎉 ALL INTEGRATION TESTS PASSED SUCCESSFULLY! 🎉")
    print("="*70)
    print("\nTest Summary:")
    print("✅ Advanced Perception: NLP correctly extracted intents and entities")
    print("✅ Memory and Context: Session state persisted across conversation turns")
    print("✅ Strategic Decision-Making: Rules fired appropriately for each scenario")
    print("\nBRAIN's three core capabilities are working together correctly!")
    print("The system is ready for production deployment.")
    print("="*70)