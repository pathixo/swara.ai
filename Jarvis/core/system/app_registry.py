"""
App Registry — Application Name Resolution
=============================================
Maps human-friendly app names/aliases to concrete launch methods.
Loads from a JSON database and supports fuzzy matching so the LLM
doesn't need to know exact executable paths.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from difflib import get_close_matches
from typing import Optional

logger = logging.getLogger("jarvis.app_registry")


# ─────────────────────── Data Model ─────────────────────────────────────────

@dataclass
class AppEntry:
    """A registered application with its launch configuration."""
    name: str                       # Canonical key (lowercase, underscores)
    display_name: str               # Human-readable name
    aliases: list[str]              # Alternative names for matching
    launch_method: str              # "exe" | "uri" | "url" | "uwp" | "protocol"
    launch_target: str              # Path, URI scheme, or URL
    process_name: Optional[str]     # Process name for detection (e.g. "chrome.exe")
    category: str                   # "browser", "media", "dev_tool", etc.


# ─────────────────────── Registry ───────────────────────────────────────────

class AppRegistry:
    """
    Resolves application names to launch configurations.

    Loads known apps from app_registry.json and builds a lookup
    table keyed by canonical name + all aliases for fast matching.
    """

    def __init__(self, registry_path: Optional[str] = None):
        self._apps: dict[str, AppEntry] = {}
        self._alias_map: dict[str, str] = {}  # alias -> canonical name

        # Default to bundled JSON in same directory
        if registry_path is None:
            registry_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "app_registry.json",
            )

        self._registry_path = registry_path
        self._load()

    def _load(self) -> None:
        """Load app entries from JSON file."""
        if not os.path.exists(self._registry_path):
            logger.warning("App registry not found: %s", self._registry_path)
            return

        try:
            with open(self._registry_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for key, entry in data.items():
                app = AppEntry(
                    name=key,
                    display_name=entry.get("display_name", key),
                    aliases=entry.get("aliases", []),
                    launch_method=entry.get("launch_method", "exe"),
                    launch_target=entry.get("launch_target", ""),
                    process_name=entry.get("process_name"),
                    category=entry.get("category", "other"),
                )
                self._apps[key] = app

                # Build alias lookup (all lowercase)
                self._alias_map[key.lower()] = key
                for alias in app.aliases:
                    self._alias_map[alias.lower()] = key

            logger.info("App registry loaded: %d apps, %d aliases",
                        len(self._apps), len(self._alias_map))

        except Exception as e:
            logger.error("Failed to load app registry: %s", e)

    # ── Lookup ──────────────────────────────────────────────────────────

    def resolve(self, query: str) -> Optional[AppEntry]:
        """
        Resolve a user query to an AppEntry.

        Tries exact match first, then fuzzy matching on aliases.

        Args:
            query: App name as spoken/typed by user (e.g. "chrome", "vscode").

        Returns:
            AppEntry if found, None otherwise.
        """
        q = query.strip().lower()

        # 1. Exact alias match
        if q in self._alias_map:
            return self._apps[self._alias_map[q]]

        # 2. Fuzzy match against all aliases
        all_aliases = list(self._alias_map.keys())
        matches = get_close_matches(q, all_aliases, n=1, cutoff=0.7)
        if matches:
            canonical = self._alias_map[matches[0]]
            logger.info("Fuzzy resolved '%s' → '%s' (via alias '%s')", query, canonical, matches[0])
            return self._apps[canonical]

        # 3. Not found
        logger.debug("App not in registry: '%s'", query)
        return None

    def get(self, canonical_name: str) -> Optional[AppEntry]:
        """Get an app by its canonical name."""
        return self._apps.get(canonical_name)

    def list_all(self) -> list[AppEntry]:
        """Return all registered apps."""
        return list(self._apps.values())

    def list_by_category(self, category: str) -> list[AppEntry]:
        """Return apps in a specific category."""
        return [a for a in self._apps.values() if a.category == category.lower()]

    def categories(self) -> list[str]:
        """Return all unique categories."""
        return sorted(set(a.category for a in self._apps.values()))

    @property
    def count(self) -> int:
        return len(self._apps)
