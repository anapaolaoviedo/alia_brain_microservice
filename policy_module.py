"""
BRAIN Policy Module - Simple Fallback Handler
============================================

This module handles edge cases that don't match explicit business rules.
It provides intelligent fallback responses when the rule engine returns None.

Current Implementation: Simple heuristic-based responses
Future Potential: Machine learning for complex scenarios

The policy module acts as BRAIN's "intuition" - handling ambiguous situations
that are too complex or rare for explicit rules but still need reasonable responses.

ARCHITECTURAL ROLE:
This is the final layer in BRAIN's decision-making hierarchy:
1. Rule Engine handles explicit business logic (deterministic)
2. Policy Module handles edge cases and ambiguous situations (heuristic/AI)

BUSINESS PURPOSE:
- Ensures customers always receive helpful responses, even in unexpected situations
- Gracefully handles conversation scenarios not covered by explicit rules
- Provides a learning opportunity by logging edge cases for future rule development
- Maintains conversation flow when customers provide unclear or complex input

CURRENT IMPLEMENTATION:
- Simple heuristic-based categorization of edge cases
- Predefined response templates for different scenario types
- Random response selection to avoid repetitive interactions
- Comprehensive logging for future improvement and rule development

FUTURE EVOLUTION PATH:
- Machine learning models for sophisticated response prediction
- Customer profile-based personalization (adjust tone, language complexity)
- A/B testing framework for optimizing response effectiveness
- Integration with customer satisfaction metrics for continuous improvement
- Natural language generation for dynamic, contextual responses

TECHNICAL DESIGN:
- Lightweight and fast (< 10ms response time)
- Stateless operation (all context from conversation state)
- Extensive logging for monitoring and improvement
- Modular design allows easy enhancement without affecting core BRAIN logic
"""

import random                       # For response variation to avoid repetition
from typing import Dict, Optional   # Type hints for better code documentation

class PolicyModule:
    """
    Simple policy module for handling edge cases and unknown scenarios.
    
    This module provides fallback behavior when no explicit business rules
    match the current conversation state. It acts as BRAIN's "common sense"
    for handling unexpected or ambiguous customer interactions.
    
    DESIGN PHILOSOPHY:
    - "Always be helpful" - Never leave customers without a response
    - "Learn from edge cases" - Log unusual scenarios for future rule development
    - "Maintain conversation flow" - Keep customers engaged even when confused
    - "Graceful degradation" - Provide reasonable responses even without perfect understanding
    
    KEY RESPONSIBILITIES:
    1. EDGE CASE HANDLING: Manage conversations that don't fit standard patterns
    2. FALLBACK RESPONSES: Provide helpful messages when rules don't apply
    3. LEARNING FACILITATION: Log edge cases to improve rule coverage over time
    4. CONVERSATION CONTINUITY: Keep interactions flowing smoothly
    
    BUSINESS SCENARIOS HANDLED:
    - Customer asks unclear or ambiguous questions
    - Technical issues beyond standard customer service scope
    - Novel conversation patterns not yet covered by rules
    - Mixed intents or complex multi-part requests
    - Customers providing unexpected information combinations
    
    CURRENT APPROACH:
    Uses simple heuristic classification based on:
    - Detected intent (or lack thereof)
    - Entities present in conversation state
    - Keywords in conversation history
    - Conversation context and patterns
    """
    
    def __init__(self):
        """
        Initialize the policy module with simple response templates.
        
        Sets up the fallback response system with categorized message templates
        and monitoring capabilities for tracking edge case patterns.
        
        INITIALIZATION COMPONENTS:
        1. Response template library organized by scenario type
        2. Usage tracking for monitoring and optimization
        3. Logging setup for edge case analysis
        
        FUTURE EXTENSIBILITY:
        In production, this could be extended with:
        - ML models for response prediction based on conversation patterns
        - Customer profile-based personalization (adjust language, tone, complexity)
        - A/B testing frameworks for optimizing response effectiveness
        - Integration with customer satisfaction metrics
        - Dynamic response generation using NLG (Natural Language Generation)
        - Multi-language support with culturally appropriate responses
        """
        print("Policy Module initialized: Ready for edge case handling.")
        
        # USAGE TRACKING AND MONITORING
        # =============================
        # Counter to track how often fallback is used (useful for monitoring)
        # High fallback usage indicates need for more comprehensive rules
        # Low usage suggests good rule coverage
        self.fallback_call_count = 0
        
        # RESPONSE TEMPLATE LIBRARY
        # ========================
        # Organized response templates for different edge case categories
        # Each category has multiple variations to avoid repetitive responses
        # Templates are in Spanish to match primary customer base
        
        self.fallback_responses = {
            # GENERAL HELP RESPONSES
            # =====================
            # Used when customer seems to need assistance but intent is unclear
            # Encouraging and open-ended to gather more specific information
            "general_help": [
                "Entiendo que necesitas ayuda. ¿Podrías ser más específico sobre lo que necesitas?",
                "Estoy aquí para ayudarte con la renovación de tu garantía. ¿Qué información necesitas?",
                "¿Puedes contarme más detalles sobre lo que buscas? Así podré ayudarte mejor."
            ],
            
            # UNCLEAR INTENT RESPONSES
            # =======================
            # Used when customer message doesn't match any known intent patterns
            # Offers multiple options to help customer clarify their needs
            "unclear_intent": [
                "No estoy seguro de entender exactamente qué necesitas. ¿Quieres renovar tu garantía o tienes otra consulta?",
                "¿Podrías reformular tu pregunta? Quiero asegurarme de darte la información correcta.",
                "Hay varias formas en que puedo ayudarte. ¿Buscas renovar, obtener información de precios, o algo más?"
            ],
            
            # TECHNICAL SUPPORT ESCALATION
            # ===========================
            # Used when customer appears to have technical issues beyond standard scope
            # Provides specific contact information for specialized support
            "technical_support": [
                "Para asistencia técnica especializada, te recomiendo contactar a nuestro equipo al 800 garanti (4272684).",
                "Parece que necesitas ayuda técnica. Nuestros especialistas pueden ayudarte mejor al 4432441212."
            ]
        }

    def predict_action(self, state: dict) -> dict:
        """
        Generate a fallback action when no rules match the current state.
        
        This is BRAIN's "intuition" method - it analyzes the conversation context
        and provides a reasonable response using simple heuristics when explicit
        business rules don't apply.
        
        PROCESSING APPROACH:
        1. Analyze conversation state for context clues
        2. Categorize the edge case using heuristic patterns
        3. Select appropriate response template category
        4. Choose specific response with variation to avoid repetition
        5. Log the edge case for future rule development
        6. Return structured action for execution
        
        HEURISTIC CLASSIFICATION:
        - Unclear Intent: No recognizable intent detected
        - Technical Issues: Keywords suggest technical problems
        - General Help: Default helpful response for other cases
        
        REAL-WORLD EXAMPLES:
        
        Example 1 - Unclear Intent:
        Customer: "Hola, tengo dudas"
        → Intent: Unknown, no specific entities
        → Category: unclear_intent
        → Response: "¿Podrías reformular tu pregunta? Quiero asegurarme de darte la información correcta."
        
        Example 2 - Technical Issue:
        Customer: "Mi auto tiene un problema con el motor"
        → Keywords: "problema" detected in conversation
        → Category: technical_support
        → Response: "Para asistencia técnica especializada, te recomiendo contactar..."
        
        Example 3 - General Help:
        Customer: "Información sobre servicios"
        → Intent: vague, but not technical
        → Category: general_help
        → Response: "Estoy aquí para ayudarte con la renovación de tu garantía..."
        
        Args:
            state: Current conversation state from MemoryManager containing:
                  - current_intent: Detected customer intent (or None/Unknown)
                  - entities: Extracted information (contact, vehicle, etc.)
                  - conversation_summary: History of the conversation
                  - various flags: Policy status, vehicle details, etc.
                  
        Returns:
            dict: Fallback action with structured response information:
                 - action_type: "fallback_response" for identification
                 - message: Customer-facing response text
                 - message_to_customer: Same as message (for consistency)
                 - policy_reasoning: Explanation of why this response was chosen
                 - fallback_count: Running count for monitoring
                 
        BUSINESS VALUE:
        - Ensures no customer conversation ends without a helpful response
        - Maintains professional tone even in unexpected situations
        - Provides data for improving rule coverage over time
        - Keeps conversation flowing toward successful resolution
        
        TECHNICAL BENEFITS:
        - Fast execution (simple heuristics, no external API calls)
        - Comprehensive logging for system improvement
        - Consistent response format for easy integration
        - Stateless operation for reliability and scalability
        """
        
        # STEP 1: UPDATE MONITORING METRICS
        # ================================
        # Increment fallback usage counter for monitoring
        # This helps track how often edge cases occur and system coverage
        self.fallback_call_count += 1
        
        # STEP 2: COMPREHENSIVE LOGGING FOR ANALYSIS
        # ==========================================
        # Log the edge case for future rule development and system improvement
        # This data is crucial for identifying patterns in unhandled scenarios
        print(f"Policy Module called (#{self.fallback_call_count}): Handling edge case")
        print(f"Current intent: {state.get('current_intent', 'None')}")
        print(f"Entities present: {list(state.get('entities', {}).keys())}")
        
        # STEP 3: EXTRACT CONVERSATION CONTEXT
        # ====================================
        # Extract key information from conversation state for heuristic analysis
        current_intent = state.get("current_intent", "")
        entities = state.get("entities", {})
        conversation_summary = state.get("conversation_summary", "").lower()
        
        # STEP 4: HEURISTIC CATEGORIZATION
        # ================================
        # Apply simple but effective heuristics to categorize the edge case
        # Each heuristic targets a specific type of customer need
        
        # HEURISTIC 1: UNCLEAR OR MISSING INTENT
        # ======================================
        # Customer message didn't match any known intent patterns
        # Likely indicates ambiguous phrasing or novel request type
        if current_intent in ["Unknown", None, ""]:
            response_category = "unclear_intent"
        
        # HEURISTIC 2: TECHNICAL ISSUE DETECTION
        # ======================================
        # Customer appears to have technical problems beyond standard service scope
        # Keywords indicate mechanical, technical, or complex operational issues
        elif any(keyword in conversation_summary for keyword in ["problema", "error", "falla", "no funciona"]):
            response_category = "technical_support"
        
        # HEURISTIC 3: GENERAL HELP FALLBACK
        # ==================================
        # Default category for other edge cases that need assistance
        # Covers miscellaneous scenarios not fitting other categories
        else:
            response_category = "general_help"
        
        # STEP 5: RESPONSE SELECTION WITH VARIATION
        # =========================================
        # Select a random response from the appropriate category to avoid repetition
        # Randomization helps conversations feel more natural and less robotic
        selected_message = random.choice(self.fallback_responses[response_category])
        
        # STEP 6: CREATE STRUCTURED ACTION RESPONSE
        # =========================================
        # Format the response as a structured action that matches BRAIN's standard format
        # This ensures consistent handling by external systems (Make.com, etc.)
        fallback_action = {
            # ACTION IDENTIFICATION
            "action_type": "fallback_response",    # Identifies this as a policy module response
            
            # CUSTOMER COMMUNICATION
            "message": selected_message,           # The actual response text
            "message_to_customer": selected_message,  # Duplicate for consistency with other actions
            
            # SYSTEM METADATA
            "policy_reasoning": f"No rule matched. Used {response_category} heuristic.",  # Explanation for debugging
            "fallback_count": self.fallback_call_count  # Current usage count for monitoring
        }
        
        # STEP 7: LOG FINAL RESPONSE
        # =========================
        # Log the selected response for monitoring and quality assurance
        print(f"Policy Module Response: {selected_message}")
        
        return fallback_action
    
    def get_fallback_stats(self) -> dict:
        """
        Get statistics about fallback usage for monitoring and optimization.
        
        This method provides insights into policy module usage patterns,
        helping identify when rule coverage might need improvement or when
        the policy module is working effectively as a safety net.
        
        MONITORING USE CASES:
        - Track fallback frequency to assess rule coverage quality
        - Identify patterns in edge cases for future rule development
        - Monitor system health and customer experience gaps
        - Support A/B testing and optimization efforts
        
        Returns:
            dict: Usage statistics and configuration information including:
                 - total_fallback_calls: How many times fallback was used
                 - response_categories: Available response types
                 - status: Current implementation approach
                 
        BUSINESS VALUE:
        - Enables data-driven improvement of customer service
        - Helps prioritize development of new business rules
        - Supports quality monitoring and system optimization
        - Provides metrics for customer experience assessment
        """
        return {
            "total_fallback_calls": self.fallback_call_count,
            "response_categories": list(self.fallback_responses.keys()),
            "status": "simple_heuristic_mode"
        }
    
    def reset_stats(self):
        """
        Reset the fallback counter (useful for testing or monitoring resets).
        
        This method allows clearing usage statistics, which is useful for:
        - Testing scenarios that need clean state
        - Periodic monitoring resets (daily/weekly cycles)
        - Development and debugging workflows
        - A/B testing with clean baseline metrics
        
        OPERATIONAL USE CASES:
        - Daily/weekly metric resets for trending analysis
        - Testing new rule sets with clean baseline data
        - Development environment cleanup
        - Performance benchmarking with consistent starting points
        """
        self.fallback_call_count = 0
        print("Policy Module stats reset.")