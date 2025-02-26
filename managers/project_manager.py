# managers/project_manager.py
import logging
from typing import List, Dict, Any, Optional, Callable, Union, Type

from models.project import ProjectData
from models.interaction import InteractionRecord
from models.suggestions import SuggestionItem

from managers.assistant_manager import AssistantManager
from managers.data_manager import DataManager
from managers.tool_manager import ToolManager
from managers.ui_manager import UIManager
from managers.conversation_manager import ConversationManager
from managers.interaction_recorder import InteractionRecorder

# Configure logger
logger = logging.getLogger(__name__)

class ProjectManager:
    """Orchestrates the overall project workflow and manages component interactions."""
    
    def __init__(
        self, 
        api_client: Any, 
        ui_manager: UIManager, 
        data_manager: DataManager,
        assistant_manager: Optional[AssistantManager] = None,
        conversation_manager: Optional[ConversationManager] = None,
        interaction_recorder: Optional[InteractionRecorder] = None
    ):
        """
        Initialize the project manager with required components.
        
        Args:
            api_client: API client for OpenAI
            ui_manager: Manager for UI interactions
            data_manager: Manager for data persistence
            assistant_manager: Optional manager for assistant interactions (created if None)
            conversation_manager: Optional manager for conversation flow (created if None)
            interaction_recorder: Optional recorder for interactions (created if None)
        """
        # Core dependencies
        self.api_client = api_client
        self.ui_manager = ui_manager
        self.data_manager = data_manager
        
        # Create or use provided components
        self.assistant_manager = assistant_manager or AssistantManager(api_client)
        self.tool_manager = None
        
        # State tracking
        self.current_project: Optional[ProjectData] = None
        
        # Set up specialized components
        self.interaction_recorder = interaction_recorder or InteractionRecorder()
        self._setup_conversation_manager(conversation_manager)
        
        # Set up UI callbacks
        self._setup_callbacks()
    
    # -------------------------------------------------------------------------
    # INITIALIZATION AND SETUP
    # -------------------------------------------------------------------------
    
    def _setup_conversation_manager(self, conversation_manager: Optional[ConversationManager]) -> None:
        """Set up the conversation manager component."""
        if conversation_manager:
            self.conversation_manager = conversation_manager
        else:
            # Will be fully initialized after tool_manager is created
            self.conversation_manager = ConversationManager(
                assistant_manager=self.assistant_manager,
                tool_manager=None,
                interaction_recorder=self.interaction_recorder
            )
    
    def _setup_callbacks(self) -> None:
        """Set up callbacks for all components."""
        # Set up UI callbacks
        self.ui_manager.on_project_selected = self.load_project
        self.ui_manager.on_new_project = self.create_new_project
        self.ui_manager.on_message_sent = self.send_message
        self.ui_manager.on_exit = self.cleanup
        
        # Set up assistant manager callbacks
        self.assistant_manager.on_message_received = self.handle_assistant_message
        self.assistant_manager.on_run_completed = self.handle_run_completed
    
    def initialize(self) -> None:
        """Initialize the application and present project selection."""
        logger.info("Initializing Project Manager")
        self.ui_manager.display_welcome()
        
        try:
            projects = self.data_manager.load_projects_list()
            self.ui_manager.display_projects_list(projects)
            self.ui_manager.select_project_prompt(projects)
            
            if self.current_project:
                self.start_conversation()
        except Exception as e:
            logger.error(f"Error initializing project manager: {e}")
            print(f"An error occurred during initialization: {e}")
    
    # -------------------------------------------------------------------------
    # PROJECT LIFECYCLE
    # -------------------------------------------------------------------------
    
    def create_new_project(self, description: str) -> None:
        """
        Create a new project with the given description.
        
        Args:
            description: User-provided project description
        """
        from datetime import datetime
        
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
            
            # Update UI manager with current project
            self.ui_manager.current_project = self.current_project
            
            # Set up assistant and start conversation
            self.setup_assistant()
            self.start_conversation()
        except Exception as e:
            logger.error(f"Error creating new project: {e}")
            print(f"An error occurred while creating the project: {e}")
    
    def load_project(self, file_path: str) -> None:
        """
        Load an existing project from file.
        
        Args:
            file_path: Path to the project file
        """
        try:
            logger.info(f"Loading project from: {file_path}")
            project_data = self.data_manager.load_project(file_path)
            
            if not project_data:
                logger.warning("Failed to load project. Creating a new one instead.")
                print("Error loading project. Creating a new one instead.")
                self.create_new_project("No description provided.")
                return
            
            self.current_project = project_data
            self.ui_manager.current_project = project_data
            self.ui_manager.display_project_info(project_data)
            
            self._setup_project_components()
            self.save_project()  # Save to ensure all IDs are updated
        except Exception as e:
            logger.error(f"Error loading project: {e}")
            print(f"An error occurred while loading the project: {e}")
    
    def _setup_project_components(self) -> None:
        """Set up assistant and thread for an existing project."""
        # Set up assistant with existing ID if available
        if self.current_project.assistant_id:
            if not self.assistant_manager.get_assistant(self.current_project.assistant_id):
                logger.warning("Could not retrieve existing assistant. Creating a new one.")
                print("Could not retrieve existing assistant. Creating a new one.")
                self.setup_assistant()
        else:
            self.setup_assistant()
        
        # Set up thread
        if self.current_project.thread_id:
            if not self.assistant_manager.get_thread(self.current_project.thread_id):
                logger.warning("Could not retrieve existing thread. Creating a new one.")
                print("Could not retrieve existing thread. Creating a new one.")
                thread_id = self.assistant_manager.create_thread()
                self.current_project.thread_id = thread_id
        else:
            thread_id = self.assistant_manager.create_thread()
            self.current_project.thread_id = thread_id
        
        # Initialize tool manager with thread
        self.initialize_tool_manager()
        
        # Cancel any active runs
        self.assistant_manager.cancel_active_runs()
    
    def save_project(self) -> None:
        """Save current project data to file."""
        if not self.current_project:
            logger.warning("Attempted to save project, but no project is active")
            return
        
        try:
            logger.debug("Saving project")
            # Update IDs from managers
            if self.assistant_manager.assistant:
                self.current_project.assistant_id = self.assistant_manager.assistant.id
            
            if self.assistant_manager.thread_id:
                self.current_project.thread_id = self.assistant_manager.thread_id
            
            # Save to file
            file_path = self.data_manager.save_project(self.current_project)
            if file_path:
                logger.debug(f"Project saved to {file_path}")
            else:
                logger.error("Failed to save project")
        except Exception as e:
            logger.error(f"Error saving project: {e}")
            print(f"Error saving project: {e}")
    
    def cleanup(self) -> None:
        """Clean up resources before exiting."""
        try:
            logger.info("Cleaning up resources")
            if self.current_project:
                self.save_project()
            print("\nProject saved. Assistant will be reused in future sessions.")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    # -------------------------------------------------------------------------
    # ASSISTANT MANAGEMENT
    # -------------------------------------------------------------------------
    
    def setup_assistant(self) -> None:
        """Set up the assistant with appropriate instructions and tools."""
        logger.info("Setting up assistant")
        
        instructions = """
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
        
        try:
            # Create thread if needed
            if not self.assistant_manager.thread_id:
                thread_id = self.assistant_manager.create_thread()
                if self.current_project:
                    self.current_project.thread_id = thread_id
            
            # Initialize tool manager
            self.initialize_tool_manager()
            
            # Create assistant
            assistant_id = self.assistant_manager.create_assistant(
                name="Project Scoping Assistant",
                instructions=instructions,
                tools=self.tool_manager.tool_definitions,
                model="gpt-4o"
            )
            
            if self.current_project:
                self.current_project.assistant_id = assistant_id
        except Exception as e:
            logger.error(f"Error setting up assistant: {e}")
            print(f"Error setting up assistant: {e}")
    
    def initialize_tool_manager(self) -> None:
        """Initialize the tool manager and set up callbacks."""
        logger.info("Initializing tool manager")
        
        if not self.assistant_manager.thread_id:
            logger.error("Thread ID not available for tool manager")
            print("Error: Thread ID not available for tool manager.")
            return
        
        try:
            self.tool_manager = ToolManager(
                self.api_client,
                self.assistant_manager.thread_id
            )
            
            # Set up callbacks
            self.tool_manager.on_scope_saved = self.handle_scope_saved
            self.tool_manager.on_suggestions_generated = self.handle_suggestions_generated
            self.tool_manager.on_project_names_generated = self.handle_project_names_generated
            
            # Update conversation manager with tool manager
            self.conversation_manager.tool_manager = self.tool_manager
        except Exception as e:
            logger.error(f"Error initializing tool manager: {e}")
            print(f"Error initializing tool manager: {e}")
    
    # -------------------------------------------------------------------------
    # CONVERSATION HANDLING
    # -------------------------------------------------------------------------
    
    def start_conversation(self) -> None:
        """Start or continue the project scoping conversation."""
        if not self.current_project:
            logger.error("Cannot start conversation: No active project")
            print("Error: No active project.")
            return
        
        logger.info("Starting project scoping conversation")
        print("\n--- Project Scoping Conversation Started ---")
        
        try:
            # Cancel any active runs before starting
            self.assistant_manager.cancel_active_runs()
            
            if self._is_continuing_project():
                self._continue_existing_project()
            else:
                self._start_new_project()
            
            # Start interactive loop
            self.interactive_loop()
        except Exception as e:
            logger.error(f"Error starting conversation: {e}")
            print(f"Error starting conversation: {e}")
    
    def _is_continuing_project(self) -> bool:
        """Check if we're continuing an existing project."""
        return (self.current_project.stage in ['scoping', 'complete'] and 
                self.current_project.name)
    
    def _continue_existing_project(self) -> None:
        """Continue an existing project conversation."""
        logger.info(f"Continuing project: {self.current_project.name}")
        print(f"Continuing project: {self.current_project.name}")
        
        content = f"We're continuing work on the project named '{self.current_project.name}'. Please continue from where we left off in the scoping process."
        self._send_initial_message(content)
    
    def _start_new_project(self) -> None:
        """Start a new project conversation."""
        description = self.current_project.description if self.current_project.description else "No description provided."
        logger.info(f"Starting new project with description: {description}")
        
        content = f"I need help scoping a new project. Here's a description of my project idea: {description}"
        self._send_initial_message(content)
    
    def _send_initial_message(self, content: str) -> None:
        """Send the initial message and handle potential failures."""
        if not self.assistant_manager.send_message(content):
            logger.warning("Error sending message. Creating a new thread.")
            print("Error sending message. Creating a new thread.")
            
            # Create new thread and try again
            thread_id = self.assistant_manager.create_thread()
            self.current_project.thread_id = thread_id
            self.initialize_tool_manager()
            
            if not self.assistant_manager.send_message(content):
                logger.error("Failed to send initial message after retry")
                print("Failed to send initial message. Please try again.")
    
    def send_message(self, message: str) -> None:
        """
        Send a user message and process it.
        
        Args:
            message: User input message
        """
        if not self.current_project:
            logger.error("Cannot send message: No active project")
            print("Error: No active project.")
            return
        
        try:
            logger.debug(f"Processing user message: {message}")
            
            # Process the message through conversation manager
            processed_message = self.conversation_manager.process_message(
                message, self.current_project)
            
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
            if self.tool_manager:
                self.tool_manager.clear_suggestions()
            
            # Save after each interaction
            self.save_project()
            
            # Run the assistant to process the message
            self.assistant_manager.run_assistant(self.tool_manager.handle_required_actions)
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            print(f"Error processing your message: {e}")
    
    def interactive_loop(self) -> None:
        """Run the interactive conversation loop."""
        try:
            while True:
                user_input = self.ui_manager.get_user_input()
                
                if user_input in ["exit", "save"]:
                    break
                elif user_input == "history":
                    # Already displayed by UI manager
                    continue
                
                # The actual message sending is handled by the UI manager's callback
                # which calls our send_message method
                
        except Exception as e:
            logger.error(f"Error in interactive loop: {e}")
            print(f"Error during conversation: {e}")
        finally:
            self.cleanup()
    
    # -------------------------------------------------------------------------
    # EVENT HANDLERS
    # -------------------------------------------------------------------------
    
    def handle_assistant_message(self, message: str) -> None:
        """
        Handle a message received from the assistant.
        
        Args:
            message: Assistant message content
        """
        if not self.current_project:
            logger.warning("Received assistant message but no project is active")
            return
        
        try:
            # Extract and record the question
            question = self._extract_assistant_question(message)
            current_category = self.tool_manager.current_suggestion_category if self.tool_manager else None
            
            # Record via interaction recorder
            self.interaction_recorder.record_question(
                self.current_project,
                question,
                current_category,
                self.tool_manager.current_suggestions.copy() if self.tool_manager else []
            )
            
            # Save project
            self.save_project()
        except Exception as e:
            logger.error(f"Error handling assistant message: {e}")
    
    def _extract_assistant_question(self, message: str) -> str:
        """
        Extract the main question from an assistant message.
        
        Args:
            message: Full message from assistant
            
        Returns:
            Extracted question or last sentence
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
    
    def handle_run_completed(self, run: Any) -> None:
        """
        Handle when an assistant run is completed.
        
        Args:
            run: Run object from Assistant API
        """
        # Could log run information or update project status
        logger.debug(f"Assistant run completed: {run.id}")
    
    def handle_scope_saved(self, scope: Dict[str, Any]) -> None:
        """
        Handle when scope is saved from the tool manager.
        
        Args:
            scope: Scope data dictionary
        """
        if self.current_project:
            logger.info("Project scope document saved")
            self.current_project.scope = scope
            self.current_project.stage = "complete"
            self.save_project()
    
    def handle_suggestions_generated(self, suggestions: List[SuggestionItem], category: str) -> None:
        """
        Handle when suggestions are generated by the tool manager.
        
        Args:
            suggestions: List of suggestion items
            category: Category of suggestions
        """
        # UI display is handled by tool manager directly
        logger.debug(f"Suggestions generated for category: {category}")
    
    def handle_project_names_generated(self, suggestions: List[SuggestionItem]) -> None:
        """
        Handle when project name suggestions are generated.
        
        Args:
            suggestions: List of name suggestions
        """
        # UI display is handled by tool manager directly
        logger.debug("Project name suggestions generated")
    
    def update_project_name(self, name: str) -> None:
        """
        Update the project name and save changes.
        
        Args:
            name: New project name
        """
        if not self.current_project:
            logger.warning("Cannot update project name: No active project")
            return
        
        try:
            # Handle rename with file update
            old_name = self.current_project.name
            if old_name and old_name != name:
                self.data_manager.delete_project_file(old_name)
            
            # Update project
            self.current_project.name = name
            self.current_project.stage = "scoping"
            
            # Save with new name
            self.save_project()
            
            logger.info(f"Project name updated to: '{name}'")
            print(f"\n[System] Project name updated to: '{name}'")
        except Exception as e:
            logger.error(f"Error updating project name: {e}")
            print(f"Error updating project name: {e}")