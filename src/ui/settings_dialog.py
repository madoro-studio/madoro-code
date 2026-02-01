"""
MADORO CODE - Settings Dialog
Allows users to configure API keys and other settings
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTabWidget, QWidget, QFormLayout, QMessageBox,
    QGroupBox, QCheckBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QFont
from pathlib import Path
import yaml
import os


class SettingsDialog(QDialog):
    """Settings dialog for API keys and configuration"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_path = self._get_config_path()
        self.config = self._load_config()

        self.setWindowTitle("Settings")
        self.setMinimumSize(500, 400)

        # Set window icon
        bundle_path = os.environ.get('MADORO_CODE_BUNDLE', str(Path(__file__).parent.parent.parent))
        icon_path = Path(bundle_path) / "assets" / "icon.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.init_ui()
        self.load_values()

    def _get_config_path(self) -> Path:
        """Get the path to models.yaml"""
        # Try EXE location first (user data)
        exe_path = os.environ.get('MADORO_CODE_BASE', '')
        if exe_path:
            config_path = Path(exe_path) / "config" / "models.yaml"
            if config_path.exists():
                return config_path

        # Fallback to bundle path
        bundle_path = os.environ.get('MADORO_CODE_BUNDLE', str(Path(__file__).parent.parent.parent))
        return Path(bundle_path) / "config" / "models.yaml"

    def _load_config(self) -> dict:
        """Load configuration from YAML"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"Failed to load config: {e}")
        return {}

    def _save_config(self):
        """Save configuration to YAML"""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True)
            return True
        except Exception as e:
            print(f"Failed to save config: {e}")
            return False

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("⚙️ Settings")
        title.setStyleSheet("font-size: 18px; font-weight: 600; color: #e8e4d9;")
        layout.addWidget(title)

        # Tabs
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #3d453d;
                border-radius: 8px;
                background-color: #2d352d;
            }
            QTabBar::tab {
                background-color: #232823;
                color: #a8a89a;
                padding: 8px 16px;
                border: 1px solid #3d453d;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            QTabBar::tab:selected {
                background-color: #2d352d;
                color: #e8e4d9;
            }
        """)

        # API Keys Tab
        api_tab = QWidget()
        api_layout = QVBoxLayout(api_tab)
        api_layout.setSpacing(16)
        api_layout.setContentsMargins(16, 16, 16, 16)

        # DeepSeek API
        deepseek_group = QGroupBox("DeepSeek API")
        deepseek_group.setStyleSheet("""
            QGroupBox {
                font-weight: 600;
                color: #98b386;
                border: 1px solid #3d453d;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
            }
        """)
        deepseek_layout = QFormLayout(deepseek_group)
        deepseek_layout.setSpacing(8)

        self.deepseek_key = QLineEdit()
        self.deepseek_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.deepseek_key.setPlaceholderText("sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
        self.deepseek_key.setStyleSheet(self._input_style())
        deepseek_layout.addRow("API Key:", self.deepseek_key)

        deepseek_hint = QLabel("Get your key from: https://platform.deepseek.com")
        deepseek_hint.setStyleSheet("color: #6a6a5a; font-size: 11px;")
        deepseek_layout.addRow("", deepseek_hint)

        api_layout.addWidget(deepseek_group)

        # Anthropic API
        anthropic_group = QGroupBox("Anthropic API (Claude)")
        anthropic_group.setStyleSheet("""
            QGroupBox {
                font-weight: 600;
                color: #98b386;
                border: 1px solid #3d453d;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
            }
        """)
        anthropic_layout = QFormLayout(anthropic_group)
        anthropic_layout.setSpacing(8)

        self.anthropic_key = QLineEdit()
        self.anthropic_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.anthropic_key.setPlaceholderText("sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxx")
        self.anthropic_key.setStyleSheet(self._input_style())
        anthropic_layout.addRow("API Key:", self.anthropic_key)

        anthropic_hint = QLabel("Get your key from: https://console.anthropic.com")
        anthropic_hint.setStyleSheet("color: #6a6a5a; font-size: 11px;")
        anthropic_layout.addRow("", anthropic_hint)

        api_layout.addWidget(anthropic_group)

        # Google API (Gemini)
        google_group = QGroupBox("Google API (Gemini)")
        google_group.setStyleSheet("""
            QGroupBox {
                font-weight: 600;
                color: #98b386;
                border: 1px solid #3d453d;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
            }
        """)
        google_layout = QFormLayout(google_group)
        google_layout.setSpacing(8)

        self.google_key = QLineEdit()
        self.google_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.google_key.setPlaceholderText("AIzaSyxxxxxxxxxxxxxxxxxxxxxxxxx")
        self.google_key.setStyleSheet(self._input_style())
        google_layout.addRow("API Key:", self.google_key)

        google_hint = QLabel("Get your key from: https://aistudio.google.com/apikey")
        google_hint.setStyleSheet("color: #6a6a5a; font-size: 11px;")
        google_layout.addRow("", google_hint)

        api_layout.addWidget(google_group)

        # Show/Hide password toggle
        show_keys = QCheckBox("Show API keys")
        show_keys.setStyleSheet("color: #a8a89a;")
        show_keys.toggled.connect(self._toggle_key_visibility)
        api_layout.addWidget(show_keys)

        api_layout.addStretch()

        # Info
        info = QLabel(
            "⚠️ API keys are stored locally in config/models.yaml.\n"
            "Never share your config file with API keys included."
        )
        info.setStyleSheet("color: #d4a84b; font-size: 11px;")
        info.setWordWrap(True)
        api_layout.addWidget(info)

        tabs.addTab(api_tab, "API Keys")

        # Ollama Tab
        ollama_tab = QWidget()
        ollama_layout = QVBoxLayout(ollama_tab)
        ollama_layout.setSpacing(16)
        ollama_layout.setContentsMargins(16, 16, 16, 16)

        ollama_group = QGroupBox("Ollama Server")
        ollama_group.setStyleSheet("""
            QGroupBox {
                font-weight: 600;
                color: #98b386;
                border: 1px solid #3d453d;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
            }
        """)
        ollama_form = QFormLayout(ollama_group)

        self.ollama_url = QLineEdit()
        self.ollama_url.setPlaceholderText("http://127.0.0.1:11434")
        self.ollama_url.setStyleSheet(self._input_style())
        ollama_form.addRow("Base URL:", self.ollama_url)

        ollama_hint = QLabel("Default: http://127.0.0.1:11434 (local Ollama server)")
        ollama_hint.setStyleSheet("color: #6a6a5a; font-size: 11px;")
        ollama_form.addRow("", ollama_hint)

        ollama_layout.addWidget(ollama_group)
        ollama_layout.addStretch()

        tabs.addTab(ollama_tab, "Ollama")

        layout.addWidget(tabs, 1)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #363e36;
                color: #a8a89a;
                border: 1px solid #3d453d;
                border-radius: 6px;
                padding: 8px 20px;
            }
            QPushButton:hover {
                background-color: #4a544a;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #7c9a6e;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #8caa7e;
            }
        """)
        save_btn.clicked.connect(self.save_settings)
        save_btn.setDefault(True)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _input_style(self) -> str:
        return """
            QLineEdit {
                background-color: #363e36;
                color: #e8e4d9;
                border: 1px solid #3d453d;
                border-radius: 6px;
                padding: 8px;
                font-family: Consolas, monospace;
            }
            QLineEdit:focus {
                border-color: #7c9a6e;
            }
        """

    def _toggle_key_visibility(self, show: bool):
        mode = QLineEdit.EchoMode.Normal if show else QLineEdit.EchoMode.Password
        self.deepseek_key.setEchoMode(mode)
        self.anthropic_key.setEchoMode(mode)
        self.google_key.setEchoMode(mode)

    def load_values(self):
        """Load current values from config"""
        api = self.config.get('api', {})

        # DeepSeek
        deepseek = api.get('deepseek', {})
        self.deepseek_key.setText(deepseek.get('api_key', ''))

        # Anthropic
        anthropic = api.get('anthropic', {})
        self.anthropic_key.setText(anthropic.get('api_key', ''))

        # Google
        google = api.get('google', {})
        self.google_key.setText(google.get('api_key', ''))

        # Ollama
        ollama = self.config.get('ollama', {})
        self.ollama_url.setText(ollama.get('base_url', 'http://127.0.0.1:11434'))

    def save_settings(self):
        """Save settings to config file"""
        # Update config
        if 'api' not in self.config:
            self.config['api'] = {}

        if 'deepseek' not in self.config['api']:
            self.config['api']['deepseek'] = {}
        self.config['api']['deepseek']['api_key'] = self.deepseek_key.text().strip()
        self.config['api']['deepseek']['base_url'] = 'https://api.deepseek.com'

        if 'anthropic' not in self.config['api']:
            self.config['api']['anthropic'] = {}
        self.config['api']['anthropic']['api_key'] = self.anthropic_key.text().strip()

        if 'google' not in self.config['api']:
            self.config['api']['google'] = {}
        self.config['api']['google']['api_key'] = self.google_key.text().strip()

        if 'ollama' not in self.config:
            self.config['ollama'] = {}
        self.config['ollama']['base_url'] = self.ollama_url.text().strip() or 'http://127.0.0.1:11434'

        # Save
        if self._save_config():
            QMessageBox.information(
                self,
                "Settings Saved",
                "Settings have been saved successfully.\n"
                "Restart the application for changes to take effect."
            )
            self.accept()
        else:
            QMessageBox.warning(
                self,
                "Save Failed",
                "Failed to save settings. Please check file permissions."
            )
