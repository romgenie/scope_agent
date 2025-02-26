# managers/interaction_recorder.py
import logging
from typing import List, Dict, Any, Optional, Union

from models.project import ProjectData
from models.interaction import InteractionRecord
from models.suggestions import SuggestionItem

# Configure logger
logger = logging.getLogger(__name__)

class InteractionRecorder:
    """Records and manages interaction history."""
    
    def __init__(self):
        """Initialize the interaction recorder."""
        self.latest_indices = {}  # Maps project names to latest interaction indices
    
    def record_question(self, 
                      project: ProjectData, 
                      question: str, 
                      category: Optional[str] = None,
                      suggestions: List[SuggestionItem] = None) -> int:
        """
        Record a question asked by the assistant.
        
        Args:
            project: Current project data
            question: The question asked
            category: Question category (e.g., "objective", "timeline")
            suggestions: List of suggestions provided
            
        Returns:
            Index of the recorded interaction
        """
        if not project or not project.interaction_history:
            logger.warning("Cannot record question: No valid project or interaction history")
            return -1
        
        try:
            # Create a new interaction record
            interaction = InteractionRecord(
                question=question,
                category=category,
                suggestions=suggestions or []
            )
            
            # Add to history
            interaction_index = project.interaction_history.add_interaction(interaction)
            
            # Store latest index for this project
            self.latest_indices[project.name] = interaction_index
            
            logger.debug(f"Recorded question in category '{category}': {question}")
            return interaction_index
        except Exception as e:
            logger.error(f"Error recording question: {e}")
            return -1
    
    def record_response(self, 
                      project: ProjectData,
                      interaction_index: int,
                      selection_text: Optional[str] = None, 
                      selection_id: Optional[str] = None,
                      custom_input: Optional[str] = None,
                      is_custom: bool = False) -> bool:
        """
        Record a user's response to a question.
        
        Args:
            project: Current project data
            interaction_index: Index of the interaction to update
            selection_text: Text of selected suggestion
            selection_id: ID of selected suggestion
            custom_input: Custom user input if not selecting from suggestions
            is_custom: Flag indicating if response was custom input
            
        Returns:
            True if recording succeeded, False otherwise
        """
        if not project or not project.interaction_history:
            logger.warning("Cannot record response: No valid project or interaction history")
            return False
        
        try:
            # Update the interaction at the given index
            updated = project.interaction_history.update_interaction(
                interaction_index,
                selection=selection_text,
                selection_id=selection_id,
                custom_input=custom_input,
                is_custom=is_custom
            )
            
            if updated:
                logger.debug(f"Recorded response to interaction {interaction_index}")
                return True
            else:
                logger.warning(f"Failed to update interaction at index {interaction_index}")
                return False
        except Exception as e:
            logger.error(f"Error recording response: {e}")
            return False
    
    def get_latest_index(self, project: ProjectData) -> int:
        """
        Get the index of the latest interaction for a project.
        
        Args:
            project: Current project data
            
        Returns:
            Latest interaction index or -1 if none exists
        """
        return self.latest_indices.get(project.name, -1)
    
    def get_interaction_summary(self, project: ProjectData) -> str:
        """
        Get a summary of interactions for a project.
        
        Args:
            project: Current project data
            
        Returns:
            Human-readable summary of interactions
        """
        if not project or not project.interaction_history:
            return "No interaction history available."
        
        return project.interaction_history.get_summary()