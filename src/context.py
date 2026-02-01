"""
VibeCoder - 컨텍스트 팩 생성기

핵심 원칙:
- 컨텍스트는 "주입"이 아니라 "조회"
- 히스토리 통째 주입 금지
- 주소(state) + 근거(evidence) + 최근 N턴만
"""

import os
import yaml
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

from memory import get_memory_store


@dataclass
class ContextPack:
    """컨텍스트 팩 - LLM에 전달할 최소 정보"""
    # 프로젝트 상태 (SSOT)
    project_state: str

    # 현재 작업 컨텍스트
    current_task: str

    # 관련 파일 (근거)
    related_files: List[Dict]

    # 최근 대화 (N턴만)
    recent_turns: List[Dict]

    # 열린 이슈
    open_issues: List[Dict]

    # 최근 변경
    recent_changes: str

    def to_prompt(self) -> str:
        """LLM 프롬프트로 변환"""
        sections = []

        # 프로젝트 상태
        sections.append("[PROJECT STATE]")
        sections.append(self.project_state)
        sections.append("")

        # 현재 작업
        if self.current_task:
            sections.append("[CURRENT TASK]")
            sections.append(self.current_task)
            sections.append("")

        # 관련 파일
        if self.related_files:
            sections.append("[RELATED FILES]")
            for f in self.related_files[:5]:  # 최대 5개
                sections.append(f"--- {f['path']} ---")
                content = f.get('content', '')
                if len(content) > 500:
                    content = content[:500] + "\n... (truncated)"
                sections.append(content)
                sections.append("")

        # 열린 이슈
        if self.open_issues:
            sections.append("[OPEN ISSUES]")
            for issue in self.open_issues[:3]:  # 최대 3개
                sections.append(f"- [{issue['severity']}] {issue['title']}")
            sections.append("")

        # 최근 변경
        if self.recent_changes:
            sections.append("[RECENT CHANGES]")
            sections.append(self.recent_changes[:500])
            sections.append("")

        # 최근 대화
        if self.recent_turns:
            sections.append("[RECENT CONVERSATION]")
            for turn in self.recent_turns[-3:]:  # 최근 3턴만
                role = turn.get('role', 'unknown')
                content = turn.get('content', '')[:200]
                sections.append(f"{role}: {content}")
            sections.append("")

        return "\n".join(sections)


class ContextBuilder:
    """컨텍스트 팩 빌더"""

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root).resolve()
        self.memory = get_memory_store()
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        """설정 로드"""
        config_path = self.project_root / "config" / "models.yaml"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        return {}

    def _read_ssot(self) -> str:
        """SSOT 문서 읽기"""
        ssot_parts = []

        # HANDOVER.md (현재 상태)
        handover_path = self.project_root / "HANDOVER.md"
        if handover_path.exists():
            content = handover_path.read_text(encoding="utf-8")
            # 요약만 추출 (처음 50줄)
            lines = content.split('\n')[:50]
            ssot_parts.append("## Current State (HANDOVER.md)")
            ssot_parts.append('\n'.join(lines))

        # CONSTITUTION.md (헌법) - 핵심만
        constitution_path = self.project_root / "CONSTITUTION.md"
        if constitution_path.exists():
            content = constitution_path.read_text(encoding="utf-8")
            # 처음 30줄만
            lines = content.split('\n')[:30]
            ssot_parts.append("\n## Rules (CONSTITUTION.md)")
            ssot_parts.append('\n'.join(lines))

        return '\n'.join(ssot_parts) if ssot_parts else "(No SSOT documents found)"

    def _get_recent_changes(self) -> str:
        """최근 변경 사항 (git diff) - 빠른 버전"""
        import subprocess

        try:
            # 빠른 타임아웃으로 git 상태만 확인
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
        """관련 파일 조회 - 비활성화 (성능 문제)"""
        # 파일 검색이 UI 블로킹을 유발하므로 비활성화
        # 필요시 사용자가 read_file 도구로 직접 요청
        return []

    def build(self, task: str = "", query: str = "") -> ContextPack:
        """컨텍스트 팩 생성"""
        # 프로젝트 상태 (SSOT)
        project_state = self._read_ssot()

        # 최근 대화 (N턴만)
        recent_turns = self.memory.get_recent_turns(
            limit=self.config.get("context", {}).get("max_recent_turns", 5)
        )

        # 열린 이슈
        open_issues = self.memory.get_open_issues()

        # 최근 변경
        recent_changes = self._get_recent_changes()

        # 관련 파일
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
# 싱글톤 인스턴스
# ============================================

_context_builder: Optional[ContextBuilder] = None


def get_context_builder(project_root: str = ".") -> ContextBuilder:
    """컨텍스트 빌더 싱글톤"""
    global _context_builder
    if _context_builder is None:
        _context_builder = ContextBuilder(project_root)
    return _context_builder


# ============================================
# 테스트
# ============================================

if __name__ == "__main__":
    print("=" * 60)
    print("  VibeCoder Context Builder Test")
    print("=" * 60)

    builder = ContextBuilder(".")

    print("\n[1] Building context pack...")
    pack = builder.build(task="테스트 컨텍스트 생성")

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
