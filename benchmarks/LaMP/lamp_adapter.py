#!/usr/bin/env python3
"""
LaMP Benchmark Adapter for CarryMem
Adapts CarryMem memory system to LaMP benchmark tasks
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.carrymem import CarryMem
from typing import List, Dict, Any, Optional
import json


class LaMP_CarryMem_Adapter:
    """Adapter to use CarryMem with LaMP benchmark"""
    
    def __init__(self, model_name: str = "claude-sonnet-4-20250514"):
        """
        Initialize CarryMem adapter for LaMP
        
        Args:
            model_name: LLM model to use (default: Claude Sonnet 4)
        """
        self.model_name = model_name
        self.memory_systems = {}  # user_id -> CarryMem instance
        
    def get_or_create_memory(self, user_id: str) -> CarryMem:
        """Get or create CarryMem instance for a user"""
        if user_id not in self.memory_systems:
            self.memory_systems[user_id] = CarryMem(
                model=self.model_name,
                memory_type="classified",
                enable_rules_engine=True
            )
        return self.memory_systems[user_id]
    
    def add_user_profile(self, user_id: str, profile: List[Dict[str, Any]]):
        """
        Add user profile/history to memory
        
        Args:
            user_id: User identifier
            profile: List of user's historical data (reviews, citations, etc.)
        """
        memory = self.get_or_create_memory(user_id)
        
        # Add each profile item to memory
        for item in profile:
            # Convert profile item to memory format
            memory_text = self._profile_item_to_text(item)
            memory.add_memory(memory_text)
    
    def _profile_item_to_text(self, item: Dict[str, Any]) -> str:
        """Convert profile item to text"""
        # Handle different LaMP task formats
        if "text" in item:
            return item["text"]
        elif "title" in item and "abstract" in item:
            return f"Title: {item['title']}\nAbstract: {item['abstract']}"
        elif "review" in item:
            return item["review"]
        else:
            return json.dumps(item)
    
    def query_with_memory(self, user_id: str, query: str, task_type: str) -> str:
        """
        Query with user's memory context
        
        Args:
            user_id: User identifier
            query: Query/input for the task
            task_type: LaMP task type (lamp-1, lamp-2, etc.)
            
        Returns:
            Model's response
        """
        memory = self.get_or_create_memory(user_id)
        
        # Build prompt based on task type
        prompt = self._build_task_prompt(query, task_type)
        
        # Query with memory context
        response = memory.query(prompt)
        
        return response
    
    def _build_task_prompt(self, query: str, task_type: str) -> str:
        """Build task-specific prompt"""
        
        task_prompts = {
            "lamp-1": f"Based on my research interests, would I cite this paper?\n\n{query}\n\nAnswer with 'yes' or 'no'.",
            "lamp-2": f"Based on my movie preferences, what tags would I give to this movie?\n\n{query}\n\nProvide comma-separated tags.",
            "lamp-3": f"Based on my product review history, what rating (1-5 stars) would I give to this product?\n\n{query}\n\nProvide only the rating number.",
            "lamp-4": f"Based on my writing style, generate a news headline for this article:\n\n{query}",
            "lamp-5": f"Based on my writing style, write a scholarly title for this abstract:\n\n{query}",
            "lamp-6": f"Based on my email writing style, write an email subject for:\n\n{query}",
            "lamp-7": f"Based on my tweet style, write a tweet about:\n\n{query}"
        }
        
        return task_prompts.get(task_type, query)
    
    def reset_memory(self, user_id: Optional[str] = None):
        """Reset memory for a user or all users"""
        if user_id:
            if user_id in self.memory_systems:
                del self.memory_systems[user_id]
        else:
            self.memory_systems.clear()


def test_adapter():
    """Test the adapter with sample data"""
    print("Testing LaMP CarryMem Adapter...")
    print("=" * 60)
    
    adapter = LaMP_CarryMem_Adapter()
    
    # Test user
    user_id = "test_user_001"
    
    # Add sample profile
    profile = [
        {"text": "I love action movies with great special effects"},
        {"text": "I prefer movies with strong character development"},
        {"text": "I usually give 5 stars to Marvel movies"}
    ]
    
    print(f"\nAdding profile for user {user_id}...")
    adapter.add_user_profile(user_id, profile)
    print("✅ Profile added")
    
    # Test query
    query = "Movie: Avengers Endgame - Epic superhero movie with amazing visual effects and emotional character arcs"
    print(f"\nQuery: {query}")
    
    response = adapter.query_with_memory(user_id, query, "lamp-3")
    print(f"\nResponse: {response}")
    
    print("\n" + "=" * 60)
    print("✅ Adapter test complete")


if __name__ == "__main__":
    test_adapter()
