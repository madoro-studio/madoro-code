"""
VibeCoder - LLM 클라이언트 (Ollama + DeepSeek + Claude API)

LLM은 작업자이지 기억 장치가 아니다.
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
    """LLM 응답"""
    content: str
    model: str
    tokens_used: int
    tool_calls: List[Dict] = None


@dataclass
class ModelConfig:
    """모델 설정"""
    name: str
    display_name: str
    provider: str  # ollama, deepseek, anthropic
    context_length: int
    temperature: float
    use_for: List[str]
    ollama_model: str = ""
    api_model: str = ""


class LLMClient:
    """통합 LLM 클라이언트 - Ollama, DeepSeek, Claude 지원"""

    def __init__(self, config_path: str = None):
        if config_path is None:
            # 우선순위: 환경변수 > 현재 디렉토리 > 상대경로
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

        # Ollama 설정
        self.ollama_url = self.config.get("ollama", {}).get("base_url", "http://127.0.0.1:11434")
        self.timeout = self.config.get("ollama", {}).get("timeout", 120)

        # API clients (lazy loading)
        self._openai_client = None
        self._anthropic_client = None
        self._gemini_model = None

    def _load_config(self, config_path) -> Dict:
        """설정 파일 로드"""
        path = Path(config_path) if not isinstance(config_path, Path) else config_path
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        return {"models": {}, "default_model": "qwen-coder"}

    def _parse_models(self) -> Dict[str, ModelConfig]:
        """모델 설정 파싱"""
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
        """DeepSeek 클라이언트 (OpenAI 호환)"""
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
                print("[LLM] openai 패키지 없음. pip install openai")
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
        """모델 선택"""
        if model_key in self.models:
            self.current_model = model_key
            return True
        return False

    def get_model_config(self) -> Optional[ModelConfig]:
        """현재 모델 설정"""
        return self.models.get(self.current_model)

    def list_models(self) -> List[str]:
        """사용 가능한 모델 목록"""
        return list(self.models.keys())

    def check_connection(self) -> bool:
        """연결 확인 (현재 모델 기준)"""
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
            # API 키가 있으면 연결된 것으로 간주
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
        print(f"[LLM] Prompt: {len(prompt)}자")

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
        """Ollama 생성"""
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
            raise TimeoutError("Ollama 응답 시간 초과")
        except Exception as e:
            raise RuntimeError(f"Ollama 호출 실패: {e}")

    def _generate_deepseek(self, prompt: str, system: str, model_cfg: ModelConfig) -> LLMResponse:
        """DeepSeek API 생성"""
        client = self._get_deepseek_client()
        if not client:
            raise RuntimeError("DeepSeek API 키가 설정되지 않았습니다. 환경변수 DEEPSEEK_API_KEY를 설정하세요.")

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
            raise RuntimeError(f"DeepSeek API 호출 실패: {e}")

    def _generate_anthropic(self, prompt: str, system: str, model_cfg: ModelConfig) -> LLMResponse:
        """Claude API 생성"""
        client = self._get_anthropic_client()
        if not client:
            raise RuntimeError("Anthropic API 키가 설정되지 않았습니다. 환경변수 ANTHROPIC_API_KEY를 설정하세요.")

        print(f"[LLM] Claude API 호출 시작... (모델: {model_cfg.api_model})")

        try:
            kwargs = {
                "model": model_cfg.api_model,
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": prompt}],
                "timeout": 120.0  # 요청별 타임아웃
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
            tool_desc += f"  파라미터: {json.dumps(tool.get('parameters', {}), ensure_ascii=False)}\n"

        tool_desc += """
도구를 사용하려면 다음 형식 중 하나로 응답하세요:

형식 1 (JSON):
```json
{"tool": "도구명", "args": {"파라미터": "값"}}
```

형식 2 (XML):
<도구명><파라미터>값</파라미터></도구명>

예시:
<read_file><path>README.md</path></read_file>
<search><query>function</query></search>

도구 사용이 필요 없으면 일반 텍스트로 응답하세요.
"""

        combined_system = f"{system}\n\n{tool_desc}" if system else tool_desc
        response = self.generate(prompt, system=combined_system)

        # 툴콜 파싱
        tool_calls = self._parse_tool_calls(response.content)
        if tool_calls:
            response.tool_calls = tool_calls

        return response

    def _parse_tool_calls(self, content: str) -> Optional[List[Dict]]:
        """응답에서 툴콜 파싱"""
        tool_calls = []

        # 1. ```json 형식 파싱
        json_pattern = r'```json\s*(.*?)\s*```'
        matches = re.findall(json_pattern, content, re.DOTALL)
        for match in matches:
            try:
                data = json.loads(match)
                if "tool" in data:
                    tool_calls.append(data)
            except:
                pass

        # 2. XML 스타일 파싱 (예: <read_file><path>...</path></read_file>)
        if not tool_calls:
            xml_tools = {
                'read_file': ['path'],
                'search': ['query', 'path'],
                'apply_patch': ['files'],
                'run_tests': ['cmd'],
                'list_files': ['path'],
                'get_diff': []
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
                            args[param] = param_match.group(1).strip()
                    if args or not params:
                        tool_calls.append({"tool": tool_name, "args": args})

        # 3. 한 줄 JSON 형식 파싱
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

        return tool_calls if tool_calls else None


# ============================================
# 하위 호환성을 위한 별칭
# ============================================
OllamaClient = LLMClient


# ============================================
# 싱글톤 인스턴스
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
    """테스트용 리셋"""
    global _llm_client
    _llm_client = None


# ============================================
# 테스트
# ============================================

if __name__ == "__main__":
    print("=" * 60)
    print("  VibeCoder LLM Client Test")
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
