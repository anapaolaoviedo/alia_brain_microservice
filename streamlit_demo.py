# streamlit_brain_demo.py

import streamlit as st
import os
import json
import psycopg2
import redis
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- BRAIN COMPONENTS IMPORTS ---
# We use try/except blocks here to allow the Streamlit app to run even if
# some components are missing (e.g., if you haven't written the final RuleEngine yet)
try:
    from decision_engine import DecisionEngine
except ImportError:
    st.error("Error: Could not import DecisionEngine. Please ensure your core BRAIN code is complete.")
    DecisionEngine = None

# --- DATABASE CONNECTION HELPERS (copied from your test scripts for direct access) ---

# Configuration for databases
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
PG_HOST = os.getenv('PG_HOST', 'localhost')
PG_DATABASE = os.getenv('PG_DATABASE', 'brain_memory')
PG_USER = os.getenv('PG_USER', 'postgres')
PG_PASSWORD = os.getenv('PG_PASSWORD', 'mysecretpassword')
PG_PORT = int(os.getenv('PG_PORT', 5432))

def get_redis_state(user_id: str):
    """Directly retrieves Redis state for the demo."""
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        key = f"session:{user_id}"
        stored_data = r.get(key)
        return json.loads(stored_data) if stored_data else {}
    except Exception as e:
        return {"error": f"Could not connect to Redis: {e}"}

def get_postgres_data(user_id: str):
    """Directly retrieves PostgreSQL data for the demo."""
    try:
        conn = psycopg2.connect(
            host=PG_HOST, database=PG_DATABASE, user=PG_USER, password=PG_PASSWORD
        )
        cur = conn.cursor()
        
        cur.execute("SELECT * FROM user_profiles WHERE user_id = %s;", (user_id,))
        profile = cur.fetchone()
        
        cur.execute("SELECT * FROM conversation_log WHERE user_id = %s ORDER BY timestamp ASC;", (user_id,))
        logs = cur.fetchall()
        
        conn.close()
        return {"profile": profile, "logs": logs}
    except Exception as e:
        return {"error": f"Could not connect to PostgreSQL: {e}"}

# --- STREAMLIT APP LOGIC ---

# Use Streamlit's caching to initialize the DecisionEngine only once
# This is crucial because Streamlit reruns the script on every user interaction
@st.cache_resource
def initialize_brain():
    """Initializes and returns the DecisionEngine instance."""
    if DecisionEngine:
        return DecisionEngine()
    return None

st.set_page_config(page_title="BRAIN Demo", page_icon="🧠")
st.title("BRAIN Demo: First-Principles AI Agent")
st.subheader("Simulate a conversation with the car insurance renovation agent.")

# Initialize session state for conversation history if it doesn't exist
if "history" not in st.session_state:
    st.session_state.history = []

if "session_id" not in st.session_state:
    st.session_state.session_id = f"st_user_{int(time.time())}"

# Display chat messages from history
for message in st.session_state.history:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# Main chat input for the user
if prompt := st.chat_input("Enter a message..."):
    # Display user message in chat message container
    with st.chat_message("user"):
        st.write(prompt)
    
    # Add user message to history
    st.session_state.history.append({"role": "user", "content": prompt})

    # Get BRAIN's response
    brain = initialize_brain()
    if brain:
        with st.spinner("BRAIN is thinking..."):
            # Call the DecisionEngine with the new message
            response = brain.decide(st.session_state.session_id, prompt)
            
            # Display BRAIN's message in chat message container
            with st.chat_message("assistant"):
                message_content = response.get("message_to_customer", response.get("message", "No response from BRAIN."))
                st.write(message_content)

            # Add BRAIN's message to history
            st.session_state.history.append({"role": "assistant", "content": message_content})
    else:
        with st.chat_message("assistant"):
            st.warning("BRAIN is not available. Check your server logs.")

# --- SIDEBAR FOR DEBUGGING AND DATABASE LOGS ---
st.sidebar.title("Debugging & Database View")

# Button to show backend data
if st.sidebar.button("Show Backend State"):
    st.sidebar.subheader(f"Session State for User: `{st.session_state.session_id}`")
    
    # Show Redis data
    redis_data = get_redis_state(st.session_state.session_id)
    if "error" in redis_data:
        st.sidebar.error(redis_data["error"])
    else:
        st.sidebar.markdown("**Redis (Short-Term Memory):**")
        st.sidebar.json(redis_data)
        
    # Show PostgreSQL data
    pg_data = get_postgres_data(st.session_state.session_id)
    if "error" in pg_data:
        st.sidebar.error(pg_data["error"])
    else:
        st.sidebar.markdown("**PostgreSQL (Long-Term Memory):**")
        st.sidebar.text("User Profile:")
        st.sidebar.text(pg_data["profile"])
        st.sidebar.text("\nConversation Log:")
        for log in pg_data["logs"]:
            st.sidebar.text(f"- {log[2]} ({log[1].strftime('%H:%M:%S')}): {log[3][:30]}...")

