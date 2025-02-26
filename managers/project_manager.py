from typing import List, Dict, Any, Optional, Callable

from models.project import ProjectData
from models.interaction import InteractionRecord
from models.suggestions import SuggestionItem

from managers.assistant_manager import AssistantManager
from managers.data_manager import DataManager
from managers.tool_manager import ToolManager
from managers.ui_manager import UIManager

class ProjectManager:
    """Orchestrates the overall project workflow and manages component interactions."""
    
    def __init__(self, api_client, ui_manager: UIManager, data_manager: DataManager):
        """Initialize the project manager with required components."""
        self.api_client = api_client
        self.ui_manager = ui_manager
        self.data_manager = data_manager
        
        self.assistant_manager = AssistantManager(api_client)
        self.tool_manager = None
        
        self.current_project: Optional[ProjectData] = None
        self.latest_interaction_index: int = -1
        
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
        self.ui_manager.display_welcome()
        projects = self.data_manager.load_projects_list()
        self.ui_manager.display_projects_list(projects)
        self.ui_manager.select_project_prompt(projects)
        
        if self.current_project:
            self.start_conversation()
    
    def create_new_project(self, description: str) -> None:
        """Create a new project with the given description."""
        from datetime import datetime
        
        # Create default project name
        default_name = f"Project_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Create project data
        self.current_project = ProjectData(
            name=default_name,
            description=description,
            stage="initial"
        )
        
        # Set up assistant and start conversation
        self.setup_assistant()
        self.start_conversation()
    
    def load_project(self, file_path: str) -> None:
        """Load an existing project from file."""
        project_data = self.data_manager.load_project(file_path)
        if not project_data:
            print("Error loading project. Creating a new one instead.")
            self.create_new_project("No description provided.")
            return
        
        self.current_project = project_data
        self.ui_manager.current_project = project_data
        self.ui_manager.display_project_info(project_data)
        
        # Set up assistant with existing IDs if available
        if self.current_project.assistant_id:
            if not self.assistant_manager.get_assistant(self.current_project.assistant_id):
                print("Could not retrieve existing assistant. Creating a new one.")
                self.setup_assistant()
        else:
            self.setup_assistant()
        
        # Set up thread
        if self.current_project.thread_id:
            if not self.assistant_manager.get_thread(self.current_project.thread_id):
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
        
        # Save project with updated IDs
        self.save_project()
    
    def setup_assistant(self) -> None:
        """Set up the assistant with appropriate instructions and tools."""
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
    
    def initialize_tool_manager(self) -> None:
        """Initialize the tool manager and set up callbacks."""
        if not self.assistant_manager.thread_id:
            print("Error: Thread ID not available for tool manager.")
            return
        
        self.tool_manager = ToolManager(
            self.api_client,
            self.assistant_manager.thread_id
        )
        
        # Set up callbacks
        self.tool_manager.on_scope_saved = self.handle_scope_saved
        self.tool_manager.on_suggestions_generated = self.handle_suggestions_generated
        self.tool_manager.on_project_names_generated = self.handle_project_names_generated
    
    def start_conversation(self) -> None:
        """Start or continue the project scoping conversation."""
        if not self.current_project:
            print("Error: No active project.")
            return
        
        print("\n--- Project Scoping Conversation Started ---")
        
        # Cancel any active runs before starting
        self.assistant_manager.cancel_active_runs()
        
        # Different approach based on project stage
        if self.current_project.stage in ['scoping', 'complete'] and self.current_project.name:
            print(f"Continuing project: {self.current_project.name}")
            
            # Continue existing project
            content = f"We're continuing work on the project named '{self.current_project.name}'. Please continue from where we left off in the scoping process."
            if not self.assistant_manager.send_message(content):
                print("Error sending message. Creating a new thread.")
                # Create new thread and try again
                thread_id = self.assistant_manager.create_thread()
                self.current_project.thread_id = thread_id
                self.initialize_tool_manager()
                self.assistant_manager.send_message(content)
        else:
            # Start new project with description
            description = self.current_project.description if self.current_project.description else "No description provided."
            content = f"I need help scoping a new project. Here's a description of my project idea: {description}"
            
            if not self.assistant_manager.send_message(content):
                print("Error sending message. Creating a new thread.")
                # Create new thread and try again
                thread_id = self.assistant_manager.create_thread()
                self.current_project.thread_id = thread_id
                self.initialize_tool_manager()
                self.assistant_manager.send_message(content)
            
        # Start interactive loop
        self.interactive_loop()
    
    def send_message(self, message: str) -> None:
        """Send a user message and process it."""
        if not self.current_project:
            print("Error: No active project.")
            return
            
        # Process the message for suggestion selection
        processed_message = self.process_suggestion_input(message)
        
        # Send to assistant
        if not self.assistant_manager.send_message(processed_message):
            # Try recovery by cancelling runs
            self.assistant_manager.cancel_active_runs()
            if not self.assistant_manager.send_message(processed_message):
                print("Failed to send message. Please try again.")
                return
        
        # Clear suggestions after sending
        if self.tool_manager:
            self.tool_manager.clear_suggestions()
        
        # Save after each interaction
        self.save_project()
        
        # Run the assistant to process the message
        self.assistant_manager.run_assistant(self.tool_manager.handle_required_actions)
    
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
            print(f"Error in interactive loop: {e}")
        finally:
            self.cleanup()
    
    def process_suggestion_input(self, user_input: str) -> str:
        """Process user input for suggestion selection and record the interaction."""
        if not self.tool_manager or not self.tool_manager.current_suggestions:
            # Record as custom input with no suggestions
            self.record_user_response(custom_input=user_input, is_custom=True)
            return user_input
        
        # Check if input is a number selecting from the list
        try:
            selection_idx = int(user_input) - 1
            if 0 <= selection_idx < len(self.tool_manager.current_suggestions):
                selected = self.tool_manager.current_suggestions[selection_idx]
                print(f"[Selected: {selected.text}]")
                
                # Record the selection
                self.record_user_response(
                    selection_text=selected.text,
                    selection_id=selected.id,
                    is_custom=False
                )
                
                # Handle project name selection
                if self.tool_manager.current_suggestion_category == "project_name" and self.current_project:
                    # Remove quotes if present
                    project_name = selected.text.strip('"\'')
                    self.update_project_name(project_name)
                
                return selected.text
        except ValueError:
            pass
        
        # Handle project name input
        if self.tool_manager.current_suggestion_category == "project_name" and self.current_project:
            project_name = user_input.strip('"\'')
            if project_name:
                self.update_project_name(project_name)
        
        # Record as custom input
        self.record_user_response(custom_input=user_input, is_custom=True)
        return user_input
    
    def update_project_name(self, name: str) -> None:
        """Update the project name and save changes."""
        if not self.current_project:
            return
        
        # Handle rename with file update
        old_name = self.current_project.name
        if old_name and old_name != name:
            self.data_manager.delete_project_file(old_name)
        
        # Update project
        self.current_project.name = name
        self.current_project.stage = "scoping"
        
        # Save with new name
        self.save_project()
        
        print(f"\n[System] Project name updated to: '{name}'")
    
    def save_project(self) -> None:
        """Save current project data to file."""
        if not self.current_project:
            return
        
        # Update IDs from managers
        if self.assistant_manager.assistant:
            self.current_project.assistant_id = self.assistant_manager.assistant.id
        
        if self.assistant_manager.thread_id:
            self.current_project.thread_id = self.assistant_manager.thread_id
        
        # Save to file
        self.data_manager.save_project(self.current_project)
    
    def handle_scope_saved(self, scope: Dict[str, Any]) -> None:
        """Handle when scope is saved from the tool manager."""
        if self.current_project:
            self.current_project.scope = scope
            self.current_project.stage = "complete"
            self.save_project()
    
    def handle_suggestions_generated(self, suggestions: List[SuggestionItem], category: str) -> None:
        """Handle when suggestions are generated."""
        # UI display is handled by tool manager directly
        pass
    
    def handle_project_names_generated(self, suggestions: List[SuggestionItem]) -> None:
        """Handle when project name suggestions are generated."""
        # UI display is handled by tool manager directly
        pass
    
    def extract_assistant_question(self, message: str) -> str:
        """Extract the main question from an assistant message."""
        # Simple extraction - get the last sentence ending with a question mark
        sentences = message.split('.')
        questions = [s.strip() + '.' for s in sentences if '?' in s]
        
        if questions:
            return questions[-1]  # Return the last question
        
        # If no question mark, just return the last sentence
        if sentences:
            return sentences[-1].strip() + '.'
        
        return message  # Fallback
    
    def handle_assistant_message(self, message: str) -> None:
        """Handle a message received from the assistant."""
        if not self.current_project:
            return
        
        # Extract and record the question
        question = self.extract_assistant_question(message)
        self.record_assistant_question(
            question=question,
            category=self.tool_manager.current_suggestion_category if self.tool_manager else None
        )
    
    def handle_run_completed(self, run: Any) -> None:
        """Handle when an assistant run is completed."""
        # Could log run information or update project status
        pass
    
    def record_assistant_question(self, question: str, category: Optional[str] = None) -> None:
        """Record a question asked by the assistant."""
        if not self.current_project or not self.current_project.interaction_history:
            return
        
        # Create a new interaction record
        interaction = InteractionRecord(
            question=question,
            category=category,
            suggestions=self.tool_manager.current_suggestions.copy() if self.tool_manager else []
        )
        
        # Add to history
        interaction_index = self.current_project.interaction_history.add_interaction(interaction)
        self.latest_interaction_index = interaction_index
        
        # Save project
        self.save_project()
    
    def record_user_response(self, selection_text: Optional[str] = None, 
                           selection_id: Optional[str] = None,
                           custom_input: Optional[str] = None,
                           is_custom: bool = False) -> None:
        """Record a user's response to a question."""
        if not self.current_project or not self.current_project.interaction_history:
            return
        
        # Update the latest interaction
        if self.latest_interaction_index >= 0:
            self.current_project.interaction_history.update_interaction(
                self.latest_interaction_index,
                selection=selection_text,
                selection_id=selection_id,
                custom_input=custom_input,
                is_custom=is_custom
            )
            
            # Save the project
            self.save_project()
    
    def cleanup(self) -> None:
        """Clean up resources before exiting."""
        if self.current_project:
            self.save_project()
        print("\nProject saved. Assistant will be reused in future sessions.")