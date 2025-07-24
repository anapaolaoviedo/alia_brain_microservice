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
        self.r = None
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
            
            try:
                # literally try RedisJSON module availability.  requires the RedisJSON module to be loaded on the Redis server
                # if not available, fall back to storing JSON as simple strings
                self.r.json().set('test_key', '.', {'test': 'value'})
                self.r.json().delete('test_key') # Clean up test key
                self.redis_json_available = True
            except Exception as e:
                print(f"RedisJSON module not available or error: {e}. Falling back to JSON string storage in Redis.")

        except redis.exceptions.ConnectionError as e:
            print(f"ERROR: Could not connect to Redis at {self.redis_host}:{self.redis_port}. "
                  f"Please ensure Redis server is running. Error: {e}")
            print("Memory Manager will operate in IN-MEMORY ONLY mode for session state.")
            
        #we jump into PostgreSQL configuration
        self.pg_conn = None # PostgreSQL connection object
        self.pg_db_config = {
            "host": os.getenv('PG_HOST', 'localhost'),
            "database": os.getenv('PG_DATABASE', 'brain_memory'),
            "user": os.getenv('PG_USER', 'postgres'), # Default user for local docker
            "password": os.getenv('PG_PASSWORD', 'mysecretpassword'), # Default password for local docker
            "port": os.getenv('PG_PORT', 5432)
        }
        
        try:
            self.pg_conn = psycopg2.connect(**self.pg_db_config)
            self.pg_conn.autocommit = True # simplicity for mvp
            print(f"Memory Manager: Connected to PostgreSQL database '{self.pg_db_config['database']}'")
            self._create_tables_if_not_exists() # create table if ti doesnt exist
        except psycopg2.Error as e:
            print(f"ERROR: Could not connect to PostgreSQL database '{self.pg_db_config['database']}'. "
                  f"Please ensure PostgreSQL server is running and credentials are correct. Error: {e}")
            print("Memory Manager will NOT persist long-term data to PostgreSQL.")

        print("Memory Manager initialized: Ready to remember!")
        
    def _create_tables_of_not_exists(self):
        
        

        
    