from nlp_pipeline import NlpPipeline
from memory_manager import ShortTermMemory
import json

# Initialize core components
pipeline = NlpPipeline()
memory = ShortTermMemory()
user_id = "4387"

message1 = """
Hola, me interesa renovar mi póliza de seguro. 
Mi número de póliza es ABC123456. 
Mi carro es un Toyota Corolla 2020, 
correo: usuario@correo.com, 
teléfono: +5215548300145, 
VIN: 1HGCM82633A123456
"""

result1 = pipeline.process_message(message1)
context1 = {
    "intent": result1["intent"],
    "entities": result1["entities"],
    "state": "awaiting_confirmation"
}
memory.store_user_context(user_id, context1)

print("\n BRAIN: Entendido. Deseas confirmar la renovación de tu póliza ABC123456?")

message2 = "cual seria el precio?"

result2 = pipeline.process_message(message2)  
context2 = memory.retrieve_user_context(user_id)

# Naive policy decision logic
if result2["intent"] == "GetQuote" and context2.get("state") == "awaiting_confirmation":
    policy_number = context2["entities"].get("policy_number", "[desconocida]")
    print(f"\n BRAIN: Necesitas ayuda para tu poliza con numero: {policy_number} ?")
    
    # Update state in memory
    context2["state"] = "completed"
    memory.store_user_context(user_id, context2)

elif context2.get("state") == "awaiting_confirmation":
    print("\n BRAIN: ¿Podrías confirmar si deseas proceder con la renovación?")
else:
    print("\n BRAIN: No entendí tu mensaje. Podrias aclararlo?")