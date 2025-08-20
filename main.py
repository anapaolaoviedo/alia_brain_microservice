"""
BRAIN - AI Assistant API Server
===============================

This is the main FastAPI server for BRAIN, an AI system inspired by human brain architecture.
BRAIN provides three core capabilities:
1. Advanced Perception - Accurately understands customer messages and intent
2. Memory and Context - Maintains conversation context across multiple interactions  
3. Strategic Decision-Making - Makes rule-based decisions for business actions

This server handles incoming webhook messages and will route them through BRAIN's
processing pipeline once fully integrated.

ARCHITECTURE OVERVIEW:
- This is BRAIN's "nervous system" - the interface between external world and internal processing
- Built on FastAPI for high performance and automatic API documentation
- Designed as a webhook receiver that integrates with platforms like Make.com, Zapier, etc.
- Stateless design: each request is independent, state is managed by BRAIN's internal components
"""

# CORE FRAMEWORK IMPORTS
# FastAPI: Modern, fast web framework for building APIs with automatic docs and validation
from fastapi import FastAPI  # Main application framework
from fastapi import Request   # For accessing raw request data (future use)

# DATA VALIDATION
# Pydantic: Automatic data validation, serialization, and documentation
from pydantic import BaseModel  # For defining request/response data structures

# BRAIN CORE SYSTEM (Currently commented out for initial deployment)
# This will be the main integration point once BRAIN's internal systems are ready
#from decision_engine import Decide 

# APPLICATION INITIALIZATION
# =========================
# Initialize FastAPI application instance
# FastAPI automatically generates OpenAPI docs and handles JSON serialization/validation
app = FastAPI()

# DATA MODELS
# ===========
# Pydantic model for incoming JSON payload validation
# Ensures all webhook requests contain required user_id and message fields
# 
# WHY PYDANTIC: 
# - Automatic validation prevents malformed requests from crashing the server
# - Generates automatic API documentation showing required fields
# - Provides clear error messages when requests are invalid
# - Ensures type safety throughout the application
class MessageInput(BaseModel):
    """
    Data structure for incoming webhook messages.
    
    This defines the contract between external systems (like Make.com) and BRAIN.
    All incoming messages must conform to this structure.
    
    REAL-WORLD EXAMPLE:
    When a customer sends "I need to renew my policy" via WhatsApp:
    - Make.com captures the message and phone number
    - Formats it as: {"user_id": "+1234567890", "message": "I need to renew my policy"}
    - Sends it to this /webhook endpoint
    """
    user_id: str    # Unique identifier for the customer/user sending the message
                   # Examples: phone number ("+1234567890"), session ID ("sess_abc123"), 
                   # or any unique customer identifier from the source platform
                   
    message: str    # The actual message content to be processed by BRAIN
                   # Examples: "I want a quote", "My car was in an accident", "What's my policy number?"

# API ENDPOINTS
# =============

# Root endpoint - basic server identification
@app.get("/")
def root():
    """
    Simple root endpoint that confirms the BRAIN server is running.
    Used for basic connectivity testing and server identification.
    
    TECHNICAL PURPOSE: Provides a simple way to verify the server is responding
    BUSINESS PURPOSE: Allows external systems to confirm BRAIN is available
    INTEGRATION USE: Make.com and other platforms can ping this to check server status
    
    Returns:
        dict: Simple confirmation message that BRAIN is operational
    """
    return {"message": "Hello from BRAIN!"}

# Health check endpoint for monitoring and load balancers
@app.get("/health")
async def health():
    """
    Health check endpoint for system monitoring.
    Returns server status - can be extended to check database connections,
    external service availability, etc.
    
    DEVOPS PURPOSE: 
    - Load balancers use this to determine if server should receive traffic
    - Monitoring systems can alert if this endpoint starts failing
    - Container orchestration (Docker/Kubernetes) uses this for health checks
    
    BUSINESS VALUE:
    - Ensures customers always reach a healthy BRAIN instance
    - Enables automatic failover and scaling based on server health
    - Provides early warning of system issues before they affect customers
    
    FUTURE ENHANCEMENTS:
    - Check database connectivity
    - Verify external API availability (NLP services, etc.)
    - Monitor memory usage and performance metrics
    - Validate BRAIN subsystem status
    
    Returns:
        dict: Health status information
    """
    return {"status": "BRAIN is alive and ready."}

# Main webhook endpoint - this is where customer messages are received and processed
@app.post("/webhook") 
async def webhook(input: MessageInput):
    """
    Primary webhook endpoint for processing incoming customer messages.
    
    This is BRAIN's main "sensory input" - where all customer interactions begin.
    
    CURRENT BEHAVIOR:
    1. Receives validated JSON payload with user_id and message
    2. Currently logs the incoming message for debugging
    3. Returns a placeholder response (will be replaced with BRAIN processing)
    
    INTEGRATION WORKFLOW:
    1. Customer sends message via WhatsApp/SMS/Chat
    2. Platform (Make.com) captures message and customer ID
    3. Platform formats as JSON and POSTs to this webhook
    4. BRAIN processes message and returns action/response
    5. Platform executes the action (send message, update CRM, etc.)
    
    FUTURE INTEGRATION (when decision_engine is connected):
    - Pass message through BRAIN's perception layer for intent analysis
    - Maintain conversation context using user_id as session identifier  
    - Apply decision-making rules to determine appropriate response/action
    - Return intelligent, contextual responses to customers
    
    EXAMPLE FLOW:
    Input:  {"user_id": "+1234567890", "message": "I need car insurance"}
    →       BRAIN processes intent: "get_quote", entities: {}
    →       BRAIN applies rules: "need vehicle info for quotes"  
    Output: {"action": "ask_vehicle_info", "message": "What car do you need to insure?"}
    
    Args:
        input (MessageInput): Validated JSON payload containing user_id and message
                             Pydantic automatically validates this matches our schema
    
    Returns:
        dict: Response object that external system will process
              Currently returns simple reply, will return complex actions once integrated
    
    ERROR HANDLING:
    - Pydantic automatically returns 422 error for invalid JSON structure
    - FastAPI handles JSON parsing errors automatically
    - Future: Will include BRAIN-specific error handling for processing failures
    """
    
    # STEP 1: LOG INCOMING MESSAGE
    # ===========================
    # Log incoming message for debugging and monitoring
    # This is critical during development and provides audit trail in production
    # 
    # DEVELOPMENT VALUE: Helps debug integration issues with external platforms
    # BUSINESS VALUE: Creates record of all customer interactions for analysis
    # COMPLIANCE VALUE: May be required for regulatory audit trails
    # 
    # TODO: Replace with proper logging system for production (structured logging, log levels, etc.)
    print(f"Received from user {input.user_id}: {input.message}")

    # STEP 2: PROCESS MESSAGE THROUGH BRAIN (Future Implementation)
    # ============================================================
    # This is where the magic will happen once BRAIN's decision engine is integrated
    # 
    # PLANNED INTEGRATION:
    # decision_engine = DecisionEngine()
    # brain_response = decision_engine.decide(input.user_id, input.message)
    # 
    # The brain_response will be a rich action object like:
    # {
    #   "action": "send_message",
    #   "message": "I'd be happy to help with your car insurance. What type of vehicle do you have?",
    #   "context": "collecting_vehicle_info",
    #   "confidence": 0.95
    # }

    # STEP 3: RETURN RESPONSE (Currently Placeholder)
    # ===============================================
    # Placeholder response - will be replaced with BRAIN's intelligent processing
    # Currently returns a simple Spanish greeting to confirm integration is working
    # 
    # TODO: Integrate with decision_engine.Decide() for actual AI responses
    # TODO: Handle different response types (messages, actions, escalations, etc.)
    # TODO: Include error handling for BRAIN processing failures
    reply = "Hola desde BRAIN. Integración exitosa "

    # STEP 4: FORMAT AND RETURN RESPONSE
    # ==================================
    # Return response in expected JSON format
    # External systems (Make.com) expect consistent response structure
    # 
    # CURRENT FORMAT: Simple reply string
    # FUTURE FORMAT: Rich action objects with multiple fields
    # 
    # EXAMPLES OF FUTURE RESPONSES:
    # {"action": "send_message", "message": "How can I help?", "next_step": "await_user_input"}
    # {"action": "generate_quote", "redirect_to": "quote_flow", "collected_data": {...}}
    # {"action": "escalate_human", "reason": "complex_claim", "priority": "urgent"}
    return {"reply": reply}

# SERVER CONFIGURATION NOTES:
# ===========================
# 
# DEPLOYMENT:
# - This server can be run with: uvicorn main:app --reload (development)
# - Production deployment typically uses Docker containers with proper logging
# - Reverse proxy (nginx) handles SSL termination and load balancing
# 
# SCALING:
# - FastAPI is async-capable, can handle thousands of concurrent connections
# - BRAIN's decision engine should be designed to be stateless for horizontal scaling
# - Database connections and external API calls should use connection pooling
# 
# SECURITY:
# - Add authentication/API keys for production webhook endpoints
# - Implement rate limiting to prevent abuse
# - Add input sanitization beyond basic validation
# - Use HTTPS only in production
# 
# MONITORING:
# - Add structured logging with correlation IDs
# - Implement metrics collection (response times, error rates, etc.)
# - Add distributed tracing for complex request flows
# - Monitor BRAIN subsystem health and performance