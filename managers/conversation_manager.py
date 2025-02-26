# managers/conversation_manager.py
import logging
from typing import List, Dict, Any, Optional, Union

from models.project import ProjectData
from models.suggestions import SuggestionItem
from managers.assistant_manager import AssistantManager
from managers.tool_manager import ToolManager
from managers.interaction_recorder import InteractionRecorder

# Configure logger
logger = logging.getLogger(__name__)

class ConversationManager:
    """Manages conversation flow with the assistant."""
    
    def __init__(
        self, 
        assistant_manager: AssistantManager,
        tool_manager: Optional[ToolManager],
        interaction_recorder: InteractionRecorder
    ):
        """
        Initialize the conversation manager.
        
        Args:
            assistant_manager: Manager for assistant interactions
            tool_manager: Manager for tool interactions (can be None initially)
            interaction_recorder: Recorder for interaction history
        """
        self.assistant_manager = assistant_manager
        self.tool_manager = tool_manager
        self.interaction_recorder = interaction_recorder
    
    def process_message(self, message: str, project: ProjectData) -> str:
        """
        Process a user message and handle suggestion selections.
        
        Args:
            message: Raw user input message
            project: Current project data
            
        Returns:
            Processed message ready to send to assistant
        """
        logger.debug(f"Processing message: {message}")
        
        if not self.tool_manager or not self.tool_manager.current_suggestions:
            # Record as custom input with no suggestions
            self.interaction_recorder.record_response(
                project=project,
                interaction_index=self.interaction_recorder.get_latest_index(project),
                custom_input=message,
                is_custom=True
            )
            return message
        
        return self._process_suggestion_input(message, project)
    
    def _process_suggestion_input(self, user_input: str, project: ProjectData) -> str:
        """
        Process user input for suggestion selection and record the interaction.
        
        Args:
            user_input: Raw user input
            project: Current project data
            
        Returns:
            Processed message to send
        """
        # Check if input is a number selecting from the list
        selected_suggestion = self._check_for_suggestion_selection(user_input)
        if selected_suggestion:
            return self._handle_suggestion_selection(selected_suggestion, project)
        
        # Handle project name input
        if self._is_project_name_selection():
            self._handle_project_name_update(user_input, project)
        
        # Record as custom input
        self.interaction_recorder.record_response(
            project=project,
            interaction_index=self.interaction_recorder.get_latest_index(project),
            custom_input=user_input,
            is_custom=True
        )
        return user_input
    
    def _check_for_suggestion_selection(self, user_input: str) -> Optional[SuggestionItem]:
        """
        Check if the input is selecting a suggestion by number.
        
        Args:
            user_input: Raw user input
            
        Returns:
            Selected suggestion or None
        """
        try:
            selection_idx = int(user_input) - 1
            if 0 <= selection_idx < len(self.tool_manager.current_suggestions):
                return self.tool_manager.current_suggestions[selection_idx]
        except ValueError:
            pass
        return None
    
    def _handle_suggestion_selection(self, 
                                   suggestion: SuggestionItem, 
                                   project: ProjectData) -> str:
        """
        Handle when user selects a suggestion.
        
        Args:
            suggestion: The selected suggestion
            project: Current project data
            
        Returns:
            Text to send to assistant
        """
        logger.debug(f"Selected suggestion: {suggestion.text}")
        print(f"[Selected: {suggestion.text}]")
        
        # Record the selection
        self.interaction_recorder.record_response(
            project=project,
            interaction_index=self.interaction_recorder.get_latest_index(project),
            selection_text=suggestion.text,
            selection_id=suggestion.id,
            is_custom=False
        )
        
        # Handle project name selection
        if self._is_project_name_selection():
            project_name = suggestion.text.strip('"\'')
            self._handle_project_name_update(project_name, project)
        
        return suggestion.text
    
    def _is_project_name_selection(self) -> bool:
        """Check if the current interaction is for project name selection."""
        return (self.tool_manager and 
                self.tool_manager.current_suggestion_category == "project_name")
    
    def _handle_project_name_update(self, name: str, project: ProjectData) -> None:
        """
        Update project name if this is a project name selection.
        
        Args:
            name: New project name
            project: Current project data
        """
        # This method is expected to be overridden by ProjectManager
        # through dependency injection or by using an event/callback pattern
        pass