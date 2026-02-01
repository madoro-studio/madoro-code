"""
MADORO CODE - Tool Call System

4 core tools:
1. read_file - Read file content
2. search - Code search (ripgrep)
3. apply_patch - Apply patches
4. run_tests - Run tests
"""

import os
import subprocess
import json
import hashlib
import difflib
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from pathlib import Path

from memory import get_memory_store


# SSOT files that require user approval before modification
SSOT_FILES = [
    "HANDOVER.md",
    "CONSTITUTION.md",
    "ARCHITECTURE.md",
    "CHECKLIST.md",
    "DECISIONS.md"
]


@dataclass
class ToolResult:
    """Tool execution result"""
    success: bool
    output: str
    error: Optional[str] = None
    data: Optional[Dict] = None


class ToolExecutor:
    """Tool executor"""

    def __init__(self, project_root: str = ".", ssot_approval_callback: Callable = None):
        self.project_root = Path(project_root).resolve()
        self.memory = get_memory_store()
        # Callback for SSOT file approval (called from main thread)
        # Signature: callback(file_name: str, file_path: str, old_content: str, new_content: str) -> bool
        self.ssot_approval_callback = ssot_approval_callback
        # Pending SSOT changes that need approval
        self.pending_ssot_changes: List[Dict] = []

    def execute(self, tool_name: str, args: Dict[str, Any]) -> ToolResult:
        """Execute tool"""
        handlers = {
            "read_file": self._read_file,
            "search": self._search,
            "apply_patch": self._apply_patch,
            "run_tests": self._run_tests,
            "list_files": self._list_files,
            "get_diff": self._get_diff,
            "update_ssot": self._update_ssot,
            "git_commit": self._git_commit,
            "git_push": self._git_push,
        }

        handler = handlers.get(tool_name)
        if not handler:
            return ToolResult(
                success=False,
                output="",
                error=f"Unknown tool: {tool_name}"
            )

        try:
            result = handler(args)
            # Log work
            self.memory.log_work(
                action="TOOL",
                target=tool_name,
                description=f"Args: {json.dumps(args, ensure_ascii=False)[:100]}",
                result="SUCCESS" if result.success else "FAIL"
            )
            return result
        except Exception as e:
            self.memory.log_work(
                action="TOOL",
                target=tool_name,
                description=str(args),
                result="FAIL",
                details={"error": str(e)}
            )
            return ToolResult(
                success=False,
                output="",
                error=str(e)
            )

    def _read_file(self, args: Dict) -> ToolResult:
        """Read file"""
        path = args.get("path", "")
        if not path:
            return ToolResult(False, "", "path parameter required")

        full_path = self.project_root / path
        print(f"[Tool] read_file: project_root={self.project_root}, path={path}")
        print(f"[Tool] read_file: full_path={full_path}, exists={full_path.exists()}")

        if not full_path.exists():
            # Case-insensitive search
            parent = full_path.parent
            name = full_path.name.lower()
            if parent.exists():
                for f in parent.iterdir():
                    if f.name.lower() == name:
                        full_path = f
                        print(f"[Tool] read_file: case fixed -> {full_path}")
                        break

        if not full_path.exists():
            return ToolResult(False, "", f"File not found: {path}")

        # Security: Validate file is within project scope
        is_valid, error_msg = self._validate_project_scope(path)
        if not is_valid:
            return ToolResult(False, "", error_msg)

        try:
            content = full_path.read_text(encoding="utf-8")

            # Line limit (optional)
            start_line = args.get("start_line", 1)
            end_line = args.get("end_line")

            if start_line > 1 or end_line:
                lines = content.split('\n')
                start_idx = max(0, start_line - 1)
                end_idx = end_line if end_line else len(lines)
                content = '\n'.join(lines[start_idx:end_idx])

            return ToolResult(
                success=True,
                output=content,
                data={"path": path, "size": full_path.stat().st_size}
            )
        except Exception as e:
            return ToolResult(False, "", f"Failed to read file: {e}")

    def _search(self, args: Dict) -> ToolResult:
        """Code search (ripgrep)"""
        query = args.get("query", "")
        if not query:
            return ToolResult(False, "", "query parameter required")

        glob_pattern = args.get("glob", "")
        max_results = args.get("max_results", 20)

        # Build ripgrep command
        cmd = ["rg", "--json", "-m", str(max_results)]

        if glob_pattern:
            cmd.extend(["-g", glob_pattern])

        cmd.append(query)
        cmd.append(str(self.project_root))

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            # Parse JSON results
            matches = []
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if data.get("type") == "match":
                        match_data = data.get("data", {})
                        path_data = match_data.get("path", {})
                        matches.append({
                            "file": path_data.get("text", ""),
                            "line": match_data.get("line_number", 0),
                            "text": match_data.get("lines", {}).get("text", "").strip()
                        })
                except:
                    pass

            output = f"Found {len(matches)} matches:\n"
            for m in matches[:max_results]:
                output += f"  {m['file']}:{m['line']}: {m['text'][:80]}\n"

            return ToolResult(
                success=True,
                output=output,
                data={"matches": matches, "count": len(matches)}
            )
        except subprocess.TimeoutExpired:
            return ToolResult(False, "", "Search timeout")
        except FileNotFoundError:
            # Fallback if ripgrep not available
            return self._search_fallback(query, glob_pattern, max_results)
        except Exception as e:
            return ToolResult(False, "", f"Search failed: {e}")

    def _search_fallback(self, query: str, glob_pattern: str,
                         max_results: int) -> ToolResult:
        """Fallback search when ripgrep not available"""
        import fnmatch

        matches = []
        for root, dirs, files in os.walk(self.project_root):
            # Exclude hidden folders
            dirs[:] = [d for d in dirs if not d.startswith('.')]

            for file in files:
                if glob_pattern and not fnmatch.fnmatch(file, glob_pattern):
                    continue

                filepath = Path(root) / file
                try:
                    content = filepath.read_text(encoding="utf-8", errors="ignore")
                    for i, line in enumerate(content.split('\n'), 1):
                        if query.lower() in line.lower():
                            rel_path = filepath.relative_to(self.project_root)
                            matches.append({
                                "file": str(rel_path),
                                "line": i,
                                "text": line.strip()[:100]
                            })
                            if len(matches) >= max_results:
                                break
                except:
                    pass

                if len(matches) >= max_results:
                    break
            if len(matches) >= max_results:
                break

        output = f"Found {len(matches)} matches (fallback):\n"
        for m in matches:
            output += f"  {m['file']}:{m['line']}: {m['text'][:80]}\n"

        return ToolResult(
            success=True,
            output=output,
            data={"matches": matches, "count": len(matches)}
        )

    def _is_ssot_file(self, path: str) -> bool:
        """Check if path is an SSOT file that requires approval"""
        filename = Path(path).name
        return filename in SSOT_FILES

    def _validate_project_scope(self, path: str) -> tuple[bool, str]:
        """
        Validate that the file path is within the project scope.
        Returns (is_valid, error_message)
        """
        try:
            full_path = self.project_root / path
            resolved = full_path.resolve()

            # Check 1: Must be within project root
            try:
                resolved.relative_to(self.project_root)
            except ValueError:
                return False, f"Path '{path}' is outside project root"

            # Check 2: No path traversal attacks (.. in path)
            if ".." in path:
                return False, f"Path traversal detected in '{path}'"

            # Check 3: No absolute paths that could escape
            if Path(path).is_absolute():
                return False, f"Absolute paths not allowed: '{path}'"

            # Check 4: Don't allow writing to sensitive system locations
            sensitive_patterns = [
                "/etc/", "/usr/", "/bin/", "/sbin/",
                "C:\\Windows", "C:\\Program Files",
                ".git/config", ".git/hooks",
                ".env", ".credentials", "secrets"
            ]
            path_lower = str(resolved).lower()
            for pattern in sensitive_patterns:
                if pattern.lower() in path_lower:
                    return False, f"Cannot write to sensitive location: '{path}'"

            return True, ""

        except Exception as e:
            return False, f"Path validation error: {e}"

    def _apply_patch(self, args: Dict) -> ToolResult:
        """Apply patch"""
        files = args.get("files", [])
        if not files:
            return ToolResult(False, "", "files parameter required")

        results = []
        for file_patch in files:
            path = file_patch.get("path", "")
            content = file_patch.get("content")
            diff = file_patch.get("diff")

            if not path:
                continue

            full_path = self.project_root / path

            # Security: Validate file is within project scope
            is_valid, error_msg = self._validate_project_scope(path)
            if not is_valid:
                results.append({"path": path, "success": False, "error": error_msg})
                continue

            try:
                # Create backup
                backup_content = None
                if full_path.exists():
                    backup_content = full_path.read_text(encoding="utf-8")

                # Determine new content
                new_content = None
                if content is not None:
                    new_content = content
                elif diff:
                    if not backup_content:
                        results.append({"path": path, "success": False, "error": "Original file not found"})
                        continue
                    new_content = self._apply_unified_diff(backup_content, diff)
                    if not new_content:
                        results.append({"path": path, "success": False, "error": "Diff apply failed"})
                        continue

                # Check if this is an SSOT file that needs approval
                if new_content and self._is_ssot_file(path):
                    if self.ssot_approval_callback:
                        file_name = Path(path).name
                        old_content = backup_content or ""

                        # Call approval callback (this will be handled in main thread)
                        approved = self.ssot_approval_callback(
                            file_name=file_name,
                            file_path=str(full_path),
                            old_content=old_content,
                            new_content=new_content
                        )

                        if not approved:
                            results.append({
                                "path": path,
                                "success": False,
                                "error": f"User rejected {file_name} changes"
                            })
                            continue
                    else:
                        # Store for later approval if no callback
                        self.pending_ssot_changes.append({
                            "path": path,
                            "full_path": str(full_path),
                            "file_name": Path(path).name,
                            "old_content": backup_content or "",
                            "new_content": new_content
                        })
                        results.append({
                            "path": path,
                            "success": False,
                            "error": f"SSOT file {Path(path).name} requires user approval"
                        })
                        continue

                # Write the file
                if new_content is not None:
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    full_path.write_text(new_content, encoding="utf-8")
                    action = "write" if content is not None else "patch"
                    results.append({"path": path, "success": True, "action": action})

                # Update file index
                if full_path.exists():
                    content_hash = hashlib.md5(
                        full_path.read_bytes()
                    ).hexdigest()
                    self.memory.update_file_index(
                        path=path,
                        size=full_path.stat().st_size,
                        content_hash=content_hash
                    )

            except Exception as e:
                results.append({"path": path, "success": False, "error": str(e)})

        success_count = sum(1 for r in results if r.get("success"))
        output = f"Patched {success_count}/{len(results)} files:\n"
        for r in results:
            status = "✅" if r.get("success") else "❌"
            output += f"  {status} {r['path']}"
            if r.get("error"):
                output += f" ({r['error']})"
            output += "\n"

        return ToolResult(
            success=success_count == len(results),
            output=output,
            data={"results": results}
        )

    def _apply_unified_diff(self, original: str, diff: str) -> Optional[str]:
        """Apply unified diff"""
        # Simple implementation - using patch tool is recommended for production
        try:
            # Parse diff
            lines = original.split('\n')
            diff_lines = diff.split('\n')

            # Parse @@ -start,count +start,count @@ format
            import re
            for i, dl in enumerate(diff_lines):
                match = re.match(r'^@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@', dl)
                if match:
                    old_start = int(match.group(1))
                    new_start = int(match.group(3))

                    # Extract changes
                    changes = []
                    for change_line in diff_lines[i+1:]:
                        if change_line.startswith('@@'):
                            break
                        changes.append(change_line)

                    # Apply changes
                    result_lines = lines[:old_start-1]
                    for cl in changes:
                        if cl.startswith('+'):
                            result_lines.append(cl[1:])
                        elif cl.startswith('-'):
                            pass  # Delete
                        elif cl.startswith(' '):
                            result_lines.append(cl[1:])
                        else:
                            result_lines.append(cl)

                    # Add remaining original
                    old_end = old_start + len([c for c in changes if not c.startswith('+')])
                    result_lines.extend(lines[old_end:])

                    return '\n'.join(result_lines)

            return None
        except:
            return None

    def _run_tests(self, args: Dict) -> ToolResult:
        """Run tests"""
        cmd = args.get("cmd", "pytest")
        timeout = args.get("timeout", 60)

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.project_root
            )

            success = result.returncode == 0
            output = result.stdout
            if result.stderr:
                output += f"\n\nSTDERR:\n{result.stderr}"

            # Log test results
            self.memory.log_work(
                action="TEST",
                target=cmd,
                description=f"Exit code: {result.returncode}",
                result="SUCCESS" if success else "FAIL",
                details={"returncode": result.returncode, "output": output[:1000]}
            )

            return ToolResult(
                success=success,
                output=output,
                data={"returncode": result.returncode}
            )
        except subprocess.TimeoutExpired:
            return ToolResult(False, "", f"Test timeout ({timeout}s)")
        except Exception as e:
            return ToolResult(False, "", f"Test execution failed: {e}")

    def _list_files(self, args: Dict) -> ToolResult:
        """List files"""
        path = args.get("path", ".")
        glob_pattern = args.get("glob", "*")
        recursive = args.get("recursive", True)

        target_path = self.project_root / path

        try:
            if recursive:
                files = list(target_path.rglob(glob_pattern))
            else:
                files = list(target_path.glob(glob_pattern))

            # Exclude hidden files/folders
            files = [f for f in files if not any(
                part.startswith('.') for part in f.parts
            )]

            file_list = []
            for f in files[:100]:  # Max 100
                rel_path = f.relative_to(self.project_root)
                file_list.append({
                    "path": str(rel_path),
                    "is_dir": f.is_dir(),
                    "size": f.stat().st_size if f.is_file() else 0
                })

            output = f"Found {len(file_list)} files:\n"
            for f in file_list[:20]:
                prefix = "📁" if f["is_dir"] else "📄"
                output += f"  {prefix} {f['path']}\n"

            if len(file_list) > 20:
                output += f"  ... and {len(file_list) - 20} more\n"

            return ToolResult(
                success=True,
                output=output,
                data={"files": file_list}
            )
        except Exception as e:
            return ToolResult(False, "", f"Failed to list files: {e}")

    def _get_diff(self, args: Dict) -> ToolResult:
        """Get Git diff"""
        staged = args.get("staged", False)
        path = args.get("path", "")

        cmd = ["git", "diff"]
        if staged:
            cmd.append("--staged")
        if path:
            cmd.append(path)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.project_root
            )

            return ToolResult(
                success=True,
                output=result.stdout or "(no changes)",
                data={"staged": staged}
            )
        except Exception as e:
            return ToolResult(False, "", f"Failed to get diff: {e}")

    def _git_commit(self, args: Dict) -> ToolResult:
        """Git add and commit"""
        message = args.get("message", "")
        files = args.get("files", [])  # List of files to add, empty = all

        if not message:
            return ToolResult(False, "", "commit message required")

        try:
            # Git add
            if files:
                for f in files:
                    add_result = subprocess.run(
                        ["git", "add", f],
                        capture_output=True,
                        text=True,
                        timeout=30,
                        cwd=self.project_root
                    )
            else:
                # Add all changes
                add_result = subprocess.run(
                    ["git", "add", "-A"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=self.project_root
                )

            # Git commit
            commit_result = subprocess.run(
                ["git", "commit", "-m", message],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.project_root
            )

            if commit_result.returncode == 0:
                return ToolResult(
                    success=True,
                    output=commit_result.stdout,
                    data={"message": message}
                )
            else:
                return ToolResult(
                    success=False,
                    output=commit_result.stdout,
                    error=commit_result.stderr
                )
        except Exception as e:
            return ToolResult(False, "", f"Git commit failed: {e}")

    def _git_push(self, args: Dict) -> ToolResult:
        """Git push"""
        remote = args.get("remote", "origin")
        branch = args.get("branch", "")

        try:
            cmd = ["git", "push", remote]
            if branch:
                cmd.append(branch)

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=self.project_root
            )

            if result.returncode == 0:
                return ToolResult(
                    success=True,
                    output=result.stdout or result.stderr or "Push successful",
                    data={"remote": remote, "branch": branch}
                )
            else:
                return ToolResult(
                    success=False,
                    output=result.stdout,
                    error=result.stderr
                )
        except Exception as e:
            return ToolResult(False, "", f"Git push failed: {e}")

    def _update_ssot(self, args: Dict) -> ToolResult:
        """Update SSOT documents (HANDOVER, CHECKLIST, DECISIONS, etc.)"""
        updates = args.get("updates", [])
        if not updates:
            return ToolResult(False, "", "No updates provided")

        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        results = []

        for update in updates:
            file_name = update.get("file", "")
            section = update.get("section", "")
            content = update.get("content", "")
            action = update.get("action", "append")  # append, replace, add_item

            if file_name not in SSOT_FILES:
                results.append(f"❌ {file_name}: Not a valid SSOT file")
                continue

            file_path = self.project_root / file_name

            try:
                if file_path.exists():
                    old_content = file_path.read_text(encoding="utf-8")
                else:
                    old_content = f"# {file_name.replace('.md', '')}\n"

                # Update timestamp
                import re
                if "Last updated:" in old_content:
                    new_content = re.sub(
                        r'Last updated:.*',
                        f'Last updated: {timestamp}',
                        old_content
                    )
                else:
                    lines = old_content.split('\n')
                    if lines:
                        lines.insert(1, f'Last updated: {timestamp}')
                        new_content = '\n'.join(lines)
                    else:
                        new_content = f"Last updated: {timestamp}\n{old_content}"

                # Apply update based on action
                if action == "append":
                    if section:
                        # Find section and append
                        section_pattern = re.compile(rf'^(##+ {re.escape(section)}.*?)(?=^##|\Z)', re.MULTILINE | re.DOTALL)
                        match = section_pattern.search(new_content)
                        if match:
                            section_end = match.end()
                            new_content = new_content[:section_end].rstrip() + f"\n{content}\n" + new_content[section_end:]
                        else:
                            new_content += f"\n## {section}\n{content}\n"
                    else:
                        new_content += f"\n{content}\n"

                elif action == "add_item":
                    # Add checklist item (- [ ] item)
                    if section:
                        section_pattern = re.compile(rf'^(##+ {re.escape(section)}.*?)(?=^##|\Z)', re.MULTILINE | re.DOTALL)
                        match = section_pattern.search(new_content)
                        if match:
                            section_text = match.group(1)
                            # Find last checkbox item
                            last_item = list(re.finditer(r'^- \[[ x]\].*$', section_text, re.MULTILINE))
                            if last_item:
                                insert_pos = match.start() + last_item[-1].end()
                                new_content = new_content[:insert_pos] + f"\n- [ ] {content}" + new_content[insert_pos:]
                            else:
                                section_end = match.end()
                                new_content = new_content[:section_end].rstrip() + f"\n- [ ] {content}\n" + new_content[section_end:]

                elif action == "check_item":
                    # Mark item as completed
                    item_pattern = re.compile(rf'^- \[ \] {re.escape(content)}', re.MULTILINE)
                    new_content = item_pattern.sub(f'- [x] {content}', new_content)

                elif action == "replace":
                    if section:
                        section_pattern = re.compile(rf'^(##+ {re.escape(section)}\n).*?(?=^##|\Z)', re.MULTILINE | re.DOTALL)
                        new_content = section_pattern.sub(rf'\1{content}\n', new_content)

                # Request approval if callback exists
                if self.ssot_approval_callback:
                    approved = self.ssot_approval_callback(file_name, str(file_path), old_content, new_content)
                    if not approved:
                        results.append(f"⏭️ {file_name}: Skipped (not approved)")
                        continue

                file_path.write_text(new_content, encoding="utf-8")
                results.append(f"✅ {file_name}: Updated successfully")

            except Exception as e:
                results.append(f"❌ {file_name}: {str(e)}")

        return ToolResult(
            success=all("✅" in r for r in results),
            output="\n".join(results),
            data={"updated_files": [u.get("file") for u in updates]}
        )


# ============================================
# Tool Definitions (for LLM)
# ============================================

TOOL_DEFINITIONS = [
    {
        "name": "read_file",
        "description": "Read file content",
        "parameters": {
            "path": "File path (required)",
            "start_line": "Start line (optional)",
            "end_line": "End line (optional)"
        }
    },
    {
        "name": "search",
        "description": "Search text in code",
        "parameters": {
            "query": "Search query (required)",
            "glob": "File pattern (optional, e.g., *.py)",
            "max_results": "Max results (optional, default 20)"
        }
    },
    {
        "name": "apply_patch",
        "description": "Create new files or modify existing files. Use this tool to write code, create schemas, config files, etc.",
        "parameters": {
            "files": "List of files to create/modify [{path: 'file/path.py', content: 'file content'}]"
        }
    },
    {
        "name": "run_tests",
        "description": "Run tests",
        "parameters": {
            "cmd": "Test command (optional, default pytest)",
            "timeout": "Timeout in seconds (optional, default 60)"
        }
    },
    {
        "name": "list_files",
        "description": "List files",
        "parameters": {
            "path": "Directory path (optional, default .)",
            "glob": "File pattern (optional, default *)",
            "recursive": "Recursive search (optional, default true)"
        }
    },
    {
        "name": "get_diff",
        "description": "Get Git diff",
        "parameters": {
            "staged": "Staged changes only (optional, default false)",
            "path": "File path (optional)"
        }
    },
    {
        "name": "update_ssot",
        "description": "Update SSOT documents (HANDOVER.md, CHECKLIST.md, DECISIONS.md, etc.)",
        "parameters": {
            "updates": "List of updates [{file, section, content, action}]. action: append|add_item|check_item|replace"
        }
    },
    {
        "name": "git_commit",
        "description": "Stage files and create a git commit",
        "parameters": {
            "message": "Commit message (required)",
            "files": "List of files to stage (optional, default: all changes)"
        }
    },
    {
        "name": "git_push",
        "description": "Push commits to remote repository",
        "parameters": {
            "remote": "Remote name (optional, default: origin)",
            "branch": "Branch name (optional, default: current branch)"
        }
    }
]


# ============================================
# Test
# ============================================

if __name__ == "__main__":
    import tempfile

    print("=" * 60)
    print("  MADORO CODE Tools Test")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test file
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("def hello():\n    print('Hello')\n")

        executor = ToolExecutor(tmpdir)

        # read_file test
        print("\n[1] read_file")
        result = executor.execute("read_file", {"path": "test.py"})
        print(f"  Success: {result.success}")
        print(f"  Output: {result.output[:50]}")

        # search test
        print("\n[2] search")
        result = executor.execute("search", {"query": "hello"})
        print(f"  Success: {result.success}")
        print(f"  Output: {result.output[:100]}")

        # list_files test
        print("\n[3] list_files")
        result = executor.execute("list_files", {"path": "."})
        print(f"  Success: {result.success}")
        print(f"  Output: {result.output[:100]}")

        # apply_patch test
        print("\n[4] apply_patch")
        result = executor.execute("apply_patch", {
            "files": [{"path": "new_file.py", "content": "# New file\n"}]
        })
        print(f"  Success: {result.success}")
        print(f"  Output: {result.output}")

        print("\n" + "=" * 60)
        print("  All tests passed!")
        print("=" * 60)
