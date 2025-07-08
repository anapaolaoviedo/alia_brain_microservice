class TableDrivenAgent:
    def __init__(self, table):
        self.percepts = []
        self.table = table  # Dict mapping tuples of percepts to actions

    def perceive_and_act(self, percept):
        # Append new percept to history
        self.percepts.append(percept)
        
        # Convert list to tuple (hashable) for table lookup
        key = tuple(self.percepts)
        
        # Look up action, default to "No action" if not found
        action = self.table.get(key, "No action defined")
        
        return action

# Example: Define a tiny table manually
example_table = {
    ("clean",): "do nothing",
    ("dirty",): "suck",
    ("dirty", "clean"): "move left",
    ("dirty", "clean", "dirty"): "suck again"
}

# Create agent
agent = TableDrivenAgent(example_table)

# Simulate percepts
print(agent.perceive_and_act("dirty"))      # "suck"
print(agent.perceive_and_act("clean"))      # "move left"
print(agent.perceive_and_act("dirty"))      # "suck again"
print(agent.perceive_and_act("clean"))      # "No action defined" (not in table!)

class TableAgent:
    def __init__(self, table):
        self.percepts = []
        self.table = table
    
    def perceive_act(self, percept):
        self.percepts.append(percept)
        
        key = tuple(self.percepts)
        action = self.table.get(key, "no action")
        return action
    
example_table2 = {
    ("dry",): "water",
    ("wet",): "do nothing",
    ("too wet",): "drain",
    ("dry", "dry"): "water again",
    ("wet", "dry"): "water light",
    ("wet", "dry", "wet"): "monitor moisture",
    ("wet", "dry", "wet", "dry"): "water",
    ("wet", "wet"): "do nothing",
}

agentini = TableAgent(example_table2)

print(agentini.perceive_act("wet"))      
print(agentini.perceive_act("dry"))      
print(agentini.perceive_act("wet"))      
print(agentini.perceive_act("dry"))         
        