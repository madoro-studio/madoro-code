"""
MADORO CODE - Project Creation/Edit Dialog
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QTextEdit, QSpinBox, QPushButton, QLabel,
    QFileDialog, QTabWidget, QWidget, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from pathlib import Path


class ProjectDialog(QDialog):
    """Project creation/edit dialog"""

    def __init__(self, parent=None, project=None):
        super().__init__(parent)
        self.project = project  # None for new project, otherwise edit
        self.result_data = None

        self.setWindowTitle("New Project" if not project else "Edit Project")
        self.setMinimumSize(600, 700)

        # Set window icon (use bundle path for EXE)
        import os
        bundle_path = os.environ.get('MADORO_CODE_BUNDLE', str(Path(__file__).parent.parent.parent))
        icon_path = Path(bundle_path) / "assets" / "icon.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.init_ui()

        if project:
            self.load_project_data(project)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Tab widget
        tabs = QTabWidget()

        # ===== Basic Info Tab =====
        basic_tab = QWidget()
        basic_layout = QFormLayout(basic_tab)
        basic_layout.setSpacing(12)

        # Project name
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. My Awesome Project")
        basic_layout.addRow("Project Name:", self.name_edit)

        # Project path
        path_layout = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("C:/src/my_project")
        path_layout.addWidget(self.path_edit)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_folder)
        path_layout.addWidget(browse_btn)
        basic_layout.addRow("Project Path:", path_layout)

        # Project description
        self.desc_edit = QTextEdit()
        self.desc_edit.setPlaceholderText("Brief description of the project...")
        self.desc_edit.setMaximumHeight(80)
        basic_layout.addRow("Description:", self.desc_edit)

        # Tech stack
        self.stack_edit = QLineEdit()
        self.stack_edit.setPlaceholderText("e.g. Flutter, Dart, Firebase, Python")
        basic_layout.addRow("Tech Stack:", self.stack_edit)

        # Conversation turns
        turn_layout = QHBoxLayout()
        self.turn_spin = QSpinBox()
        self.turn_spin.setRange(10, 200)
        self.turn_spin.setValue(50)
        self.turn_spin.setSuffix(" turns")
        turn_layout.addWidget(self.turn_spin)
        turn_layout.addWidget(QLabel("(Recent conversations AI remembers)"))
        turn_layout.addStretch()
        basic_layout.addRow("History:", turn_layout)

        tabs.addTab(basic_tab, "Basic Info")

        # ===== AI Guidelines Tab (CONSTITUTION) =====
        const_tab = QWidget()
        const_layout = QVBoxLayout(const_tab)

        const_label = QLabel("Define principles and rules for AI to follow:")
        const_label.setStyleSheet("color: #888;")
        const_layout.addWidget(const_label)

        self.constitution_edit = QTextEdit()
        self.constitution_edit.setPlaceholderText("""## Project Principles
1. Code quality first
2. Maintain test coverage
3. Documentation required

## Coding Conventions
- Use descriptive variable names
- Functions should be snake_case
- Classes should be PascalCase

## Prohibited
- Hardcoded secrets
- Deployment without tests
- Complex logic without comments""")
        const_layout.addWidget(self.constitution_edit)

        tabs.addTab(const_tab, "AI Guidelines")

        # ===== Architecture Tab =====
        arch_tab = QWidget()
        arch_layout = QVBoxLayout(arch_tab)

        arch_label = QLabel("Describe project architecture and structure:")
        arch_label.setStyleSheet("color: #888;")
        arch_layout.addWidget(arch_label)

        self.architecture_edit = QTextEdit()
        self.architecture_edit.setPlaceholderText("""## Project Structure
```
src/
├── ui/          # UI components
├── services/    # Business logic
├── models/      # Data models
└── utils/       # Utilities
```

## Core Components
- **MainApp**: App entry point
- **ApiService**: API communication
- **DatabaseHelper**: Local DB management

## Data Flow
User → UI → Service → API/DB → Service → UI → User""")
        arch_layout.addWidget(self.architecture_edit)

        tabs.addTab(arch_tab, "Architecture")

        # ===== Checklist Tab =====
        check_tab = QWidget()
        check_layout = QVBoxLayout(check_tab)

        check_label = QLabel("Project TODO and checklist:")
        check_label.setStyleSheet("color: #888;")
        check_layout.addWidget(check_label)

        self.checklist_edit = QTextEdit()
        self.checklist_edit.setPlaceholderText("""## In Progress
- [ ] Implement feature A
- [ ] Fix bug B

## Completed
- [x] Project setup
- [x] Basic structure created

## Planned
- [ ] Write tests
- [ ] Documentation
- [ ] Deployment preparation""")
        check_layout.addWidget(self.checklist_edit)

        tabs.addTab(check_tab, "Checklist")

        # ===== Decisions Tab (DECISIONS.md) =====
        decisions_tab = QWidget()
        decisions_layout = QVBoxLayout(decisions_tab)

        decisions_label = QLabel("Key decisions and rationale (why we chose this approach):")
        decisions_label.setStyleSheet("color: #888;")
        decisions_layout.addWidget(decisions_label)

        self.decisions_edit = QTextEdit()
        self.decisions_edit.setPlaceholderText("""## Decision Log

### [2024-01-15] Database Choice
**Decision:** Use SQLite instead of PostgreSQL
**Rationale:** Single-user app, no need for server. Simpler deployment.
**Alternatives Considered:** PostgreSQL, MySQL
**Impact:** Faster development, easier distribution

### [2024-01-16] UI Framework
**Decision:** PyQt6 over Electron
**Rationale:** Native performance, smaller binary size
**Alternatives Considered:** Electron, Tauri
**Impact:** ~50MB vs 150MB+ binary

---
Format: Date, Decision, Rationale, Alternatives, Impact""")
        decisions_layout.addWidget(self.decisions_edit)

        tabs.addTab(decisions_tab, "Decisions")

        # ===== Current State Tab (HANDOVER) =====
        handover_tab = QWidget()
        handover_layout = QVBoxLayout(handover_tab)

        handover_label = QLabel("Current project state (for session continuity):")
        handover_label.setStyleSheet("color: #888;")
        handover_layout.addWidget(handover_label)

        self.handover_edit = QTextEdit()
        self.handover_edit.setPlaceholderText("""## Current State
- Project initialization complete

## Recently Completed
- None

## In Progress
- None

## Next Steps
- Design project structure
- Implement core features

## Notes
- This file helps AI understand project state
- Update when significant changes occur""")
        handover_layout.addWidget(self.handover_edit)

        tabs.addTab(handover_tab, "Handover")

        layout.addWidget(tabs)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save" if self.project else "Create")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self.save_project)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Project Folder",
            str(Path.home())
        )
        if folder:
            self.path_edit.setText(folder)

    def load_project_data(self, project):
        """Load existing project data"""
        self.name_edit.setText(project.name)
        self.path_edit.setText(project.path)
        self.desc_edit.setPlainText(project.description)

        # Load documents from project folder
        project_path = Path(project.path)

        # CONSTITUTION.md
        const_path = project_path / "CONSTITUTION.md"
        if const_path.exists():
            self.constitution_edit.setPlainText(const_path.read_text(encoding="utf-8"))

        # ARCHITECTURE.md
        arch_path = project_path / "ARCHITECTURE.md"
        if arch_path.exists():
            self.architecture_edit.setPlainText(arch_path.read_text(encoding="utf-8"))

        # CHECKLIST.md
        check_path = project_path / "CHECKLIST.md"
        if check_path.exists():
            self.checklist_edit.setPlainText(check_path.read_text(encoding="utf-8"))

        # DECISIONS.md
        decisions_path = project_path / "DECISIONS.md"
        if decisions_path.exists():
            self.decisions_edit.setPlainText(decisions_path.read_text(encoding="utf-8"))

        # HANDOVER.md
        handover_path = project_path / "HANDOVER.md"
        if handover_path.exists():
            self.handover_edit.setPlainText(handover_path.read_text(encoding="utf-8"))

        # Load turn count from project settings
        try:
            from project_manager import get_project_manager
            pm = get_project_manager()
            project_data_dir = pm.projects_dir / project.id
            settings_path = project_data_dir / "settings.json"
            if settings_path.exists():
                import json
                with open(settings_path, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                    self.turn_spin.setValue(settings.get("max_turns", 50))
                    self.stack_edit.setText(settings.get("tech_stack", ""))
        except:
            pass

    def save_project(self):
        """Save project"""
        name = self.name_edit.text().strip()
        base_path = self.path_edit.text().strip()

        if not name:
            QMessageBox.warning(self, "Error", "Please enter a project name.")
            return

        if not base_path:
            QMessageBox.warning(self, "Error", "Please select a project path.")
            return

        # Create project subfolder with sanitized name
        folder_name = name.replace(" ", "_").replace("-", "_")
        folder_name = "".join(c for c in folder_name if c.isalnum() or c == "_")
        project_path = Path(base_path) / folder_name

        try:
            project_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to create folder: {e}")
            return

        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Save SSOT documents
        try:
            # CONSTITUTION.md
            const_content = self.constitution_edit.toPlainText().strip()
            if not const_content:
                const_content = f"""# {name} - CONSTITUTION
> Last updated: {timestamp}

## Project Principles
1. Code quality first
2. Maintain test coverage
3. Documentation required

## Tech Stack
{self.stack_edit.text() or '(Not specified)'}

## Coding Conventions
- (Add coding rules here)

## Prohibited
- Hardcoded secrets
- Deployment without tests
"""
            else:
                # Update timestamp
                if "Last updated:" in const_content:
                    import re
                    const_content = re.sub(
                        r'Last updated:.*',
                        f'Last updated: {timestamp}',
                        const_content
                    )
                else:
                    const_content = f"> Last updated: {timestamp}\n\n{const_content}"

            (project_path / "CONSTITUTION.md").write_text(const_content, encoding="utf-8")

            # ARCHITECTURE.md
            arch_content = self.architecture_edit.toPlainText().strip()
            if not arch_content:
                arch_content = f"""# {name} - ARCHITECTURE
> Last updated: {timestamp}

## Project Structure
```
(Add project structure here)
```

## Core Components
- (Describe main components)

## Data Flow
- (Describe data flow)
"""
            else:
                if "Last updated:" in arch_content:
                    import re
                    arch_content = re.sub(
                        r'Last updated:.*',
                        f'Last updated: {timestamp}',
                        arch_content
                    )
                else:
                    arch_content = f"> Last updated: {timestamp}\n\n{arch_content}"

            (project_path / "ARCHITECTURE.md").write_text(arch_content, encoding="utf-8")

            # CHECKLIST.md
            check_content = self.checklist_edit.toPlainText().strip()
            if not check_content:
                check_content = f"""# {name} - CHECKLIST
> Last updated: {timestamp}

## In Progress
- [ ] Project setup

## Completed
- [x] Project created ({timestamp})

## Planned
- [ ] Implement core features
- [ ] Write tests
"""
            else:
                if "Last updated:" in check_content:
                    import re
                    check_content = re.sub(
                        r'Last updated:.*',
                        f'Last updated: {timestamp}',
                        check_content
                    )
                else:
                    check_content = f"> Last updated: {timestamp}\n\n{check_content}"

            (project_path / "CHECKLIST.md").write_text(check_content, encoding="utf-8")

            # DECISIONS.md
            decisions_content = self.decisions_edit.toPlainText().strip()
            if not decisions_content:
                decisions_content = f"""# {name} - DECISIONS
> Last updated: {timestamp}

## Decision Log

### [{timestamp[:10]}] Project Initialization
**Decision:** Project created with MADORO CODE
**Rationale:** Centralized AI-assisted development environment
**Alternatives Considered:** Manual setup, other IDEs
**Impact:** Structured documentation, session continuity

---
*Add new decisions above this line. Format: Date, Decision, Rationale, Alternatives, Impact*
"""
            else:
                if "Last updated:" in decisions_content:
                    import re
                    decisions_content = re.sub(
                        r'Last updated:.*',
                        f'Last updated: {timestamp}',
                        decisions_content
                    )
                else:
                    decisions_content = f"> Last updated: {timestamp}\n\n{decisions_content}"

            (project_path / "DECISIONS.md").write_text(decisions_content, encoding="utf-8")

            # HANDOVER.md
            handover_content = self.handover_edit.toPlainText().strip()
            if not handover_content:
                handover_content = f"""# {name} - HANDOVER
> Last updated: {timestamp}

## Current State
- Project initialization complete
- Created: {timestamp}

## Recently Completed
- [x] Project setup complete

## In Progress
- None

## Next Steps
- Design project structure
- Implement core features

## Session Summary
This project was created on {timestamp}.
Tech Stack: {self.stack_edit.text() or 'Not specified'}

## Notes
- This file helps AI understand project state
- Update when significant changes occur
"""
            else:
                if "Last updated:" in handover_content:
                    import re
                    handover_content = re.sub(
                        r'Last updated:.*',
                        f'Last updated: {timestamp}',
                        handover_content
                    )
                else:
                    handover_content = f"> Last updated: {timestamp}\n\n{handover_content}"

            (project_path / "HANDOVER.md").write_text(handover_content, encoding="utf-8")

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save documents: {e}")
            return

        # Set result data (use actual project subfolder path)
        self.result_data = {
            "name": name,
            "path": str(project_path),
            "description": self.desc_edit.toPlainText().strip(),
            "tech_stack": self.stack_edit.text().strip(),
            "max_turns": self.turn_spin.value()
        }

        self.accept()

    def get_result(self):
        return self.result_data
