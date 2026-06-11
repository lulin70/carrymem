"""Example Notification Plugin for CarryMem.

Demonstrates the plugin system by:
- Subscribing to on_memory_stored hook
- Printing a console notification when sensitive memories are stored
- Subscribing to on_error hook for error logging

Usage:
    This plugin is auto-discovered by PluginManager when placed in the plugin directory.
"""

from typing import Any

from carrymem.plugins import HookPoint, PluginProtocol, PluginManager


class ExampleNotificationPlugin(PluginProtocol):
    """Example plugin that sends notifications when sensitive memories are stored."""

    name = "example_notification"
    version = "1.0.0"

    def __init__(self):
        self._notification_count: int = 0
        self._error_count: int = 0
        self._loaded: bool = False

    def on_load(self, carrymem: Any) -> None:
        """Called when the plugin is loaded."""
        self._loaded = True
        print(f"[{self.name}] Plugin loaded (v{self.version})")
        print(f"[{self.name}] Will notify on sensitive memory storage and errors")

    def on_unload(self) -> None:
        """Called when the plugin is unloaded."""
        self._loaded = False
        print(f"[{self.name}] Plugin unloaded. "
              f"Sent {self._notification_count} notifications, "
              f"logged {self._error_count} errors.")

    def on_memory_stored(self, memory_id: str = "", content: str = "",
                         classification: str = "", **kwargs: Any) -> None:
        """Called after a memory is stored.

        Prints a notification if the memory looks sensitive.
        """
        self._notification_count += 1

        # Simple sensitivity detection
        sensitive_keywords = [
            "password", "secret", "token", "api_key", "credential",
            "private", "confidential", "敏感", "密码", "密钥",
        ]
        content_lower = content.lower()
        is_sensitive = any(kw in content_lower for kw in sensitive_keywords)

        if is_sensitive:
            print(
                f"[{self.name}] ⚠️  SENSITIVE MEMORY DETECTED!\n"
                f"    ID: {memory_id}\n"
                f"    Classification: {classification}\n"
                f"    Content preview: {content[:80]}{'...' if len(content) > 80 else ''}"
            )
        elif self._notification_count % 10 == 0:
            # Periodic summary every 10 stores
            print(f"[{self.name}] Memory storage summary: "
                  f"{self._notification_count} memories processed so far.")

    def on_memory_recalled(self, query: str = "", results_count: int = 0,
                           **kwargs: Any) -> None:
        """Called after a memory recall operation."""
        pass  # No-op for this example; could log recall stats

    def on_classified(self, raw_text: str = "", classification: str = "",
                      **kwargs: Any) -> None:
        """Called after classification completes."""
        pass  # No-op for this example

    def on_error(self, error_type: str = "", error_message: str = "",
                 **kwargs: Any) -> None:
        """Called when an error occurs in CarryMem."""
        self._error_count += 1
        print(
            f"[{self.name}] 🚨 Error detected!\n"
            f"    Type: {error_type}\n"
            f"    Message: {error_message}"
        )


# Module-level singleton for auto-discovery
plugin = ExampleNotificationPlugin()
