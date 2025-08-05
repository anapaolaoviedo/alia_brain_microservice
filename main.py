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
"""

from fastapi import FastAPI
from fastapi import Request
from pydantic import BaseModel
#from decision_engine import Decide 

# Initialize FastAPI application instance
app = FastAPI()

# Pydantic model for incoming JSON payload validation
# Ensures all webhook requests contain required user_id and message fields
class MessageInput(BaseModel):
    user_id: str    # Unique identifier for the customer/user sending the message
    message: str    # The actual message content to be processed by BRAIN

# Root endpoint - basic server identification
@app.get("/")
def root():
    """
    Simple root endpoint that confirms the BRAIN server is running.
    Used for basic connectivity testing and server identification.
    """
    return {"message": "Hello from BRAIN!"}

# Health check endpoint for monitoring and load balancers
@app.get("/health")
async def health():
    """
    Health check endpoint for system monitoring.
    Returns server status - can be extended to check database connections,
    external service availability, etc.
    """
    return {"status": "BRAIN is alive and ready."}

# Main webhook endpoint - this is where customer messages are received and processed
@app.post("/webhook") 
async def webhook(input: MessageInput):
    """
    Primary webhook endpoint for processing incoming customer messages.
    
    This endpoint:
    1. Receives validated JSON payload with user_id and message
    2. Currently logs the incoming message for debugging
    3. Returns a placeholder response (will be replaced with BRAIN processing)
    
    Future integration will:
    - Pass message through BRAIN's perception layer for intent analysis
    - Maintain conversation context using user_id as session identifier
    - Apply decision-making rules to determine appropriate response/action
    - Return intelligent, contextual responses to customers
    """
    # Log incoming message for debugging and monitoring
    # TODO: Replace with proper logging system for production
    print(f"Received from user {input.user_id}: {input.message}")

    # Placeholder response - will be replaced with BRAIN's intelligent processing
    # TODO: Integrate with decision_engine.Decide() for actual AI responses
    reply = "Hola desde BRAIN. Integración exitosa "

    # Return response in expected JSON format
    return {"reply": reply}