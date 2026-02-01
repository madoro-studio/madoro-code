"""
MADORO CODE - Chat UI
PyQt6 Desktop Application

Theme: Nordic Olive Retro
- Nordic minimalism + retro aesthetics
- Olive green tone base
- Apple-style simplicity
"""

import sys
import os
import json
from datetime import datetime
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QLabel, QScrollArea,
    QFrame, QSplitter, QComboBox, QStatusBar, QFileDialog, QMessageBox,
    QListView, QStyledItemDelegate
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSettings, QMimeData, QUrl
from PyQt6.QtGui import QFont, QColor, QPalette, QIcon, QImage, QCloseEvent


# ============================================
# 🎨 Nordic Olive Retro 테마 컬러
# ============================================
class Theme:
    # 베이스 컬러 (올리브 그린 톤)
    BG_DARK = "#1a1f1a"          # 가장 어두운 배경
    BG_MAIN = "#232823"          # 메인 배경
    BG_CARD = "#2d352d"          # 카드/패널 배경
    BG_INPUT = "#363e36"         # 입력 필드 배경

    # 악센트 컬러
    OLIVE = "#7c9a6e"            # 메인 올리브
    OLIVE_LIGHT = "#98b386"      # 밝은 올리브
    OLIVE_DARK = "#5a7a4a"       # 어두운 올리브
    SAGE = "#a8b5a0"             # 세이지 그린

    # 레트로 악센트
    CREAM = "#e8e4d9"            # 크림색 (텍스트)
    WARM_WHITE = "#f5f2eb"       # 따뜻한 화이트
    TERRACOTTA = "#c17f59"       # 테라코타 (하이라이트)
    MUSTARD = "#d4a84b"          # 머스타드 (경고/강조)

    # 상태 컬러
    SUCCESS = "#7c9a6e"          # 성공 (올리브)
    ERROR = "#b85c5c"            # 에러 (머티드 레드)
    INFO = "#6b8fa3"             # 정보 (머티드 블루)

    # 테두리
    BORDER = "#3d453d"           # 기본 테두리
    BORDER_LIGHT = "#4a544a"     # 밝은 테두리

    # 텍스트
    TEXT_PRIMARY = "#e8e4d9"     # 기본 텍스트
    TEXT_SECONDARY = "#a8a89a"   # 보조 텍스트
    TEXT_MUTED = "#6a6a5a"       # 흐린 텍스트


# 설정 파일 경로
SETTINGS_FILE = Path(__file__).parent.parent.parent / "config" / "app_settings.json"


class SSOTApprovalBridge:
    """Bridge for SSOT approval between worker thread and main thread"""

    def __init__(self):
        self.pending_approval = None
        self.approval_result = None
        self.approval_event = None

    def request_approval(self, file_name: str, file_path: str,
                         old_content: str, new_content: str) -> bool:
        """Store approval request (called from worker thread)"""
        import threading
        self.pending_approval = {
            "file_name": file_name,
            "file_path": file_path,
            "old_content": old_content,
            "new_content": new_content
        }
        self.approval_event = threading.Event()
        self.approval_result = None

        # Wait for main thread to process
        self.approval_event.wait(timeout=300)  # 5 minute timeout

        return self.approval_result if self.approval_result is not None else False

    def set_result(self, approved: bool):
        """Set approval result (called from main thread)"""
        self.approval_result = approved
        if self.approval_event:
            self.approval_event.set()

    def get_pending(self):
        """Get pending approval request"""
        return self.pending_approval

    def clear(self):
        """Clear pending request"""
        self.pending_approval = None


class LLMWorker(QThread):
    """LLM 호출을 별도 스레드에서 처리"""
    finished = pyqtSignal(str, list)  # message, tool_results
    error = pyqtSignal(str)
    progress = pyqtSignal(str, str)  # status, detail
    ssot_approval_needed = pyqtSignal()  # Signal when SSOT approval is needed

    def __init__(self, agent, user_input, ssot_bridge: SSOTApprovalBridge = None):
        super().__init__()
        self.agent = agent
        self.user_input = user_input
        self.ssot_bridge = ssot_bridge
        # Agent에 progress callback 연결
        self.agent.progress_callback = self._on_progress

    def _on_progress(self, status: str, detail: str):
        """Agent에서 진행 상황 수신"""
        self.progress.emit(status, detail)

    def _on_ssot_approval(self, file_name: str, file_path: str,
                          old_content: str, new_content: str) -> bool:
        """Handle SSOT approval request (called from tools in worker thread)"""
        if self.ssot_bridge:
            # Signal main thread that approval is needed
            self.ssot_approval_needed.emit()
            # Wait for approval through bridge
            return self.ssot_bridge.request_approval(
                file_name, file_path, old_content, new_content
            )
        return True  # Auto-approve if no bridge

    def run(self):
        try:
            # Set up SSOT approval callback on the tools
            if self.ssot_bridge:
                self.agent.tools.ssot_approval_callback = self._on_ssot_approval

            response = self.agent.process(self.user_input)
            self.finished.emit(response.message or "", response.tool_results or [])
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error.emit(str(e))


class PasteableTextEdit(QTextEdit):
    """이미지/파일 붙여넣기를 지원하는 TextEdit"""

    imagePasted = pyqtSignal(QImage)
    fileDropped = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.pasted_images = []
        self.dropped_files = []

    def canInsertFromMimeData(self, source: QMimeData) -> bool:
        if source.hasImage():
            return True
        if source.hasUrls():
            return True
        return super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source: QMimeData):
        if source.hasImage():
            image = QImage(source.imageData())
            if not image.isNull():
                self.pasted_images.append(image)
                self.insertPlainText(f"[Image attached: {image.width()}x{image.height()}]\n")
                self.imagePasted.emit(image)
                return

        if source.hasUrls():
            files = []
            for url in source.urls():
                if url.isLocalFile():
                    file_path = url.toLocalFile()
                    files.append(file_path)
                    self.insertPlainText(f"[File: {Path(file_path).name}]\n")
            if files:
                self.dropped_files.extend(files)
                self.fileDropped.emit(files)
                return

        super().insertFromMimeData(source)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() or event.mimeData().hasImage():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event):
        mime = event.mimeData()
        if mime.hasUrls():
            files = []
            for url in mime.urls():
                if url.isLocalFile():
                    file_path = url.toLocalFile()
                    files.append(file_path)
                    self.insertPlainText(f"[File: {Path(file_path).name}]\n")
            if files:
                self.dropped_files.extend(files)
                self.fileDropped.emit(files)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def clear_attachments(self):
        self.pasted_images.clear()
        self.dropped_files.clear()

    def get_attachments(self) -> dict:
        return {
            'images': self.pasted_images.copy(),
            'files': self.dropped_files.copy()
        }


class MessageWidget(QFrame):
    """Nordic Olive 스타일 메시지 위젯"""

    def __init__(self, text: str, is_user: bool = True, is_system: bool = False, parent=None):
        super().__init__(parent)
        self.message_text = text
        self.setFrameShape(QFrame.Shape.NoFrame)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 12)
        layout.setSpacing(14)

        # 아바타 (미니멀 원형)
        avatar = QLabel()
        avatar.setFixedSize(36, 36)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if is_system:
            avatar.setText("•")
            avatar.setStyleSheet(f"""
                background-color: {Theme.BG_CARD};
                color: {Theme.SAGE};
                border-radius: 18px;
                font-size: 20px;
                border: 1px solid {Theme.BORDER};
            """)
        elif is_user:
            avatar.setText("U")
            avatar.setStyleSheet(f"""
                background-color: {Theme.OLIVE};
                color: {Theme.WARM_WHITE};
                border-radius: 18px;
                font-size: 13px;
                font-weight: 600;
            """)
        else:
            avatar.setText("M")
            avatar.setStyleSheet(f"""
                background-color: {Theme.TERRACOTTA};
                color: {Theme.WARM_WHITE};
                border-radius: 18px;
                font-size: 13px;
                font-weight: 600;
            """)

        layout.addWidget(avatar, alignment=Qt.AlignmentFlag.AlignTop)

        # 메시지 내용
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(6)

        # 헤더 (이름 + 시간 + 복사버튼)
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)

        if is_system:
            sender_name = "System"
            name_color = Theme.TEXT_MUTED
        elif is_user:
            sender_name = "You"
            name_color = Theme.OLIVE_LIGHT
        else:
            sender_name = "MADORO"
            name_color = Theme.TERRACOTTA

        name_label = QLabel(sender_name)
        name_label.setStyleSheet(f"""
            color: {name_color};
            font-size: 12px;
            font-weight: 600;
            letter-spacing: 0.5px;
        """)
        header_layout.addWidget(name_label)

        time_label = QLabel(datetime.now().strftime("%H:%M"))
        time_label.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-size: 11px;")
        header_layout.addWidget(time_label)

        header_layout.addStretch()

        # 복사 버튼 (미니멀 아이콘 스타일)
        if not is_system:
            copy_btn = QPushButton("⊏")  # 미니멀 복사 아이콘
            copy_btn.setFixedSize(28, 28)
            copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            copy_btn.setToolTip("Copy to clipboard")
            copy_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {Theme.TEXT_MUTED};
                    border: none;
                    border-radius: 6px;
                    font-size: 14px;
                }}
                QPushButton:hover {{
                    background-color: {Theme.BORDER};
                    color: {Theme.CREAM};
                }}
            """)
            copy_btn.clicked.connect(self.copy_to_clipboard)
            header_layout.addWidget(copy_btn)

        content_layout.addLayout(header_layout)

        # 메시지 텍스트
        message_label = QLabel(text)
        message_label.setWordWrap(True)
        message_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse |
            Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        message_label.setStyleSheet(f"""
            color: {Theme.TEXT_PRIMARY};
            font-size: 14px;
            line-height: 1.6;
            padding: 2px 0;
        """)

        content_layout.addWidget(message_label)
        layout.addLayout(content_layout, 1)

        # 메시지 박스 스타일
        if is_system:
            self.setStyleSheet(f"""
                MessageWidget {{
                    background-color: {Theme.BG_CARD};
                    border-radius: 12px;
                    padding: 10px;
                    border-left: 3px solid {Theme.BORDER_LIGHT};
                }}
            """)
        elif is_user:
            self.setStyleSheet(f"""
                MessageWidget {{
                    background-color: {Theme.BG_CARD};
                    border-radius: 12px;
                    padding: 10px;
                    border-left: 3px solid {Theme.OLIVE};
                }}
            """)
        else:
            self.setStyleSheet(f"""
                MessageWidget {{
                    background-color: {Theme.BG_CARD};
                    border-radius: 12px;
                    padding: 10px;
                    border-left: 3px solid {Theme.TERRACOTTA};
                }}
            """)

    def copy_to_clipboard(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.message_text)
        btn = self.sender()
        if btn:
            btn.setText("✓")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {Theme.OLIVE_DARK};
                    color: {Theme.WARM_WHITE};
                    border: none;
                    border-radius: 6px;
                    font-size: 12px;
                }}
            """)
            QTimer.singleShot(1500, lambda: self._reset_copy_btn(btn))

    def _reset_copy_btn(self, btn):
        btn.setText("⊏")
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {Theme.TEXT_MUTED};
                border: none;
                border-radius: 6px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {Theme.BORDER};
                color: {Theme.CREAM};
            }}
        """)


class ChatWindow(QMainWindow):
    """메인 채팅 윈도우 - Nordic Olive Theme"""

    def __init__(self):
        super().__init__()
        self.agent = None
        self.worker = None
        self.project_path = None
        self.project_context = None
        self.thinking_msg = None
        self.elapsed_timer = None
        self.elapsed_seconds = 0
        self.ssot_bridge = SSOTApprovalBridge()  # Bridge for SSOT approvals
        self.approval_check_timer = None  # Timer to check for pending approvals

        self.load_settings()
        self.init_ui()
        QTimer.singleShot(200, self._delayed_init)

    def _delayed_init(self):
        if self.project_path:
            self.init_agent(self.project_path)
            self.load_project_context()
            self.update_model_combo()
            self.load_previous_conversation()
        self.update_status()

    def load_previous_conversation(self):
        if not self.agent:
            return

        try:
            turns = self.agent.memory.get_recent_turns(limit=20)
            if turns:
                self.add_message(f"─── Previous ({len(turns)}) ───", is_user=False, is_system=True)
                for turn in turns:
                    is_user = turn.role == "user"
                    content = turn.content
                    if len(content) > 500:
                        content = content[:500] + "..."
                    self.add_message(content, is_user=is_user)
                self.add_message("─── End of history ───", is_user=False, is_system=True)
        except Exception as e:
            print(f"Failed to load previous conversation: {e}")

    def load_settings(self):
        """Load active project from project manager"""
        try:
            from project_manager import get_project_manager
            pm = get_project_manager()
            active_project = pm.get_active_project()
            if active_project and Path(active_project.path).exists():
                self.project_path = active_project.path
                print(f"[UI] Active project: {active_project.name} ({active_project.path})")
        except Exception as e:
            print(f"Project load failed: {e}")
            # fallback: existing settings file
            try:
                if SETTINGS_FILE.exists():
                    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                        settings = json.load(f)
                        saved_path = settings.get("project_path", "")
                        if saved_path and Path(saved_path).exists():
                            self.project_path = saved_path
            except:
                pass

    def save_settings(self):
        try:
            SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
            settings = {
                "project_path": self.project_path or "",
                "last_updated": datetime.now().isoformat()
            }
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Settings save failed: {e}")

    def init_agent(self, project_path: str = None):
        try:
            import agent as agent_module
            import llm as llm_module
            import memory as memory_module
            import context as context_module

            agent_module._agent = None
            llm_module._llm_client = None
            memory_module._memory_store = None
            context_module._context_builder = None

            from agent import Agent
            path = project_path or "."
            self.agent = Agent(path)
            print(f"Agent 초기화 완료: {path}")
            print(f"LLM 연결: {self.agent.llm.check_connection()}")
            print(f"모델: {list(self.agent.llm.models.keys())}")
            return True
        except Exception as e:
            import traceback
            print(f"Agent 초기화 실패: {e}")
            traceback.print_exc()
            return False

    def load_project_context(self):
        if not self.project_path:
            return

        project_dir = Path(self.project_path)
        context_parts = []

        doc_patterns = [
            "HANDOVER.md", "CONSTITUTION.md", "README.md",
            "SPEC/HANDOVER.md", "SPEC/CONSTITUTION.md", "SPEC/CHECKLIST.md"
        ]

        found_docs = []
        for pattern in doc_patterns:
            doc_path = project_dir / pattern
            if doc_path.exists():
                try:
                    content = doc_path.read_text(encoding="utf-8")
                    lines = content.split('\n')[:100]
                    context_parts.append(f"=== {pattern} ===\n" + '\n'.join(lines))
                    found_docs.append(pattern)
                except:
                    pass

        if context_parts:
            self.project_context = '\n\n'.join(context_parts)

        return found_docs

    def init_ui(self):
        self.setWindowTitle("MADORO CODE")
        self.setMinimumSize(600, 400)

        # Set window icon (use bundle path for EXE)
        import os
        bundle_path = os.environ.get('MADORO_CODE_BUNDLE', str(Path(__file__).parent.parent.parent))
        icon_path = Path(bundle_path) / "assets" / "icon.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        # Set window to half screen (vertical rectangle on right side)
        screen = QApplication.primaryScreen().availableGeometry()
        window_width = screen.width() // 2
        window_height = screen.height()
        self.resize(window_width, window_height)
        # Position on right half of screen
        self.move(screen.width() // 2, 0)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = self.create_header()
        layout.addWidget(header)

        project_bar = self.create_project_bar()
        layout.addWidget(project_bar)

        chat_area = self.create_chat_area()
        layout.addWidget(chat_area, 1)

        input_area = self.create_input_area()
        layout.addWidget(input_area)

        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.update_status()

        self.apply_styles()

    def create_header(self) -> QWidget:
        header = QFrame()
        header.setFixedHeight(56)
        header.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.BG_DARK};
                border-bottom: 1px solid {Theme.BORDER};
            }}
        """)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(24, 0, 24, 0)

        # 로고 (미니멀)
        title = QLabel("MADORO")
        title.setStyleSheet(f"""
            font-size: 18px;
            font-weight: 700;
            color: {Theme.OLIVE_LIGHT};
            letter-spacing: 2px;
        """)
        layout.addWidget(title)

        subtitle = QLabel("CODE")
        subtitle.setStyleSheet(f"""
            font-size: 18px;
            font-weight: 300;
            color: {Theme.TEXT_SECONDARY};
            letter-spacing: 2px;
        """)
        layout.addWidget(subtitle)

        layout.addStretch()

        # 모델 선택
        model_label = QLabel("Model")
        model_label.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-size: 11px; letter-spacing: 1px;")
        layout.addWidget(model_label)

        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(180)
        self.model_combo.setMinimumHeight(32)
        self.model_combo.setEditable(False)
        # 스타일시트 없이 기본 스타일 사용 (드롭다운 문제 해결)

        layout.addWidget(self.model_combo)

        QTimer.singleShot(100, self.update_model_combo)

        return header

    def create_project_bar(self) -> QWidget:
        bar = QFrame()
        bar.setFixedHeight(48)
        bar.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.BG_MAIN};
                border-bottom: 1px solid {Theme.BORDER};
            }}
        """)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(24, 0, 24, 0)

        # 프로젝트 아이콘
        folder_icon = QLabel("◈")
        folder_icon.setStyleSheet(f"color: {Theme.OLIVE}; font-size: 14px;")
        layout.addWidget(folder_icon)

        project_label = QLabel("Project")
        project_label.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-size: 11px; letter-spacing: 1px;")
        layout.addWidget(project_label)

        # 프로젝트 선택 콤보박스
        self.project_combo = QComboBox()
        self.project_combo.setMinimumWidth(200)
        self.project_combo.setEditable(False)
        # 스타일시트 없이 기본 스타일 사용
        self.project_combo.currentIndexChanged.connect(self.on_project_changed)
        layout.addWidget(self.project_combo)

        # 프로젝트 경로 표시
        self.project_path_label = QLabel("")
        self.project_path_label.setStyleSheet(f"""
            color: {Theme.TEXT_MUTED};
            font-size: 11px;
            margin-left: 8px;
        """)
        layout.addWidget(self.project_path_label)

        layout.addStretch()

        # 새 프로젝트 버튼
        self.new_project_btn = QPushButton("+")
        self.new_project_btn.setFixedSize(28, 28)
        self.new_project_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.new_project_btn.setToolTip("New Project")
        self.new_project_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {Theme.OLIVE_LIGHT};
                border: 1px solid {Theme.OLIVE_DARK};
                border-radius: 6px;
                font-size: 16px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Theme.OLIVE_DARK};
                color: {Theme.WARM_WHITE};
            }}
        """)
        self.new_project_btn.clicked.connect(self.create_new_project)
        layout.addWidget(self.new_project_btn)

        # 프로젝트 편집 버튼
        self.edit_project_btn = QPushButton("⚙")
        self.edit_project_btn.setFixedSize(28, 28)
        self.edit_project_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.edit_project_btn.setToolTip("Edit Project Settings")
        self.edit_project_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {Theme.TEXT_MUTED};
                border: 1px solid {Theme.BORDER};
                border-radius: 6px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {Theme.BG_INPUT};
                color: {Theme.OLIVE_LIGHT};
                border-color: {Theme.OLIVE_DARK};
            }}
        """)
        self.edit_project_btn.clicked.connect(self.edit_current_project)
        layout.addWidget(self.edit_project_btn)

        # Settings button (API Keys, etc.)
        self.settings_btn = QPushButton("🔑")
        self.settings_btn.setFixedSize(28, 28)
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.setToolTip("Settings (API Keys)")
        self.settings_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {Theme.TEXT_MUTED};
                border: 1px solid {Theme.BORDER};
                border-radius: 6px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {Theme.BG_INPUT};
                color: {Theme.MUSTARD};
                border-color: {Theme.OLIVE_DARK};
            }}
        """)
        self.settings_btn.clicked.connect(self.open_settings)
        layout.addWidget(self.settings_btn)

        # Load project list
        QTimer.singleShot(100, self.update_project_combo)

        return bar

    def _get_display_path(self) -> str:
        if not self.project_path:
            return ""

        path = Path(self.project_path)
        parts = path.parts
        if len(parts) > 3:
            return f".../{'/'.join(parts[-2:])}"
        return str(path)

    def update_project_combo(self):
        """Update project list"""
        try:
            from project_manager import get_project_manager
            pm = get_project_manager()
            projects = pm.list_projects()

            self.project_combo.blockSignals(True)
            self.project_combo.clear()

            active_project = pm.get_active_project()
            active_idx = 0

            for i, project in enumerate(projects):
                self.project_combo.addItem(project.name, project.id)
                if active_project and project.id == active_project.id:
                    active_idx = i
                    self.project_path = project.path

            if projects:
                self.project_combo.setCurrentIndex(active_idx)
                self.project_path_label.setText(self._get_display_path())

            self.project_combo.blockSignals(False)
        except Exception as e:
            print(f"[UI] Failed to load project list: {e}")

    def on_project_changed(self, index: int):
        """Switch project"""
        project_id = self.project_combo.itemData(index)
        if not project_id:
            return

        try:
            from project_manager import get_project_manager
            pm = get_project_manager()
            project = pm.switch_project(project_id)

            if project:
                self.project_path = project.path
                self.project_path_label.setText(self._get_display_path())

                # Memory 리셋 (새 프로젝트 DB 로드)
                import memory as memory_module
                memory_module.reset_memory_store()

                # Agent 재초기화
                if self.init_agent(project.path):
                    self.load_project_context()
                    self.update_model_combo()
                    self.update_status()
                    self.add_message(f"Switched to project: {project.name}", is_user=False, is_system=True)
        except Exception as e:
            print(f"[UI] Project switch failed: {e}")

    def create_new_project(self):
        """Create new project - using ProjectDialog"""
        from ui.project_dialog import ProjectDialog

        dialog = ProjectDialog(self)
        if dialog.exec() == ProjectDialog.DialogCode.Accepted:
            result = dialog.get_result()
            if result:
                try:
                    from project_manager import get_project_manager
                    pm = get_project_manager()
                    project = pm.create_project(
                        name=result["name"],
                        path=result["path"],
                        description=result.get("description", ""),
                        tech_stack=result.get("tech_stack", ""),
                        max_turns=result.get("max_turns", 50)
                    )

                    # 프로젝트 목록 갱신
                    self.update_project_combo()

                    # 새 프로젝트로 전환
                    idx = self.project_combo.findData(project.id)
                    if idx >= 0:
                        self.project_combo.setCurrentIndex(idx)

                    self.add_message(
                        f"✅ Project created: {project.name}\n"
                        f"📁 Path: {project.path}\n"
                        f"📝 Tech Stack: {result.get('tech_stack', 'Not specified')}\n"
                        f"💬 History: {result.get('max_turns', 50)} turns",
                        is_user=False, is_system=True
                    )
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to create project: {e}")

    def edit_current_project(self):
        """Edit current project"""
        from ui.project_dialog import ProjectDialog
        from project_manager import get_project_manager

        pm = get_project_manager()
        current_project = pm.get_current_project()
        if not current_project:
            QMessageBox.information(self, "Info", "No project selected.")
            return

        dialog = ProjectDialog(self, project=current_project)
        if dialog.exec() == ProjectDialog.DialogCode.Accepted:
            result = dialog.get_result()
            if result:
                try:
                    # 프로젝트 설정 업데이트
                    pm.save_project_settings(current_project.id, {
                        "max_turns": result.get("max_turns", 50),
                        "tech_stack": result.get("tech_stack", "")
                    })

                    # 프로젝트 기본 정보 업데이트
                    pm.update_project(
                        current_project.id,
                        name=result["name"],
                        description=result.get("description", "")
                    )

                    # 프로젝트 목록 갱신
                    self.update_project_combo()

                    self.add_message(
                        f"✅ Project updated: {result['name']}",
                        is_user=False, is_system=True
                    )
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to update project: {e}")

    def open_settings(self):
        """Open settings dialog for API keys configuration"""
        from ui.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self)
        dialog.exec()

    def update_model_combo(self):
        self.model_combo.clear()

        if self.agent and self.agent.llm:
            for model_key in self.agent.llm.list_models():
                cfg = self.agent.llm.models[model_key]
                self.model_combo.addItem(cfg.display_name, model_key)

            # Restore last used model from project settings
            last_model = None
            try:
                project = self.project_manager.get_active_project()
                if project:
                    settings = self.project_manager.get_project_settings(project.id)
                    last_model = settings.get("last_model")
            except:
                pass

            # Set model: last used > current > default
            if last_model:
                self.agent.llm.set_model(last_model)

            current_idx = self.model_combo.findData(self.agent.llm.current_model)
            if current_idx >= 0:
                self.model_combo.setCurrentIndex(current_idx)

            try:
                self.model_combo.currentIndexChanged.disconnect()
            except:
                pass
            self.model_combo.currentIndexChanged.connect(self.on_model_changed)
            self.model_combo.setEnabled(True)
        else:
            self.model_combo.addItem("Not connected")
            self.model_combo.setEnabled(False)

    def create_chat_area(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background-color: {Theme.BG_MAIN};
            }}
            QScrollBar:vertical {{
                background-color: {Theme.BG_DARK};
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {Theme.BORDER_LIGHT};
                border-radius: 4px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {Theme.OLIVE_DARK};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.chat_layout.setSpacing(8)
        self.chat_layout.setContentsMargins(48, 24, 48, 24)

        scroll.setWidget(self.chat_container)
        self.scroll_area = scroll

        # 환영 메시지
        welcome = "Welcome to MADORO CODE.\n"
        if self.project_path:
            welcome += f"Current project: {Path(self.project_path).name}"
        else:
            welcome += "Please select a project folder to begin."
        self.add_message(welcome, is_user=False)

        return scroll

    def create_input_area(self) -> QWidget:
        input_frame = QFrame()
        input_frame.setMinimumHeight(80)
        input_frame.setMaximumHeight(180)
        input_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.BG_DARK};
                border-top: 1px solid {Theme.BORDER};
            }}
        """)

        layout = QHBoxLayout(input_frame)
        layout.setContentsMargins(48, 16, 48, 16)
        layout.setSpacing(12)

        # 입력 필드
        self.input_field = PasteableTextEdit()
        self.input_field.setPlaceholderText("Type a message... (Ctrl+V to paste, drag & drop supported)")
        self.input_field.imagePasted.connect(self.on_image_pasted)
        self.input_field.fileDropped.connect(self.on_file_dropped)
        self.input_field.setStyleSheet(f"""
            QTextEdit {{
                background-color: {Theme.BG_INPUT};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER};
                border-radius: 12px;
                padding: 12px 16px;
                font-size: 14px;
                selection-background-color: {Theme.OLIVE_DARK};
            }}
            QTextEdit:focus {{
                border-color: {Theme.OLIVE};
            }}
        """)
        self.input_field.setMinimumHeight(48)
        self.input_field.setMaximumHeight(140)
        self.input_field.installEventFilter(self)
        layout.addWidget(self.input_field)

        # 전송 버튼
        self.send_btn = QPushButton("→")
        self.send_btn.setFixedSize(48, 48)
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.OLIVE};
                color: {Theme.WARM_WHITE};
                border: none;
                border-radius: 24px;
                font-size: 18px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {Theme.OLIVE_LIGHT};
            }}
            QPushButton:disabled {{
                background-color: {Theme.BORDER};
                color: {Theme.TEXT_MUTED};
            }}
        """)
        self.send_btn.clicked.connect(self.send_message)
        layout.addWidget(self.send_btn, alignment=Qt.AlignmentFlag.AlignBottom)

        return input_frame

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent

        if obj == self.input_field and event.type() == QEvent.Type.KeyPress:
            key_event = event
            if key_event.key() == Qt.Key.Key_Return or key_event.key() == Qt.Key.Key_Enter:
                if key_event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    return False
                else:
                    self.send_message()
                    return True
        return super().eventFilter(obj, event)

    def on_image_pasted(self, image: QImage):
        self.add_message(
            f"[Image attached: {image.width()}x{image.height()}px]\n(Note: Image analysis is not yet supported)",
            is_user=False, is_system=True
        )

    def on_file_dropped(self, files: list):
        file_list = "\n".join([f"  • {Path(f).name}" for f in files])
        self.add_message(
            f"[Files attached]\n{file_list}\n(Note: Provide file path for content analysis)",
            is_user=False, is_system=True
        )

    def apply_styles(self):
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {Theme.BG_MAIN};
            }}
            QStatusBar {{
                background-color: {Theme.BG_DARK};
                color: {Theme.TEXT_MUTED};
                font-size: 11px;
                padding: 4px 16px;
            }}
            QToolTip {{
                background-color: {Theme.BG_CARD};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER};
                border-radius: 6px;
                padding: 6px 10px;
            }}
        """)

    def add_message(self, text: str, is_user: bool = True, is_system: bool = False):
        message_widget = MessageWidget(text, is_user, is_system)
        self.chat_layout.addWidget(message_widget)
        QTimer.singleShot(100, self.scroll_to_bottom)

    def scroll_to_bottom(self):
        scrollbar = self.scroll_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def send_message(self):
        text = self.input_field.toPlainText().strip()
        if not text:
            return

        if not self.project_path:
            self.add_message("Please select a project folder first.", is_user=False, is_system=True)
            return

        self.add_message(text, is_user=True)
        self.input_field.clear()
        self.input_field.clear_attachments()

        # 특수 명령어
        if text.lower() == "doctor":
            if self.agent:
                report = self.agent.doctor()
                self.add_message(report, is_user=False)
            return

        if text.lower() == "clear":
            while self.chat_layout.count():
                item = self.chat_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            self.add_message("Conversation cleared.", is_user=False)
            return

        if text.lower() == "context":
            if self.project_context:
                preview = self.project_context[:500] + "..." if len(self.project_context) > 500 else self.project_context
                self.add_message(f"[Current Context]\n{preview}", is_user=False, is_system=True)
            else:
                self.add_message("No project context loaded.", is_user=False, is_system=True)
            return

        # LLM 호출
        if self.agent:
            self.send_btn.setEnabled(False)
            self.input_field.setEnabled(False)

            model_cfg = self.agent.llm.get_model_config()
            model_name = model_cfg.display_name if model_cfg else "Unknown"

            self._current_status = f"Starting: {model_name}"
            self.thinking_msg = MessageWidget(f"⟳ {self._current_status}", is_user=False, is_system=True)
            self.chat_layout.addWidget(self.thinking_msg)
            self.scroll_to_bottom()

            self.elapsed_seconds = 0
            self.elapsed_timer = QTimer()
            self.elapsed_timer.timeout.connect(self._update_elapsed_time)
            self.elapsed_timer.start(1000)

            self.statusBar.showMessage(f"{self._current_status}")

            self.ssot_bridge.clear()  # Clear any previous pending approvals
            self.worker = LLMWorker(self.agent, text, self.ssot_bridge)
            self.worker.finished.connect(self.on_response_received)
            self.worker.error.connect(self.on_response_error)
            self.worker.progress.connect(self.on_progress_update)
            self.worker.ssot_approval_needed.connect(self.on_ssot_approval_needed)
            self.worker.start()
        else:
            self.add_message("Agent not initialized. Please check if Ollama is running.", is_user=False)

    def _update_elapsed_time(self):
        self.elapsed_seconds += 1
        # 상태바는 progress_update에서 업데이트하므로 시간만 추가
        if hasattr(self, '_current_status'):
            self.statusBar.showMessage(f"{self._current_status} ({self.elapsed_seconds}s)")

    def on_progress_update(self, status: str, detail: str):
        """Receive progress from Agent"""
        if status == "Complete":
            return

        # 상태 저장 (타이머에서 사용)
        if detail:
            self._current_status = f"{status}: {detail}"
        else:
            self._current_status = status

        # 상태바 업데이트
        self.statusBar.showMessage(f"{self._current_status} ({self.elapsed_seconds}s)")

        # thinking_msg 위젯 텍스트 업데이트
        if self.thinking_msg:
            # 메시지 라벨 찾아서 업데이트
            labels = self.thinking_msg.findChildren(QLabel)
            for label in labels:
                if label.wordWrap():  # 메시지 라벨은 wordWrap이 True
                    label.setText(f"⟳ {self._current_status}")
                    break

    def _stop_elapsed_timer(self):
        if self.elapsed_timer and self.elapsed_timer.isActive():
            self.elapsed_timer.stop()
        if self.thinking_msg:
            self.thinking_msg.setParent(None)
            self.thinking_msg.deleteLater()
            self.thinking_msg = None

    def on_response_received(self, message: str, tool_results: list):
        self._stop_elapsed_timer()

        self.send_btn.setEnabled(True)
        self.input_field.setEnabled(True)
        self.input_field.setFocus()

        if tool_results:
            tools_text = f"[Tools executed: {len(tool_results)}]\n"
            for tr in tool_results[:3]:
                status = "✓" if tr.get("success") else "✗"
                tools_text += f" {status} {tr.get('tool')}\n"
            self.add_message(tools_text, is_user=False, is_system=True)

        if message:
            self.add_message(message, is_user=False)

        self.update_status()

    def on_response_error(self, error: str):
        self._stop_elapsed_timer()

        self.send_btn.setEnabled(True)
        self.input_field.setEnabled(True)
        self.input_field.setFocus()

        self.add_message(f"Error: {error}", is_user=False)
        self.statusBar.showMessage(f"Error: {error}")

    def on_ssot_approval_needed(self):
        """Handle SSOT file approval request"""
        pending = self.ssot_bridge.get_pending()
        if not pending:
            self.ssot_bridge.set_result(True)  # Auto-approve if no pending
            return

        from ui.handover_dialog import HandoverApprovalDialog, SSOTFileChangeDialog

        file_name = pending["file_name"]
        file_path = pending["file_path"]
        old_content = pending["old_content"]
        new_content = pending["new_content"]

        # Use specialized dialog for HANDOVER.md
        if file_name == "HANDOVER.md":
            dialog = HandoverApprovalDialog(
                self,
                old_content=old_content,
                new_content=new_content,
                file_path=file_path
            )
        else:
            dialog = SSOTFileChangeDialog(
                self,
                file_name=file_name,
                old_content=old_content,
                new_content=new_content,
                file_path=file_path
            )

        # Update status to show waiting for approval
        self.statusBar.showMessage(f"Waiting for approval: {file_name}")

        # Show dialog and get result
        dialog.exec()
        approved = dialog.is_approved()

        # Send result back to worker thread
        self.ssot_bridge.set_result(approved)

        if approved:
            self.add_message(f"✅ Approved: {file_name} changes", is_user=False, is_system=True)
        else:
            self.add_message(f"❌ Rejected: {file_name} changes", is_user=False, is_system=True)

    def on_model_changed(self, index: int):
        model_key = self.model_combo.itemData(index)
        if self.agent and model_key:
            self.agent.llm.set_model(model_key)
            self.update_status()
            self.add_message(f"Model changed to {self.model_combo.currentText()}", is_user=False, is_system=True)

            # Save last used model to project settings
            try:
                project = self.project_manager.get_active_project()
                if project:
                    settings = self.project_manager.get_project_settings(project.id)
                    settings["last_model"] = model_key
                    self.project_manager.save_project_settings(project.id, settings)
            except Exception as e:
                print(f"[UI] Failed to save last model: {e}")

    def update_status(self):
        parts = []

        if self.project_path:
            parts.append(f"◈ {Path(self.project_path).name}")
        else:
            parts.append("◈ No project")

        if self.agent and self.agent.llm:
            connected = self.agent.llm.check_connection()
            cfg = self.agent.llm.get_model_config()
            model_name = cfg.display_name if cfg else "Unknown"

            if connected:
                parts.append(f"● Connected • {model_name}")
            else:
                parts.append("○ Disconnected")
        else:
            parts.append("○ No agent")

        self.statusBar.showMessage("  │  ".join(parts))

    def closeEvent(self, event: QCloseEvent):
        """Handle window close - prompt for SSOT update"""
        # Check if there's an active project and recent conversation
        if self.project_path and self.agent and self.agent.memory:
            recent_turns = self.agent.memory.get_recent_turns(limit=10)

            if len(recent_turns) > 2:  # Only ask if there was meaningful conversation
                reply = QMessageBox.question(
                    self,
                    "Save Progress",
                    "Do you want to update project documents (HANDOVER, CHECKLIST) before closing?\n\n"
                    "This will save your session progress to SSOT files.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.Yes
                )

                if reply == QMessageBox.StandardButton.Cancel:
                    event.ignore()
                    return
                elif reply == QMessageBox.StandardButton.Yes:
                    self._save_session_to_ssot()

        event.accept()

    def _save_session_to_ssot(self):
        """Save current session progress to SSOT documents"""
        if not self.project_path or not self.agent:
            return

        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            # Get recent conversation summary
            recent_turns = self.agent.memory.get_recent_turns(limit=20)

            # Build session summary from recent turns
            session_summary = []
            for turn in recent_turns[-10:]:
                if turn['role'] == 'user':
                    content = turn['content'][:100]
                    if len(turn['content']) > 100:
                        content += "..."
                    session_summary.append(f"- User: {content}")

            # Update HANDOVER.md
            handover_path = Path(self.project_path) / "HANDOVER.md"
            if handover_path.exists():
                content = handover_path.read_text(encoding="utf-8")

                # Update timestamp
                import re
                if "Last updated:" in content:
                    content = re.sub(r'Last updated:.*', f'Last updated: {timestamp}', content)

                # Add session note
                session_note = f"\n\n---\n### Session Note ({timestamp})\nRecent activity recorded.\n"

                # Find a good place to insert (after "## Current State" or at end)
                if "## Current State" in content:
                    # Insert after Current State section header
                    idx = content.find("## Current State")
                    next_section = content.find("\n## ", idx + 1)
                    if next_section > 0:
                        content = content[:next_section] + session_note + content[next_section:]
                    else:
                        content += session_note
                else:
                    content += session_note

                handover_path.write_text(content, encoding="utf-8")
                print(f"[UI] HANDOVER.md updated at {timestamp}")

        except Exception as e:
            print(f"[UI] Failed to save session to SSOT: {e}")


def main():
    app = QApplication(sys.argv)

    app.setApplicationName("MADORO CODE")
    app.setOrganizationName("MADORO STUDIO")

    # Nordic Olive 테마 팔레트
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(Theme.BG_MAIN))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(Theme.TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Base, QColor(Theme.BG_INPUT))
    palette.setColor(QPalette.ColorRole.Text, QColor(Theme.TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Button, QColor(Theme.BG_CARD))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(Theme.TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(Theme.OLIVE))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(Theme.WARM_WHITE))
    app.setPalette(palette)

    # 폰트 (시스템 산세리프)
    font = QFont("Segoe UI", 10)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    app.setFont(font)

    window = ChatWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
