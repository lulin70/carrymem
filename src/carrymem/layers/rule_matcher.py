import re
from typing import Dict, List, Optional, Any
from carrymem.utils.helpers import extract_content
from carrymem.utils.language import language_manager

class RuleMatcher:
    """Rule-based memory matcher."""
    
    def __init__(self, rules: List[Dict[str, Any]]):
        """Initialize the rule matcher.
        
        Args:
            rules: List of rules to use for matching.
        """
        self.rules = rules
    
    def match(self, message: str, context: Optional[Dict[str, Any]] = None, execution_context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Match rules against a message.
        
        Args:
            message: The message to match against.
            context: Optional context for the message.
            execution_context: Optional execution context containing feedback signals.
            
        Returns:
            A list of matching memories, sorted by priority (highest first).
        """
        matches = []
        
        # Handle None message
        if message is None:
            return matches
        
        language, _ = language_manager.detect_language(message)
        
        for rule in self.rules:
            pattern = rule.get('pattern')
            memory_type = rule.get('memory_type')
            tier = rule.get('tier')
            action = rule.get('action')
            description = rule.get('description')
            rule_language = rule.get('language')
            priority = rule.get('priority', 5)  # Default priority if not specified
            
            if rule_language and rule_language != "all" and rule_language != language:
                continue
            
            if re.search(pattern, message):
                if action == "extract":
                    # For extract action, use the entire message as content
                    content = message
                else:
                    content = extract_content(message, pattern, action)
                
                if content:
                    # Build source field, ensure preference rules include 'preference' in source
                    if memory_type == 'user_preference':
                        source = 'rule:preference'
                    else:
                        source = f'rule:{pattern}'
                    
                    match = {
                        'memory_type': memory_type,
                        'tier': tier,
                        'content': content,
                        'source': source,
                        'description': description,
                        'language': language,
                        'priority': priority  # Add priority to match
                    }
                    matches.append(match)
        
        # Sort matches by priority (highest first)
        matches.sort(key=lambda x: x.get('priority', 5), reverse=True)
        
        return matches
    
    def add_rule(self, rule: Dict[str, Any]):
        """Add a new rule to the matcher.
        
        Args:
            rule: The rule to add.
        """
        self.rules.append(rule)
    
    def remove_rule(self, pattern: str):
        """Remove a rule from the matcher.
        
        Args:
            pattern: The pattern of the rule to remove.
        """
        self.rules = [rule for rule in self.rules if rule.get('pattern') != pattern]
    
    def get_rules(self) -> List[Dict[str, Any]]:
        """Get all rules.
        
        Returns:
            List of rules.
        """
        return self.rules
