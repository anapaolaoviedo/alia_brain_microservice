#  BRAIN — A First-Principles Cognitive Agent Framework

##  Overview

**BRAIN** is a first-principles blueprint for building cognitive agents.  
It is not just a framework  it is a living embodiment of theoretical agent formalism, designed to move beyond mere automation and towards real cognition.

It is the logic and reason center of an AI workflow created in Make.com called 'ALIA'. 
**BRAIN** will actually bring ALIA to life.


This project is grounded in:

- Agent theory and formal models
- Rationality and policy design
- State summarization and memory persistence
- Ethical constraints and guardrails

---



BRAIN rejects shallow pre-built templates and embraces foundational design. Every component is built and reasoned from first principles, integrating theoretical CS, AI, and cognitive science.

---

## Core Modules

- `decision_engine.py` — Orchestrator logic; main policy function and action decision loop.
- `rule_engine.py` — Symbolic guardrails and constraints to enforce ethical and logical limits.
- `policy_module.py` — Placeholder or learned policy suggesting actions beyond symbolic logic.
- `memory_manager.py` — Context and state summarization; approximates percept history.
- `nlp_pipeline.py` — NLP percept processing (intent, entity, and context extraction).
- `reward_model.py` — (Future) Utility and performance modeling for adaptive behaviors.

---

##  Architecture Overview

```plaintext
User sends WhatsApp message
        ↓
Make.com receives and forwards (as JSON)
        ↓
FastAPI webhook (main.py) receives JSON
        ↓
NLP Pipeline (nlp_pipeline.py)
   - Parse text
   - Extract intent and entities
        ↓
Memory Manager (memory_manager.py)
   - Load or update session state
        ↓
Decision Engine (decision_engine.py)
   - Core orchestrator logic
   - Calls Rule Engine (rule_engine.py) for constraints
   - Calls Policy Module (policy_module.py) for suggestions
        ↓
Rule Engine (rule_engine.py)
   - Check safety rules
   - Validate slots & guardrails
        ↓
Decision finalized (best action chosen)
        ↓
Memory Manager updates session context
        ↓
Create JSON reply
        ↓
Send reply back to Make.com
        ↓
WhatsApp API
        ↓
User receives responsePercepts (inputs) 
    ↓
NLP Pipeline (parse & extract) 
    ↓
Memory Manager (update state) 
    ↓
Decision Engine (core policy logic)
    ↓
Rule Engine (constraints & guardrails)
    ↓
Actions (outputs)
