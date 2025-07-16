from nlp_pipeline import process_message 

class MemoryManager:
    
    def __init__(self):
        # A simple Python dictionary to store session states.
        # Key: user_id (str)
        # Value: dict representing the current state of that user's conversation
        
        self.sessions = {}
        print("Memory manager initialized: ready to remember") #making sure it works 
        
    def get_session_state(self, user_id, str) ->