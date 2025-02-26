# managers/project_manager.py
import logging
import sys
import signal
from typing import Any, Optional

from openai import OpenAI

from utils.event_bus import EventBus
from managers.data_manager import DataManager
from managers.ui_manager import UIManager
from managers.assistant_manager import AssistantManager
from managers.project_lifecycle_manager import ProjectLifecycleManager
from managers.conversation_flow import ConversationFlow
from managers.tool_coordinator import ToolCoordinator
from managers.ui_coordinator import UICoordinator
from managers.interaction_recorder import InteractionRecorder

# Configure logger
logger = logging.getLogger(__name__)

class ProjectManager:
    """
    Orchestrates the overall project workflow by coordinating specialized managers.
    
    This class has been refactored to act as a high-level coordinator that delegates
    specific responsibilities to specialized manager classes.
    """
    
    def __init__(
        self, 
        api_client: OpenAI, 
        ui_manager: UIManager, 
        data_manager: DataManager
    ):
        """
        Initialize the project manager with required components.
        
        Args:
            api_client: API client for OpenAI
            ui_manager: Manager for UI interactions
            data_manager: Manager for data persistence
        """
        # Create event bus for communication between components
        self.event_bus = EventBus()
        
        # Set up signal handler for Ctrl+C
        signal.signal(signal.SIGINT, self._signal_handler)
        
        # Create core managers
        self.assistant_manager = AssistantManager(api_client)
        self.interaction_recorder = InteractionRecorder()
        self.lifecycle_manager = ProjectLifecycleManager(data_manager, self.event_bus)
        
        # Create specialized coordinators
        self.tool_coordinator = ToolCoordinator(api_client, self.event_bus)
        self.ui_coordinator = UICoordinator(ui_manager, self.event_bus)
        self.conversation_flow = ConversationFlow(
            self.assistant_manager,
            self.tool_coordinator,
            self.interaction_recorder,
            self.event_bus
        )
        
        # Set up event listeners
        self._setup_event_listeners()
        
        # Store main components for access
        self.api_client = api_client
        self.ui_manager = ui_manager
        self.data_manager = data_manager
    
    def _signal_handler(self, sig, frame) -> None:
        """Handle keyboard interrupts gracefully."""
        logger.info("Keyboard interrupt detected")
        print("\n\nKeyboard interrupt detected. Cleaning up...")
        self.cleanup()
        print("Exiting...")
        sys.exit(0)
    
    def _setup_event_listeners(self) -> None:
        """Set up event listeners for inter-component communication."""
        # Project lifecycle events
        self.event_bus.register("project_created", self._on_project_created)
        self.event_bus.register("project_loaded", self._on_project_loaded)
        self.event_bus.register("project_saved", self._on_project_saved)
        self.event_bus.register("project_updated", self._on_project_updated)
        
        # Project selection events
        self.event_bus.register("new_project_requested", self._on_new_project_requested)
        self.event_bus.register("project_file_selected", self._on_project_file_selected)
        self.event_bus.register("project_name_selected", self._on_project_name_selected)
        
        # Conversation events
        self.event_bus.register("message_sent", self._on_message_sent)
        self.event_bus.register("assistant_message", self._on_assistant_message)
        self.event_bus.register("run_completed", self._on_run_completed)
        
        # Tool events
        self.event_bus.register("thread_created", self._on_thread_created)
        self.event_bus.register("suggestions_generated", self._on_suggestions_generated)
        self.event_bus.register("project_names_generated", self._on_project_names_generated)
        self.event_bus.register("scope_saved", self._on_scope_saved)
        
        # UI events
        self.event_bus.register("user_input", self._on_user_input)
        self.event_bus.register("exit_requested", self._on_exit_requested)
        
        # Current project request
        self.event_bus.register("get_current_project", self._on_get_current_project)
    
    def initialize(self) -> None:
        """Initialize the application and present project selection."""
        logger.info("Initializing Project Manager")
        
        try:
            # Display welcome message
            self.ui_coordinator.display_welcome()
            
            # Load and display projects list
            projects = self.data_manager.load_projects_list()
            self.ui_coordinator.display_projects_list(projects)
            
            # Let UI coordinator handle project selection
            self.ui_coordinator.handle_project_selection(projects)
            
            # Interactive loop is started by project selection
        except Exception as e:
            logger.error(f"Error initializing project manager: {e}")
            print(f"An error occurred during initialization: {e}")
    
    def cleanup(self) -> None:
        """Clean up resources before exiting."""
        logger.info("Cleaning up resources")
        
        try:
            # Save current project if one exists
            if self.lifecycle_manager.get_current_project():
                self.lifecycle_manager.save_project()
                
            print("\nProject saved. Assistant will be reused in future sessions.")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    # -------------------------------------------------------------------------
    # Project Lifecycle Event Handlers
    # -------------------------------------------------------------------------
    
    def _on_project_created(self, project) -> None:
        """
        Handle project created event.
        
        Args:
            project: The created project
        """
        self.ui_coordinator.update_current_project(project)
        
        # Set up assistant
        assistant_id = self.assistant_manager.create_assistant(
            name="Project Scoping Assistant",
            instructions=self._get_assistant_instructions(),
            tools=self.tool_coordinator.tool_definitions,
            model="gpt-4o"
        )
        
        # Update project
        if assistant_id:
            self.lifecycle_manager.update_project_metadata("assistant_id", assistant_id)
        
        # Create thread
        thread_id = self.assistant_manager.create_thread()
        if thread_id:
            self.lifecycle_manager.update_project_metadata("thread_id", thread_id)
            self.tool_coordinator.set_thread_id(thread_id)
        
        # Start conversation
        self.conversation_flow.start_conversation(project)
        
        # Start interactive loop
        self.ui_coordinator.handle_user_input()
    
    def _on_project_loaded(self, project) -> None:
        """
        Handle project loaded event.
        
        Args:
            project: The loaded project
        """
        self.ui_coordinator.update_current_project(project)
        self.ui_coordinator.display_project_info(project)
        
        # Set up assistant with existing ID if available
        if project.assistant_id:
            if not self.assistant_manager.get_assistant(project.assistant_id):
                logger.warning("Could not retrieve existing assistant. Creating a new one.")
                print("Could not retrieve existing assistant. Creating a new one.")
                
                assistant_id = self.assistant_manager.create_assistant(
                    name="Project Scoping Assistant",
                    instructions=self._get_assistant_instructions(),
                    tools=self.tool_coordinator.tool_definitions,
                    model="gpt-4o"
                )
                
                if assistant_id:
                    self.lifecycle_manager.update_project_metadata("assistant_id", assistant_id)
        else:
            assistant_id = self.assistant_manager.create_assistant(
                name="Project Scoping Assistant",
                instructions=self._get_assistant_instructions(),
                tools=self.tool_coordinator.tool_definitions,
                model="gpt-4o"
            )
            
            if assistant_id:
                self.lifecycle_manager.update_project_metadata("assistant_id", assistant_id)
        
        # Set up thread
        if project.thread_id:
            if not self.assistant_manager.get_thread(project.thread_id):
                logger.warning("Could not retrieve existing thread. Creating a new one.")
                print("Could not retrieve existing thread. Creating a new one.")
                
                thread_id = self.assistant_manager.create_thread()
                if thread_id:
                    self.lifecycle_manager.update_project_metadata("thread_id", thread_id)
                    self.tool_coordinator.set_thread_id(thread_id)
        else:
            thread_id = self.assistant_manager.create_thread()
            if thread_id:
                self.lifecycle_manager.update_project_metadata("thread_id", thread_id)
                self.tool_coordinator.set_thread_id(thread_id)
        
        # Initialize tools
        self.tool_coordinator.initialize_tools(project.thread_id)
        
        # Cancel any active runs
        self.assistant_manager.cancel_active_runs()
        
        # Start conversation
        self.conversation_flow.start_conversation(project)
        
        # Start interactive loop
        self.ui_coordinator.handle_user_input()
    
    def _on_project_saved(self, project) -> None:
        """
        Handle project saved event.
        
        Args:
            project: The saved project
        """
        logger.debug("Project saved successfully")
    
    def _on_project_updated(self, update_data) -> None:
        """
        Handle project updated event.
        
        Args:
            update_data: Dictionary with project and updated field
        """
        project = update_data["project"]
        updated_field = update_data["updated_field"]
        
        logger.debug(f"Project updated: {updated_field}")
        
        # Handle specific updates
        if updated_field == "name":
            print(f"\n[System] Project name updated to: '{project.name}'")
        elif updated_field == "stage" and project.stage == "complete":
            print(f"\n[System] Project marked as complete")
    
    # -------------------------------------------------------------------------
    # Project Selection Event Handlers
    # -------------------------------------------------------------------------
    
    def _on_new_project_requested(self, description) -> None:
        """
        Handle new project requested event.
        
        Args:
            description: Description of the new project
        """
        self.lifecycle_manager.create_new_project(description)
    
    def _on_project_file_selected(self, file_path) -> None:
        """
        Handle project file selected event.
        
        Args:
            file_path: Path to the selected project file
        """
        self.lifecycle_manager.load_project(file_path)
    
    def _on_project_name_selected(self, name_data) -> None:
        """
        Handle project name selected event.
        
        Args:
            name_data: Dictionary with name and project
        """
        name = name_data["name"]
        project = name_data["project"]
        
        self.lifecycle_manager.update_project_metadata("name", name)
        self.lifecycle_manager.update_project_metadata("stage", "scoping")
    
    # -------------------------------------------------------------------------
    # Conversation Event Handlers
    # -------------------------------------------------------------------------
    
    def _on_message_sent(self, message_data) -> None:
        """
        Handle message sent event.
        
        Args:
            message_data: Dictionary with message and project
        """
        # Save project after message sent
        self.lifecycle_manager.save_project()
        
        # Run the assistant
        self.assistant_manager.run_assistant(self.tool_coordinator.handle_required_actions)
    
    def _on_assistant_message(self, message) -> None:
        """
        Handle assistant message event.
        
        Args:
            message: The assistant's message
        """
        # Update current project with assistant message
        project = self.lifecycle_manager.get_current_project()
        if project:
            # Conversation flow will handle recording the question
            self.conversation_flow.set_current_project(project)
            
            # Save project after receiving message
            self.lifecycle_manager.save_project()
    
    def _on_run_completed(self, run) -> None:
        """
        Handle run completed event.
        
        Args:
            run: The completed run
        """
        logger.debug(f"Run completed: {run.id}")
    
    # -------------------------------------------------------------------------
    # Tool Event Handlers
    # -------------------------------------------------------------------------
    
    def _on_thread_created(self, thread_id) -> None:
        """
        Handle thread created event.
        
        Args:
            thread_id: The created thread ID
        """
        project = self.lifecycle_manager.get_current_project()
        if project:
            self.lifecycle_manager.update_project_metadata("thread_id", thread_id)
            self.tool_coordinator.set_thread_id(thread_id)
    
    def _on_suggestions_generated(self, suggestion_data) -> None:
        """
        Handle suggestions generated event.
        
        Args:
            suggestion_data: Dictionary with suggestions and category
        """
        suggestions = suggestion_data["suggestions"]
        category = suggestion_data["category"]
        allow_custom = suggestion_data.get("allow_custom", True)
        
        self.ui_coordinator.display_suggestions(suggestions, category, allow_custom)
    
    def _on_project_names_generated(self, name_data) -> None:
        """
        Handle project names generated event.
        
        Args:
            name_data: Dictionary with suggestions
        """
        suggestions = name_data["suggestions"]
        allow_custom = name_data.get("allow_custom", True)
        
        self.ui_coordinator.display_suggestions(suggestions, "project_name", allow_custom)
    
    def _on_scope_saved(self, scope_data) -> None:
        """
        Handle scope saved event.
        
        Args:
            scope_data: The saved scope data
        """
        project = self.lifecycle_manager.get_current_project()
        if project:
            self.lifecycle_manager.update_project_metadata("scope", scope_data)
            self.lifecycle_manager.update_project_metadata("stage", "complete")
            self.lifecycle_manager.save_project()
    
    # -------------------------------------------------------------------------
    # UI Event Handlers
    # -------------------------------------------------------------------------
    
    def _on_user_input(self, input_data) -> None:
        """
        Handle user input event.
        
        Args:
            input_data: Dictionary with message and project
        """
        message = input_data["message"]
        project = input_data["project"]
        
        if not message or not project:
            return
            
        self.conversation_flow.process_message(message, project)
    
    def _on_exit_requested(self, _) -> None:
        """
        Handle exit requested event.
        
        Args:
            _: Unused parameter
        """
        self.cleanup()
    
    def _on_get_current_project(self, _) -> None:
        """
        Handle get current project event.
        
        Args:
            _: Unused parameter
        """
        project = self.lifecycle_manager.get_current_project()
        if project and self.conversation_flow:
            self.conversation_flow.set_current_project(project)
    
    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------
    
    def _get_assistant_instructions(self) -> str:
        """
        Get the instructions for the assistant.
        
        Returns:
            Instructions string
        """
        return """
        You are a project scoping specialist who helps users define and plan their projects through a 
        guided, step-by-step conversation. Follow this specific conversational flow:

        1. INITIAL STAGE: The user will provide their project description in the first message. Don't
        acknowledge the description separately - immediately proceed to the naming stage.

        2. NAMING STAGE: After receiving the project description, in your VERY FIRST response, call 
        the generate_project_names tool with the description. Do not send any separate acknowledgment 
        message before generating names.
        
        3. SCOPING STAGE: After the user selects or provides a project name, begin the detailed scoping process 
        by asking ONE question at a time about different aspects of the project:
        - Ask a focused question
        - IMMEDIATELY call the generate_suggestions tool to provide options
        - Wait for the user's response before asking the next question
        
        IMPORTANT TIMING GUIDELINES:
        - Call tools IMMEDIATELY after receiving relevant user information - don't delay
        - Use generate_project_names immediately in your first response after receiving the initial project description
        - Use generate_suggestions immediately after asking each scoping question
        - Use save_scope at the end of the conversation to save all gathered information
        
        Cover these key areas during the scoping stage (one question at a time):
        - Project objectives and specific goals
        - Target audience or users
        - Key deliverables
        - Timeline and milestones
        - Budget and resources
        - Potential risks and challenges
        - Success metrics
        
        IMPORTANT: If the user asks to "save progress" or "save our progress", DO NOT attempt to generate a final 
        scope document. Instead, acknowledge their request and confirm that progress is automatically saved after 
        each interaction. Let them know they can continue the conversation later by selecting the same project.
        
        When the user has answered all the key questions, offer to generate a project scope document by 
        using the save_scope tool. This should be done proactively rather than waiting for the user to request it.
        
        Maintain a helpful, professional tone throughout the conversation.
        """