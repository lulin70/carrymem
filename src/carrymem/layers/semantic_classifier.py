import json

from carrymem.utils.logger import logger


class SemanticClassifier:
    """LLM-backed classifier that assigns a memory type to messages."""

    def __init__(self, config):
        self.config = config
        self.llm_enabled = self.config.get("llm.enabled", False)
        self.llm_api_key = self.config.get("llm.api_key", "")
        self.llm_model = self.config.get("llm.model", "glm-4-plus")
        self.llm_temperature = self.config.get("llm.temperature", 0.3)
        self.llm_max_tokens = self.config.get("llm.max_tokens", 500)
        self.llm_timeout = self.config.get("llm.timeout", 30)

        # LLM client
        self.llm_client = self._init_llm_client()

        # Classification prompt template
        self.classification_prompt = (
            "You are a memory classification assistant. Your task is to "
            "classify the given message into one of the following memory types:"
            "\n\n"
            "1. user_preference: User's explicitly expressed preferences, "
            "habits, and style requirements\n"
            "2. correction: User's correction of AI's judgment or output\n"
            "3. fact_declaration: User's statements about themselves or business facts\n"
            "4. decision: Clear conclusions or choices reached in the conversation\n"
            "5. relationship: Information about relationships between people, teams, and organizations\n"
            "6. task_pattern: Repeated task types and their processing methods\n"
            "7. sentiment_marker: User's explicit emotional tendency towards a topic\n"
            "\n"
            "Please also determine the appropriate memory tier for storage:\n"
            "- Tier 2: Procedural Memory (user_preference, task_pattern)\n"
            "- Tier 3: Episodic Memory (correction, decision, sentiment_marker)\n"
            "- Tier 4: Semantic Memory (fact_declaration, relationship)\n"
            "\n"
            "Message: {message}\n"
            "Context: {context}\n"
            "\n"
            "Please return your classification in JSON format with the following fields:\n"
            "- memory_type: The classified memory type\n"
            "- tier: The appropriate memory tier\n"
            "- confidence: A float between 0 and 1 indicating your confidence in the classification\n"
            "- reason: A brief explanation of your classification"
        )

    def _init_llm_client(self):
        """Initialize LLM client."""
        if not self.llm_enabled:
            return None

        # Attempt to initialize LLM client from available providers
        # Supports ZhipuAI (GLM) as primary LLM backend
        try:
            from zhipuai import ZhipuAI

            if self.llm_api_key:
                return ZhipuAI(api_key=self.llm_api_key)
        except ImportError:
            pass

        return None

    def classify(self, message, context=None, execution_context=None):
        """Classify message using LLM."""
        if not self.llm_enabled or not self.llm_client:
            return None

        try:
            # Format classification prompt
            prompt = self.classification_prompt.format(message=message, context=context or "")

            # Append execution context if available
            if execution_context:
                prompt += f"\n\nExecution Context: {json.dumps(execution_context)}"

            # Call LLM API
            response = self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.llm_temperature,
                max_tokens=self.llm_max_tokens,
                timeout=self.llm_timeout,
            )

            # Parse LLM response
            content = response.choices[0].message.content
            result = json.loads(content)

            return result
        except Exception as e:
            logger.error("Semantic classification failed: %s", e)
            return None

    def should_use_llm(self, message, context=None):
        """Determine whether LLM should be used for classification."""
        # Cost control logic can be implemented here
        return True
