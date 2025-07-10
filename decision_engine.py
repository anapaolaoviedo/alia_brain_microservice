# decision_engine.py

class DecisionEngine:
    def __init__(self):
        self.rule_engine = RuleEngine()
        self.memory_manager = MemoryManager()
        self.nlp_pipeline = NlpPipeline()
        self.policy_module = PolicyModule()
        
    def decide(self,user_id, message):
        percept = nlp_pipeline.process(message)
        state = memory_manager.load_context(user_id)
        rule_action = rule_engine.check_rules(state,percept)
        
        if rule_action is not None:
            chosen_action = rule_action
        else:
            policy_action = policy_module.suggest_action(state, percept)
            chosen_action = policy_action
        
        memory_manager.update_context(user_id, state, chosen_action)
        
        return chosen_action
        
        
        
        
        
        
    
    