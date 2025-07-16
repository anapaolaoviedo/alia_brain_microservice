Cliente manda mensaje por WhatsApp
        ↓
Make.com recibe el mensaje y lo convierte en un JSON (formato de datos estructurado)
        ↓
BRAIN (FastAPI) recibe el mensaje en su webhook
        ↓
🔎 **Pipeline NLP**
   - Analiza el texto (extrae intención y datos clave, por ejemplo: nombre, póliza, modelo del auto)
        ↓
🧠 **Gestor de Memoria**
   - Guarda o actualiza la información del cliente (para tener contexto de la conversación)
        ↓
⚖️ **Motor de Decisiones (Decision Engine)**
   - Decide qué hacer con la intención detectada y el contexto actual
   - Consulta el **Motor de Reglas** para aplicar restricciones o validaciones
   - Consulta el **Módulo de Política** (sugerencias o lógica más flexible)
        ↓
🛡️ **Motor de Reglas**
   - Revisa reglas importantes (ej. si falta información, si hay algún dato incorrecto)
   - Garantiza que se cumplan políticas y condiciones definidas
        ↓
✅ **Acción Final**
   - Se elige la mejor respuesta o acción a tomar (ej. enviar info, pedir más datos, escalar a humano)
        ↓
🗂️ **Actualización de Memoria**
   - Se guarda el resultado de la interacción para futuras conversaciones
        ↓
Se crea la respuesta en formato JSON
        ↓
Make.com reenvía la respuesta al cliente por WhatsApp
        ↓
Cliente recibe la respuesta final