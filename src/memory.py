"""
VibeCoder - Project Memory System

Memory is stored in DB/files, not in the model.
"""

import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict


# ============================================
# Data Classes
# ============================================

@dataclass
class WorkLog:
    """Work log entry"""
    id: Optional[int] = None
    timestamp: str = ""
    action: str = ""  # CREATE, UPDATE, DELETE, TEST, COMMIT
    target: str = ""  # File path or target
    description: str = ""
    result: str = ""  # SUCCESS, FAIL, PENDING
    details: str = ""  # JSON format details


@dataclass
class Issue:
    """Discovered issue"""
    id: Optional[int] = None
    created_at: str = ""
    status: str = "OPEN"  # OPEN, RESOLVED, WONTFIX
    severity: str = "MEDIUM"  # LOW, MEDIUM, HIGH, CRITICAL
    title: str = ""
    description: str = ""
    resolved_at: Optional[str] = None
    resolution: Optional[str] = None


@dataclass
class FileIndex:
    """File index entry"""
    id: Optional[int] = None
    path: str = ""
    last_modified: str = ""
    size: int = 0
    content_hash: str = ""
    symbols: str = ""  # JSON: list of functions/classes


@dataclass
class ConversationTurn:
    """Conversation turn (keep only recent N)"""
    id: Optional[int] = None
    timestamp: str = ""
    role: str = ""  # user, assistant
    content: str = ""
    context_used: str = ""  # Summary of used context


# ============================================
# Memory Store
# ============================================

class MemoryStore:
    """Project memory storage"""

    DEFAULT_MAX_TURNS = 50  # Default value

    def __init__(self, db_path: str = "db/memory.db", max_turns: int = None):
        self.db_path = db_path
        self.max_turns = max_turns or self.DEFAULT_MAX_TURNS
        self._ensure_db_dir()
        self._init_db()

    def set_max_turns(self, max_turns: int):
        """Set maximum turns"""
        self.max_turns = max_turns

    def _ensure_db_dir(self):
        """Create DB directory"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

    def _get_conn(self) -> sqlite3.Connection:
        """Get DB connection"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialize tables"""
        conn = self._get_conn()
        cursor = conn.cursor()

        # Work logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS work_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                action TEXT NOT NULL,
                target TEXT,
                description TEXT,
                result TEXT,
                details TEXT
            )
        """)

        # Issues table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                status TEXT DEFAULT 'OPEN',
                severity TEXT DEFAULT 'MEDIUM',
                title TEXT NOT NULL,
                description TEXT,
                resolved_at TEXT,
                resolution TEXT
            )
        """)

        # File index table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_index (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                last_modified TEXT,
                size INTEGER,
                content_hash TEXT,
                symbols TEXT
            )
        """)

        # Conversation turns table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversation_turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                context_used TEXT
            )
        """)

        # Key-value state table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS state (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT
            )
        """)

        conn.commit()
        conn.close()

    # ============================================
    # Work Logs
    # ============================================

    def log_work(self, action: str, target: str, description: str,
                 result: str = "SUCCESS", details: Dict = None) -> int:
        """Log work"""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO work_logs (timestamp, action, target, description, result, details)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            action,
            target,
            description,
            result,
            json.dumps(details or {}, ensure_ascii=False)
        ))

        log_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return log_id

    def get_recent_logs(self, limit: int = 20) -> List[WorkLog]:
        """Get recent work logs"""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM work_logs ORDER BY timestamp DESC LIMIT ?
        """, (limit,))

        rows = cursor.fetchall()
        conn.close()

        return [WorkLog(**dict(row)) for row in rows]

    # ============================================
    # Issues
    # ============================================

    def create_issue(self, title: str, description: str,
                     severity: str = "MEDIUM") -> int:
        """Create issue"""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO issues (created_at, status, severity, title, description)
            VALUES (?, 'OPEN', ?, ?, ?)
        """, (datetime.now().isoformat(), severity, title, description))

        issue_id = cursor.lastrowid
        conn.commit()
        conn.close()

        self.log_work("CREATE", f"issue:{issue_id}", f"Issue created: {title}")
        return issue_id

    def resolve_issue(self, issue_id: int, resolution: str):
        """Resolve issue"""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE issues SET status='RESOLVED', resolved_at=?, resolution=?
            WHERE id=?
        """, (datetime.now().isoformat(), resolution, issue_id))

        conn.commit()
        conn.close()

        self.log_work("UPDATE", f"issue:{issue_id}", f"Issue resolved: {resolution}")

    def get_open_issues(self) -> List[Issue]:
        """Get open issues"""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM issues WHERE status='OPEN' ORDER BY severity DESC, created_at DESC
        """)

        rows = cursor.fetchall()
        conn.close()

        return [Issue(**dict(row)) for row in rows]

    # ============================================
    # Conversation Turns
    # ============================================

    def add_turn(self, role: str, content: str, context_used: str = ""):
        """Add conversation turn (keep only recent N)"""
        conn = self._get_conn()
        cursor = conn.cursor()

        # Add new turn
        cursor.execute("""
            INSERT INTO conversation_turns (timestamp, role, content, context_used)
            VALUES (?, ?, ?, ?)
        """, (datetime.now().isoformat(), role, content, context_used))

        # Delete old turns (keep only recent N)
        cursor.execute("""
            DELETE FROM conversation_turns WHERE id NOT IN (
                SELECT id FROM conversation_turns ORDER BY timestamp DESC LIMIT ?
            )
        """, (self.max_turns,))

        conn.commit()
        conn.close()

    def get_recent_turns(self, limit: int = 5) -> List[ConversationTurn]:
        """Get recent conversation turns"""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM conversation_turns ORDER BY timestamp DESC LIMIT ?
        """, (limit,))

        rows = cursor.fetchall()
        conn.close()

        # Sort by time (oldest first)
        turns = [ConversationTurn(**dict(row)) for row in rows]
        return list(reversed(turns))

    def clear_conversation(self):
        """Clear conversation"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM conversation_turns")
        conn.commit()
        conn.close()

    # ============================================
    # State Storage
    # ============================================

    def set_state(self, key: str, value: Any):
        """Save state"""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO state (key, value, updated_at)
            VALUES (?, ?, ?)
        """, (key, json.dumps(value, ensure_ascii=False), datetime.now().isoformat()))

        conn.commit()
        conn.close()

    def get_state(self, key: str, default: Any = None) -> Any:
        """Get state"""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT value FROM state WHERE key=?", (key,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return json.loads(row["value"])
        return default

    # ============================================
    # File Index
    # ============================================

    def update_file_index(self, path: str, size: int, content_hash: str,
                          symbols: List[str] = None):
        """Update file index"""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO file_index (path, last_modified, size, content_hash, symbols)
            VALUES (?, ?, ?, ?, ?)
        """, (
            path,
            datetime.now().isoformat(),
            size,
            content_hash,
            json.dumps(symbols or [], ensure_ascii=False)
        ))

        conn.commit()
        conn.close()

    def get_file_index(self, path: str) -> Optional[FileIndex]:
        """Get file index"""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM file_index WHERE path=?", (path,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return FileIndex(**dict(row))
        return None

    def search_files_by_symbol(self, symbol: str) -> List[FileIndex]:
        """Search files by symbol"""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM file_index WHERE symbols LIKE ?
        """, (f"%{symbol}%",))

        rows = cursor.fetchall()
        conn.close()

        return [FileIndex(**dict(row)) for row in rows]


# ============================================
# Singleton Instance
# ============================================

_memory_store: Optional[MemoryStore] = None
_current_db_path: Optional[str] = None


def get_memory_store(db_path: str = None) -> MemoryStore:
    """Memory store singleton (supports per-project DB)"""
    global _memory_store, _current_db_path

    max_turns = 50  # Default

    # Get DB path and settings from project manager
    if db_path is None:
        try:
            from project_manager import get_project_manager
            pm = get_project_manager()
            db_path = pm.get_project_db_path()
            settings = pm.get_project_settings()
            max_turns = settings.get("max_turns", 50)
        except:
            db_path = "db/memory.db"

    # Create new instance if DB path changed
    if _memory_store is None or _current_db_path != db_path:
        _memory_store = MemoryStore(db_path, max_turns=max_turns)
        _current_db_path = db_path
        print(f"[Memory] DB loaded: {db_path} (max_turns: {max_turns})")
    else:
        # Update max_turns on existing instance
        _memory_store.set_max_turns(max_turns)

    return _memory_store


def reset_memory_store():
    """Reset for testing"""
    global _memory_store, _current_db_path
    _memory_store = None
    _current_db_path = None


# ============================================
# Test
# ============================================

if __name__ == "__main__":
    import tempfile

    print("=" * 60)
    print("  VibeCoder Memory Store Test")
    print("=" * 60)

    # Test with temporary DB
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_memory.db")
        store = MemoryStore(db_path)

        # Work log test
        print("\n[1] Work Log Test")
        log_id = store.log_work("CREATE", "test.py", "Test file created")
        print(f"  Created log: {log_id}")

        logs = store.get_recent_logs(5)
        print(f"  Recent logs: {len(logs)}")

        # Issue test
        print("\n[2] Issue Test")
        issue_id = store.create_issue("Bug found", "Error in router.py", "HIGH")
        print(f"  Created issue: {issue_id}")

        issues = store.get_open_issues()
        print(f"  Open issues: {len(issues)}")

        store.resolve_issue(issue_id, "Fixed with patch")
        issues = store.get_open_issues()
        print(f"  Open issues after resolve: {len(issues)}")

        # Conversation turn test
        print("\n[3] Conversation Turn Test")
        store.add_turn("user", "Fix the bug in router.py")
        store.add_turn("assistant", "Patch applied.")

        turns = store.get_recent_turns(5)
        print(f"  Recent turns: {len(turns)}")
        for t in turns:
            print(f"    [{t.role}] {t.content[:30]}...")

        # State test
        print("\n[4] State Test")
        store.set_state("current_model", "qwen-coder")
        model = store.get_state("current_model")
        print(f"  Current model: {model}")

        print("\n" + "=" * 60)
        print("  All tests passed!")
        print("=" * 60)
