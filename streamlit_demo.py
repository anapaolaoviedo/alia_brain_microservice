# streamlit_brain_demo.py
import streamlit as st
import os
import json
import psycopg2
import redis
import time
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- CUSTOM CSS STYLING ---
def load_css():
    st.markdown("""
    <style>
    /* Import Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    /* Global Styling */
    .stApp {
        font-family: 'Inter', sans-serif;
    }
    
    /* Header Styling */
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem 1.5rem;
        border-radius: 15px;
        margin-bottom: 2rem;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
    }
    
    .main-header h1 {
        color: white;
        font-size: 2.5rem;
        font-weight: 700;
        margin: 0;
        text-align: center;
    }
    
    .main-header p {
        color: rgba(255, 255, 255, 0.9);
        font-size: 1.1rem;
        margin: 0.5rem 0 0 0;
        text-align: center;
    }
    
    /* Chat Container */
    .chat-container {
        background: transparent;
        border-radius: 15px;
        padding: 1rem;
        margin-bottom: 2rem;
        min-height: 300px;
    }
    
    /* Message Styling */
    .user-message {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 20px 20px 5px 20px;
        margin: 0.5rem 0;
        max-width: 80%;
        margin-left: auto;
        box-shadow: 0 2px 10px rgba(102, 126, 234, 0.3);
    }
    
    .assistant-message {
        background: linear-gradient(135deg, #f8f9ff 0%, #e8eeff 100%);
        color: #2d3748;
        padding: 1rem 1.5rem;
        border-radius: 20px 20px 20px 5px;
        margin: 0.5rem 0;
        max-width: 80%;
        border-left: 4px solid #667eea;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);
    }
    
    /* Status Cards */
    .status-card {
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 2px 15px rgba(0, 0, 0, 0.08);
        margin-bottom: 1rem;
        border-left: 4px solid #667eea;
    }
    
    .status-card h3 {
        color: #2d3748;
        font-size: 1.2rem;
        font-weight: 600;
        margin: 0 0 1rem 0;
    }
    
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 12px;
        text-align: center;
        margin: 0.5rem 0;
    }
    
    .metric-card h2 {
        font-size: 2rem;
        font-weight: 700;
        margin: 0;
    }
    
    .metric-card p {
        margin: 0.5rem 0 0 0;
        opacity: 0.9;
    }
    
    /* Sidebar Styling */
    .css-1d391kg {
        background: linear-gradient(180deg, #f8f9ff 0%, #ffffff 100%);
    }
    
    /* Button Styling */
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 25px;
        padding: 0.5rem 2rem;
        font-weight: 600;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
    }
    
    /* Loading Spinner */
    .stSpinner > div {
        border-top-color: #667eea !important;
    }
    
    /* Chat Input */
    .stChatInput > div > div > textarea {
        border-radius: 25px;
        border: 2px solid #e2e8f0;
        padding: 1rem 1.5rem;
        font-size: 1rem;
    }
    
    .stChatInput > div > div > textarea:focus {
        border-color: #667eea;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
    }
    
    /* JSON Display */
    .json-container {
        background: #f7fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
    }
    
    /* Success/Error Messages */
    .success-message {
        background: linear-gradient(135deg, #48bb78 0%, #38a169 100%);
        color: white;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    
    .error-message {
        background: linear-gradient(135deg, #f56565 0%, #e53e3e 100%);
        color: white;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    
    /* Responsive Design */
    @media (max-width: 768px) {
        .main-header h1 {
            font-size: 2rem;
        }
        
        .user-message, .assistant-message {
            max-width: 95%;
        }
    }
    </style>
    """, unsafe_allow_html=True)

# --- BRAIN COMPONENTS IMPORTS ---
try:
    from decision_engine import DecisionEngine
except ImportError:
    DecisionEngine = None

# --- DATABASE CONNECTION HELPERS ---
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

@st.cache_resource
def initialize_brain():
    """Initializes and returns the DecisionEngine instance."""
    if DecisionEngine:
        return DecisionEngine()
    return None

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="BRAIN Demo",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load custom CSS
load_css()

# --- HEADER SECTION ---
st.markdown("""
<div class="main-header">
    <h1>🧠 BRAIN Demo</h1>
    <p>Agente de IA inteligente para renovación de garantías • Construido con primeros principios</p>
    <p>By Ana Paola Oviedo</p>
</div>
""", unsafe_allow_html=True)

# --- MAIN LAYOUT ---
col1, col2 = st.columns([3, 1])

with col1:
    # Initialize session state
    if "history" not in st.session_state:
        st.session_state.history = []

    if "session_id" not in st.session_state:
        st.session_state.session_id = f"st_user_{int(time.time())}"

    # Chat Container
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    
    # Display chat messages from history
    if st.session_state.history:
        for i, message in enumerate(st.session_state.history):
            if message["role"] == "user":
                st.markdown(f"""
                <div class="user-message">
                    <strong>Tú:</strong> {message["content"]}
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="assistant-message">
                    <strong>🧠 BRAIN:</strong> {message["content"]}
                </div>
                """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="text-align: center; padding: 2rem 1rem; color: #718096; background: rgba(255, 255, 255, 0.7); border-radius: 15px; margin: 1rem 0;">
            <h3 style="color: #4a5568; margin-bottom: 1rem;">👋 ¡Bienvenido al asistente BRAIN!</h3>
            <p style="margin: 0;">Comienza una conversación escribiendo un mensaje abajo.</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

    # Chat Input
    if prompt := st.chat_input("💬 Escribe tu mensaje aquí..."):
        # Add user message to history
        st.session_state.history.append({"role": "user", "content": prompt})

        # Get BRAIN's response
        brain = initialize_brain()
        if brain:
            with st.spinner("🧠 BRAIN está procesando tu solicitud..."):
                try:
                    response = brain.decide(st.session_state.session_id, prompt)
                    message_content = response.get("message_to_customer", response.get("message", "Lo siento, no pude procesar tu solicitud."))
                    
                    # Add BRAIN's message to history
                    st.session_state.history.append({"role": "assistant", "content": message_content})
                    
                    # Rerun to show the new messages
                    st.rerun()
                    
                except Exception as e:
                    error_message = f"Error al procesar la solicitud: {str(e)}"
                    st.session_state.history.append({"role": "assistant", "content": error_message})
                    st.rerun()
        else:
            error_message = "⚠️ BRAIN no está disponible en este momento. Por favor, verifica la configuración del servidor."
            st.session_state.history.append({"role": "assistant", "content": error_message})
            st.rerun()

with col2:
    # Session Info
    st.markdown(f"""
    <div class="status-card">
        <h3>📊 Información de Sesión</h3>
        <p><strong>ID de Sesión:</strong><br><code>{st.session_state.session_id}</code></p>
        <p><strong>Mensajes:</strong> {len(st.session_state.history)}</p>
        <p><strong>Hora de inicio:</strong> {datetime.now().strftime("%H:%M:%S")}</p>
    </div>
    """, unsafe_allow_html=True)

    # System Status
    brain_status = "🟢 Conectado" if initialize_brain() else "🔴 Desconectado"
    st.markdown(f"""
    <div class="status-card">
        <h3>🔧 Estado del Sistema</h3>
        <p><strong>BRAIN Engine:</strong> {brain_status}</p>
        <p><strong>Base de datos:</strong> Configurada</p>
        <p><strong>Redis:</strong> Activo</p>
    </div>
    """, unsafe_allow_html=True)

# --- SIDEBAR FOR DEBUGGING ---
st.sidebar.markdown("## 🔍 Panel de Desarrollo")
st.sidebar.markdown("---")

# Clear Chat Button
if st.sidebar.button("🗑️ Limpiar Conversación", help="Elimina todo el historial de chat"):
    st.session_state.history = []
    st.rerun()

# New Session Button
if st.sidebar.button("🆕 Nueva Sesión", help="Inicia una nueva sesión con ID único"):
    st.session_state.session_id = f"st_user_{int(time.time())}"
    st.session_state.history = []
    st.success("¡Nueva sesión iniciada!")
    st.rerun()

st.sidebar.markdown("---")

# Backend State Expander
with st.sidebar.expander("🗄️ Estado de Base de Datos", expanded=False):
    if st.button("📊 Actualizar Estado", key="refresh_state"):
        user_id = st.session_state.session_id
        
        # Redis Data
        st.markdown("**💾 Redis (Memoria a Corto Plazo):**")
        redis_data = get_redis_state(user_id)
        if "error" in redis_data:
            st.markdown(f'<div class="error-message">❌ {redis_data["error"]}</div>', unsafe_allow_html=True)
        else:
            if redis_data:
                st.json(redis_data)
            else:
                st.info("No hay datos en Redis para esta sesión")
        
        st.markdown("---")
        
        # PostgreSQL Data
        st.markdown("**🐘 PostgreSQL (Memoria a Largo Plazo):**")
        pg_data = get_postgres_data(user_id)
        if "error" in pg_data:
            st.markdown(f'<div class="error-message">❌ {pg_data["error"]}</div>', unsafe_allow_html=True)
        else:
            if pg_data["profile"]:
                st.markdown("**👤 Perfil de Usuario:**")
                st.code(str(pg_data["profile"]), language="python")
            else:
                st.info("No hay perfil de usuario")
            
            if pg_data["logs"]:
                st.markdown("**📝 Registro de Conversación:**")
                for i, log in enumerate(pg_data["logs"][-5:]):  # Show last 5 logs
                    timestamp = log[1].strftime('%H:%M:%S') if len(log) > 1 else "N/A"
                    content = log[3][:50] + "..." if len(log) > 3 and len(str(log[3])) > 50 else str(log[3])
                    st.text(f"{i+1}. [{timestamp}] {content}")
            else:
                st.info("No hay registros de conversación")

# Development Tools
with st.sidebar.expander("🛠️ Herramientas de Desarrollo", expanded=False):
    st.markdown("**Configuración de Entorno:**")
    env_vars = {
        "REDIS_HOST": REDIS_HOST,
        "REDIS_PORT": REDIS_PORT,
        "PG_HOST": PG_HOST,
        "PG_DATABASE": PG_DATABASE,
        "PG_USER": PG_USER
    }
    
    for key, value in env_vars.items():
        st.text(f"{key}: {value}")
    
    if st.button("🧪 Test Conexiones"):
        # Test Redis
        try:
            r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
            r.ping()
            st.success("✅ Redis conectado")
        except Exception as e:
            st.error(f"❌ Redis error: {e}")
        
        # Test PostgreSQL
        try:
            conn = psycopg2.connect(
                host=PG_HOST, database=PG_DATABASE, user=PG_USER, password=PG_PASSWORD
            )
            conn.close()
            st.success("✅ PostgreSQL conectado")
        except Exception as e:
            st.error(f"❌ PostgreSQL error: {e}")

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("🚀 **BRAIN v1.0** - Hecho con ❤️")
st.sidebar.markdown("💡 *Powered by Streamlit & AI*")