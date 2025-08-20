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

# EXTERNAL DEPENDENCIES - These modules provide specialized functionality
# Think of these as BRAIN's specialized "organs" that handle specific tasks
from rule_engine import RuleEngine        # Business logic and guardrails
from memory_manager import MemoryManager  # Conversation memory and context
from nlp_pipeline import NlpPipeline      # Natural language understanding
from policy_module import PolicyModule    # AI-driven decision making (future)

class DecisionEngine:
    """
    The central orchestrator for BRAIN. It takes a user message,
    processes it through the NLP pipeline, retrieves/updates the
    session memory, applies rule-based logic, and falls back to
    a learned policy if no rules are triggered.
    
    ARCHITECTURE OVERVIEW:
    - This is the "CEO" of BRAIN - it delegates tasks to specialists but makes final decisions
    - Follows a pipeline approach: Perception → Memory → Decision → Action
    - Designed to be stateless (all state is managed by MemoryManager)
    - Returns actions in a standard format that external systems can execute
    """
    
    def __init__(self):
        """
        Initialize all BRAIN subsystems:
        - RuleEngine: Handles explicit business rules and guardrails
        - MemoryManager: Maintains conversation context and session state
        - NlpPipeline: Processes natural language to extract intent and entities
        - PolicyModule: Handles complex learned behaviors (placeholder for now)
        
        WHY THIS DESIGN:
        - Separation of concerns: Each module has one clear responsibility
        - Modularity: Can swap out or upgrade individual components
        - Testability: Each component can be tested independently
        - Scalability: Can distribute these components across different services
        """
        # RULE ENGINE: The "legal department" - enforces business rules and compliance
        # Example: "Always ask for policy number before providing quotes"
        self.rule_engine = RuleEngine()
        
        # MEMORY MANAGER: The "librarian" - remembers everything about each conversation
        # Example: Remembers that John mentioned his car is a 2020 Toyota Camry 3 messages ago
        self.memory_manager = MemoryManager()
        
        # NLP PIPELINE: The "interpreter" - understands what customers are saying
        # Example: Converts "I need to renew my car insurance" → intent: "policy_renewal"
        self.nlp_pipeline = NlpPipeline()
        
        # POLICY MODULE: The "AI brain" - handles complex decisions that can't be hard-coded
        # This will be a placeholder for now (future machine learning integration)
        self.policy_module = PolicyModule()

    def decide(self, user_id: str, message: str) -> dict:
        """
        Makes a decision based on the incoming user message and current context.
        
        This is BRAIN's main processing pipeline that:
        1. Extracts meaning from the message (Perception)
        2. Retrieves conversation context (Memory)
        3. Updates state with new information
        4. Applies business rules or learned policies (Decision-Making)
        5. Saves the updated state for future turns

        REAL-WORLD EXAMPLE:
        User says: "My Honda needs new coverage"
        → NLP extracts: intent="get_quote", entities={"vehicle_make": "Honda"}
        → Memory recalls: This user previously mentioned model="Civic", year="2019"
        → Rules check: "Need complete vehicle info for quotes"
        → Action: "ask_for_missing_vehicle_details" because year is missing
        → Memory saves: Updated conversation state for next message

        Args:
            user_id (str): A unique identifier for the user/session.
                          In practice, this comes from WhatsApp/SMS phone number or session ID
                          Example: "+1234567890" or "session_abc123"
            
            message (str): The raw text message from the user (e.g., from WhatsApp).
                          Example: "I want to add my son to my policy"

        Returns:
            dict: A dictionary representing the chosen action to be performed.
                  This action will be sent back to Make.com (in JSON form).
                  Example: {"action": "ask_policy_number", "message": "Could you provide your policy number?"}
        """
        
        # STEP 1: PERCEPTION - Extract intent and entities from raw message
        # =================================================================
        # The NLP pipeline acts as BRAIN's "sensory system", converting unstructured
        # text into structured data that can be reasoned about
        # 
        # TECHNICAL NOTE: This is where we transform unstructured natural language
        # into structured data that our rule engine can work with
        #
        # BUSINESS VALUE: Enables BRAIN to understand customer requests accurately,
        # reducing miscommunication and improving customer experience
        percept_data = self.nlp_pipeline.process_message(message)
        # Example percept_data: {"intent": "RenovatePolicy", "entities": {"policy_number": "XYZ123"}}

        # STEP 2: MEMORY RETRIEVAL - Get current conversation context
        # ==========================================================
        # Retrieves the ongoing conversation state for this specific user session
        # This enables BRAIN to maintain context across multiple message exchanges
        # 
        # TECHNICAL NOTE: Each user_id has its own isolated conversation state
        # This prevents cross-contamination between different customer conversations
        #
        # BUSINESS VALUE: Customers don't have to repeat information they've already provided
        # Creates a seamless, human-like conversation experience
        current_state = self.memory_manager.get_session_state(user_id)
        # Example current_state (before update): {"current_intent": None, "entities": {}, "status": "new_session"}

        # STEP 3: STATE UPDATE - Merge new information with existing context
        # =================================================================
        # This is critical: the decision engine must operate on the most recent state
        # We merge the extracted intent and entities into the ongoing conversation state
        #
        # WHY THIS MATTERS: Information accumulates across conversation turns
        # Turn 1: Customer mentions policy number
        # Turn 2: Customer mentions vehicle make/model  
        # Turn 3: Customer asks for quote
        # → BRAIN has all info needed to generate quote without re-asking

        # Update the primary intent based on the latest message
        # Preserves existing intent if no new intent was detected (customer elaborating on previous request)
        # Overwrites if new intent detected (customer changing topic/request)
        current_state["current_intent"] = percept_data.get("intent", current_state.get("current_intent"))
        
        # Merge newly extracted entities with existing entities
        # This accumulates information across conversation turns (e.g., policy number from turn 1, 
        # vehicle details from turn 3, contact info from turn 5)
        if "entities" in percept_data and percept_data["entities"]:
            # Initialize entities dict if it doesn't exist (first message in conversation)
            if "entities" not in current_state:
                current_state["entities"] = {}
            # Update with new entities, overwriting duplicates with latest values
            # TECHNICAL NOTE: .update() merges dictionaries, with new values taking precedence
            # BUSINESS EXAMPLE: If customer first says "2019 Honda" then later corrects to "2020 Honda"
            # the year entity gets updated to reflect the correction
            current_state["entities"].update(percept_data["entities"])
            
        # STEP 3B: DERIVED STATE FLAGS - Set convenience flags based on accumulated entities
        # ==================================================================================
        # These flags make it easier for rules to check if we have sufficient information
        # Instead of complex nested checks, rules can simply check boolean flags
        #
        # DEVELOPER BENEFIT: Cleaner, more readable rule conditions
        # BUSINESS BENEFIT: Consistent data validation across all business processes
        
        # Flag: Do we have the customer's policy number?
        # BUSINESS RULE: Many operations require policy number for customer verification
        if current_state["entities"].get("policy_number"):
            current_state["policy_number_provided"] = True
        
        # Flag: Do we have complete vehicle information?
        # All three pieces are required for a complete vehicle profile
        # BUSINESS RULE: Insurance quotes require complete vehicle identification
        if current_state["entities"].get("vehicle_make") and \
           current_state["entities"].get("vehicle_model") and \
           current_state["entities"].get("vehicle_year"):
            current_state["vehicle_details_provided"] = True
            
        # Flag: Do we have customer contact information?
        # Either email OR phone number is sufficient for contact
        # BUSINESS RULE: Need contact method for policy updates and communications
        if current_state["entities"].get("email") or current_state["entities"].get("phone_number"):
            current_state["contact_info_provided"] = True
            
        # Initialize action variable - this will hold our final decision
        chosen_action = None

        # STEP 4: RULE-BASED DECISION MAKING - Apply explicit business rules first
        # ========================================================================
        # Rules provide explicit guardrails and handle clear, deterministic scenarios
        # These are the "hard-coded" business logic that must always be followed
        # 
        # TECHNICAL APPROACH: Rule engines use if-then logic that's easy to audit and modify
        # BUSINESS VALUE: Ensures compliance, consistency, and predictable behavior
        # 
        # EXAMPLES OF RULES:
        # - "If customer wants quote but missing vehicle info → ask for vehicle details"
        # - "If customer mentions claim but no policy number → ask for policy number"
        # - "If after business hours and urgent claim → escalate to emergency line"
        #
        # NOTE: Pass the complete current_state (with all updates) to rule evaluation
        rule_action = self.rule_engine.evaluate_rules(current_state)

        if rule_action is not None:
            # If a rule fires, that action takes precedence
            # Rules are designed to handle critical business scenarios (policy renewals, quotes, etc.)
            # TECHNICAL NOTE: Rules have higher priority than AI decisions for compliance/safety
            # BUSINESS NOTE: Ensures regulatory requirements and business policies are always followed
            chosen_action = rule_action
        else:
            # STEP 5: LEARNED POLICY FALLBACK - Handle complex or edge cases
            # ==============================================================
            # If no explicit rule applies, consult the learned policy module
            # This handles more nuanced behaviors that are difficult to encode as rules
            # 
            # FUTURE CAPABILITY: This is where machine learning and AI decision-making will happen
            # For now, this returns a placeholder action (TBD for future ML integration)
            #
            # EXAMPLES OF POLICY DECISIONS:
            # - Customer sentiment analysis → adjust response tone
            # - Conversation flow optimization → choose best next question
            # - Personalization → tailor responses to customer history
            # - Complex multi-step process handling → navigate complicated workflows
            policy_action = self.policy_module.predict_action(current_state)
            chosen_action = policy_action

        # STEP 6: MEMORY UPDATE - Save the complete interaction for future reference
        # =========================================================================
        # This ensures BRAIN remembers:
        # - The updated conversation state (all accumulated information)
        # - The customer's message (for conversation history)
        # - The action that was taken (for learning and audit purposes)
        # 
        # TECHNICAL IMPORTANCE: This must happen AFTER all processing is complete
        # BUSINESS VALUE: Enables conversation continuity and allows for later analysis
        # COMPLIANCE VALUE: Creates audit trail of all customer interactions
        #
        # Critical: Save current_state AFTER all updates and decisions are complete
        self.memory_manager.update_session_state(user_id, current_state, message, chosen_action)

        # FINAL STEP: Return the chosen action to be executed by the external system (Make.com)
        # ===================================================================================
        # The returned action is a standardized dictionary that tells the external system
        # what to do next (send message, update database, trigger workflow, etc.)
        #
        # INTEGRATION NOTE: This is the "output interface" - external systems like Make.com
        # will parse this dictionary and execute the specified action
        #
        # EXAMPLE RETURNS:
        # {"action": "send_message", "message": "What's your policy number?"}
        # {"action": "generate_quote", "policy_type": "auto", "coverage_level": "full"}
        # {"action": "escalate_to_human", "reason": "complex_claim", "priority": "high"}
        return chosen_action