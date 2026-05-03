"""Classification pipeline for coordinating classification layers."""

import re
from typing import Dict, List, Optional, Any
from memory_classification_engine.layers.rule_matcher import RuleMatcher
from memory_classification_engine.layers.pattern_analyzer import PatternAnalyzer
from memory_classification_engine.layers.semantic_classifier import SemanticClassifier
from memory_classification_engine.utils.logger import logger
from memory_classification_engine.utils.confirmation import is_confirmation, summarize_context


class ClassificationPipeline:
    """Coordinates the classification layers in order."""
    
    def __init__(self, config: Any):
        """Initialize classification pipeline.
        
        Args:
            config: Configuration manager instance.
        """
        self.config = config
        
        rules = config.get_rules().get('rules', [])
        self.rule_matcher = RuleMatcher(rules)
        self.pattern_analyzer = PatternAnalyzer()
        
        self.semantic_classifier = SemanticClassifier(self.config)
    
    def classify(self, message: str, context: Optional[Dict[str, Any]] = None, execution_context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Classify a message through the pipeline.
        
        Args:
            message: The message to classify.
            context: Optional context for the message.
            execution_context: Optional execution context containing feedback signals.
            
        Returns:
            List of classification matches.
        """
        rule_matches = self.rule_matcher.match(message, context, execution_context)
        
        if rule_matches:
            logger.debug(f"Rule matching found {len(rule_matches)} matches")
            return rule_matches
        
        pattern_matches = self.pattern_analyzer.analyze(message, context, execution_context)
        
        if pattern_matches:
            logger.debug(f"Pattern analysis found {len(pattern_matches)} matches")
            return pattern_matches
        
        semantic_matches = self.semantic_classifier.classify(message, context, execution_context)
        
        if semantic_matches:
            logger.debug(f"Semantic classification found {len(semantic_matches)} matches")
            return semantic_matches
        
        logger.debug("No classification matches found")
        return []
    
    def classify_with_defaults(self, message: str, language: str, context: Optional[Dict[str, Any]] = None, execution_context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Classify a message with default fallback.

        Phase A Fix #1 (Critical): Noise filtering at pipeline level to prevent
        _get_default_classification() from generating false positives on noise.

        Args:
            message: The message to classify.
            language: The detected language code.
            context: Optional context for the message.
            execution_context: Optional execution context containing feedback signals.

        Returns:
            List of classification matches, with default if no matches found.
        """
        # Phase A Fix #1: Pipeline-level noise filtering (P0-3d)
        # This prevents _get_default_classification from matching noise messages
        ai_reply = None
        if context and isinstance(context, dict):
            ai_reply = context.get('ai_reply', '')

        is_confirmation_with_context = bool(ai_reply and is_confirmation(message))

        if self.pattern_analyzer._is_noise(message) and not is_confirmation_with_context:
            return []

        matches = self.classify(message, context, execution_context)
        
        if not matches:
            default_match = self._get_default_classification(message, language)
            if default_match:
                matches = [default_match]

        if matches and context and isinstance(context, dict):
            ai_reply = context.get('ai_reply', '')
            if ai_reply and is_confirmation(message):
                for match in matches:
                    match_type = match.get('memory_type') or match.get('type', '')
                    if match_type in ('decision', 'correction'):
                        if not match.get('context_source'):
                            ai_summary = summarize_context(ai_reply)
                            original_content = match.get('content', '')
                            if original_content and len(original_content) > 5:
                                match['content'] = f"{original_content}: {ai_summary}"
                            else:
                                match['content'] = f"Confirmed: {ai_summary}"
                            match['context_source'] = 'ai_reply'
                            match['original_user_message'] = message
        
        return matches
    
    def _get_default_classification(self, message: str, language: str) -> Optional[Dict[str, Any]]:
        """Get default classification for a message when no other matches found.

        V4-03 Fix: Added quality gates to reduce FP from 18 to <10.
        - Minimum length requirement (skip ultra-short messages)
        - Chitchat/blacklist keyword filtering
        - Content substance check (require meaningful keywords)

        Args:
            message: The message to classify.
            language: The detected language code.

        Returns:
            A default classification match if found, None otherwise.
        """
        from memory_classification_engine.utils.language import language_manager

        # Handle None message
        if message is None:
            return {
                'memory_type': 'fact_declaration',
                'tier': 3,
                'content': '',
                'confidence': 0.5,
                'source': 'default:general',
                'description': 'General fact declaration',
                'language': language
            }

        message_lower = message.lower()
        msg_stripped = message.strip()

        # === V4-03 Quality Gate 1: Minimum length (ultra-short = likely noise) ===
        if len(msg_stripped) < 8:
            return None

        # === V4-03 Quality Gate 2: Chitchat/Noise blacklist ===
        chitchat_blacklist = [
            # Weather/small talk
            'sunny', 'rainy', 'weather', 'beautiful day', 'pretty',
            # Acknowledgments that slipped through
            'sounds good', 'oh really', 'interesting', 'hmm', 'cool',
            # Filler responses
            'see you', 'okay', 'ok then', 'alright', 'sure thing',
            # Emojis/short reactions
            '😎', '😊', '👍', '🎉', '❤️', '💪', '🔥',
            # Question-like but not real questions
            'really?', 'right?', 'yes?', 'no?',
        ]
        if any(black in message_lower for black in chitchat_blacklist):
            return None

        # === V4-03 Quality Gate 3: Require substantive content ===
        # Messages with only 1-2 words are likely noise/chitchat
        word_count = len(msg_stripped.split())
        if word_count <= 2 and len(msg_stripped) < 20:
            return None
        
        preference_keywords = language_manager.get_keywords('user_preference', language)
        correction_keywords = language_manager.get_keywords('correction', language)
        fact_keywords = language_manager.get_keywords('fact_declaration', language)
        decision_keywords = language_manager.get_keywords('decision', language)
        relationship_keywords = language_manager.get_keywords('relationship', language)
        task_keywords = language_manager.get_keywords('task_pattern', language)
        sentiment_keywords = language_manager.get_keywords('sentiment_marker', language)
        
        if any(keyword in message_lower for keyword in preference_keywords):
            return {
                'memory_type': 'user_preference',
                'tier': 2,
                'content': message,
                'confidence': 0.9,
                'source': 'default:preference',
                'description': 'User preference detected',
                'language': language
            }
        elif any(keyword in message_lower for keyword in correction_keywords):
            return {
                'memory_type': 'correction',
                'tier': 3,
                'content': message,
                'confidence': 0.8,
                'source': 'default:correction',
                'description': 'Correction detected',
                'language': language
            }
        elif any(keyword in message_lower for keyword in fact_keywords):
            return {
                'memory_type': 'fact_declaration',
                'tier': 3,
                'content': message,
                'confidence': 0.7,
                'source': 'default:fact',
                'description': 'Fact declaration detected',
                'language': language
            }
        elif any(keyword in message_lower for keyword in decision_keywords):
            return {
                'memory_type': 'decision',
                'tier': 2,
                'content': message,
                'confidence': 0.8,
                'source': 'default:decision',
                'description': 'Decision detected',
                'language': language
            }
        elif any(keyword in message_lower for keyword in relationship_keywords):
            return {
                'memory_type': 'relationship',
                'tier': 3,
                'content': message,
                'confidence': 0.7,
                'source': 'default:relationship',
                'description': 'Relationship information detected',
                'language': language
            }
        elif any(keyword in message_lower for keyword in task_keywords):
            return {
                'memory_type': 'task_pattern',
                'tier': 2,
                'content': message,
                'confidence': 0.8,
                'source': 'default:task',
                'description': 'Task pattern detected',
                'language': language
            }
        elif any(keyword in message_lower for keyword in sentiment_keywords):
            return {
                'memory_type': 'sentiment_marker',
                'tier': 3,
                'content': message,
                'confidence': 0.7,
                'source': 'default:sentiment',
                'description': 'Sentiment detected',
                'language': language
            }
        else:
            return {
                'memory_type': 'fact_declaration',
                'tier': 3,
                'content': message,
                'confidence': 0.5,
                'source': 'default:general',
                'description': 'General fact declaration',
                'language': language
            }
