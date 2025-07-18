from nlp_pipeline import process_message 

class MemoryManager:
    
    def __init__(self):
        # A simple Python dictionary to store session states.
        # Key: user_id (str)
        # Value: dict representing the current state of that user's conversation
        
        self.sessions = {}
        print("Memory manager initialized: ready to remember") #making sure it works 
        
    def get_session_state(self, user_id, str) -> dict:
        '''
        Args:
            user_id (str): The unique identifier for the user/session.

        Returns:
            dict: The current session state for the user.
                  Returns a *copy* of the state to prevent direct modification
                  of the stored dictionary from outside this class.
        '''
        #define the default structure for a new session state 
        default_state = {
            "session_id": user_id,
            "current_intent": None,
            "entities": {}, # To store extracted entities like policy_number, email, etc.
            "policy_number_provided": False,
            "vehicle_details_provided": False,
            "contact_info_provided": False,
            "quote_provided": False,
            "renovation_lead_notified": False, # To track if the human team has been notified
            "status": "new_session", # Tracks the current stage of the renovation process
            "conversation_summary": "" # To build a summary for human handoff
        }
        # get the state. if not found, use the default_state.
        # Use .copy() to ensure we're working with a mutable copy, not a reference
        # to the stored dictionary, preventing unintended side effects.
        return self._sessions.get(user_id, default_state).copy()
    
    def update_session_state(self, user_id: str, state: dict, chosen_action: dict = None):
        
        
    