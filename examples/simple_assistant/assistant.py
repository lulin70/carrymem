#!/usr/bin/env python3
"""
Simple AI Assistant with CarryMem

A minimal but complete example showing how to build an AI assistant
that remembers user preferences and context.

Usage:
    python assistant.py
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from memory_classification_engine import CarryMem


class SimpleAssistant:
    """Simple AI assistant with memory"""
    
    def __init__(self):
        """Initialize assistant"""
        # Initialize CarryMem with default settings
        self.memory = CarryMem()
        print("🤖 Simple Assistant initialized!")
        print("I'll remember our conversations.\n")
    
    def chat(self, user_input: str) -> str:
        """
        Process user input and generate response
        
        Args:
            user_input: User's message
            
        Returns:
            Assistant's response
        """
        # Store the input as memory
        self.memory.classify_and_remember(user_input)
        
        # Search for related memories
        related = self.memory.recall_memories(user_input, limit=3)
        
        # Generate response based on memory
        if len(related) > 1:
            return f"I remember you mentioned something similar before: '{related[1]['content']}'"
        else:
            return "Got it! I'll remember that."
    
    def run(self):
        """Run the assistant"""
        print("Type 'exit' to quit\n")
        
        while True:
            try:
                user_input = input("You: ")
                
                if user_input.lower() in ['exit', 'quit']:
                    print("👋 Goodbye!")
                    break
                
                if not user_input.strip():
                    continue
                
                response = self.chat(user_input)
                print(f"Assistant: {response}\n")
                
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"Error: {e}\n")


if __name__ == "__main__":
    assistant = SimpleAssistant()
    assistant.run()
