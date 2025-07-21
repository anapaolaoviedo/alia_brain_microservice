# decision_engine.py
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
    
        self.rule_engine = RuleEngine()
        self.memory_manager = MemoryManager()
        self.nlp_pipeline = NlpPipeline()
        self.policy_module = PolicyModule() # This will be a placeholder for now

    def decide(self, user_id: str, message: str) -> dict:
        """
        Makes a decision based on the incoming user message and current context.

        Args:
            user_id (str): A unique identifier for the user/session.
            message (str): The raw text message from the user (e.g., from WhatsApp).

        Returns:
            dict: A dictionary representing the chosen action to be performed.
                  This action will be sent back to Make.com (in JSON form).
        """
        # 1. using nlp as the sensor 
        # extracts entities and intent from the raw text 
        percept_data = self.nlp_pipeline.process_message(message)
        # ex percept_data: {"intent": "RenovatePolicy", "entities": {"policy_number": "XYZ123"}}

        # 2. get the current session state from memory (Memory)
        #  provides historical context for the current user/session
        current_state = self.memory_manager.get_session_state(user_id)
        # ex current_state (before update): {"current_intent": None, "entities": {}, "status": "new_session"}

        # 3. updating the current_state with the new percept data
        # cricial: deciison engine must operate on the most recent state
        # We merge the extracted intent and entities into the state.

        # update current_intent
        current_state["current_intent"] = percept_data.get("intent", current_state.get("current_intent"))
        
        # unite entities from percept_data into current_state["entities"]
        if "entities" in percept_data and percept_data["entities"]:
            #  current_state has an 'entities' dict to merge into
            if "entities" not in current_state:
                current_state["entities"] = {}
            current_state["entities"].update(percept_data["entities"])
            
        #  specific flags based on extracted entities in the NOW UPDATED current_state["entities"]
        if current_state["entities"].get("policy_number"):
            current_state["policy_number_provided"] = True
        
        #  for vehicle details (make, model, year)
        if current_state["entities"].get("vehicle_make") and \
           current_state["entities"].get("vehicle_model") and \
           current_state["entities"].get("vehicle_year"):
            current_state["vehicle_details_provided"] = True
            
        #  for contact info (email or phone number)
        if current_state["entities"].get("email") or current_state["entities"].get("phone_number"):
            current_state["contact_info_provided"] = True
            
        chosen_action = None

        # 4. see rule-based policy first (RuleEngine - part of Policy)
        # ruless provide explicit guardrails and handle clear, deterministic scenarios
        # SEEEEE!!! Use evaluate_rules method and pass only current_state
        rule_action = self.rule_engine.evaluate_rules(current_state)

        if rule_action is not None:
            # IF  a rule fires, that action is chosen (rules will be context of renovation policy from garantiplus)
            chosen_action = rule_action
        else:
            # 5. but if no rule applies, consult the learned policy (PolicyModule - part of Policy)
            # this  is for more complex, nuanced, or learned behaviors so tbd
            # for now, this will return a placeholder action 
            policy_action = self.policy_module.predict_action(current_state)
            chosen_action = policy_action

        # 6. to update pdate memory with the final state and chosen action (Memory)
        #  ensures the agent remembers the outcome of this turn for future interactions.
        #  important to save the `current_state`ONLY AFTER AFTERRall updates and decisions.
        self.memory_manager.update_session_state(user_id, current_state, message, chosen_action)

        return chosen_action

