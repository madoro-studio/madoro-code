"""
MADORO CODE - LLM Client (Ollama + DeepSeek + Claude API)

LLM is a worker, not a memory storage.
"""

import os
import requests
import json
import yaml
import re
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class LLMResponse:
    """LLM Response"""
    content: str
    model: str
    tokens_used: int
    tool_calls: List[Dict] = None


@dataclass
class ModelConfig:
    """Model Configuration"""
    name: str
    display_name: str
    provider: str  # ollama, deepseek, anthropic
    context_length: int
    temperature: float
    use_for: List[str]
    ollama_model: str = ""
    api_model: str = ""


class LLMClient:
    """Unified LLM Client - Supports Ollama, DeepSeek, Claude"""

    def __init__(self, config_path: str = None):
        if config_path is None:
            # Priority: environment variable > current directory > relative path
            base_path = os.environ.get('MADORO_CODE_BASE')
            if base_path:
                config_path = Path(base_path) / "config" / "models.yaml"
            else:
                # 현재 작업 디렉토리 기준
                cwd_config = Path.cwd() / "config" / "models.yaml"
                if cwd_config.exists():
                    config_path = cwd_config
                else:
                    config_path = Path(__file__).parent.parent / "config" / "models.yaml"

        self.config = self._load_config(config_path)
        print(f"[LLM] Config loaded from: {config_path}")
        print(f"[LLM] Config exists: {Path(config_path).exists()}")
        self.models = self._parse_models()
        self.current_model = self.config.get("default_model", "qwen-coder")

        # Ollama settings
        self.ollama_url = self.config.get("ollama", {}).get("base_url", "http://127.0.0.1:11434")
        self.timeout = self.config.get("ollama", {}).get("timeout", 120)

        # API clients (lazy loading)
        self._openai_client = None
        self._anthropic_client = None
        self._gemini_model = None

    def _load_config(self, config_path) -> Dict:
        """Load configuration file"""
        path = Path(config_path) if not isinstance(config_path, Path) else config_path
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        return {"models": {}, "default_model": "qwen-coder"}

    def _parse_models(self) -> Dict[str, ModelConfig]:
        """Parse model configuration"""
        models = {}
        for key, cfg in self.config.get("models", {}).items():
            models[key] = ModelConfig(
                name=cfg.get("name", key),
                display_name=cfg.get("display_name", key),
                provider=cfg.get("provider", "ollama"),
                context_length=cfg.get("context_length", 4096),
                temperature=cfg.get("temperature", 0.3),
                use_for=cfg.get("use_for", []),
                ollama_model=cfg.get("ollama_model", ""),
                api_model=cfg.get("api_model", "")
            )
        return models

    def _get_deepseek_client(self):
        """DeepSeek client (OpenAI compatible)"""
        if self._openai_client is None:
            try:
                from openai import OpenAI
                api_key = (
                    self.config.get("api", {}).get("deepseek", {}).get("api_key") or
                    os.environ.get("DEEPSEEK_API_KEY")
                )
                if api_key:
                    self._openai_client = OpenAI(
                        api_key=api_key,
                        base_url="https://api.deepseek.com"
                    )
            except ImportError:
                print("[LLM] openai package not found. pip install openai")
        return self._openai_client

    def _get_anthropic_client(self):
        """Anthropic client"""
        if self._anthropic_client is None:
            try:
                import anthropic
                api_key = (
                    self.config.get("api", {}).get("anthropic", {}).get("api_key") or
                    os.environ.get("ANTHROPIC_API_KEY")
                )
                if api_key:
                    self._anthropic_client = anthropic.Anthropic(
                        api_key=api_key,
                        timeout=120.0
                    )
            except ImportError:
                print("[LLM] anthropic package not found. pip install anthropic")
        return self._anthropic_client

    def _get_gemini_client(self, model_name: str):
        """Google Gemini client"""
        try:
            import google.generativeai as genai
            api_key = (
                self.config.get("api", {}).get("google", {}).get("api_key") or
                os.environ.get("GOOGLE_API_KEY")
            )
            if api_key:
                genai.configure(api_key=api_key)
                return genai.GenerativeModel(model_name)
        except ImportError:
            print("[LLM] google-generativeai package not found. pip install google-generativeai")
        return None

    def set_model(self, model_key: str) -> bool:
        """Select model"""
        if model_key in self.models:
            self.current_model = model_key
            return True
        return False

    def get_model_config(self) -> Optional[ModelConfig]:
        """Get current model configuration"""
        return self.models.get(self.current_model)

    def list_models(self) -> List[str]:
        """List available models"""
        return list(self.models.keys())

    def check_connection(self) -> bool:
        """Check connection (based on current model)"""
        model_cfg = self.get_model_config()
        if not model_cfg:
            return False

        if model_cfg.provider == "ollama":
            try:
                resp = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
                return resp.status_code == 200
            except:
                return False
        elif model_cfg.provider == "deepseek":
            # Consider connected if API key exists
            api_key = (
                self.config.get("api", {}).get("deepseek", {}).get("api_key") or
                os.environ.get("DEEPSEEK_API_KEY")
            )
            return bool(api_key)
        elif model_cfg.provider == "anthropic":
            api_key = (
                self.config.get("api", {}).get("anthropic", {}).get("api_key") or
                os.environ.get("ANTHROPIC_API_KEY")
            )
            return bool(api_key)
        elif model_cfg.provider == "google":
            api_key = (
                self.config.get("api", {}).get("google", {}).get("api_key") or
                os.environ.get("GOOGLE_API_KEY")
            )
            return bool(api_key)
        return False

    def check_model_available(self, model_key: str = None) -> bool:
        """Check if model is available"""
        model_key = model_key or self.current_model
        model_cfg = self.models.get(model_key)
        if not model_cfg:
            return False

        if model_cfg.provider == "ollama":
            try:
                resp = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    available = [m["name"] for m in data.get("models", [])]
                    return (model_cfg.ollama_model in available or
                            model_cfg.ollama_model.split(":")[0] in [m.split(":")[0] for m in available])
            except:
                pass
            return False
        elif model_cfg.provider == "deepseek":
            return self._get_deepseek_client() is not None
        elif model_cfg.provider == "anthropic":
            return self._get_anthropic_client() is not None
        elif model_cfg.provider == "google":
            return self._get_gemini_client(model_cfg.api_model) is not None
        return False

    def generate(self, prompt: str, system: str = None) -> LLMResponse:
        """Generate text - route by provider"""
        model_cfg = self.get_model_config()
        if not model_cfg:
            raise ValueError(f"Unknown model: {self.current_model}")

        print(f"[LLM] Provider: {model_cfg.provider}, Model: {model_cfg.display_name}")
        print(f"[LLM] Prompt: {len(prompt)} chars")

        if model_cfg.provider == "ollama":
            return self._generate_ollama(prompt, system, model_cfg)
        elif model_cfg.provider == "deepseek":
            return self._generate_deepseek(prompt, system, model_cfg)
        elif model_cfg.provider == "anthropic":
            return self._generate_anthropic(prompt, system, model_cfg)
        elif model_cfg.provider == "google":
            return self._generate_gemini(prompt, system, model_cfg)
        else:
            raise ValueError(f"Unknown provider: {model_cfg.provider}")

    def _generate_ollama(self, prompt: str, system: str, model_cfg: ModelConfig) -> LLMResponse:
        """Ollama generation"""
        payload = {
            "model": model_cfg.ollama_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": model_cfg.temperature,
                "num_ctx": model_cfg.context_length
            }
        }
        if system:
            payload["system"] = system

        try:
            resp = requests.post(
                f"{self.ollama_url}/api/generate",
                json=payload,
                timeout=self.timeout
            )
            resp.raise_for_status()
            data = resp.json()
            return LLMResponse(
                content=data.get("response", ""),
                model=model_cfg.name,
                tokens_used=data.get("eval_count", 0)
            )
        except requests.exceptions.Timeout:
            raise TimeoutError("Ollama response timeout")
        except Exception as e:
            raise RuntimeError(f"Ollama call failed: {e}")

    def _generate_deepseek(self, prompt: str, system: str, model_cfg: ModelConfig) -> LLMResponse:
        """DeepSeek API generation"""
        client = self._get_deepseek_client()
        if not client:
            raise RuntimeError("DeepSeek API key not set. Set DEEPSEEK_API_KEY environment variable.")

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            response = client.chat.completions.create(
                model=model_cfg.api_model,
                messages=messages,
                temperature=model_cfg.temperature,
                max_tokens=4096
            )
            return LLMResponse(
                content=response.choices[0].message.content,
                model=model_cfg.name,
                tokens_used=response.usage.total_tokens if response.usage else 0
            )
        except Exception as e:
            raise RuntimeError(f"DeepSeek API call failed: {e}")

    def _generate_anthropic(self, prompt: str, system: str, model_cfg: ModelConfig) -> LLMResponse:
        """Claude API generation"""
        client = self._get_anthropic_client()
        if not client:
            raise RuntimeError("Anthropic API key not set. Set ANTHROPIC_API_KEY environment variable.")

        print(f"[LLM] Claude API call starting... (model: {model_cfg.api_model})")

        try:
            kwargs = {
                "model": model_cfg.api_model,
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": prompt}],
                "timeout": 120.0  # Per-request timeout
            }
            if system:
                kwargs["system"] = system

            response = client.messages.create(**kwargs)

            content = ""
            if response.content:
                content = response.content[0].text

            print(f"[LLM] Claude API 응답 완료 (tokens: {response.usage.input_tokens + response.usage.output_tokens if response.usage else 0})")

            return LLMResponse(
                content=content,
                model=model_cfg.name,
                tokens_used=response.usage.input_tokens + response.usage.output_tokens if response.usage else 0
            )
        except TimeoutError as e:
            print(f"[LLM] Claude API timeout: {e}")
            raise RuntimeError(f"Claude API timeout (120s)")
        except Exception as e:
            print(f"[LLM] Claude API error: {e}")
            raise RuntimeError(f"Claude API call failed: {e}")

    def _generate_gemini(self, prompt: str, system: str, model_cfg: ModelConfig) -> LLMResponse:
        """Google Gemini API generation"""
        client = self._get_gemini_client(model_cfg.api_model)
        if not client:
            raise RuntimeError("Google API key not set. Set GOOGLE_API_KEY environment variable or configure in Settings.")

        print(f"[LLM] Gemini API call starting... (model: {model_cfg.api_model})")

        try:
            # Combine system prompt with user prompt
            full_prompt = prompt
            if system:
                full_prompt = f"{system}\n\n{prompt}"

            response = client.generate_content(full_prompt)

            content = response.text if response.text else ""

            # Estimate tokens (Gemini doesn't always return exact count)
            tokens_used = len(full_prompt.split()) + len(content.split())

            print(f"[LLM] Gemini API response complete (estimated tokens: {tokens_used})")

            return LLMResponse(
                content=content,
                model=model_cfg.name,
                tokens_used=tokens_used
            )
        except Exception as e:
            print(f"[LLM] Gemini API error: {e}")
            raise RuntimeError(f"Gemini API call failed: {e}")

    def generate_with_tools(self, prompt: str, tools: List[Dict], system: str = None) -> LLMResponse:
        """Generate with tool calls"""
        tool_desc = "Available tools:\n"
        for tool in tools:
            tool_desc += f"- {tool['name']}: {tool['description']}\n"
            tool_desc += f"  Parameters: {json.dumps(tool.get('parameters', {}), ensure_ascii=False)}\n"

        tool_desc += """
To use a tool, respond with the following JSON format:

```json
{"tool": "tool_name", "args": {"parameter": "value"}}
```

Example - Read file:
```json
{"tool": "read_file", "args": {"path": "README.md"}}
```

Example - Create/modify file (IMPORTANT!):
```json
{"tool": "apply_patch", "args": {"files": [{"path": "schema.py", "content": "# Schema content here\\nclass User:\\n    pass"}]}}
```

Example - Git commit:
```json
{"tool": "git_commit", "args": {"message": "Add schema file"}}
```

ALWAYS use apply_patch tool when creating or modifying files.
If no tool is needed, respond with plain text.
"""

        combined_system = f"{system}\n\n{tool_desc}" if system else tool_desc
        response = self.generate(prompt, system=combined_system)

        # Parse tool calls
        tool_calls = self._parse_tool_calls(response.content)
        if tool_calls:
            response.tool_calls = tool_calls

        return response

    def _parse_tool_calls(self, content: str) -> Optional[List[Dict]]:
        """Parse tool calls from response"""
        tool_calls = []

        # 1. Parse ```json format (highest priority)
        json_pattern = r'```json\s*(.*?)\s*```'
        matches = re.findall(json_pattern, content, re.DOTALL)
        for match in matches:
            try:
                data = json.loads(match)
                # Handle JSON array format
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and "tool" in item:
                            tool_calls.append(item)
                # Handle single object format
                elif isinstance(data, dict) and "tool" in data:
                    tool_calls.append(data)
            except:
                pass

        # 2. Dedicated apply_patch parsing (file creation/modification)
        if not tool_calls:
            # Pattern: <apply_patch> ... </apply_patch> containing JSON or file info
            apply_pattern = r'<apply_patch>(.*?)</apply_patch>'
            apply_match = re.search(apply_pattern, content, re.DOTALL)
            if apply_match:
                inner = apply_match.group(1).strip()
                files = []

                # Method 1: JSON array inside
                try:
                    parsed = json.loads(inner)
                    if isinstance(parsed, list):
                        files = parsed
                    elif isinstance(parsed, dict) and "files" in parsed:
                        files = parsed["files"]
                except:
                    pass

                # Method 2: Wrapped in <file> tags
                if not files:
                    file_pattern = r'<file>(.*?)</file>'
                    file_matches = re.findall(file_pattern, inner, re.DOTALL)
                    for fm in file_matches:
                        try:
                            file_data = json.loads(fm)
                            files.append(file_data)
                        except:
                            # Extract path and content directly
                            path_match = re.search(r'<path>(.*?)</path>', fm, re.DOTALL)
                            content_match = re.search(r'<content>(.*?)</content>', fm, re.DOTALL)
                            if path_match and content_match:
                                files.append({
                                    "path": path_match.group(1).strip(),
                                    "content": content_match.group(1)
                                })

                # Method 3: Direct path/content tags
                if not files:
                    path_match = re.search(r'<path>(.*?)</path>', inner, re.DOTALL)
                    content_match = re.search(r'<content>(.*?)</content>', inner, re.DOTALL)
                    if path_match and content_match:
                        files.append({
                            "path": path_match.group(1).strip(),
                            "content": content_match.group(1)
                        })

                if files:
                    tool_calls.append({"tool": "apply_patch", "args": {"files": files}})

        # 3. Other XML style parsing (simple parameter tools)
        if not tool_calls:
            xml_tools = {
                'read_file': ['path'],
                'search': ['query', 'path'],
                'run_tests': ['cmd'],
                'list_files': ['path'],
                'get_diff': [],
                'update_ssot': ['updates'],
                'git_commit': ['message', 'files'],
                'git_push': ['remote', 'branch']
            }
            for tool_name, params in xml_tools.items():
                pattern = rf'<{tool_name}>(.*?)</{tool_name}>'
                match = re.search(pattern, content, re.DOTALL)
                if match:
                    inner = match.group(1)
                    args = {}
                    for param in params:
                        param_pattern = rf'<{param}>(.*?)</{param}>'
                        param_match = re.search(param_pattern, inner, re.DOTALL)
                        if param_match:
                            value = param_match.group(1).strip()
                            # Try parsing if JSON array/object
                            if value.startswith('[') or value.startswith('{'):
                                try:
                                    value = json.loads(value)
                                except:
                                    pass
                            args[param] = value
                    if args or not params:
                        tool_calls.append({"tool": tool_name, "args": args})

        # 4. Single line JSON format parsing
        if not tool_calls:
            for line in content.split('\n'):
                line = line.strip()
                if line.startswith('{') and '"tool"' in line:
                    try:
                        data = json.loads(line)
                        if "tool" in data:
                            tool_calls.append(data)
                    except:
                        pass

        # 5. Multiline JSON object parsing (direct JSON without code block)
        if not tool_calls:
            # Find { "tool": ... } pattern
            json_obj_pattern = r'\{\s*"tool"\s*:\s*"[^"]+"\s*,\s*"args"\s*:\s*\{.*?\}\s*\}'
            obj_matches = re.findall(json_obj_pattern, content, re.DOTALL)
            for obj_match in obj_matches:
                try:
                    data = json.loads(obj_match)
                    if "tool" in data:
                        tool_calls.append(data)
                except:
                    pass

        return tool_calls if tool_calls else None


# ============================================
# Backward compatibility alias
# ============================================
OllamaClient = LLMClient


# ============================================
# Singleton Instance
# ============================================

_llm_client: Optional[LLMClient] = None


def get_llm_client(config_path: str = None) -> LLMClient:
    """LLM Client singleton"""
    global _llm_client
    if _llm_client is None:
        if config_path is None:
            # Use bundle path for config (EXE or script)
            import os
            bundle_path = os.environ.get('MADORO_CODE_BUNDLE', '.')
            config_path = os.path.join(bundle_path, "config", "models.yaml")
        _llm_client = LLMClient(config_path)
    return _llm_client


def reset_llm_client():
    """Reset for testing"""
    global _llm_client
    _llm_client = None


# ============================================
# Test
# ============================================

if __name__ == "__main__":
    print("=" * 60)
    print("  MADORO CODE LLM Client Test")
    print("=" * 60)

    client = LLMClient()

    print("\n[1] Configuration")
    print(f"  Models: {client.list_models()}")
    print(f"  Current: {client.current_model}")

    print("\n[2] Model Status")
    for model_key in client.list_models():
        cfg = client.models[model_key]
        client.set_model(model_key)
        available = client.check_model_available(model_key)
        status = "[OK]" if available else "[--]"
        print(f"  {status} {cfg.display_name} ({cfg.provider})")

    print("\n" + "=" * 60)
