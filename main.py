from fastapi import FastAPI
from fastapi import Request
from pydantic import BaseModel

app = FastAPI()

#  model for incoming JSON
class MessageInput(BaseModel):
    user_id: str
    message: str

# root route
@app.get("/")
def root():
    return {"message": "Hello from BRAIN!"}

# health check route
@app.get("/health")
async def health():
    return {"status": "BRAIN is alive and ready."}

# webhook route using Pydantic
@app.post("/webhook")
async def webhook(input: MessageInput):
    #  access fields directly
    print(f"Received from user {input.user_id}: {input.message}")

    # a reply for now?
    reply = "Hola desde BRAIN. Integración exitosa "

    return {"reply": reply}