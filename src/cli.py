"""
MADORO CODE - CLI Entry Point

Commands:
- vibe doctor: Diagnose project status
- vibe chat: Start conversation
- vibe chat --model <model>: Chat with specific model
"""

import sys
import os
import argparse
from pathlib import Path

# Set project root
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from agent import get_agent
from llm import get_llm_client
from memory import get_memory_store


def cmd_doctor(args):
    """Diagnose project status"""
    agent = get_agent(str(PROJECT_ROOT))
    print(agent.doctor())


def cmd_chat(args):
    """Start conversation"""
    agent = get_agent(str(PROJECT_ROOT))
    llm = get_llm_client()

    # Select model
    if args.model:
        if llm.set_model(args.model):
            print(f"Model selected: {args.model}")
        else:
            print(f"Unknown model: {args.model}")
            print(f"Available: {llm.list_models()}")
            return

    # Check connection
    if not llm.check_connection():
        print("❌ Ollama connection failed. Start Ollama first.")
        print("   ollama serve")
        return

    # Check model
    if not llm.check_model_available():
        model_cfg = llm.get_model_config()
        print(f"❌ Model not found: {model_cfg.ollama_model}")
        print(f"   ollama pull {model_cfg.ollama_model}")
        return

    # Start conversation
    print("=" * 60)
    print("  MADORO CODE Chat")
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
                print("Conversation cleared")
                continue

            if user_input.lower().startswith('model '):
                model_name = user_input[6:].strip()
                if llm.set_model(model_name):
                    print(f"Model changed: {llm.get_model_config().display_name}")
                else:
                    print(f"Unknown model: {model_name}")
                    print(f"Available: {llm.list_models()}")
                continue

            # Agent processing
            print("...")
            response = agent.process(user_input)

            if response.error:
                print(f"❌ Error: {response.error}")
            else:
                print(f"\nVibe: {response.message}")
                if response.tool_results:
                    print(f"\n[Tools executed: {len(response.tool_results)}]")
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
    """List available models"""
    llm = get_llm_client()

    print("Available models:")
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
        print(f"       Use for: {', '.join(cfg.use_for)}")
        print()

    if not connected:
        print("⚠️  Ollama not connected - Cannot check model status")


def main():
    parser = argparse.ArgumentParser(
        description="MADORO CODE - Project Memory System"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # doctor
    parser_doctor = subparsers.add_parser("doctor", help="Diagnose project status")
    parser_doctor.set_defaults(func=cmd_doctor)

    # chat
    parser_chat = subparsers.add_parser("chat", help="Start conversation")
    parser_chat.add_argument(
        "--model", "-m",
        help="Model to use (deepseek, qwen-coder)"
    )
    parser_chat.set_defaults(func=cmd_chat)

    # models
    parser_models = subparsers.add_parser("models", help="List available models")
    parser_models.set_defaults(func=cmd_models)

    args = parser.parse_args()

    if args.command is None:
        # Default: doctor
        cmd_doctor(args)
    else:
        args.func(args)


if __name__ == "__main__":
    main()
