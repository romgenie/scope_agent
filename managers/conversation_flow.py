# managers/conversation_flow.py
import logging
from typing import Optional, Dict, Any

from models.project import ProjectData
from models.suggestions import SuggestionItem
from managers.assistant_manager import AssistantManager
from managers.interaction_recorder import InteractionRecorder
from utils.event_bus import EventBus

logger = logging.getLogger(__name__)

class ConversationFlow:
    """
    Manages the flow of conversation between user and assistant.
    
    Handles message processing, suggestion selection, and conversation state.
    """
    
    def __init__(
        self,
        assistant_manager: AssistantManager,
        tool_coordinator: Any,  # Avoid circular import
        interaction_recorder: InteractionRecorder,
        event_bus: Optional[EventBus] = None
    ):
        """
        Initialize the conversation flow manager.
        
        Args:
            assistant_manager: Manager for assistant interactions
            tool_coordinator: Coordinator for tool interactions
            interaction_recorder: Recorder for interaction history
            event_bus: Optional event bus for publishing events
        """
        self.assistant_manager = assistant_manager
        self.tool_coordinator = tool_coordinator
        self.interaction_recorder = interaction_recorder
        self.event_bus = event_bus
        
        # Setup assistant manager callbacks
        self.assistant_manager.on_message_received = self._on_assistant_message
        self.assistant_manager.on_run_completed = self._on_run_completed
    
    def start_conversation(self, project: ProjectData) -> None:
        """
        Start or continue a conversation for the given project.
        
        Args:
            project: The project to converse about
        """
        if not project:
            logger.error("Cannot start conversation: No project provided")
            return
        
        logger.info(f"Starting conversation for project: {project.name}")
        
        try:
            # Cancel any active runs before starting
            self.assistant_manager.cancel_active_runs()
            
            if self._is_continuing_project(project):
                self._continue_existing_project(project)
            else:
                self._start_new_project(project)
                
            # Publish event if event bus exists
            if self.event_bus:
                self.event_bus.publish("conversation_started", project)
        except Exception as e:
            logger.error(f"Error starting conversation: {e}")
            print(f"Error starting conversation: {e}")
    
    def process_message(self, message: str, project: ProjectData) -> None:
        """
        Process a user message, handling suggestion selections.
        
        Args:
            message: The user's message
            project: The current project
        """
        logger.debug(f"Processing message: {message}")
        
        if not project:
            logger.error("Cannot process message: No project provided")
            return
        
        try:
            # Process potential suggestion selection
            processed_message = self._process_suggestion_input(message, project)
            
            # Send to assistant
            if not self.assistant_manager.send_message(processed_message):
                # Try recovery by cancelling runs
                logger.warning("Send failed. Attempting recovery by cancelling runs.")
                self.assistant_manager.cancel_active_runs()
                
                if not self.assistant_manager.send_message(processed_message):
                    logger.error("Failed to send message even after recovery attempt")
                    print("Failed to send message. Please try again.")
                    return
            
            # Clear suggestions after sending
            self.tool_coordinator.clear_suggestions()
            
            # Publish event if event bus exists
            if self.event_bus:
                self.event_bus.publish("message_sent", {
                    "project": project,
                    "message": processed_message
                })
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            print(f"Error processing your message: {e}")
    
    def _is_continuing_project(self, project: ProjectData) -> bool:
        """
        Check if we're continuing an existing project conversation.
        
        Args:
            project: The project to check
            
        Returns:
            True if continuing an existing project, False otherwise
        """
        return (project.stage in ['scoping', 'complete'] and project.name)
    
    def _continue_existing_project(self, project: ProjectData) -> None:
        """
        Continue an existing project conversation.
        
        Args:
            project: The project to continue
        """
        logger.info(f"Continuing project: {project.name}")
        print(f"Continuing project: {project.name}")
        
        content = f"We're continuing work on the project named '{project.name}'. Please continue from where we left off in the scoping process."
        self._send_initial_message(content)
    
    def _start_new_project(self, project: ProjectData) -> None:
        """
        Start a new project conversation.
        
        Args:
            project: The new project
        """
        description = project.description if project.description else "No description provided."
        logger.info(f"Starting new project with description: {description}")
        
        content = f"I need help scoping a new project. Here's a description of my project idea: {description}"
        self._send_initial_message(content)
    
    def _send_initial_message(self, content: str) -> None:
        """
        Send the initial message to the assistant, handling failures.
        
        Args:
            content: The message content
        """
        if not self.assistant_manager.send_message(content):
            logger.warning("Error sending message. Creating a new thread.")
            print("Error sending message. Creating a new thread.")
            
            # Create new thread and try again
            thread_id = self.assistant_manager.create_thread()
            
            # Publish thread created event
            if self.event_bus:
                self.event_bus.publish("thread_created", thread_id)
            
            if not self.assistant_manager.send_message(content):
                logger.error("Failed to send initial message after retry")
                print("Failed to send initial message. Please try again.")
    
    def _process_suggestion_input(self, user_input: str, project: ProjectData) -> str:
        """
        Process user input for suggestion selection.
        
        Args:
            user_input: Raw user input
            project: Current project
            
        Returns:
            Processed message ready to send to assistant
        """
        # Get current suggestions from tool coordinator
        current_suggestions = self.tool_coordinator.get_current_suggestions()
        current_category = self.tool_coordinator.get_current_category()
        
        if not current_suggestions:
            # Record as custom input with no suggestions
            self.interaction_recorder.record_response(
                project=project,
                interaction_index=self.interaction_recorder.get_latest_index(project),
                custom_input=user_input,
                is_custom=True
            )
            return user_input
        
        # Check if input is a number selecting from the list
        selected_suggestion = self._check_for_suggestion_selection(user_input, current_suggestions)
        if selected_suggestion:
            return self._handle_suggestion_selection(selected_suggestion, project, current_category)
        
        # Handle project name input
        if current_category == "project_name":
            self._publish_project_name_update(user_input, project)
        
        # Record as custom input
        self.interaction_recorder.record_response(
            project=project,
            interaction_index=self.interaction_recorder.get_latest_index(project),
            custom_input=user_input,
            is_custom=True
        )
        return user_input
    
    def _check_for_suggestion_selection(self, user_input: str, suggestions: list) -> Optional[SuggestionItem]:
        """
        Check if the user input is selecting a suggestion by number.
        
        Args:
            user_input: Raw user input
            suggestions: List of available suggestions
            
        Returns:
            Selected suggestion or None
        """
        try:
            selection_idx = int(user_input) - 1
            if 0 <= selection_idx < len(suggestions):
                return suggestions[selection_idx]
        except ValueError:
            pass
        return None
    
    def _handle_suggestion_selection(self, suggestion: SuggestionItem, project: ProjectData, category: str) -> str:
        """
        Handle when user selects a suggestion.
        
        Args:
            suggestion: The selected suggestion
            project: Current project
            category: The suggestion category
            
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
        if category == "project_name":
            project_name = suggestion.text.strip('"\'')
            self._publish_project_name_update(project_name, project)
        
        return suggestion.text
    
    def _publish_project_name_update(self, name: str, project: ProjectData) -> None:
        """
        Publish project name update event.
        
        Args:
            name: New project name
            project: Current project
        """
        if self.event_bus:
            self.event_bus.publish("project_name_selected", {
                "name": name,
                "project": project
            })
    
    def _on_assistant_message(self, message: str) -> None:
        """
        Handle message received from the assistant.
        
        Args:
            message: Assistant's message content
        """
        if self.event_bus:
            self.event_bus.publish("assistant_message", message)
        
        # Extract question
        question = self._extract_assistant_question(message)
        
        # Get current category from tool coordinator
        current_category = self.tool_coordinator.get_current_category()
        current_suggestions = self.tool_coordinator.get_current_suggestions()
        
        # Get the current project via event
        if self.event_bus:
            self.event_bus.publish("get_current_project", None)
            # The project will be provided via callback
    
    def set_current_project(self, project: ProjectData) -> None:
        """
        Set the current project (callback from event_bus).
        
        Args:
            project: Current project
        """
        if not project:
            return
            
        # Extract question from last assistant message
        last_message = self._get_last_assistant_message()
        if last_message:
            question = self._extract_assistant_question(last_message)
            current_category = self.tool_coordinator.get_current_category()
            current_suggestions = self.tool_coordinator.get_current_suggestions()
            
            # Record the question
            self.interaction_recorder.record_question(
                project,
                question,
                current_category,
                current_suggestions
            )
    
    def _get_last_assistant_message(self) -> Optional[str]:
        """
        Get the last message from the assistant.
        
        Returns:
            The last message content or None
        """
        # This is a stub - in a real implementation, we would get
        # the last message from the assistant's message history
        return None
    
    def _extract_assistant_question(self, message: str) -> str:
        """
        Extract the main question from an assistant message.
        
        Args:
            message: Assistant's full message
            
        Returns:
            Extracted question or the last sentence
        """
        # Simple extraction - get the last sentence ending with a question mark
        sentences = message.split('.')
        questions = [s.strip() + '.' for s in sentences if '?' in s]
        
        if questions:
            return questions[-1]  # Return the last question
        
        # If no question mark, just return the last sentence
        if sentences:
            return sentences[-1].strip() + '.'
        
        return message  # Fallback
    
    def _on_run_completed(self, run: Any) -> None:
        """
        Handle when an assistant run is completed.
        
        Args:
            run: Run object from Assistant API
        """
        if self.event_bus:
            self.event_bus.publish("run_completed", run)