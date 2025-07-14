# decision_engine.py
from rule_engine import RuleEngine
from memory_manager import MemoryManager
from nlp_pipeline import NlpPipeline
from policy_module import PolicyModule

class DecisionEngine:
    def __init__(self):
        self.rule_engine = RuleEngine()
        self.memory_manager = MemoryManager()
        self.nlp_pipeline = NlpPipeline()
        self.policy_module = PolicyModule() #place holder for now 
        
    def decide(self,user_id: str, message: str)-> dict:
        """
        Makes a decision based on the incoming user message and current context.

        Args:
            user_id (str): A unique identifier for the user/session.
            message (str): The raw text message from the user (from WhatsApp).

        Returns:
            dict: A dictionary representing the chosen action to be performed.
                  This action will be sent back to Make.com. (in JSON form)
        """
        percept_data = self.nlp_pipeline.process(message)
        current_state = self.memory_manager.load_context(user_id)
        current_state["current_intent"] = percept_data.get("intent", current_state.get("current_intent"))
        
        if "entities" in percept_data and percept_data["entities"]:
            if "entities" not in current_state:
                current_state["entities"] = {}
            current_state["entities"].update(percept_data["entities"])
            
          #specific flags based on extracted entities for easier rule checking
        if current_state["entities"].get("policy_number"):
            current_state["policy_number_provided"] = True
        if current_state["entities"].get("vehicle_make") and \
           current_state["entities"].get("vehicle_model") and \
           current_state["entities"].get("vehicle_year"):
            current_state["vehicle_details_provided"] = True
            
        chosen_action = None
        
        rule_action = self.rule_engine.check_rules(current_state,percept_data)
        
        if rule_action is not None:
            chosen_action = rule_action
        else:
            # For now, this will return a placeholder action as per Week 2 plan.
            policy_action = self.policy_module.predict_action(current_state)
            chosen_action = policy_action

        # update memory with the final state and chosen action (Memory)
        #  ensuring that the agent remembers the outcome of this turn for future interactions.
        self.memory_manager.update_session_state(user_id, current_state, chosen_action)

        return chosen_action
        
        
        
        
        
        
    
    