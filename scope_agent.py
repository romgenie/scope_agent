import os
import time
import json
import signal
import sys
import glob
from datetime import datetime
from typing import List, Dict, Any, Optional, Union

from openai import OpenAI
from models import (
    SuggestionItem, ProjectData, InteractionRecord, InteractionHistory
)
from tools import ToolManager

class ProgressIndicator:
    """Static progress indicator that doesn't cause blinking."""
    def __init__(self):
        self.active = False
    
    def start(self, message="Working"):
        """Display a static progress message without animation."""
        self.active = True
        print(f"\n{message}")
    
    def update(self, message):
        """Update the progress message if needed."""
        if self.active:
            print(f"{message}")
    
    def stop(self):
        """Stop the progress indicator."""
        self.active = False

class ProjectScopingAgent:
    def __init__(self, api_key=None, projects_dir="projects"):
        """Initialize the Project Scoping Agent with OpenAI API key."""
        self.client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
        self.assistant = None
        self.thread_id = None
        self.project_name = None
        self.projects_dir = projects_dir
        self.progress = ProgressIndicator()
        
        # Initialize with empty project data
        self.project_data = None
        
        # Ensure projects directory exists
        os.makedirs(self.projects_dir, exist_ok=True)
        
        # Tool manager will be initialized after thread creation
        self.tool_manager = None
        
        # Track the latest interaction for recording responses
        self.latest_interaction_index: int = -1
    
    def load_projects(self) -> List[Dict[str, str]]:
        """Load list of existing projects from the projects directory."""
        project_files = glob.glob(os.path.join(self.projects_dir, "*.json"))
        projects = []
        
        for file_path in project_files:
            try:
                with open(file_path, 'r') as f:
                    project_dict = json.load(f)
                    project_data = ProjectData(**project_dict)
                    projects.append({
                        'name': project_data.name,
                        'file_path': file_path,
                        'created_at': project_data.created_at,
                        'last_modified': project_data.last_modified
                    })
            except Exception as e:
                print(f"Error loading project from {file_path}: {e}")
        
        return projects
    
    def select_project(self) -> bool:
        """Present user with existing projects or option to create a new one."""
        projects = self.load_projects()
        
        # Clear screen for better UX
        print("\n\n" + "="*50)
        print("   PROJECT SCOPING ASSISTANT")
        print("="*50 + "\n")
        
        if not projects:
            print("No existing projects found.")
            create_new = input("Would you like to create a new project? (Y/n): ").lower()
            if create_new != "n":
                return self.create_new_project()
            else:
                print("Exiting application.")
                sys.exit(0)
        
        print("=== Existing Projects ===")
        for i, project in enumerate(projects, 1):
            # Format dates for better readability
            created = project['created_at'].split()[0] if ' ' in project['created_at'] else project['created_at']
            modified = project['last_modified'].split()[0] if ' ' in project['last_modified'] else project['last_modified']
            
            print(f"{i}. {project['name']}")
            print(f"   Created: {created} | Last modified: {modified}")
        
        print(f"\n{len(projects) + 1}. Create a new project")
        print(f"{len(projects) + 2}. Exit")
        
        while True:
            try:
                choice = input("\nSelect an option (enter number): ")
                choice_idx = int(choice) - 1
                
                if choice_idx == len(projects):
                    return self.create_new_project()
                elif choice_idx == len(projects) + 1:
                    print("Exiting application.")
                    sys.exit(0)
                elif 0 <= choice_idx < len(projects):
                    return self.load_project(projects[choice_idx]['file_path'])
                else:
                    print("Invalid selection. Please try again.")
            except ValueError:
                print("Please enter a valid number.")
            except KeyboardInterrupt:
                print("\nExiting application.")
                sys.exit(0)

    def create_new_project(self) -> bool:
        """Initialize a new project with a user-provided description."""
        print("\n=== Creating New Project ===")
        default_name = f"Project_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Ask for project description immediately
        print("\nPlease provide a brief description of your project:")
        project_description = input("> ")
        
        # Create project data with description
        self.project_data = ProjectData(
            name=default_name,
            description=project_description,
            stage="initial"
        )
        
        # Set up the assistant and tools
        self.setup_assistant()
        
        print("\nProject initialized with description.")
        return True
    
    def check_and_cancel_active_runs(self) -> None:
        """Check for active runs on the thread and cancel them."""
        if not self.thread_id:
            return
            
        try:
            self.progress.start("Checking for active runs")
            # List all runs for the thread
            runs = self.client.beta.threads.runs.list(thread_id=self.thread_id)
            
            # Check for any runs that aren't in a terminal state
            active_runs = []
            for run in runs.data:
                if run.status not in ["completed", "failed", "cancelled", "expired"]:
                    active_runs.append(run.id)
            
            # Cancel any active runs
            for run_id in active_runs:
                print(f"Cancelling active run: {run_id}")
                try:
                    self.client.beta.threads.runs.cancel(
                        thread_id=self.thread_id,
                        run_id=run_id
                    )
                    print(f"Successfully cancelled run: {run_id}")
                except Exception as e:
                    print(f"Error cancelling run {run_id}: {e}")
                    
            # If we had active runs, wait a moment to ensure they're fully cancelled
            if active_runs:
                print("Waiting for run cancellation to complete...")
                time.sleep(2)
                
        except Exception as e:
            print(f"Error checking for active runs: {e}")
        finally:
            self.progress.stop()

    def display_project_info(self) -> None:
        """Display current project information in a structured format."""
        if not self.project_data:
            print("No project data available.")
            return
        
        print("\n" + "="*50)
        print(f"   PROJECT: {self.project_data.name}")
        print("="*50)
        
        print(f"Status: {self.project_data.status}")
        print(f"Stage: {self.project_data.stage}")
        
        if self.project_data.description:
            print("\nDescription:")
            print(f"  {self.project_data.description}")
        
        # Show current progress
        if self.project_data.stage != "initial":
            print("\nProgress:")
            num_interactions = len(self.project_data.interaction_history.interactions)
            print(f"  {num_interactions} questions answered")
        
        # Show scope summary if we have data
        if self.project_data.scope:
            print("\nScope Data Collected:")
            for key, value in self.project_data.scope.items():
                if isinstance(value, str):
                    print(f"  {key.replace('_', ' ').title()}: {value[:50]}{'...' if len(value) > 50 else ''}")
                else:
                    print(f"  {key.replace('_', ' ').title()}: [Data collected]")
        
        print("\nCreated: " + self.project_data.created_at)
        print("Last Modified: " + self.project_data.last_modified)
        print("="*50 + "\n")

    def load_project(self, file_path: str) -> bool:
        """Load an existing project from file."""
        try:
            with open(file_path, 'r') as f:
                project_dict = json.load(f)
                self.project_data = ProjectData(**project_dict)
            
            # Display project info after loading
            self.display_project_info()
            
            self.project_name = self.project_data.name
            
            # Check if we need to create a new assistant or use existing one
            if self.project_data.assistant_id:
                try:
                    # Try to retrieve the existing assistant
                    self.progress.start("Connecting to assistant")
                    self.assistant = self.client.beta.assistants.retrieve(
                        assistant_id=self.project_data.assistant_id
                    )
                    self.progress.stop()
                    print(f"Reconnected to assistant: {self.assistant.id}")
                except Exception as e:
                    self.progress.stop()
                    print(f"Could not retrieve existing assistant: {e}")
                    print("Creating a new assistant for this project...")
                    self.setup_assistant()
            else:
                self.setup_assistant()
            
            # Check if we need to create a new thread or use existing one
            if self.project_data.thread_id:
                try:
                    # Verify thread exists by retrieving a message
                    self.progress.start("Connecting to thread")
                    self.client.beta.threads.messages.list(
                        thread_id=self.project_data.thread_id
                    )
                    self.thread_id = self.project_data.thread_id
                    self.progress.stop()
                    print(f"Reconnected to thread: {self.thread_id}")
                    
                    # Initialize tool manager with the thread ID
                    self.initialize_tool_manager()
                    
                    # Check and cancel any active runs
                    self.check_and_cancel_active_runs()
                    
                except Exception as e:
                    self.progress.stop()
                    print(f"Could not retrieve existing thread: {e}")
                    print("Creating a new thread for this project...")
                    thread = self.client.beta.threads.create()
                    self.thread_id = thread.id
                    self.project_data.thread_id = thread.id
                    self.initialize_tool_manager()
            else:
                thread = self.client.beta.threads.create()
                self.thread_id = thread.id
                self.project_data.thread_id = thread.id
                self.initialize_tool_manager()
            
            # Update last modified
            self.project_data.last_modified = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.save_project()
            return True
            
        except Exception as e:
            if hasattr(self, 'progress'):
                self.progress.stop()
            print(f"Error loading project: {e}")
            print("Creating a new project instead.")
            return self.create_new_project()
    
    def save_project(self) -> None:
        """Save project data to file."""
        if not self.project_data:
            print("No project data to save.")
            return
        
        # Update project data
        if self.assistant:
            self.project_data.assistant_id = self.assistant.id
        if self.thread_id:
            self.project_data.thread_id = self.thread_id
        
        self.project_data.last_modified = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Ensure we have a project name for the filename
        project_name = self.project_data.name
        safe_name = ''.join(c if c.isalnum() else '_' for c in project_name)
        file_path = os.path.join(self.projects_dir, f"{safe_name}.json")
        
        try:
            with open(file_path, 'w') as f:
                json.dump(self.project_data.model_dump(), f, indent=2)
            print(f"Project saved to {file_path}")
        except Exception as e:
            print(f"Error saving project: {e}")
    
    def initialize_tool_manager(self) -> None:
        """Initialize the tool manager with callbacks."""
        if not self.thread_id:
            print("Error: Thread ID not available for tool manager.")
            return
            
        self.tool_manager = ToolManager(self.client, self.thread_id)
        
        # Set up callbacks
        self.tool_manager.on_scope_saved = self.on_scope_saved
        self.tool_manager.on_suggestions_generated = self.on_suggestions_generated
        self.tool_manager.on_project_names_generated = self.on_project_names_generated
    
    def on_scope_saved(self, scope: Dict[str, Any]) -> None:
        """Callback when scope is saved by the tool."""
        if self.project_data:
            self.project_data.scope = scope
            self.project_data.stage = "complete"
            self.save_project()
    
    def on_suggestions_generated(self, suggestions: List[SuggestionItem], category: str) -> None:
        """Callback when suggestions are generated."""
        # Store for later use in user input processing
        pass  # We'll access the tool_manager's properties directly
    
    def on_project_names_generated(self, suggestions: List[SuggestionItem]) -> None:
        """Callback when project name suggestions are generated."""
        # Store for later use in user input processing
        pass  # We'll access the tool_manager's properties directly

    def setup_assistant(self) -> None:
        """Create and configure the OpenAI Assistant."""
        print("Setting up Project Scoping Assistant...")
        self.progress.start("Creating assistant")
        
        # Create a thread if we don't have one yet
        if not self.thread_id:
            thread = self.client.beta.threads.create()
            self.thread_id = thread.id
            if self.project_data:
                self.project_data.thread_id = self.thread_id
        
        # Initialize tool manager
        self.initialize_tool_manager()
        
        # Create the assistant with specific instructions and tools
        self.assistant = self.client.beta.assistants.create(
            name="Project Scoping Assistant",
            instructions="""
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
            """,
            tools=self.tool_manager.tool_definitions,
            model="gpt-4o",
        )
        self.progress.stop()
        print(f"Assistant created with ID: {self.assistant.id}")
        
        # Update project data with assistant ID
        if self.project_data:
            self.project_data.assistant_id = self.assistant.id

    def cleanup(self) -> None:
        """Save project data and perform cleanup operations."""
        if self.project_data:
            self.save_project()
        print("\nProject saved. Assistant will be reused in future sessions.")
    
    def record_assistant_question(self, question: str, category: Optional[str] = None) -> None:
        """Record a question asked by the assistant."""
        if not self.project_data:
            return
        
        # Create a new interaction record for this question
        interaction = InteractionRecord(
            question=question,
            category=category,
            suggestions=self.tool_manager.current_suggestions.copy() if self.tool_manager and self.tool_manager.current_suggestions else []
        )
        
        # Add to history
        self.project_data.interaction_history.interactions.append(interaction)
        self.save_project()
        
        # Store the latest interaction ID for when we record the response
        self.latest_interaction_index = len(self.project_data.interaction_history.interactions) - 1

    def record_user_response(self, selection_text: Optional[str] = None, 
                            selection_id: Optional[str] = None,
                            custom_input: Optional[str] = None,
                            is_custom: bool = False) -> None:
        """Record a user's response to a question."""
        if not self.project_data or not hasattr(self, 'latest_interaction_index'):
            return
        
        # Get the latest interaction
        if self.latest_interaction_index >= 0 and self.latest_interaction_index < len(self.project_data.interaction_history.interactions):
            interaction = self.project_data.interaction_history.interactions[self.latest_interaction_index]
            
            # Update with user's response
            interaction.selection = selection_text
            interaction.selection_id = selection_id
            interaction.custom_input = custom_input
            interaction.is_custom = is_custom
            
            # Save changes
            self.save_project()
        
    def start_conversation(self) -> None:
        """Start the project scoping conversation with an initial message."""
        if not self.assistant or not self.thread_id:
            print("Error: Assistant or thread not initialized.")
            return
            
        print("\n--- Project Scoping Conversation Started ---")
        
        # Cancel any active runs before starting a new conversation
        self.check_and_cancel_active_runs()
        
        # If loading an existing project with a name, skip initial and naming stages
        if self.project_data.stage in ['scoping', 'complete'] and self.project_data.name:
            print(f"Continuing project: {self.project_data.name}")
            
            # Inform the assistant we're continuing an existing project
            try:
                self.client.beta.threads.messages.create(
                    thread_id=self.thread_id,
                    role="user",
                    content=f"We're continuing work on the project named '{self.project_data.name}'. Please continue from where we left off in the scoping process."
                )
            except Exception as e:
                print(f"Error starting conversation: {e}")
                print("Creating a new thread to continue the project...")
                # Create a new thread if we can't use the existing one
                thread = self.client.beta.threads.create()
                self.thread_id = thread.id
                self.project_data.thread_id = thread.id
                self.initialize_tool_manager()
                self.client.beta.threads.messages.create(
                    thread_id=self.thread_id,
                    role="user",
                    content=f"We're continuing work on the project named '{self.project_data.name}'. Please continue from where we left off in the scoping process."
                )
        else:
            # For new projects, provide the description we already collected
            # This way the agent can immediately start suggesting names
            try:
                project_description = self.project_data.description if self.project_data.description else "No description provided."
                self.client.beta.threads.messages.create(
                    thread_id=self.thread_id,
                    role="user",
                    content=f"I need help scoping a new project. Here's a description of my project idea: {project_description}"
                )
            except Exception as e:
                print(f"Error starting conversation: {e}")
                print("Creating a new thread to start the project...")
                # Create a new thread if we can't use the existing one
                thread = self.client.beta.threads.create()
                self.thread_id = thread.id
                self.project_data.thread_id = thread.id
                self.initialize_tool_manager()
                self.client.beta.threads.messages.create(
                    thread_id=self.thread_id,
                    role="user",
                    content=f"I need help scoping a new project. Here's a description of my project idea: {project_description}"
                )
        
        # Process the message
        self._process_message()
    
    def update_project_name(self, name: str) -> None:
        """Update the project name and save changes."""
        if not self.project_data:
            return
            
        # If this is a rename, we need to delete the old file
        old_name = self.project_data.name
        if old_name and old_name != name:
            old_safe_name = ''.join(c if c.isalnum() else '_' for c in old_name)
            old_file_path = os.path.join(self.projects_dir, f"{old_safe_name}.json")
            if os.path.exists(old_file_path):
                try:
                    os.remove(old_file_path)
                except Exception as e:
                    print(f"Warning: Could not delete old project file: {e}")
        
        # Update name and stage
        self.project_data.name = name
        self.project_data.stage = "scoping"
        self.project_name = name
        
        # Save with new name
        self.save_project()
        
        print(f"\n[System] Project name updated to: '{name}'")
    
    def extract_assistant_question(self, message_content: str) -> str:
        """Extract the main question from an assistant message."""
        # Simple extraction - get the last sentence ending with a question mark
        sentences = message_content.split('.')
        questions = [s.strip() + '.' for s in sentences if '?' in s]
        
        if questions:
            return questions[-1]  # Return the last question
        
        # If no question mark, just return the last sentence
        if sentences:
            return sentences[-1].strip() + '.'
        
        return message_content  # Fallback
    
    def _process_message(self) -> None:
        """Process the message and get a response from the assistant."""
        # Create a run to process the messages
        try:
            self.progress.start("Assistant is processing your request")
            run = self.client.beta.threads.runs.create(
                thread_id=self.thread_id,
                assistant_id=self.assistant.id
            )
            
            # Poll for the run to complete
            status_reported = set()  # Track statuses we've already reported
            while True:
                run = self.client.beta.threads.runs.retrieve(
                    thread_id=self.thread_id,
                    run_id=run.id
                )
                
                # Only report a status once to avoid repeating messages
                if run.status not in status_reported and run.status != "requires_action":
                    self.progress.update(f"Assistant is {run.status}")
                    status_reported.add(run.status)
                
                if run.status == "completed":
                    break
                elif run.status == "requires_action":
                    # Handle tool calls when needed
                    self.progress.stop()
                    self.tool_manager.handle_required_actions(run)
                    
                    # Reset the status tracking after actions
                    status_reported = set()
                elif run.status in ["failed", "expired", "cancelled"]:
                    print(f"Run failed with status: {run.status}")
                    break
                    
                time.sleep(0.5)
            
            # Make sure progress indicator is stopped before showing messages
            self.progress.stop()
            
            # Get the latest message from the assistant
            messages = self.client.beta.threads.messages.list(
                thread_id=self.thread_id,
                order="desc",
                limit=1
            )
            
            latest_message = messages.data[0]
            if latest_message.role == "assistant":
                message_content = latest_message.content[0].text.value
                print("\nAssistant:", message_content)
                
                # Extract and record the question
                question = self.extract_assistant_question(message_content)
                self.record_assistant_question(
                    question=question,
                    category=self.tool_manager.current_suggestion_category if self.tool_manager else None
                )
                
        except Exception as e:
            self.progress.stop()
            print(f"Error processing message: {e}")
    
    def _process_suggestion_input(self, user_input: str) -> str:
        """Process user input that might be selecting from suggestions and record the selection."""
        # If no suggestions are active, just return the original input
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
                
                # Special handling for project name selection
                if self.tool_manager.current_suggestion_category == "project_name" and not self.project_name:
                    # Remove quotes if present
                    project_name = selected.text.strip('"\'')
                    self.update_project_name(project_name)
                
                return selected.text
        except ValueError:
            pass
                
        # If this is a project name stage and we're processing a custom name
        if self.tool_manager.current_suggestion_category == "project_name" and not self.project_name:
            # User may be providing a custom project name
            project_name = user_input.strip('"\'')
            if project_name:
                self.update_project_name(project_name)
        
        # Input is not a selection number, treat as custom input
        self.record_user_response(custom_input=user_input, is_custom=True)
        return user_input
        
    def send_message(self, message: str) -> None:
        """Send a user message and get a response."""
        # Handle save progress command directly
        if message.lower() in ["save progress", "save our progress"]:
            self.save_project()
            print("\n[System] Progress saved. You can continue this session later by selecting this project.")
            return
            
        # Process the message if it might be selecting from suggestions
        processed_message = self._process_suggestion_input(message)
        
        # Add the message to the thread
        try:
            self.client.beta.threads.messages.create(
                thread_id=self.thread_id,
                role="user",
                content=processed_message
            )
            
            # Clear current suggestions after sending a response
            if self.tool_manager:
                self.tool_manager.clear_suggestions()
            
            # Process the message
            self._process_message()
            
        except Exception as e:
            print(f"Error sending message: {e}")
            # Try to recover by cancelling any active runs
            self.check_and_cancel_active_runs()
            # Try again after cancelling runs
            try:
                time.sleep(1)  # Give a brief pause
                self.client.beta.threads.messages.create(
                    thread_id=self.thread_id,
                    role="user",
                    content=processed_message
                )
                self._process_message()
            except Exception as e2:
                print(f"Failed to recover: {e2}")
        
        # Save project after each interaction to preserve conversation state
        self.save_project()
    
    def export_interaction_history(self, format: str = "json") -> Union[str, Dict]:
        """Export the interaction history in various formats."""
        if not self.project_data or not self.project_data.interaction_history:
            return "No interaction history available"
        
        history = self.project_data.interaction_history.model_dump()
        
        if format.lower() == "json":
            return json.dumps(history, indent=2)
        elif format.lower() == "dict":
            return history
        elif format.lower() == "summary":
            # Create a human-readable summary
            summary = f"Interaction History for {self.project_data.name}:\n\n"
            for i, interaction in enumerate(history.get('interactions', []), 1):
                summary += f"Interaction {i}:\n"
                summary += f"  Question: {interaction.get('question', 'N/A')}\n"
                
                if interaction.get('is_custom', False):
                    summary += f"  Custom Response: {interaction.get('custom_input', 'N/A')}\n"
                else:
                    summary += f"  Selected: {interaction.get('selection', 'N/A')}\n"
                
                summary += "\n"
            return summary
        
        return "Unsupported format"

    def run_interactive_session(self) -> None:
        """Run an interactive project scoping session."""
        # First, check for existing projects or create a new one
        self.select_project()
        
        # Start the conversation
        self.start_conversation()
        
        try:
            while True:
                user_input = input("\nYour response (or 'exit' to end): ")
                
                if user_input.lower() in ["exit", "quit", "bye"]:
                    print("\n--- Project Scoping Conversation Ended ---")
                    break
                
                if user_input.lower() in ["history", "show history"]:
                    print("\n--- Interaction History ---")
                    print(self.export_interaction_history(format="summary"))
                    continue
                    
                self.send_message(user_input)
        except KeyboardInterrupt:
            print("\n\nKeyboard interrupt detected. Cleaning up...")
        finally:
            # Save project data before exiting
            self.save_project()
            # Clean up resources when done
            self.cleanup()

def signal_handler(sig, frame) -> None:
    """Handle keyboard interrupts gracefully."""
    print("\n\nKeyboard interrupt detected. Cleaning up...")
    if 'agent' in globals() and agent is not None:
        agent.save_project()
        agent.cleanup()
    print("Exiting...")
    sys.exit(0)

def main() -> None:
    """Main function to run the Project Scoping Agent."""
    # Set up signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    # Check if API key is set
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        api_key = input("Please enter your OpenAI API key: ")
        os.environ["OPENAI_API_KEY"] = api_key
    
    # Create and run the agent
    global agent  # Make it global so signal handler can access it
    agent = ProjectScopingAgent(api_key)
    agent.run_interactive_session()

if __name__ == "__main__":
    main()
