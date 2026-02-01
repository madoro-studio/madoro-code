"""
MADORO CODE - Project Manager
Multi-project management (create, switch, delete)
"""

import os
import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict


@dataclass
class Project:
    """Project information"""
    id: str
    name: str
    path: str
    created_at: str
    last_opened: str
    description: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'Project':
        return cls(**data)


class ProjectManager:
    """Project Manager"""

    def __init__(self, base_path: str = None):
        if base_path is None:
            base_path = os.environ.get('MADORO_CODE_BASE', '.')
        self.base_path = Path(base_path)
        self.config_file = self.base_path / "config" / "projects.json"
        self.projects_dir = self.base_path / "projects"

        # Create directories
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.config_file.parent.mkdir(parents=True, exist_ok=True)

        # Load config
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        """Load project configuration"""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return {"projects": [], "active_project": None}

    def _save_config(self):
        """Save project configuration"""
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)

    def list_projects(self) -> List[Project]:
        """List projects"""
        return [Project.from_dict(p) for p in self.config.get("projects", [])]

    def get_project(self, project_id: str) -> Optional[Project]:
        """Get project"""
        for p in self.config.get("projects", []):
            if p["id"] == project_id:
                return Project.from_dict(p)
        return None

    def get_active_project(self) -> Optional[Project]:
        """Get current active project"""
        active_id = self.config.get("active_project")
        if active_id:
            return self.get_project(active_id)
        return None

    def create_project(self, name: str, path: str, description: str = "",
                       tech_stack: str = "", max_turns: int = 50) -> Project:
        """Create new project"""
        # Generate ID (name-based slug)
        project_id = name.lower().replace(" ", "_").replace("-", "_")
        project_id = "".join(c for c in project_id if c.isalnum() or c == "_")

        # Check duplicates
        existing_ids = [p["id"] for p in self.config.get("projects", [])]
        if project_id in existing_ids:
            # Append number
            i = 2
            while f"{project_id}_{i}" in existing_ids:
                i += 1
            project_id = f"{project_id}_{i}"

        now = datetime.now().isoformat()
        project = Project(
            id=project_id,
            name=name,
            path=path,
            created_at=now,
            last_opened=now,
            description=description
        )

        # Create project data directory
        project_data_dir = self.projects_dir / project_id
        project_data_dir.mkdir(parents=True, exist_ok=True)

        # Create project meta file
        meta_file = project_data_dir / "project.json"
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(project.to_dict(), f, ensure_ascii=False, indent=2)

        # Create project settings file
        settings_file = project_data_dir / "settings.json"
        settings = {
            "tech_stack": tech_stack,
            "max_turns": max_turns,
            "created_at": now,
            "updated_at": now
        }
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)

        # Create template SSOT files (if not exist in project path)
        self._create_ssot_templates(Path(path), name)

        # Add to config
        self.config.setdefault("projects", []).append(project.to_dict())
        self.config["active_project"] = project_id
        self._save_config()

        return project

    def _create_ssot_templates(self, project_path: Path, project_name: str):
        """Create SSOT template files"""
        project_path.mkdir(parents=True, exist_ok=True)

        # HANDOVER.md
        handover_path = project_path / "HANDOVER.md"
        if not handover_path.exists():
            handover_content = f"""# {project_name} - HANDOVER

## Current State
- Project initialization complete
- Created: {datetime.now().strftime("%Y-%m-%d")}

## Completed Tasks
- [ ] Project setup

## In Progress
- None

## Next Steps
- Design project structure
- Implement core features

## Notes
- This file helps MADORO CODE understand project state
- Update when tasks are completed
"""
            handover_path.write_text(handover_content, encoding="utf-8")

        # CONSTITUTION.md
        constitution_path = project_path / "CONSTITUTION.md"
        if not constitution_path.exists():
            constitution_content = f"""# {project_name} - CONSTITUTION

## Project Principles
1. Code quality first
2. Maintain test coverage
3. Documentation required

## Tech Stack
- (Specify technologies here)

## Coding Conventions
- (Specify coding rules here)

## Prohibited
- Hardcoded secrets
- Deployment without tests

## Reference Documents
- README.md
- HANDOVER.md
"""
            constitution_path.write_text(constitution_content, encoding="utf-8")

    def switch_project(self, project_id: str) -> Optional[Project]:
        """Switch project"""
        project = self.get_project(project_id)
        if project:
            # Update last_opened
            for p in self.config.get("projects", []):
                if p["id"] == project_id:
                    p["last_opened"] = datetime.now().isoformat()
                    break

            self.config["active_project"] = project_id
            self._save_config()
            return project
        return None

    def get_current_project(self) -> Optional[Project]:
        """Get current active project (alias for get_active_project)"""
        return self.get_active_project()

    def update_project(self, project_id: str, name: str = None, description: str = None) -> Optional[Project]:
        """Update project basic info"""
        for p in self.config.get("projects", []):
            if p["id"] == project_id:
                if name is not None:
                    p["name"] = name
                if description is not None:
                    p["description"] = description
                p["last_opened"] = datetime.now().isoformat()
                self._save_config()
                return Project.from_dict(p)
        return None

    def delete_project(self, project_id: str, delete_data: bool = False) -> bool:
        """Delete project"""
        projects = self.config.get("projects", [])
        new_projects = [p for p in projects if p["id"] != project_id]

        if len(new_projects) == len(projects):
            return False  # No project to delete

        # Delete data (optional)
        if delete_data:
            project_data_dir = self.projects_dir / project_id
            if project_data_dir.exists():
                shutil.rmtree(project_data_dir)

        # Update config
        self.config["projects"] = new_projects
        if self.config.get("active_project") == project_id:
            self.config["active_project"] = new_projects[0]["id"] if new_projects else None
        self._save_config()

        return True

    def get_project_db_path(self, project_id: str = None) -> str:
        """Get project-specific DB path"""
        if project_id is None:
            project_id = self.config.get("active_project", "default")

        project_data_dir = self.projects_dir / project_id
        project_data_dir.mkdir(parents=True, exist_ok=True)

        return str(project_data_dir / "memory.db")

    def get_project_settings(self, project_id: str = None) -> Dict:
        """Get project settings"""
        if project_id is None:
            project_id = self.config.get("active_project")

        if not project_id:
            return {"max_turns": 50, "tech_stack": ""}

        settings_file = self.projects_dir / project_id / "settings.json"
        if settings_file.exists():
            try:
                with open(settings_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass

        return {"max_turns": 50, "tech_stack": ""}

    def save_project_settings(self, project_id: str, settings: Dict):
        """Save project settings"""
        project_data_dir = self.projects_dir / project_id
        project_data_dir.mkdir(parents=True, exist_ok=True)

        settings["updated_at"] = datetime.now().isoformat()
        settings_file = project_data_dir / "settings.json"
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)

    def import_existing_project(self, name: str, path: str, description: str = "") -> Project:
        """Import existing project (when HANDOVER.md etc. already exist)"""
        return self.create_project(name, path, description)


# Singleton Instance
_project_manager: Optional[ProjectManager] = None


def get_project_manager(base_path: str = None) -> ProjectManager:
    """Project manager singleton"""
    global _project_manager
    if _project_manager is None:
        _project_manager = ProjectManager(base_path)
    return _project_manager


def reset_project_manager():
    """Reset for testing"""
    global _project_manager
    _project_manager = None
