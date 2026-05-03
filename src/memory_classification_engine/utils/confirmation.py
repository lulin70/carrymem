from typing import Dict, Optional
import re

_CONFIRMATION_PATTERNS = {
    'en': [
        r'^(ok|okay|sure|yes|yeah|yep|got it|sounds good|go ahead|let\'?s do it|agreed|fine|right|exactly|will do|make it so)$',
        r'^(good|great|perfect|nice|cool|alright|absolutely|definitely|roger)$',
        r'^(ok|okay|sure|yes|yeah|yep|sounds good|go ahead|agreed|fine|alright)[,\s]',
        r'^(sounds?\s+good)[,\s]',
    ],
    'zh': [
        r'^(好的|行|可以|没问题|就这样|同意|确认|对|嗯|是|好的呀|行吧|就这么办)$',
        r'^(好的|行|可以|没问题|就这样|同意|确认|对|嗯|是)[，,.]',
    ],
    'ja': [
        r'^(はい|いいよ|わかりました|オッケー|OK|そうしよう|賛成|了解|りょうかい)$',
    ],
}


def is_confirmation(message: str) -> bool:
    msg_lower = message.strip().lower().rstrip('!.。！')
    for lang_patterns in _CONFIRMATION_PATTERNS.values():
        for pattern in lang_patterns:
            if re.match(pattern, msg_lower):
                return True
    return False


def summarize_context(context_text: str, max_length: int = 100) -> str:
    if len(context_text) <= max_length:
        return context_text
    return context_text[:max_length - 3] + '...'


def has_confirmation_context(context: Optional[Dict]) -> bool:
    if not context or not isinstance(context, dict):
        return False
    return bool(context.get('ai_reply', ''))
