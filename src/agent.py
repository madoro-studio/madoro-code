"""
MADORO CODE - Agent Loop

Workflow:
1. User request
2. Build context pack (SSOT + related files + recent conversation)
3. LLM generates tool calls (JSON) for patches
4. Executor applies patches
5. Run tests
6. Log work -> feedback to model
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
    """Agent response"""
    message: str
    tool_results: List[Dict] = None
    error: Optional[str] = None


class Agent:
    """MADORO CODE Agent"""

    SYSTEM_PROMPT = """You are MADORO CODE, a coding assistant.

Core Principles:
1. Memory is managed by the system. Don't try to remember entire conversation history.
2. Only reference the provided context (SSOT docs, related files, recent conversation).
3. Use tools when file modifications are needed.
4. Don't guess - use the search tool when you need to find something.

Response Rules:
- Respond in the same language the user uses
- IMPORTANT: When creating or modifying files, ALWAYS use the apply_patch tool. Never just show code in text.
- Use apply_patch tool for: creating new files, writing code, schemas, configs, any file content
- Use run_tests tool when testing is needed
- Use git_commit tool when user asks to commit changes
- Use git_push tool when user asks to push to remote
- If the user pastes content directly, analyze it immediately without using file read tools
- Only use read_file tool when the user mentions a file path without providing content
- Avoid unnecessary tool calls: respond directly if the user already provided the information

File Creation Rules:
- When asked to create a file, schema, or any code: USE apply_patch tool immediately
- Format: {"tool": "apply_patch", "args": {"files": [{"path": "path/to/file.py", "content": "file content here"}]}}
- Do NOT just display code in response - actually create the file using the tool

Git Rules:
- When user says "commit", "커밋": use git_commit tool with appropriate message
- When user says "push", "푸시": use git_push tool
- Commit message should describe what changed

SSOT Update Rules (when user says "save", "update docs", "save progress"):
- Use update_ssot tool to update project documentation
- Analyze recent conversation to extract: completed tasks, decisions, progress
- Update appropriate files:
  - HANDOVER.md: Current state, completed items, in progress, next steps
  - CHECKLIST.md: Check completed items [x], add new items [ ]
  - DECISIONS.md: Add new architectural/design decisions
- Include brief description of changes
"""

    MAX_ITERATIONS = 5  # Max tool call iterations

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

        # Record conversation turn
        self.memory.add_turn("user", user_input)

        # Build context pack
        self._report_progress("Building context", "Loading project state...")
        context_pack = self.context_builder.build(
            task=user_input,
            query=self._extract_search_query(user_input)
        )
        self._report_progress("Context ready", f"{len(context_pack.project_state)} chars")

        # LLM call (with tool calls)
        all_tool_results = []
        final_response = None

        for iteration in range(self.MAX_ITERATIONS):
            # Build prompt
            prompt = self._build_prompt(user_input, context_pack, all_tool_results)

            # Get current model name
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

            # Process tool calls
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

                # Auto-run tests after patch applied (only if test files exist)
                if any(tc.get("tool") == "apply_patch" and tc.get("success")
                       for tc in all_tool_results):
                    # Check if test files exist before running tests
                    from pathlib import Path
                    project_path = Path(self.project_root)
                    test_files_exist = (
                        list(project_path.rglob("test_*.py")) or
                        list(project_path.rglob("*_test.py")) or
                        list(project_path.rglob("tests/*.py"))
                    )

                    if test_files_exist:
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
                        self._report_progress("Tests skipped", "No test files found")
            else:
                # No tool calls, final response
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

        # Record response
        self.memory.add_turn("assistant", final_response[:500])

        # Log work
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
        """Generate tool execution detail info"""
        if tool_name == "read_file":
            return args.get("path", "")[:50]
        elif tool_name == "search":
            return f'"{args.get("query", "")}"'
        elif tool_name == "apply_patch":
            files = args.get("files", [])
            if files:
                return f"{len(files)} files"
            return ""
        elif tool_name == "run_tests":
            return args.get("cmd", "pytest")[:30]
        elif tool_name == "list_files":
            return args.get("path", ".")[:30]
        elif tool_name == "get_diff":
            return "git changes"
        return ""

    def _extract_search_query(self, user_input: str) -> str:
        """Extract search query from user input"""
        # Simple keyword extraction
        keywords = []
        for word in user_input.split():
            if len(word) > 2:
                keywords.append(word)
        return ' '.join(keywords[:3])

    def _build_prompt(self, user_input: str, context: ContextPack,
                      tool_results: List[Dict]) -> str:
        """Build LLM prompt"""
        parts = []

        # Context
        parts.append(context.to_prompt())

        # Previous tool results
        if tool_results:
            parts.append("[TOOL RESULTS]")
            for tr in tool_results[-3:]:  # Last 3 only
                status = "✅" if tr.get("success") else "❌"
                parts.append(f"{status} {tr.get('tool')}: {tr.get('output', '')[:200]}")
            parts.append("")

        # User request
        parts.append("[USER REQUEST]")
        parts.append(user_input)

        return "\n".join(parts)

    def _build_summary_prompt(self, user_input: str, context: ContextPack,
                              tool_results: List[Dict]) -> str:
        """Build final summary prompt"""
        parts = []

        parts.append("The following tasks have been completed. Please summarize the results.")
        parts.append("")
        parts.append(f"[Request] {user_input}")
        parts.append("")
        parts.append("[Performed Tasks]")
        for tr in tool_results:
            status = "success" if tr.get("success") else "failed"
            parts.append(f"- {tr.get('tool')}: {status}")
            if tr.get("error"):
                parts.append(f"  Error: {tr.get('error')}")

        return "\n".join(parts)

    def doctor(self) -> str:
        """Project status diagnosis (vibe doctor)"""
        context = self.context_builder.build(task="Project status check")

        report = []
        report.append("=" * 60)
        report.append("  MADORO CODE Doctor - Project Status Report")
        report.append("=" * 60)
        report.append("")

        # Project status
        report.append("[📋 Project Status]")
        # Extract current state from HANDOVER.md
        if "Current" in context.project_state or "Status" in context.project_state:
            for line in context.project_state.split('\n'):
                if '|' in line:
                    report.append(f"  {line.strip()}")
        report.append("")

        # Open issues
        report.append("[🐛 Open Issues]")
        if context.open_issues:
            for issue in context.open_issues:
                report.append(f"  [{issue['severity']}] {issue['title']}")
        else:
            report.append("  None")
        report.append("")

        # Recent changes
        report.append("[📝 Recent Changes]")
        if context.recent_changes and context.recent_changes != "(No git history)":
            for line in context.recent_changes.split('\n')[:5]:
                report.append(f"  {line}")
        else:
            report.append("  No changes")
        report.append("")

        # Recent conversation
        report.append("[💬 Recent Conversation]")
        if context.recent_turns:
            for turn in context.recent_turns[-3:]:
                content = turn['content'][:50] + "..." if len(turn['content']) > 50 else turn['content']
                report.append(f"  [{turn['role']}] {content}")
        else:
            report.append("  No conversation")
        report.append("")

        # Model status
        report.append("[🤖 Model Status]")
        report.append(f"  Current model: {self.llm.current_model}")
        connected = self.llm.check_connection()
        report.append(f"  Ollama connection: {'✅ Connected' if connected else '❌ Not connected'}")
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
# Singleton Instance
# ============================================

_agent: Optional[Agent] = None


def get_agent(project_root: str = ".") -> Agent:
    """Agent singleton"""
    global _agent
    if _agent is None:
        _agent = Agent(project_root)
    return _agent


# ============================================
# Test
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

        # Simple test
        print("\n[3] Simple Request")
        response = agent.process("Show me the file list in current directory")
        print(f"  Response: {response.message[:200]}...")
        if response.tool_results:
            print(f"  Tool calls: {len(response.tool_results)}")
    else:
        print("  ❌ Ollama not connected. Start Ollama first.")

    print("\n" + "=" * 60)
