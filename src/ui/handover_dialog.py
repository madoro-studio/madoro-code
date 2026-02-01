"""
MADORO CODE - Handover Approval Dialog
Shows diff and asks for user confirmation before updating HANDOVER.md
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QSplitter, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QFont
from pathlib import Path
import difflib


class HandoverApprovalDialog(QDialog):
    """Dialog for approving HANDOVER.md changes"""

    def __init__(self, parent=None, old_content: str = "", new_content: str = "", file_path: str = ""):
        super().__init__(parent)
        self.old_content = old_content
        self.new_content = new_content
        self.file_path = file_path
        self.approved = False

        self.setWindowTitle("Approve HANDOVER.md Changes")
        self.setMinimumSize(800, 600)

        # Set window icon
        import os
        bundle_path = os.environ.get('MADORO_CODE_BUNDLE', str(Path(__file__).parent.parent.parent))
        icon_path = Path(bundle_path) / "assets" / "icon.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header
        header_layout = QHBoxLayout()

        warning_icon = QLabel("⚠️")
        warning_icon.setStyleSheet("font-size: 24px;")
        header_layout.addWidget(warning_icon)

        title = QLabel("HANDOVER.md Update Detected")
        title.setStyleSheet("""
            font-size: 16px;
            font-weight: 600;
            color: #d4a84b;
        """)
        header_layout.addWidget(title)
        header_layout.addStretch()

        layout.addLayout(header_layout)

        # Description
        desc = QLabel(
            "The AI is attempting to modify HANDOVER.md, which tracks your project's current state.\n"
            "Please review the changes below before approving."
        )
        desc.setStyleSheet("color: #a8a89a; font-size: 12px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # File path
        path_label = QLabel(f"File: {self.file_path}")
        path_label.setStyleSheet("color: #6a6a5a; font-size: 11px;")
        layout.addWidget(path_label)

        # Splitter for side-by-side diff
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Old content (left)
        old_frame = QFrame()
        old_layout = QVBoxLayout(old_frame)
        old_layout.setContentsMargins(0, 0, 0, 0)

        old_label = QLabel("Current Content")
        old_label.setStyleSheet("color: #b85c5c; font-weight: 600; font-size: 12px;")
        old_layout.addWidget(old_label)

        self.old_text = QTextEdit()
        self.old_text.setPlainText(self.old_content)
        self.old_text.setReadOnly(True)
        self.old_text.setFont(QFont("Consolas", 10))
        self.old_text.setStyleSheet("""
            QTextEdit {
                background-color: #2d352d;
                color: #e8e4d9;
                border: 1px solid #3d453d;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        old_layout.addWidget(self.old_text)

        splitter.addWidget(old_frame)

        # New content (right)
        new_frame = QFrame()
        new_layout = QVBoxLayout(new_frame)
        new_layout.setContentsMargins(0, 0, 0, 0)

        new_label = QLabel("Proposed Changes")
        new_label.setStyleSheet("color: #7c9a6e; font-weight: 600; font-size: 12px;")
        new_layout.addWidget(new_label)

        self.new_text = QTextEdit()
        self.new_text.setPlainText(self.new_content)
        self.new_text.setReadOnly(True)
        self.new_text.setFont(QFont("Consolas", 10))
        self.new_text.setStyleSheet("""
            QTextEdit {
                background-color: #2d352d;
                color: #e8e4d9;
                border: 1px solid #3d453d;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        new_layout.addWidget(self.new_text)

        splitter.addWidget(new_frame)

        # Set equal widths
        splitter.setSizes([400, 400])
        layout.addWidget(splitter, 1)

        # Diff summary
        diff_summary = self._generate_diff_summary()
        if diff_summary:
            summary_label = QLabel(diff_summary)
            summary_label.setStyleSheet("""
                color: #a8b5a0;
                font-size: 11px;
                background-color: #232823;
                padding: 8px;
                border-radius: 6px;
            """)
            summary_label.setWordWrap(True)
            layout.addWidget(summary_label)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        reject_btn = QPushButton("Reject Changes")
        reject_btn.setStyleSheet("""
            QPushButton {
                background-color: #b85c5c;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #c96c6c;
            }
        """)
        reject_btn.clicked.connect(self.reject_changes)
        btn_layout.addWidget(reject_btn)

        approve_btn = QPushButton("Approve & Save")
        approve_btn.setStyleSheet("""
            QPushButton {
                background-color: #7c9a6e;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #8caa7e;
            }
        """)
        approve_btn.clicked.connect(self.approve_changes)
        approve_btn.setDefault(True)
        btn_layout.addWidget(approve_btn)

        layout.addLayout(btn_layout)

    def _generate_diff_summary(self) -> str:
        """Generate a summary of changes"""
        old_lines = self.old_content.split('\n')
        new_lines = self.new_content.split('\n')

        diff = list(difflib.unified_diff(old_lines, new_lines, lineterm=''))

        added = sum(1 for line in diff if line.startswith('+') and not line.startswith('+++'))
        removed = sum(1 for line in diff if line.startswith('-') and not line.startswith('---'))

        if added == 0 and removed == 0:
            return "No significant changes detected."

        return f"Changes: +{added} lines added, -{removed} lines removed"

    def approve_changes(self):
        self.approved = True
        self.accept()

    def reject_changes(self):
        self.approved = False
        self.reject()

    def is_approved(self) -> bool:
        return self.approved


class SSOTFileChangeDialog(QDialog):
    """Generic dialog for SSOT file changes (CONSTITUTION, ARCHITECTURE, etc.)"""

    def __init__(self, parent=None, file_name: str = "", old_content: str = "",
                 new_content: str = "", file_path: str = ""):
        super().__init__(parent)
        self.old_content = old_content
        self.new_content = new_content
        self.file_path = file_path
        self.file_name = file_name
        self.approved = False

        self.setWindowTitle(f"Confirm {file_name} Changes")
        self.setMinimumSize(700, 500)

        # Set window icon
        import os
        bundle_path = os.environ.get('MADORO_CODE_BUNDLE', str(Path(__file__).parent.parent.parent))
        icon_path = Path(bundle_path) / "assets" / "icon.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Header
        title = QLabel(f"📝 {self.file_name} modification detected")
        title.setStyleSheet("font-size: 14px; font-weight: 600; color: #d4a84b;")
        layout.addWidget(title)

        desc = QLabel(f"The AI wants to modify {self.file_name}. Review and approve?")
        desc.setStyleSheet("color: #a8a89a; font-size: 12px;")
        layout.addWidget(desc)

        # Content preview
        preview = QTextEdit()
        preview.setPlainText(self.new_content)
        preview.setReadOnly(True)
        preview.setFont(QFont("Consolas", 10))
        preview.setStyleSheet("""
            QTextEdit {
                background-color: #2d352d;
                color: #e8e4d9;
                border: 1px solid #3d453d;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        layout.addWidget(preview, 1)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        reject_btn = QPushButton("Reject")
        reject_btn.clicked.connect(self.reject)
        btn_layout.addWidget(reject_btn)

        approve_btn = QPushButton("Approve")
        approve_btn.setStyleSheet("""
            QPushButton {
                background-color: #7c9a6e;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
            }
        """)
        approve_btn.clicked.connect(self.approve_changes)
        approve_btn.setDefault(True)
        btn_layout.addWidget(approve_btn)

        layout.addLayout(btn_layout)

    def approve_changes(self):
        self.approved = True
        self.accept()

    def is_approved(self) -> bool:
        return self.approved
