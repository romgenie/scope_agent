# managers/project_lifecycle_manager.py
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from models.project import ProjectData
from managers.data_manager import DataManager
from utils.event_bus import EventBus

logger = logging.getLogger(__name__)

class ProjectLifecycleManager:
    """
    Manages the lifecycle of projects including creation, loading, and saving.
    
    This class centralizes all project state management and persistence operations.
    """
    
    def __init__(self, data_manager: DataManager, event_bus: Optional[EventBus] = None):
        """
        Initialize the project lifecycle manager.
        
        Args:
            data_manager: Manager for data persistence
            event_bus: Optional event bus for publishing events
        """
        self.data_manager = data_manager
        self.event_bus = event_bus
        self.current_project: Optional[ProjectData] = None
    
    def create_new_project(self, description: str) -> ProjectData:
        """
        Create a new project with the given description.
        
        Args:
            description: User-provided project description
            
        Returns:
            The newly created project
        """
        try:
            logger.info(f"Creating new project with description: {description}")
            
            # Create default project name
            default_name = f"Project_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Create project data
            self.current_project = ProjectData(
                name=default_name,
                description=description,
                stage="initial"
            )
            
            # Save the new project
            self._save_project()
            
            # Publish event if event bus exists
            if self.event_bus:
                self.event_bus.publish("project_created", self.current_project)
            
            return self.current_project
        except Exception as e:
            logger.error(f"Error creating new project: {e}")
            raise
    
    def load_project(self, file_path: str) -> Optional[ProjectData]:
        """
        Load an existing project from file.
        
        Args:
            file_path: Path to the project file
            
        Returns:
            The loaded project or None if loading failed
        """
        try:
            logger.info(f"Loading project from: {file_path}")
            project_data = self.data_manager.load_project(file_path)
            
            if not project_data:
                logger.warning("Failed to load project")
                return None
            
            self.current_project = project_data
            
            # Publish event if event bus exists
            if self.event_bus:
                self.event_bus.publish("project_loaded", self.current_project)
            
            return self.current_project
        except Exception as e:
            logger.error(f"Error loading project: {e}")
            return None
    
    def save_project(self) -> bool:
        """
        Save the current project to file.
        
        Returns:
            True if saving succeeded, False otherwise
        """
        return self._save_project()
    
    def _save_project(self) -> bool:
        """
        Internal method to save the current project.
        
        Returns:
            True if saving succeeded, False otherwise
        """
        if not self.current_project:
            logger.warning("Attempted to save project, but no project is active")
            return False
        
        try:
            logger.debug("Saving project")
            self.current_project.update_last_modified()
            
            # Save to file
            file_path = self.data_manager.save_project(self.current_project)
            if file_path:
                logger.debug(f"Project saved to {file_path}")
                
                # Publish event if event bus exists
                if self.event_bus:
                    self.event_bus.publish("project_saved", self.current_project)
                
                return True
            else:
                logger.error("Failed to save project")
                return False
        except Exception as e:
            logger.error(f"Error saving project: {e}")
            return False
    
    def update_project_metadata(self, key: str, value: Any) -> bool:
        """
        Update a metadata field on the current project.
        
        Args:
            key: The metadata field to update
            value: The new value
            
        Returns:
            True if the update succeeded, False otherwise
        """
        if not self.current_project:
            logger.warning("Attempted to update project, but no project is active")
            return False
        
        try:
            if hasattr(self.current_project, key):
                setattr(self.current_project, key, value)
                
                # Special case for project name updates - rename the file
                if key == "name":
                    old_name = self.current_project.name
                    if old_name and old_name != value:
                        self.data_manager.delete_project_file(old_name)
                
                self._save_project()
                
                # Publish event if event bus exists
                if self.event_bus:
                    self.event_bus.publish("project_updated", {
                        "project": self.current_project,
                        "updated_field": key
                    })
                
                return True
            else:
                logger.warning(f"Attempted to update unknown field: {key}")
                return False
        except Exception as e:
            logger.error(f"Error updating project metadata: {e}")
            return False
    
    def get_current_project(self) -> Optional[ProjectData]:
        """
        Get the current active project.
        
        Returns:
            The current project or None if no project is active
        """
        return self.current_project
    
    def get_projects_list(self) -> List[Dict[str, str]]:
        """
        Get a list of all available projects.
        
        Returns:
            List of project dictionaries with metadata
        """
        return self.data_manager.load_projects_list()