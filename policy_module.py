"""
BRAIN Policy Module - Simple Fallback Handler
============================================

This module handles edge cases that don't match explicit business rules.
It provides intelligent fallback responses when the rule engine returns None.

Current Implementation: Simple heuristic-based responses
Future Potential: Machine learning for complex scenarios

The policy module acts as BRAIN's "intuition" - handling ambiguous situations
that are too complex or rare for explicit rules but still need reasonable responses.
"""

import random
from typing import Dict, Optional

class PolicyModule:
    """
    Simple policy module for handling edge cases and unknown scenarios.
    
    This module provides fallback behavior when no explicit business rules
    match the current conversation state. It uses simple heuristics to
    provide reasonable responses while logging edge cases for future rule development.
    """
    
    def __init__(self):
        """
        Initialize the policy module with simple response templates.
        
        In production, this could be extended with:
        - ML models for response prediction
        - Customer profile-based personalization
        - A/B testing frameworks
        """
        print("Policy Module initialized: Ready for edge case handling.")
        
        # Counter to track how often fallback is used (useful for monitoring)
        self.fallback_call_count = 0
        
        # Simple response templates for different scenarios
        self.fallback_responses = {
            "general_help": [
                "Entiendo que necesitas ayuda. ¿Podrías ser más específico sobre lo que necesitas?",
                "Estoy aquí para ayudarte con la renovación de tu garantía. ¿Qué información necesitas?",
                "¿Puedes contarme más detalles sobre lo que buscas? Así podré ayudarte mejor."
            ],
            "unclear_intent": [
                "No estoy seguro de entender exactamente qué necesitas. ¿Quieres renovar tu garantía o tienes otra consulta?",
                "¿Podrías reformular tu pregunta? Quiero asegurarme de darte la información correcta.",
                "Hay varias formas en que puedo ayudarte. ¿Buscas renovar, obtener información de precios, o algo más?"
            ],
            "technical_support": [
                "Para asistencia técnica especializada, te recomiendo contactar a nuestro equipo al 800 garanti (4272684).",
                "Parece que necesitas ayuda técnica. Nuestros especialistas pueden ayudarte mejor al 4432441212."
            ]
        }

    def predict_action(self, state: dict) -> dict:
        """
        Generate a fallback action when no rules match the current state.
        
        This method analyzes the conversation state and provides a reasonable
        response using simple heuristics. It's designed to be helpful while
        encouraging customers to provide more specific information.
        
        Args:
            state: Current conversation state from MemoryManager
            
        Returns:
            dict: Fallback action with appropriate message
        """
        # Increment fallback usage counter for monitoring
        self.fallback_call_count += 1
        
        # Log the edge case for future rule development
        print(f"Policy Module called (#{self.fallback_call_count}): Handling edge case")
        print(f"Current intent: {state.get('current_intent', 'None')}")
        print(f"Entities present: {list(state.get('entities', {}).keys())}")
        
        # Simple heuristic-based response selection
        current_intent = state.get("current_intent", "")
        entities = state.get("entities", {})
        conversation_summary = state.get("conversation_summary", "").lower()
        
        # HEURISTIC 1: If customer seems confused or gave unclear input
        if current_intent in ["Unknown", None, ""]:
            response_category = "unclear_intent"
        
        # HEURISTIC 2: If they're asking for technical help or complex issues
        elif any(keyword in conversation_summary for keyword in ["problema", "error", "falla", "no funciona"]):
            response_category = "technical_support"
        
        # HEURISTIC 3: General help fallback
        else:
            response_category = "general_help"
        
        # Select a random response from the appropriate category to avoid repetition
        selected_message = random.choice(self.fallback_responses[response_category])
        
        # Create the fallback action
        fallback_action = {
            "action_type": "fallback_response",
            "message": selected_message,
            "message_to_customer": selected_message,
            "policy_reasoning": f"No rule matched. Used {response_category} heuristic.",
            "fallback_count": self.fallback_call_count
        }
        
        print(f"Policy Module Response: {selected_message}")
        return fallback_action
    
    def get_fallback_stats(self) -> dict:
        """
        Get statistics about fallback usage for monitoring and optimization.
        
        Returns:
            dict: Usage statistics for the policy module
        """
        return {
            "total_fallback_calls": self.fallback_call_count,
            "response_categories": list(self.fallback_responses.keys()),
            "status": "simple_heuristic_mode"
        }
    
    def reset_stats(self):
        """Reset the fallback counter (useful for testing or monitoring resets)."""
        self.fallback_call_count = 0
        print("Policy Module stats reset.")