"""
VibeCoder - CLI 진입점

명령어:
- vibe doctor: 프로젝트 상태 진단
- vibe chat: 대화 시작
- vibe chat --model <model>: 특정 모델로 대화
"""

import sys
import os
import argparse
from pathlib import Path

# 프로젝트 루트 설정
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from agent import get_agent
from llm import get_llm_client
from memory import get_memory_store


def cmd_doctor(args):
    """프로젝트 상태 진단"""
    agent = get_agent(str(PROJECT_ROOT))
    print(agent.doctor())


def cmd_chat(args):
    """대화 시작"""
    agent = get_agent(str(PROJECT_ROOT))
    llm = get_llm_client()

    # 모델 선택
    if args.model:
        if llm.set_model(args.model):
            print(f"모델 선택: {args.model}")
        else:
            print(f"알 수 없는 모델: {args.model}")
            print(f"사용 가능: {llm.list_models()}")
            return

    # 연결 확인
    if not llm.check_connection():
        print("❌ Ollama 연결 실패. Ollama를 먼저 실행하세요.")
        print("   ollama serve")
        return

    # 모델 확인
    if not llm.check_model_available():
        model_cfg = llm.get_model_config()
        print(f"❌ 모델 없음: {model_cfg.ollama_model}")
        print(f"   ollama pull {model_cfg.ollama_model}")
        return

    # 대화 시작
    print("=" * 60)
    print("  VibeCoder Chat")
    print(f"  Model: {llm.get_model_config().display_name}")
    print("  Type 'exit' to quit, 'doctor' for status")
    print("=" * 60)
    print()

    while True:
        try:
            user_input = input("You: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ['exit', 'quit', 'q']:
                print("Goodbye!")
                break

            if user_input.lower() == 'doctor':
                print(agent.doctor())
                continue

            if user_input.lower() == 'clear':
                memory = get_memory_store()
                memory.clear_conversation()
                print("대화 기록 초기화됨")
                continue

            if user_input.lower().startswith('model '):
                model_name = user_input[6:].strip()
                if llm.set_model(model_name):
                    print(f"모델 변경: {llm.get_model_config().display_name}")
                else:
                    print(f"알 수 없는 모델: {model_name}")
                    print(f"사용 가능: {llm.list_models()}")
                continue

            # 에이전트 처리
            print("...")
            response = agent.process(user_input)

            if response.error:
                print(f"❌ Error: {response.error}")
            else:
                print(f"\nVibe: {response.message}")
                if response.tool_results:
                    print(f"\n[실행된 도구: {len(response.tool_results)}개]")
                    for tr in response.tool_results:
                        status = "✅" if tr.get("success") else "❌"
                        print(f"  {status} {tr.get('tool')}")

            print()

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except EOFError:
            print("\nGoodbye!")
            break


def cmd_models(args):
    """사용 가능한 모델 목록"""
    llm = get_llm_client()

    print("사용 가능한 모델:")
    print("-" * 40)

    connected = llm.check_connection()

    for model_key in llm.list_models():
        cfg = llm.models[model_key]
        current = "→ " if model_key == llm.current_model else "  "

        if connected:
            available = llm.check_model_available(model_key)
            status = "✅" if available else "❌"
        else:
            status = "?"

        print(f"{current}{status} {model_key}: {cfg.display_name}")
        print(f"       Ollama: {cfg.ollama_model}")
        print(f"       용도: {', '.join(cfg.use_for)}")
        print()

    if not connected:
        print("⚠️  Ollama 연결 안됨 - 모델 상태 확인 불가")


def main():
    parser = argparse.ArgumentParser(
        description="VibeCoder - 프로젝트 기억 시스템"
    )
    subparsers = parser.add_subparsers(dest="command", help="명령어")

    # doctor
    parser_doctor = subparsers.add_parser("doctor", help="프로젝트 상태 진단")
    parser_doctor.set_defaults(func=cmd_doctor)

    # chat
    parser_chat = subparsers.add_parser("chat", help="대화 시작")
    parser_chat.add_argument(
        "--model", "-m",
        help="사용할 모델 (deepseek, qwen-coder)"
    )
    parser_chat.set_defaults(func=cmd_chat)

    # models
    parser_models = subparsers.add_parser("models", help="사용 가능한 모델 목록")
    parser_models.set_defaults(func=cmd_models)

    args = parser.parse_args()

    if args.command is None:
        # 기본: doctor
        cmd_doctor(args)
    else:
        args.func(args)


if __name__ == "__main__":
    main()
