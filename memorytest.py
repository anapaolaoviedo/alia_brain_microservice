# test_memory.py

from memory_manager import ShortTermMemory

memory = ShortTermMemory()

user_id = "user123"
context_data = {
    "intent": "RenovatePolicy",
    "entities": {
        "policy_number": "ABC123456",
        "vehicle_make": "Toyota"
    }
}

# Store
memory.store_user_context(user_id, context_data)

# Retrieve
retrieved = memory.retrieve_user_context(user_id)
print("🔁 Retrieved:", retrieved)

# Clear
memory.clear_user_context(user_id)
print("✅ Cleared.")