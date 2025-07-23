# memory_manager.py
import redis
import json
import psycopg2 #for postgres 
import os #to read enviromental variables for credentials
from dotenv import load_dotenv #for the .env file

load_dotenv()
    
class MemoryManager:
    '''
    Managing BRAIN memory using a hybrid approach:
    -Redis for short-term working memory
    -PostgreSQL for long-term user history and conversation logs 
    '''
    
    def __init_(self):
        #we start with REDIS configuration
        self.redis_host = os.getenv('REDIS_HOST', 'localhost')
        self.redis_port = int(os.getenv('REDIS_PORT', 6379))
        self.redis_db = int(os.getenv('REDIS_DB', 0))
        self.redis_json_available = False
        self._in_memory_sessions = {}
        
        try:
            self.r = redis.Redis(
                host = self.redis_host,
                port = self.redis_port,
                db = self.redis_db,
                decode_responses=True
            )
            self.r.ping() # testing connection
            print(f"Memory Manager: Connected to Redis at {self.redis_host}:{self.redis_port}")
            
    

        
    