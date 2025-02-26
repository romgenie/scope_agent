# managers/data_manager.py
import os
import json
import glob
from typing import List, Dict, Any, Optional, Union
from datetime import datetime

from models.project import ProjectData
from models.interaction import InteractionRecord

class DataManager:
    """Handles data persistence operations for projects."""
    
    def __init__(self, projects_dir="projects"):
        """Initialize the data manager with the projects directory."""
        self.projects_dir = projects_dir
        # Ensure projects directory exists
        os.makedirs(self.projects_dir, exist_ok=True)
    
    def load_projects_list(self) -> List[Dict[str, str]]:
        """Load list of existing projects from the projects directory."""
        project_files = glob.glob(os.path.join(self.projects_dir, "*.json"))
        projects = []
        
        for file_path in project_files:
            try:
                with open(file_path, 'r') as f:
                    project_dict = json.load(f)
                    project_data = ProjectData.model_validate(project_dict)
                    projects.append({
                        'name': project_data.name,
                        'file_path': file_path,
                        'created_at': project_data.created_at,
                        'last_modified': project_data.last_modified,
                        'completion': f"{project_data.get_completion_percentage()}%"
                    })
            except Exception as e:
                print(f"Error loading project from {file_path}: {e}")
        
        # Sort by last modified, newest first
        return sorted(projects, key=lambda x: x['last_modified'], reverse=True)
    
    def load_project(self, file_path: str) -> Optional[ProjectData]:
        """Load a project from a file path."""
        try:
            with open(file_path, 'r') as f:
                project_dict = json.load(f)
                return ProjectData.model_validate(project_dict)
        except Exception as e:
            print(f"Error loading project: {e}")
            return None
    
    def save_project(self, project: ProjectData) -> str:
        """Save a project to file and return the file path."""
        project.update_last_modified()
        
        # Create safe filename
        safe_name = ''.join(c if c.isalnum() else '_' for c in project.name)
        file_path = os.path.join(self.projects_dir, f"{safe_name}.json")
        
        try:
            with open(file_path, 'w') as f:
                json.dump(project.model_dump(), f, indent=2)
            return file_path
        except Exception as e:
            print(f"Error saving project: {e}")
            return ""
    
    def delete_project_file(self, project_name: str) -> bool:
        """Delete a project file by name."""
        safe_name = ''.join(c if c.isalnum() else '_' for c in project_name)
        file_path = os.path.join(self.projects_dir, f"{safe_name}.json")
        
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                return True
            except Exception as e:
                print(f"Error deleting project file: {e}")
        
        return False
    
    def rename_project(self, old_name: str, new_name: str, project: ProjectData) -> bool:
        """Rename a project by deleting the old file and saving with new name."""
        # Delete the old file
        if old_name != new_name:
            self.delete_project_file(old_name)
        
        # Update project name
        project.name = new_name
        
        # Save with new name
        file_path = self.save_project(project)
        return bool(file_path)
    
    def wipe_all_projects(self) -> bool:
        """Delete all project files (for database reset)."""
        try:
            project_files = glob.glob(os.path.join(self.projects_dir, "*.json"))
            for file_path in project_files:
                os.remove(file_path)
            return True
        except Exception as e:
            print(f"Error wiping projects: {e}")
            return False
    
    def export_scope_document(self, project: ProjectData, format: str = "md") -> str:
        """Export the project scope as a markdown or JSON document."""
        if format == "json":
            # Return the scope as JSON
            return json.dumps(project.scope.model_dump(), indent=2)
        else:
            # Create a markdown document
            md = f"# {project.name} - Project Scope Document\n\n"
            md += f"*Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n"
            md += f"**Project Completion: {project.get_completion_percentage()}%**\n\n"
            
            if project.description:
                md += "## Project Description\n\n"
                md += f"{project.description}\n\n"
            
            # Add each completed category
            categories = [
                ("Project Objectives", project.scope.objective),
                ("Target Audience", project.scope.audience),
                ("Deliverables", project.scope.deliverable),
                ("Timeline", project.scope.timeline),
                ("Resources", project.scope.resource),
                ("Risks", project.scope.risk),
                ("Success Metrics", project.scope.success_metric)
            ]
            
            for title, category in categories:
                if category.is_complete():
                    md += f"## {title}\n\n"
                    md += f"{category.value}\n\n"
                    if category.description:
                        md += f"*{category.description}*\n\n"
            
            # Add any additional categories
            for key, category in project.scope.additional_categories.items():
                if category.is_complete():
                    md += f"## {key.replace('_', ' ').title()}\n\n"
                    md += f"{category.value}\n\n"
                    if category.description:
                        md += f"*{category.description}*\n\n"
            
            return md