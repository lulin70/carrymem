"""Semantic Expander — Zero-dependency semantic query expansion for CarryMem.

Provides:
- Synonym graph expansion
- Spell correction via edit distance
- Cross-language mapping
- Token-aware CJK/EN/JP tokenization

Architecture:
    query → tokenize → synonym_expand → spell_correct → cross_lang_map → expanded_queries
"""

from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

try:
    from carrymem.utils.logger import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)


class SemanticExpander:
    """Zero-dependency semantic expander for memory recall.

    Usage:
        expander = SemanticExpander()
        expansions = expander.expand("数据库", language="zh")
        # → ["数据库", "database", "DB", "PostgreSQL", "MySQL", ...]

        expansions = expander.expand("Postgres", language="en")
        # → ["Postgres", "PostgreSQL"]  (spell-corrected)
    """

    def __init__(
        self,
        custom_synonym_files: Optional[List[str]] = None,
        enable_spell_correction: bool = True,
        max_expansions: int = 50,
        edit_distance_threshold: int = 2,
    ):
        self._synonym_graph: Dict[str, List[str]] = {}
        self._enable_spell = enable_spell_correction
        self._max_expansions = max_expansions
        self._edit_threshold = edit_distance_threshold
        self._vocabulary: Set[str] = set()
        self._loaded = False

        self._load_builtin_synonyms()

        if custom_synonym_files:
            self._load_custom_synonyms(custom_synonym_files)

    def _load_builtin_synonyms(self):
        """Load built-in synonym YAML files from package data directory."""
        if not YAML_AVAILABLE:
            return

        data_dir = Path(__file__).parent / "data"
        yaml_files = [
            "synonyms_technical_cn.yaml",
            "synonyms_daily_en.yaml",
            "synonyms_jp.yaml",
        ]

        for yaml_file in yaml_files:
            file_path = data_dir / yaml_file
            if file_path.exists():
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                        if isinstance(data, dict):
                            for term, synonyms in data.items():
                                if isinstance(synonyms, list):
                                    self._add_to_graph(term, synonyms)
                except Exception as e:
                    logger.warning(f"Failed to load synonym file {yaml_file}: {e}")

        self._loaded = True

    def _load_custom_synonyms(self, files: List[str]):
        """Load user-provided synonym YAML files."""
        if not YAML_AVAILABLE:
            return

        for file_path in files:
            path = Path(file_path)
            if path.exists():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                        if isinstance(data, dict):
                            for term, synonyms in data.items():
                                if isinstance(synonyms, list):
                                    self._add_to_graph(term, synonyms)
                except Exception as e:
                    logger.warning(f"Failed to load custom synonym file {file_path}: {e}")

    def _add_to_graph(self, term: str, synonyms: List[str]):
        """Add term and its synonyms to the graph."""
        term_lower = term.lower().strip()
        all_terms = [term_lower] + [s.lower().strip() for s in synonyms if isinstance(s, str)]

        for t in all_terms:
            if t and len(t) > 0:
                self._vocabulary.add(t)
                if t not in self._synonym_graph:
                    self._synonym_graph[t] = []
                for other in all_terms:
                    if other != t and other not in self._synonym_graph[t]:
                        self._synonym_graph[t].append(other)

    def expand(
        self,
        query: str,
        language: Optional[str] = None,
    ) -> List[str]:
        """Expand a query into semantically related terms.

        Args:
            query: Original search query
            language: Optional language hint ("en", "zh", "ja", or auto-detect)

        Returns:
            List of expanded queries including original + synonyms + corrections
        """
        if not query or not query.strip():
            return [query] if query else []

        # Use cached version for better performance
        result = self._expand_cached(query.strip(), language or "auto")
        return list(result)

    @lru_cache(maxsize=1000)
    def _expand_cached(
        self,
        query: str,
        language: str,
    ) -> Tuple[str, ...]:
        """Cached version of expand for performance.

        Returns tuple instead of list for hashability.
        """
        expansions: Set[str] = set()
        expansions.add(query)

        tokens = self._tokenize(query)

        for token in tokens:
            if len(token) < 2:
                continue

            token_lower = token.lower()

            # Phase 1: Synonym expansion
            synonyms = self._synonym_graph.get(token_lower, [])
            for syn in synonyms:
                if len(expansions) < self._max_expansions:
                    expansions.add(syn)

            # Phase 2: Spell correction
            if self._enable_spell and token_lower not in self._vocabulary:
                corrected = self._spell_correct(token_lower)
                if corrected and corrected != token_lower:
                    expansions.add(corrected)
                    # Also expand corrections
                    corr_synonyms = self._synonym_graph.get(corrected, [])
                    for syn in corr_synonyms:
                        if len(expansions) < self._max_expansions:
                            expansions.add(syn)

        result = list(expansions)

        # Always put original query first
        if query in result:
            result.remove(query)
        result.insert(0, query)

        return tuple(result[: self._max_expansions])

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text with CJK awareness.

        - English: split by whitespace and punctuation
        - Chinese/Japanese: extract individual words/phrases, then generate
          bigram/trigram sub-tokens for long CJK sequences to improve overlap matching
        """
        tokens = []
        current_token = ""
        is_cjk_mode = False

        for char in text:
            cjk_char = "\u4e00" <= char <= "\u9fff" or "\u3040" <= char <= "\u309f" or "\u30a0" <= char <= "\u30ff"

            if cjk_char:
                if current_token and not is_cjk_mode:
                    tokens.append(current_token.strip())
                    current_token = ""
                current_token += char
                is_cjk_mode = True
            elif char in " \t\n\r-,.;:!?'\"()[]{}":
                if current_token:
                    tokens.append(current_token.strip())
                    current_token = ""
                is_cjk_mode = False
            else:
                if is_cjk_mode and current_token:
                    tokens.append(current_token.strip())
                    current_token = ""
                current_token += char
                is_cjk_mode = False

        if current_token:
            tokens.append(current_token.strip())

        expanded_tokens = []
        for t in tokens:
            if not t or len(t) < 1:
                continue
            expanded_tokens.append(t)
            if self._is_cjk_token(t) and len(t) > 2:
                for n in (2, 3):
                    for i in range(len(t) - n + 1):
                        sub = t[i : i + n]
                        if sub not in expanded_tokens:
                            expanded_tokens.append(sub)

        return expanded_tokens

    @staticmethod
    def _is_cjk_token(token: str) -> bool:
        return any("\u4e00" <= c <= "\u9fff" or "\u3040" <= c <= "\u309f" or "\u30a0" <= c <= "\u30ff" for c in token)

    def _spell_correct(self, word: str) -> Optional[str]:
        """Correct spelling using edit distance against vocabulary.

        Only corrects if:
        - Word not in vocabulary
        - Found candidate within edit_distance_threshold
        """
        if not self._vocabulary or word in self._vocabulary:
            return None

        best_match = None
        best_distance = self._edit_threshold + 1

        word_len = len(word)

        for vocab_word in self._vocabulary:
            vocab_len = len(vocab_word)

            if abs(word_len - vocab_len) > self._edit_threshold * 2:
                continue

            dist = self._edit_distance(word, vocab_word)
            if dist < best_distance:
                best_distance = dist
                best_match = vocab_word

        return best_match if best_distance <= self._edit_threshold else None

    @staticmethod
    def _edit_distance(s1: str, s2: str) -> int:
        """Calculate Levenshtein edit distance between two strings."""
        if len(s1) < len(s2):
            return SemanticExpander._edit_distance(s2, s1)

        if len(s2) == 0:
            return len(s1)

        previous_row = list(range(len(s2) + 1))

        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]

    @property
    def vocabulary_size(self) -> int:
        """Return number of terms in vocabulary."""
        return len(self._vocabulary)

    @property
    def graph_size(self) -> int:
        """Return number of entries in synonym graph."""
        return len(self._synonym_graph)

    @property
    def is_loaded(self) -> bool:
        """Return whether synonym data has been loaded."""
        return self._loaded

    def get_synonyms(self, term: str) -> List[str]:
        """Get synonyms for a specific term."""
        return self._synonym_graph.get(term.lower().strip(), [])

    def add_synonym(self, term: str, synonyms: List[str]):
        """Dynamically add a new synonym mapping at runtime."""
        self._add_to_graph(term, synonyms)
