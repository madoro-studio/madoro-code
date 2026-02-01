# MADORO CODE

<p align="center">
  <img src="assets/icon.png" alt="MADORO CODE Logo" width="128" height="128">
</p>

<p align="center">
  <strong>Project-aware AI coding assistant with SSOT-based persistent memory.</strong>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#installation">Installation</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#supported-models">Models</a> •
  <a href="#configuration">Configuration</a>
</p>

---

## What is MADORO CODE?

**MADORO CODE** is a desktop AI coding assistant that remembers your project context across sessions. Unlike chat-based AI tools that forget everything after each conversation, MADORO CODE maintains a **persistent memory** of your project's architecture, decisions, and progress through SSOT (Single Source of Truth) documents.

### Why MADORO CODE?

| Traditional AI Chat | MADORO CODE |
|---------------------|-------------|
| Forgets everything after session | Remembers project context |
| You repeat explanations every time | AI knows your project structure |
| No project continuity | Seamless handover between sessions |
| Generic responses | Context-aware suggestions |

### Core Philosophy

1. **Memory is External, Not in the Model** - Project knowledge is stored in files and databases, not in the AI's context window
2. **Everything is Logged** - All changes, decisions, and test results are automatically recorded
3. **Context on Demand** - The system builds context from your project's SSOT documents
4. **LLM as Worker, Not Storage** - AI does the thinking and coding; the system handles memory

---

## Features

### 🧠 Persistent Project Memory
- Automatic project state tracking via HANDOVER.md
- Decision history in DECISIONS.md
- Architecture documentation in ARCHITECTURE.md
- Per-project conversation history in SQLite

### 🔧 Multi-Model Support
- **DeepSeek** - Cost-effective, excellent for coding (V3, R1 Reasoner)
- **Claude** - Best performance (Sonnet 4, Opus 4)
- **Gemini** - Fast with huge context (3 Flash, 2.5 Pro)
- **Ollama** - Local models for privacy (any Ollama-compatible model)

### 📁 Multi-Project Management
- Create and switch between multiple projects
- Each project has isolated memory and settings
- Import existing codebases

### 🛡️ SSOT Document Protection
- Approval popup before modifying critical documents
- Side-by-side diff view for changes
- Prevents accidental overwrites

### 🌐 Multi-Language Support
- Interface in English
- AI responds in user's language automatically

---

## Installation

### Build from Source

```bash
# Clone the repository
git clone https://github.com/madoro-studio/madoro-code.git
cd madoro-code

# Install dependencies
pip install -r requirements.txt

# Run from source
python main.py

# Or build executable
pip install pyinstaller
pyinstaller MADORO_CODE.spec --noconfirm
```

### Download Release

Pre-built executables will be available in [Releases](https://github.com/madoro-studio/madoro-code/releases) soon.

---

## Quick Start

### 1. Set Up API Keys

On first launch:
1. Click the 🔑 **Settings** button (top right)
2. Enter your API key(s):
   - **DeepSeek**: Get from [platform.deepseek.com](https://platform.deepseek.com)
   - **Anthropic (Claude)**: Get from [console.anthropic.com](https://console.anthropic.com)
   - **Google (Gemini)**: Get from [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
3. Click **Save** and restart the app

### 2. Create a Project

1. Click **+ New** button
2. Enter project details:
   - **Name**: Your project name
   - **Path**: Folder containing your code
   - **Tech Stack**: e.g., "Python, FastAPI, PostgreSQL"
3. Click **Create**

### 3. Start Coding

1. Select your project from the dropdown
2. Choose a model (DeepSeek R1 recommended for reasoning)
3. Start chatting:
   ```
   You: Analyze the codebase and suggest improvements
   You: Add error handling to the API endpoints
   You: Write unit tests for the user service
   ```

---

## Supported Models

### Cloud API Models

| Provider | Model | Best For | API Key Required |
|----------|-------|----------|------------------|
| DeepSeek | V3 | General coding | Yes |
| DeepSeek | R1 Reasoner | Complex reasoning, debugging | Yes |
| Anthropic | Claude Sonnet 4 | Balanced performance | Yes |
| Anthropic | Claude Opus 4 | Best quality, architecture | Yes |
| Google | Gemini 3 Flash | Fast tasks | Yes |
| Google | Gemini 2.5 Pro | Long context, reasoning | Yes |

### Local Models (Ollama)

For privacy-conscious users or offline work:

1. Install [Ollama](https://ollama.ai)
2. Pull a model: `ollama pull qwen2.5-coder:7b`
3. Edit `config/models.yaml`:
   ```yaml
   ollama-local:
     ollama_model: "qwen2.5-coder:7b"  # Change to any model
   ```
4. Select "Ollama Local Model" in the app

**Popular Ollama models for coding:**
- `qwen2.5-coder:7b` - Fast, good for simple tasks
- `codellama:34b` - Strong coding capabilities
- `deepseek-coder:33b` - Excellent reasoning
- `llama3.3:70b` - Best open-source (requires good GPU)

---

## Configuration

### Project Structure

```
MADORO_CODE/
├── MADORO_CODE.exe          # Main application
├── config/
│   ├── models.yaml          # Model configuration
│   ├── projects.json        # Project list
│   └── app_settings.json    # App settings
├── projects/
│   └── [project_id]/
│       ├── memory.db        # Conversation history
│       └── settings.json    # Project settings
└── assets/
    └── icon.ico
```

### SSOT Documents

MADORO CODE uses these files in your project folder:

| File | Purpose |
|------|---------|
| `HANDOVER.md` | Current project state, in-progress tasks |
| `CONSTITUTION.md` | Project rules, coding standards |
| `ARCHITECTURE.md` | System design, component overview |
| `CHECKLIST.md` | Todo items, pending tasks |
| `DECISIONS.md` | Key decisions and rationale |

These are automatically created when you create a project. The AI references these to understand your project context.

### Model Configuration

Edit `config/models.yaml` to customize:

```yaml
models:
  ollama-local:
    ollama_model: "your-model:tag"  # Change this
    context_length: 8192
    temperature: 0.3

# API Keys (or use Settings UI)
api:
  deepseek:
    api_key: "sk-..."
  anthropic:
    api_key: "sk-ant-..."
  google:
    api_key: "AIza..."
```

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Enter` | Send message |
| `Shift+Enter` | New line in message |
| `Ctrl+L` | Clear chat |
| `Escape` | Cancel current operation |

---

## FAQ

### Q: Why is my project not loading?

Make sure you're running from the correct folder. If using a desktop shortcut, right-click → Properties → verify "Start in" points to the folder containing `config/`.

### Q: How do I use a different Ollama model?

Edit `config/models.yaml` and change the `ollama_model` value under `ollama-local`. Then restart the app.

### Q: Can I use multiple API providers?

Yes! Enter all your API keys in Settings. Then select different models for different tasks.

### Q: Is my code sent to external servers?

Only if you use cloud API models (DeepSeek, Claude, Gemini). For full privacy, use Ollama with local models.

### Q: How do I update MADORO CODE?

Download the latest release and replace the exe. Your `config/` and `projects/` folders will be preserved.

---

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## Acknowledgments

- Built with [PyQt6](https://www.riverbankcomputing.com/software/pyqt/)
- AI powered by [DeepSeek](https://deepseek.com), [Anthropic](https://anthropic.com), [Google](https://ai.google.dev), and [Ollama](https://ollama.ai)

---

<p align="center">
  Made with ❤️ for developers who want AI that remembers
</p>
