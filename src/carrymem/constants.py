"""CarryMem Path Constants and Configuration.

This module centralizes all path configurations to improve portability
and eliminate hardcoded paths throughout the codebase.

All paths support environment variable overrides for flexibility.
"""

import os
from pathlib import Path
from typing import Optional


# ============================================================================
# Base Directories
# ============================================================================

HOME_DIR = Path.home()
"""User's home directory"""

DEFAULT_CONFIG_DIR = HOME_DIR / ".carrymem"
"""Default CarryMem configuration directory"""


# ============================================================================
# Configurable Paths (Environment Variable Support)
# ============================================================================

def get_config_dir() -> Path:
    """Get CarryMem configuration directory.
    
    Environment variable: CARRYMEM_CONFIG_DIR
    Default: ~/.carrymem
    """
    config_dir = os.getenv("CARRYMEM_CONFIG_DIR")
    if config_dir:
        return Path(config_dir).expanduser().resolve()
    return DEFAULT_CONFIG_DIR


def get_db_path() -> Path:
    """Get database file path.
    
    Environment variable: CARRYMEM_DB_PATH
    Default: ~/.carrymem/memories.db
    """
    db_path = os.getenv("CARRYMEM_DB_PATH")
    if db_path:
        return Path(db_path).expanduser().resolve()
    return get_config_dir() / "memories.db"


def get_config_file() -> Path:
    """Get configuration file path.
    
    Environment variable: CARRYMEM_CONFIG_FILE
    Default: ~/.carrymem/config.yaml
    """
    config_file = os.getenv("CARRYMEM_CONFIG_FILE")
    if config_file:
        return Path(config_file).expanduser().resolve()
    return get_config_dir() / "config.yaml"


def get_log_dir() -> Path:
    """Get log directory path.
    
    Environment variable: CARRYMEM_LOG_DIR
    Default: ~/.carrymem/logs
    """
    log_dir = os.getenv("CARRYMEM_LOG_DIR")
    if log_dir:
        return Path(log_dir).expanduser().resolve()
    return get_config_dir() / "logs"


def get_cache_dir() -> Path:
    """Get cache directory path.
    
    Environment variable: CARRYMEM_CACHE_DIR
    Default: ~/.carrymem/cache
    """
    cache_dir = os.getenv("CARRYMEM_CACHE_DIR")
    if cache_dir:
        return Path(cache_dir).expanduser().resolve()
    return get_config_dir() / "cache"


def get_backup_dir() -> Path:
    """Get backup directory path.
    
    Environment variable: CARRYMEM_BACKUP_DIR
    Default: ~/.carrymem/backups
    """
    backup_dir = os.getenv("CARRYMEM_BACKUP_DIR")
    if backup_dir:
        return Path(backup_dir).expanduser().resolve()
    return get_config_dir() / "backups"


# ============================================================================
# MCP Integration Paths
# ============================================================================

def get_mcp_config_path(tool: str) -> Optional[Path]:
    """Get MCP configuration file path for a specific tool.
    
    Args:
        tool: Tool name ('cursor', 'claude', 'windsurf', 'cline', etc.)
    
    Returns:
        Path to MCP config file, or None if tool not recognized
    """
    tool = tool.lower()
    
    mcp_paths = {
        'cursor': HOME_DIR / ".cursor" / "mcp.json",
        'claude': HOME_DIR / ".claude" / "mcp.json",
        'claude-code': HOME_DIR / ".claude" / "mcp.json",
        'windsurf': HOME_DIR / ".windsurf" / "mcp.json",
        'cline': HOME_DIR / ".cline" / "mcp.json",
        'continue': HOME_DIR / ".continue" / "config.json",
        'aider': HOME_DIR / ".aider" / "mcp.json",
    }
    
    # Check for environment variable override
    env_var = f"CARRYMEM_MCP_{tool.upper()}_CONFIG"
    custom_path = os.getenv(env_var)
    if custom_path:
        return Path(custom_path).expanduser().resolve()
    
    return mcp_paths.get(tool)


MCP_CONFIG_CURSOR = get_mcp_config_path('cursor')
"""Cursor MCP configuration file path"""

MCP_CONFIG_CLAUDE = get_mcp_config_path('claude')
"""Claude Code MCP configuration file path"""

MCP_CONFIG_WINDSURF = get_mcp_config_path('windsurf')
"""Windsurf MCP configuration file path"""

MCP_CONFIG_CLINE = get_mcp_config_path('cline')
"""Cline MCP configuration file path"""

TRAE_MCP_CONFIG = HOME_DIR / ".trae" / "mcp.json"
"""TRAE MCP configuration file path"""

TRAE_CN_DIR = HOME_DIR / ".trae-cn"
"""TRAE-CN configuration directory"""

TRAE_CN_MCP_CONFIG = TRAE_CN_DIR / "mcp.json"
"""TRAE-CN MCP configuration file path"""

CLAUDE_GLOBAL_CONFIG = HOME_DIR / ".claude.json"
"""Claude Code global configuration file path"""


# ============================================================================
# Security: Dangerous System Directories
# ============================================================================

DANGEROUS_SYSTEM_DIRS = [
    Path('/etc'),
    Path('/usr'),
    Path('/bin'),
    Path('/sbin'),
    Path('/System'),
    Path('/Library'),
    Path('/private/etc'),
]
"""System directories that should never be written to or read from as data paths"""


# ============================================================================
# Knowledge Base Paths (Obsidian, etc.)
# ============================================================================

def get_obsidian_vault_path() -> Optional[Path]:
    """Get Obsidian vault path.
    
    Environment variable: CARRYMEM_OBSIDIAN_VAULT
    Default: ~/Documents/Obsidian (if exists)
    """
    vault_path = os.getenv("CARRYMEM_OBSIDIAN_VAULT")
    if vault_path:
        return Path(vault_path).expanduser().resolve()
    
    # Try common default locations
    common_locations = [
        HOME_DIR / "Documents" / "Obsidian",
        HOME_DIR / "Obsidian",
        HOME_DIR / "Documents" / "ObsidianVault",
    ]
    
    for location in common_locations:
        if location.exists() and location.is_dir():
            return location
    
    return None


OBSIDIAN_DEFAULT_VAULT = get_obsidian_vault_path()
"""Default Obsidian vault path (if found)"""


# ============================================================================
# Temporary and Runtime Paths
# ============================================================================

def get_temp_dir() -> Path:
    """Get temporary directory for CarryMem.
    
    Environment variable: CARRYMEM_TEMP_DIR
    Default: System temp dir / carrymem
    """
    temp_dir = os.getenv("CARRYMEM_TEMP_DIR")
    if temp_dir:
        return Path(temp_dir).expanduser().resolve()
    
    import tempfile
    return Path(tempfile.gettempdir()) / "carrymem"


def get_lock_file() -> Path:
    """Get lock file path for preventing concurrent access.
    
    Environment variable: CARRYMEM_LOCK_FILE
    Default: ~/.carrymem/carrymem.lock
    """
    lock_file = os.getenv("CARRYMEM_LOCK_FILE")
    if lock_file:
        return Path(lock_file).expanduser().resolve()
    return get_config_dir() / "carrymem.lock"


# ============================================================================
# Path Utilities
# ============================================================================

def ensure_dir_exists(path: Path) -> Path:
    """Ensure directory exists, create if necessary.
    
    Args:
        path: Directory path
    
    Returns:
        The path (for chaining)
    
    Raises:
        PermissionError: If cannot create directory
    """
    path = Path(path)
    if not path.exists():
        try:
            path.mkdir(parents=True, exist_ok=True)
        except PermissionError as e:
            raise PermissionError(
                f"Cannot create directory {path}: {e}"
            ) from e
    return path


def validate_path_safety(path: Path, allowed_base: Optional[Path] = None) -> bool:
    """Validate that a path is safe to use.
    
    Args:
        path: Path to validate
        allowed_base: If provided, path must be within this directory
    
    Returns:
        True if path is safe
    
    Raises:
        ValueError: If path is unsafe
    """
    path = Path(path).resolve()
    
    # Check if path escapes allowed base
    if allowed_base:
        allowed_base = Path(allowed_base).resolve()
        try:
            path.relative_to(allowed_base)
        except ValueError:
            raise ValueError(
                f"Path {path} escapes allowed directory {allowed_base}"
            )
    
    # Check for dangerous system directories
    for dangerous in DANGEROUS_SYSTEM_DIRS:
        try:
            path.relative_to(dangerous)
            raise ValueError(
                f"Path {path} points to dangerous system directory {dangerous}"
            )
        except ValueError:
            # Path is not relative to dangerous dir, which is good
            continue
    
    return True


# ============================================================================
# Initialization
# ============================================================================

def initialize_directories() -> None:
    """Initialize all required directories.
    
    Creates config, log, cache, and backup directories if they don't exist.
    """
    directories = [
        get_config_dir(),
        get_log_dir(),
        get_cache_dir(),
        get_backup_dir(),
    ]
    
    for directory in directories:
        ensure_dir_exists(directory)


# ============================================================================
# Export commonly used paths
# ============================================================================

CONFIG_DIR = get_config_dir()
DB_PATH = get_db_path()
CONFIG_FILE = get_config_file()
LOG_DIR = get_log_dir()
CACHE_DIR = get_cache_dir()
BACKUP_DIR = get_backup_dir()
TEMP_DIR = get_temp_dir()
LOCK_FILE = get_lock_file()


__all__ = [
    # Base directories
    'HOME_DIR',
    'DEFAULT_CONFIG_DIR',
    
    # Getter functions
    'get_config_dir',
    'get_db_path',
    'get_config_file',
    'get_log_dir',
    'get_cache_dir',
    'get_backup_dir',
    'get_temp_dir',
    'get_lock_file',
    'get_mcp_config_path',
    'get_obsidian_vault_path',
    
    # Commonly used paths
    'CONFIG_DIR',
    'DB_PATH',
    'CONFIG_FILE',
    'LOG_DIR',
    'CACHE_DIR',
    'BACKUP_DIR',
    'TEMP_DIR',
    'LOCK_FILE',
    
    # MCP paths
    'MCP_CONFIG_CURSOR',
    'MCP_CONFIG_CLAUDE',
    'MCP_CONFIG_WINDSURF',
    'MCP_CONFIG_CLINE',
    'TRAE_MCP_CONFIG',
    'TRAE_CN_DIR',
    'TRAE_CN_MCP_CONFIG',
    'CLAUDE_GLOBAL_CONFIG',

    # Security
    'DANGEROUS_SYSTEM_DIRS',

    # Knowledge base paths
    'OBSIDIAN_DEFAULT_VAULT',
    
    # Utilities
    'ensure_dir_exists',
    'validate_path_safety',
    'initialize_directories',
]
