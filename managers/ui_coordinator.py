# managers/ui_coordinator.py
import logging
from typing import List, Dict, Any, Optional, Callable

from models.project import ProjectData
from models.suggestions import SuggestionItem
from managers.ui_manager import UIManager
from utils.event_bus import EventBus

logger = logging.getLogger(__name__)

class UICoordinator:
    """
    Coordinates user interface interactions.
    
    This class centralizes all UI-related functionality and provides
    a clean interface for handling UI events.
    """
    
    def __init__(self, ui_manager: UIManager, event_bus: Optional[EventBus] = None):
        """
        Initialize the UI coordinator.
        
        Args:
            ui_manager: Manager for UI interactions
            event_bus: Optional event bus for publishing events
        """
        self.ui_manager = ui_manager
        self.event_bus = event_bus
        self.current_project: Optional[ProjectData] = None
        
        # Set up UI callbacks
        self._setup_ui_callbacks()
    
    def _setup_ui_callbacks(self) -> None:
        """Set up callbacks for the UI manager."""
        self.ui_manager.on_project_selected = self._on_project_selected
        self.ui_manager.on_new_project = self._on_new_project
        self.ui_manager.on_message_sent = self._on_message_sent
        self.ui_manager.on_exit = self._on_exit
    
    def display_welcome(self) -> None:
        """Display welcome message."""
        self.ui_manager.display_welcome()
    
    def display_projects_list(self, projects: List[Dict[str, str]]) -> None:
        """
        Display list of available projects.
        
        Args:
            projects: List of project dictionaries
        """
        self.ui_manager.display_projects_list(projects)
    
    def handle_project_selection(self, projects: List[Dict[str, str]]) -> None:
        """
        Handle project selection from the user.
        
        Args:
            projects: List of project dictionaries
        """
        self.ui_manager.select_project_prompt(projects)
    
    def display_project_info(self, project: ProjectData) -> None:
        """
        Display information about a project.
        
        Args:
            project: The project to display
        """
        self.ui_manager.display_project_info(project)
    
    def display_suggestions(self, suggestions: List[SuggestionItem], category: str, allow_custom: bool = True) -> None:
        """
        Display suggestions to the user.
        
        Args:
            suggestions: List of suggestions
            category: Category of suggestions
            allow_custom: Whether custom input is allowed
        """
        self.ui_manager.display_suggestions(suggestions, category, allow_custom)
    
    def update_current_project(self, project: ProjectData) -> None:
        """
        Update the current project.
        
        Args:
            project: The new current project
        """
        self.current_project = project
        self.ui_manager.current_project = project
    
    def _on_project_selected(self, file_path: str) -> None:
        """
        Handle project selected callback.
        
        Args:
            file_path: Path to the selected project file
        """
        if self.event_bus:
            self.event_bus.publish("project_file_selected", file_path)
    
    def _on_new_project(self, description: str) -> None:
        """
        Handle new project callback.
        
        Args:
            description: Description of the new project
        """
        if self.event_bus:
            self.event_bus.publish("new_project_requested", description)
    
    def _on_message_sent(self, message: str) -> None:
        """
        Handle message sent callback.
        
        Args:
            message: The sent message
        """
        if self.event_bus:
            self.event_bus.publish("user_input", {
                "message": message,
                "project": self.current_project
            })
    
    def _on_exit(self) -> None:
        """Handle exit callback."""
        if self.event_bus:
            self.event_bus.publish("exit_requested", None)
    
    def handle_user_input(self) -> None:
        """Handle user input in the interactive loop."""
        try:
            while True:
                user_input = self.ui_manager.get_user_input()
                
                if user_input in ["exit", "save"]:
                    self._on_exit()
                    break
                elif user_input == "history":
                    # Already displayed by UI manager
                    continue
                # The actual message sending is handled by the UI manager's callback
        except Exception as e:
            logger.error(f"Error in interactive loop: {e}")
            print(f"Error during conversation: {e}")
            self._on_exit()