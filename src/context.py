"""
MADORO CODE - Context Pack Generator

Core Principles:
- Context is "queried", not "injected"
- Never inject entire history
- State + evidence + only recent N turns
"""

import os
import yaml
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

from memory import get_memory_store


@dataclass
class ContextPack:
    """Context Pack - Minimal info to pass to LLM"""
    # Project state (SSOT)
    project_state: str

    # Current task context
    current_task: str

    # Related files (evidence)
    related_files: List[Dict]

    # Recent conversation (N turns only)
    recent_turns: List[Dict]

    # Open issues
    open_issues: List[Dict]

    # Recent changes
    recent_changes: str

    def to_prompt(self) -> str:
        """Convert to LLM prompt"""
        sections = []

        # Project state
        sections.append("[PROJECT STATE]")
        sections.append(self.project_state)
        sections.append("")

        # Current task
        if self.current_task:
            sections.append("[CURRENT TASK]")
            sections.append(self.current_task)
            sections.append("")

        # Related files
        if self.related_files:
            sections.append("[RELATED FILES]")
            for f in self.related_files[:5]:  # Max 5
                sections.append(f"--- {f['path']} ---")
                content = f.get('content', '')
                if len(content) > 500:
                    content = content[:500] + "\n... (truncated)"
                sections.append(content)
                sections.append("")

        # Open issues
        if self.open_issues:
            sections.append("[OPEN ISSUES]")
            for issue in self.open_issues[:3]:  # Max 3
                sections.append(f"- [{issue['severity']}] {issue['title']}")
            sections.append("")

        # Recent changes
        if self.recent_changes:
            sections.append("[RECENT CHANGES]")
            sections.append(self.recent_changes[:500])
            sections.append("")

        # Recent conversation
        if self.recent_turns:
            sections.append("[RECENT CONVERSATION]")
            for turn in self.recent_turns[-3:]:  # Last 3 turns only
                role = turn.get('role', 'unknown')
                content = turn.get('content', '')[:200]
                sections.append(f"{role}: {content}")
            sections.append("")

        return "\n".join(sections)


class ContextBuilder:
    """Context Pack Builder"""

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root).resolve()
        self.memory = get_memory_store()
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        """Load configuration"""
        config_path = self.project_root / "config" / "models.yaml"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        return {}

    def _read_ssot(self) -> str:
        """Read SSOT documents"""
        ssot_parts = []

        # HANDOVER.md (current state)
        handover_path = self.project_root / "HANDOVER.md"
        if handover_path.exists():
            content = handover_path.read_text(encoding="utf-8")
            # Extract summary only (first 50 lines)
            lines = content.split('\n')[:50]
            ssot_parts.append("## Current State (HANDOVER.md)")
            ssot_parts.append('\n'.join(lines))

        # CONSTITUTION.md (rules) - core only
        constitution_path = self.project_root / "CONSTITUTION.md"
        if constitution_path.exists():
            content = constitution_path.read_text(encoding="utf-8")
            # First 30 lines only
            lines = content.split('\n')[:30]
            ssot_parts.append("\n## Rules (CONSTITUTION.md)")
            ssot_parts.append('\n'.join(lines))

        return '\n'.join(ssot_parts) if ssot_parts else "(No SSOT documents found)"

    def _get_recent_changes(self) -> str:
        """Get recent changes (git diff) - fast version"""
        import subprocess

        try:
            # Quick timeout, check git status only
            result = subprocess.run(
                ["git", "status", "--short"],
                capture_output=True,
                text=True,
                timeout=3,
                cwd=self.project_root
            )
            if result.returncode == 0:
                return result.stdout[:300] if result.stdout else "(No changes)"
            return "(Not a git repo)"
        except:
            return ""

    def _get_related_files(self, query: str = "",
                           max_files: int = 5) -> List[Dict]:
        """Get related files - disabled (performance issue)"""
        # File search causes UI blocking, so disabled
        # User can request via read_file tool when needed
        return []

    def build(self, task: str = "", query: str = "") -> ContextPack:
        """Build context pack"""
        # Project state (SSOT)
        project_state = self._read_ssot()

        # Recent conversation (N turns only)
        recent_turns = self.memory.get_recent_turns(
            limit=self.config.get("context", {}).get("max_recent_turns", 5)
        )

        # Open issues
        open_issues = self.memory.get_open_issues()

        # Recent changes
        recent_changes = self._get_recent_changes()

        # Related files
        related_files = self._get_related_files(
            query=query,
            max_files=self.config.get("context", {}).get("max_related_files", 10)
        )

        return ContextPack(
            project_state=project_state,
            current_task=task,
            related_files=related_files,
            recent_turns=[{
                "role": t.role,
                "content": t.content
            } for t in recent_turns],
            open_issues=[{
                "severity": i.severity,
                "title": i.title
            } for i in open_issues],
            recent_changes=recent_changes
        )


# ============================================
# Singleton Instance
# ============================================

_context_builder: Optional[ContextBuilder] = None


def get_context_builder(project_root: str = ".") -> ContextBuilder:
    """Context builder singleton"""
    global _context_builder
    if _context_builder is None:
        _context_builder = ContextBuilder(project_root)
    return _context_builder


# ============================================
# Test
# ============================================

if __name__ == "__main__":
    print("=" * 60)
    print("  MADORO CODE Context Builder Test")
    print("=" * 60)

    builder = ContextBuilder(".")

    print("\n[1] Building context pack...")
    pack = builder.build(task="Test context generation")

    print("\n[2] Context Pack Contents:")
    print(f"  Project state: {len(pack.project_state)} chars")
    print(f"  Current task: {pack.current_task}")
    print(f"  Related files: {len(pack.related_files)}")
    print(f"  Recent turns: {len(pack.recent_turns)}")
    print(f"  Open issues: {len(pack.open_issues)}")

    print("\n[3] Generated Prompt Preview:")
    prompt = pack.to_prompt()
    print(prompt[:500])
    print("...")

    print("\n" + "=" * 60)
