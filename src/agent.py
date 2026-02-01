"""
MADORO CODE - 에이전트 루프

작동 플로우:
1. 사용자 요청
2. 컨텍스트 팩 생성 (SSOT + 관련 파일 + 최근 대화)
3. LLM이 툴콜(JSON)로 패치 생성
4. Executor가 패치 적용
5. 테스트 실행
6. 로그 기록 → 다시 모델에 피드백
"""

import json
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from memory import get_memory_store
from llm import get_llm_client, LLMResponse
from tools import ToolExecutor, TOOL_DEFINITIONS, ToolResult
from context import get_context_builder, ContextPack


@dataclass
class AgentResponse:
    """에이전트 응답"""
    message: str
    tool_results: List[Dict] = None
    error: Optional[str] = None


class Agent:
    """MADORO CODE 에이전트"""

    SYSTEM_PROMPT = """You are MADORO CODE, a coding assistant.

Core Principles:
1. Memory is managed by the system. Don't try to remember entire conversation history.
2. Only reference the provided context (SSOT docs, related files, recent conversation).
3. Use tools when file modifications are needed.
4. Don't guess - use the search tool when you need to find something.

Response Rules:
- Respond in the same language the user uses
- Use apply_patch tool for code modifications
- Use run_tests tool when testing is needed
- If the user pastes content directly, analyze it immediately without using file read tools
- Only use read_file tool when the user mentions a file path without providing content
- Avoid unnecessary tool calls: respond directly if the user already provided the information
"""

    MAX_ITERATIONS = 5  # 최대 툴콜 반복 횟수

    def __init__(self, project_root: str = ".", progress_callback=None,
                 ssot_approval_callback=None):
        self.project_root = project_root
        self.memory = get_memory_store()
        self.llm = get_llm_client()
        self.tools = ToolExecutor(project_root, ssot_approval_callback=ssot_approval_callback)
        self.context_builder = get_context_builder(project_root)
        self.progress_callback = progress_callback  # Progress callback
        self.ssot_approval_callback = ssot_approval_callback  # SSOT file approval callback

    def _report_progress(self, status: str, detail: str = ""):
        """Report progress"""
        print(f"[Agent] {status}: {detail}")
        if self.progress_callback:
            self.progress_callback(status, detail)

    def process(self, user_input: str) -> AgentResponse:
        """Process user input"""
        self._report_progress("Starting", user_input[:50])

        # 대화 턴 기록
        self.memory.add_turn("user", user_input)

        # Build context pack
        self._report_progress("Building context", "Loading project state...")
        context_pack = self.context_builder.build(
            task=user_input,
            query=self._extract_search_query(user_input)
        )
        self._report_progress("Context ready", f"{len(context_pack.project_state)} chars")

        # LLM 호출 (툴콜 포함)
        all_tool_results = []
        final_response = None

        for iteration in range(self.MAX_ITERATIONS):
            # 프롬프트 구성
            prompt = self._build_prompt(user_input, context_pack, all_tool_results)

            # 현재 모델명 가져오기
            model_cfg = self.llm.get_model_config()
            model_name = model_cfg.display_name if model_cfg else "LLM"
            self._report_progress("LLM call", f"Waiting for {model_name}...")

            try:
                response = self.llm.generate_with_tools(
                    prompt=prompt,
                    tools=TOOL_DEFINITIONS,
                    system=self.SYSTEM_PROMPT
                )
                self._report_progress("LLM response", f"Received {len(response.content)} chars")
            except Exception as e:
                self._report_progress("LLM error", str(e))
                return AgentResponse(
                    message="",
                    error=f"LLM call failed: {e}"
                )

            # 툴콜 처리
            if response.tool_calls:
                for tool_call in response.tool_calls:
                    tool_name = tool_call.get("tool", "")
                    tool_args = tool_call.get("args", {})

                    # Show tool execution status
                    tool_detail = self._get_tool_detail(tool_name, tool_args)
                    self._report_progress("Running tool", f"{tool_name}: {tool_detail}")

                    result = self.tools.execute(tool_name, tool_args)
                    status = "✓" if result.success else "✗"
                    self._report_progress("Tool done", f"{status} {tool_name}")

                    all_tool_results.append({
                        "tool": tool_name,
                        "args": tool_args,
                        "success": result.success,
                        "output": result.output[:500],
                        "error": result.error
                    })

                # Auto-run tests after patch applied
                if any(tc.get("tool") == "apply_patch" and tc.get("success")
                       for tc in all_tool_results):
                    self._report_progress("Running tests", "Executing pytest...")
                    test_result = self.tools.execute("run_tests", {"cmd": "pytest -q"})
                    status = "✓ Passed" if test_result.success else "✗ Failed"
                    self._report_progress("Tests done", status)
                    all_tool_results.append({
                        "tool": "run_tests (auto)",
                        "success": test_result.success,
                        "output": test_result.output[:300]
                    })
            else:
                # 툴콜 없으면 최종 응답
                final_response = response.content
                break

        if not final_response:
            # Generate final response after tool iterations
            self._report_progress("Generating", "Summarizing results...")
            summary_prompt = self._build_summary_prompt(
                user_input, context_pack, all_tool_results
            )
            try:
                response = self.llm.generate(summary_prompt, system=self.SYSTEM_PROMPT)
                final_response = response.content
            except Exception as e:
                final_response = f"Task complete. (Summary generation failed: {e})"

        self._report_progress("Complete", "")

        # 응답 기록
        self.memory.add_turn("assistant", final_response[:500])

        # 작업 로그
        self.memory.log_work(
            action="CHAT",
            target="agent",
            description=user_input[:100],
            result="SUCCESS",
            details={
                "tool_calls": len(all_tool_results),
                "response_length": len(final_response)
            }
        )

        return AgentResponse(
            message=final_response,
            tool_results=all_tool_results
        )

    def _get_tool_detail(self, tool_name: str, args: Dict) -> str:
        """도구 실행 상세 정보 생성"""
        if tool_name == "read_file":
            return args.get("path", "")[:50]
        elif tool_name == "search":
            return f'"{args.get("query", "")}"'
        elif tool_name == "apply_patch":
            files = args.get("files", [])
            if files:
                return f"{len(files)}개 파일"
            return ""
        elif tool_name == "run_tests":
            return args.get("cmd", "pytest")[:30]
        elif tool_name == "list_files":
            return args.get("path", ".")[:30]
        elif tool_name == "get_diff":
            return "git 변경사항"
        return ""

    def _extract_search_query(self, user_input: str) -> str:
        """사용자 입력에서 검색 쿼리 추출"""
        # 간단한 키워드 추출
        keywords = []
        for word in user_input.split():
            if len(word) > 2 and not word.startswith(('이', '그', '저', '뭐', '어떻')):
                keywords.append(word)
        return ' '.join(keywords[:3])

    def _build_prompt(self, user_input: str, context: ContextPack,
                      tool_results: List[Dict]) -> str:
        """LLM 프롬프트 구성"""
        parts = []

        # 컨텍스트
        parts.append(context.to_prompt())

        # 이전 툴 결과
        if tool_results:
            parts.append("[TOOL RESULTS]")
            for tr in tool_results[-3:]:  # 최근 3개만
                status = "✅" if tr.get("success") else "❌"
                parts.append(f"{status} {tr.get('tool')}: {tr.get('output', '')[:200]}")
            parts.append("")

        # 사용자 요청
        parts.append("[USER REQUEST]")
        parts.append(user_input)

        return "\n".join(parts)

    def _build_summary_prompt(self, user_input: str, context: ContextPack,
                              tool_results: List[Dict]) -> str:
        """최종 요약 프롬프트"""
        parts = []

        parts.append("다음 작업을 완료했습니다. 결과를 요약해주세요.")
        parts.append("")
        parts.append(f"[요청] {user_input}")
        parts.append("")
        parts.append("[수행된 작업]")
        for tr in tool_results:
            status = "성공" if tr.get("success") else "실패"
            parts.append(f"- {tr.get('tool')}: {status}")
            if tr.get("error"):
                parts.append(f"  오류: {tr.get('error')}")

        return "\n".join(parts)

    def doctor(self) -> str:
        """프로젝트 상태 진단 (vibe doctor)"""
        context = self.context_builder.build(task="프로젝트 상태 점검")

        report = []
        report.append("=" * 60)
        report.append("  MADORO CODE Doctor - 프로젝트 상태 리포트")
        report.append("=" * 60)
        report.append("")

        # 프로젝트 상태
        report.append("[📋 프로젝트 상태]")
        # HANDOVER.md에서 현재 상태 추출
        if "현재 상태" in context.project_state:
            for line in context.project_state.split('\n'):
                if '|' in line and ('버전' in line or '단계' in line or '작업' in line):
                    report.append(f"  {line.strip()}")
        report.append("")

        # 열린 이슈
        report.append("[🐛 열린 이슈]")
        if context.open_issues:
            for issue in context.open_issues:
                report.append(f"  [{issue['severity']}] {issue['title']}")
        else:
            report.append("  없음")
        report.append("")

        # 최근 변경
        report.append("[📝 최근 변경]")
        if context.recent_changes and context.recent_changes != "(No git history)":
            for line in context.recent_changes.split('\n')[:5]:
                report.append(f"  {line}")
        else:
            report.append("  변경 없음")
        report.append("")

        # 최근 대화
        report.append("[💬 최근 대화]")
        if context.recent_turns:
            for turn in context.recent_turns[-3:]:
                content = turn['content'][:50] + "..." if len(turn['content']) > 50 else turn['content']
                report.append(f"  [{turn['role']}] {content}")
        else:
            report.append("  대화 없음")
        report.append("")

        # 모델 상태
        report.append("[🤖 모델 상태]")
        report.append(f"  현재 모델: {self.llm.current_model}")
        connected = self.llm.check_connection()
        report.append(f"  Ollama 연결: {'✅ 정상' if connected else '❌ 연결 안됨'}")
        if connected:
            for model_key in self.llm.list_models():
                available = self.llm.check_model_available(model_key)
                cfg = self.llm.models[model_key]
                status = "✅" if available else "❌"
                report.append(f"  {status} {cfg.display_name}")
        report.append("")

        report.append("=" * 60)

        return "\n".join(report)


# ============================================
# 싱글톤 인스턴스
# ============================================

_agent: Optional[Agent] = None


def get_agent(project_root: str = ".") -> Agent:
    """에이전트 싱글톤"""
    global _agent
    if _agent is None:
        _agent = Agent(project_root)
    return _agent


# ============================================
# 테스트
# ============================================

if __name__ == "__main__":
    print("=" * 60)
    print("  MADORO CODE Agent Test")
    print("=" * 60)

    agent = Agent(".")

    print("\n[1] Doctor")
    print(agent.doctor())

    print("\n[2] Connection Check")
    if agent.llm.check_connection():
        print("  Ollama connected!")

        # 간단한 테스트
        print("\n[3] Simple Request")
        response = agent.process("현재 디렉토리의 파일 목록을 보여줘")
        print(f"  Response: {response.message[:200]}...")
        if response.tool_results:
            print(f"  Tool calls: {len(response.tool_results)}")
    else:
        print("  ❌ Ollama not connected. Start Ollama first.")

    print("\n" + "=" * 60)
