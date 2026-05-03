# Simple AI Assistant Example

A minimal but complete example showing how to build an AI assistant with CarryMem.

## Features

- 💬 Interactive chat interface
- 🧠 Remembers conversation history
- 🔍 Recalls related memories
- ⚡ Zero configuration required

## Quick Start

```bash
# Run the assistant
python assistant.py
```

## Example Conversation

```
🤖 Simple Assistant initialized!
I'll remember our conversations.

Type 'exit' to quit

You: I prefer dark mode
Assistant: Got it! I'll remember that.

You: I like Python programming
Assistant: Got it! I'll remember that.

You: What do I prefer?
Assistant: I remember you mentioned something similar before: 'I prefer dark mode'

You: exit
👋 Goodbye!
```

## How It Works

```python
from memory_classification_engine import CarryMem

# Initialize CarryMem
memory = CarryMem()

# Store memories
memory.classify_and_remember("I prefer dark mode")

# Recall memories
results = memory.recall_memories("dark mode")
```

## Customization

### Change Database Location

```python
memory = CarryMem(storage_path="/path/to/database.db")
```

### Use Namespace

```python
memory = CarryMem(namespace="my_assistant")
```

### Adjust Recall Limit

```python
results = memory.recall_memories("query", limit=10)
```

## Next Steps

- Add natural language processing
- Integrate with LLM (GPT, Claude, etc.)
- Add voice interface
- Build web UI

## Learn More

- [Quick Start Guide](../../docs/QUICK_START_GUIDE.md)
- [User Stories](../../docs/USER_STORIES.md)
- [Architecture](../../docs/ARCHITECTURE.md)
