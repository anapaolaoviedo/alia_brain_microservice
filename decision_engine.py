"""
BRAIN Decision Engine
====================

The central orchestrator that implements BRAIN's three core capabilities:

1. Advanced Perception: Uses NLP pipeline to extract meaning from customer messages
2. Memory and Context: Manages session state and conversation history  
3. Strategic Decision-Making: Applies business rules and learned policies

This module coordinates all components to process incoming messages and determine
the appropriate response or action to take.
"""

from rule_engine import RuleEngine
from memory_manager import MemoryManager
from nlp_pipeline import NlpPipeline
from policy_module import PolicyModule

class DecisionEngine:
    """
    The central orchestrator for BRAIN. It takes a user message,
    processes it through the NLP pipeline, retrieves/updates the
    session memory, applies rule-based logic, and falls back to
    a learned policy if no rules are triggered.
    """
    def __init__(self):
        """
        Initialize all BRAIN subsystems:
        - RuleEngine: Handles explicit business rules and guardrails
        - MemoryManager: Maintains conversation context and session state
        - NlpPipeline: Processes natural language to extract intent and entities
        - PolicyModule: Handles complex learned behaviors (placeholder for now)
        """
        self.rule_engine = RuleEngine()
        self.memory_manager = MemoryManager()
        self.nlp_pipeline = NlpPipeline()
        self.policy_module = PolicyModule() # This will be a placeholder for now

    def decide(self, user_id: str, message: str) -> dict:
        """
        Makes a decision based on the incoming user message and current context.
        
        This is BRAIN's main processing pipeline that:
        1. Extracts meaning from the message (Perception)
        2. Retrieves conversation context (Memory)
        3. Updates state with new information
        4. Applies business rules or learned policies (Decision-Making)
        5. Saves the updated state for future turns

        Args:
            user_id (str): A unique identifier for the user/session.
            message (str): The raw text message from the user (e.g., from WhatsApp).

        Returns:
            dict: A dictionary representing the chosen action to be performed.
                  This action will be sent back to Make.com (in JSON form).
        """
        
        # STEP 1: PERCEPTION - Extract intent and entities from raw message
        # The NLP pipeline acts as BRAIN's "sensory system", converting unstructured
        # text into structured data that can be reasoned about
        percept_data = self.nlp_pipeline.process_message(message)
        # Example percept_data: {"intent": "RenovatePolicy", "entities": {"policy_number": "XYZ123"}}

        # STEP 2: MEMORY RETRIEVAL - Get current conversation context
        # Retrieves the ongoing conversation state for this specific user session
        # This enables BRAIN to maintain context across multiple message exchanges
        current_state = self.memory_manager.get_session_state(user_id)
        # Example current_state (before update): {"current_intent": None, "entities": {}, "status": "new_session"}

        # STEP 3: STATE UPDATE - Merge new information with existing context
        # This is critical: the decision engine must operate on the most recent state
        # We merge the extracted intent and entities into the ongoing conversation state

        # Update the primary intent based on the latest message
        # Preserves existing intent if no new intent was detected
        current_state["current_intent"] = percept_data.get("intent", current_state.get("current_intent"))
        
        # Merge newly extracted entities with existing entities
        # This accumulates information across conversation turns (e.g., policy number from turn 1, 
        # vehicle details from turn 3, contact info from turn 5)
        if "entities" in percept_data and percept_data["entities"]:
            # Initialize entities dict if it doesn't exist
            if "entities" not in current_state:
                current_state["entities"] = {}
            # Update with new entities, overwriting duplicates with latest values
            current_state["entities"].update(percept_data["entities"])
            
        # STEP 3B: DERIVED STATE FLAGS - Set convenience flags based on accumulated entities
        # These flags make it easier for rules to check if we have sufficient information
        
        # Flag: Do we have the customer's policy number?
        if current_state["entities"].get("policy_number"):
            current_state["policy_number_provided"] = True
        
        # Flag: Do we have complete vehicle information?
        # All three pieces are required for a complete vehicle profile
        if current_state["entities"].get("vehicle_make") and \
           current_state["entities"].get("vehicle_model") and \
           current_state["entities"].get("vehicle_year"):
            current_state["vehicle_details_provided"] = True
            
        # Flag: Do we have customer contact information?
        # Either email OR phone number is sufficient for contact
        if current_state["entities"].get("email") or current_state["entities"].get("phone_number"):
            current_state["contact_info_provided"] = True
            
        # Initialize action variable
        chosen_action = None

        # STEP 4: RULE-BASED DECISION MAKING - Apply explicit business rules first
        # Rules provide explicit guardrails and handle clear, deterministic scenarios
        # These are the "hard-coded" business logic that must always be followed
        # NOTE: Pass the complete current_state (with all updates) to rule evaluation
        rule_action = self.rule_engine.evaluate_rules(current_state)

        if rule_action is not None:
            # If a rule fires, that action takes precedence
            # Rules are designed to handle critical business scenarios (policy renewals, quotes, etc.)
            chosen_action = rule_action
        else:
            # STEP 5: LEARNED POLICY FALLBACK - Handle complex or edge cases
            # If no explicit rule applies, consult the learned policy module
            # This handles more nuanced behaviors that are difficult to encode as rules
            # For now, this returns a placeholder action (TBD for future ML integration)
            policy_action = self.policy_module.predict_action(current_state)
            chosen_action = policy_action

        # STEP 6: MEMORY UPDATE - Save the complete interaction for future reference
        # This ensures BRAIN remembers:
        # - The updated conversation state
        # - The customer's message
        # - The action that was taken
        # Critical: Save current_state AFTER all updates and decisions are complete
        self.memory_manager.update_session_state(user_id, current_state, message, chosen_action)

        # Return the chosen action to be executed by the external system (Make.com)
        return chosen_action