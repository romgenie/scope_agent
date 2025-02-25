import os
import time
import json
import signal
import sys
import glob
import uuid
import threading
import shutil
from datetime import datetime
from typing import List, Dict, Any, Optional, Union, Literal
from pydantic import BaseModel, Field, validator
from openai import OpenAI

# ---- Pydantic Models ----

class SuggestionItem(BaseModel):
    """Model for a single suggestion item."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str
    description: Optional[str] = None
    best_practice: Optional[str] = None

class SuggestionRequest(BaseModel):
    """Model for generating suggestions."""
    category: Literal["project_name", "objective", "timeline", "resource", 
                      "risk", "deliverable", "audience", "success_metric", "best_practice"]
    question: str
    suggestions: List[SuggestionItem]
    allow_custom_input: bool = True

class ProjectNameRequest(BaseModel):
    """Model for generating project name suggestions."""
    project_description: str
    suggestions: List[SuggestionItem]
    allow_custom_input: bool = True

class SuggestionResponse(BaseModel):
    """Model for suggestion generation response."""
    status: str
    rendered: bool = True
    num_suggestions: int

class ScopeData(BaseModel):
    """Model for project scope data."""
    scope: Dict[str, Any]

class ScopeResponse(BaseModel):
    """Model for save scope response."""
    status: str
    message: str

class ProjectData(BaseModel):
    """Model for project data."""
    name: str
    created_at: str = Field(default_factory=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    last_modified: str = Field(default_factory=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    status: str = "new"
    stage: Literal["initial", "naming", "scoping", "complete"] = "initial"
    assistant_id: Optional[str] = None
    thread_id: Optional[str] = None
    scope: Dict[str, Any] = Field(default_factory=dict)
    description: Optional[str] = None
    
    class Config:
        validate_assignment = True

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
        self.thread_id = None  # Store thread_id directly
        self.project_name = None
        self.projects_dir = projects_dir
        self.progress = ProgressIndicator()
        
        # Initialize with empty project data
        self.project_data = None
        
        # Ensure projects directory exists
        os.makedirs(self.projects_dir, exist_ok=True)
        
        # Store suggestions for UI rendering
        self.current_suggestions: List[SuggestionItem] = []
        self.current_suggestion_category: Optional[str] = None
    
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
        
        if not projects:
            print("No existing projects found. Creating a new project.")
            return self.create_new_project()
        
        print("\n=== Existing Projects ===")
        for i, project in enumerate(projects, 1):
            print(f"{i}. {project['name']} (Created: {project['created_at']}, Last modified: {project['last_modified']})")
        print(f"{len(projects) + 1}. Create a new project")
        
        while True:
            try:
                choice = input("\nSelect a project (enter number): ")
                choice_idx = int(choice) - 1
                
                if choice_idx == len(projects):
                    return self.create_new_project()
                elif 0 <= choice_idx < len(projects):
                    return self.load_project(projects[choice_idx]['file_path'])
                else:
                    print("Invalid selection. Please try again.")
            except ValueError:
                print("Please enter a valid number.")
    
    def create_new_project(self) -> bool:
        """Initialize a new project."""
        print("\n=== Creating New Project ===")
        default_name = f"Project_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        self.project_data = ProjectData(name=default_name)
        
        self.setup_assistant()
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
    
    def load_project(self, file_path: str) -> bool:
        """Load an existing project from file."""
        try:
            with open(file_path, 'r') as f:
                project_dict = json.load(f)
                self.project_data = ProjectData(**project_dict)
            
            print(f"\nLoaded project: {self.project_data.name}")
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
                    
                    # Check and cancel any active runs
                    self.check_and_cancel_active_runs()
                    
                except Exception as e:
                    self.progress.stop()
                    print(f"Could not retrieve existing thread: {e}")
                    print("Creating a new thread for this project...")
                    thread = self.client.beta.threads.create()
                    self.thread_id = thread.id
                    self.project_data.thread_id = thread.id
            else:
                thread = self.client.beta.threads.create()
                self.thread_id = thread.id
                self.project_data.thread_id = thread.id
            
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
                json.dump(self.project_data.model_dump(), f, indent=2)  # Use model_dump instead of dict
            print(f"Project saved to {file_path}")
        except Exception as e:
            print(f"Error saving project: {e}")

    def setup_assistant(self) -> None:
        """Create and configure the OpenAI Assistant."""
        print("Setting up Project Scoping Assistant...")
        self.progress.start("Creating assistant")
        
        # Define the tools the assistant can use
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "save_scope",
                    "description": "Save the final project scope document",
                    "parameters": ScopeData.model_json_schema()
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "generate_project_names",
                    "description": "Generate project name suggestions based on project description",
                    "parameters": ProjectNameRequest.model_json_schema()
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "generate_suggestions",
                    "description": "Generate structured suggestions for various project aspects",
                    "parameters": SuggestionRequest.model_json_schema()
                }
            }
        ]
        
        # Create the assistant with specific instructions and tools
        self.assistant = self.client.beta.assistants.create(
            name="Project Scoping Assistant",
            instructions="""
            You are a project scoping specialist who helps users define and plan their projects through a 
            guided, step-by-step conversation. Follow this specific conversational flow:
            
            1. INITIAL STAGE: First, ask the user for a general description of their project. Just one simple 
            question to understand the basic concept. Store this description for later use.
            
            2. NAMING STAGE: After receiving the project description, IMMEDIATELY call the generate_project_names 
            tool with the description to suggest possible names. Don't wait for the user to ask for names - 
            offer them right after getting the description.
            
            3. SCOPING STAGE: After the user selects or provides a project name, begin the detailed scoping process 
            by asking ONE question at a time about different aspects of the project:
            - Ask a focused question
            - IMMEDIATELY call the generate_suggestions tool to provide options
            - Wait for the user's response before asking the next question
            
            IMPORTANT TIMING GUIDELINES:
            - Call tools IMMEDIATELY after receiving relevant user information - don't delay
            - Use generate_project_names immediately after receiving the initial project description
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
            tools=tools,
            model="gpt-4o",
        )
        self.progress.stop()
        print(f"Assistant created with ID: {self.assistant.id}")
        
        # Update project data with assistant ID
        if self.project_data:
            self.project_data.assistant_id = self.assistant.id
        
        # Create a thread for the conversation if not already loaded
        if not self.thread_id:
            thread = self.client.beta.threads.create()
            self.thread_id = thread.id
            print(f"Thread created with ID: {self.thread_id}")
            
            # Update project data with thread ID
            if self.project_data:
                self.project_data.thread_id = self.thread_id    
           
    def cleanup(self) -> None:
        """Save project data and perform cleanup operations."""
        if self.project_data:
            self.save_project()
            
        # No longer deleting the assistant since we want to reuse it in future sessions
        # if self.assistant:
        #     try:
        #         print(f"\nCleaning up: Deleting assistant {self.assistant.id}...")
        #         self.client.beta.assistants.delete(assistant_id=self.assistant.id)
        #         print("Assistant deleted successfully.")
        #     except Exception as e:
        #         print(f"Error deleting assistant: {e}")
        
        print("\nProject saved. Assistant will be reused in future sessions.")
        
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
                self.client.beta.threads.messages.create(
                    thread_id=self.thread_id,
                    role="user",
                    content=f"We're continuing work on the project named '{self.project_data.name}'. Please continue from where we left off in the scoping process."
                )
        else:
            # Initial message requesting just a project description
            try:
                self.client.beta.threads.messages.create(
                    thread_id=self.thread_id,
                    role="user",
                    content="I need help scoping a new project. I'd like to start by describing my project idea to you."
                )
            except Exception as e:
                print(f"Error starting conversation: {e}")
                print("Creating a new thread to start the project...")
                # Create a new thread if we can't use the existing one
                thread = self.client.beta.threads.create()
                self.thread_id = thread.id
                self.project_data.thread_id = thread.id
                self.client.beta.threads.messages.create(
                    thread_id=self.thread_id,
                    role="user",
                    content="I need help scoping a new project. I'd like to start by describing my project idea to you."
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
    
    def handle_suggestion_selection(self, selection_id: Optional[str] = None, 
                                    custom_input: Optional[str] = None) -> Optional[str]:
        """Handle user selection from generated suggestions."""
        if not self.current_suggestions:
            return None
        
        # If user provided a selection ID, find the matching suggestion
        if selection_id:
            for suggestion in self.current_suggestions:
                if suggestion.id == selection_id:
                    return suggestion.text
        
        # If user provided custom input, use that instead
        if custom_input:
            return custom_input
            
        return None
        
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
                    self._handle_required_actions(run)
                    
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
                
        except Exception as e:
            self.progress.stop()
            print(f"Error processing message: {e}")
    
    def _handle_required_actions(self, run) -> None:
        """Handle required actions from the assistant."""
        tool_outputs = []
        
        # First, analyze all the tool calls to prepare outputs
        for tool_call in run.required_action.submit_tool_outputs.tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            
            if function_name == "save_scope":
                # Parse and validate the scope data
                try:
                    scope_data = ScopeData(**function_args)
                    
                    # Save the scope to the project data
                    self.project_data.scope = scope_data.scope
                    self.project_data.stage = "complete"
                    self.save_project()
                    
                    print("\n=== PROJECT SCOPE DOCUMENT ===")
                    print(json.dumps(scope_data.scope, indent=2))
                    print("=== END OF SCOPE DOCUMENT ===\n")
                    
                    # Create and validate the response
                    response = ScopeResponse(
                        status="success",
                        message="Project scope saved successfully"
                    )
                except Exception as e:
                    # Handle validation error with a more graceful fallback
                    print(f"\n[Warning] Cannot generate complete scope document yet: {e}")
                    # Create a partial scope with what we have so far
                    partial_scope = {
                        "status": "in_progress",
                        "message": "Project scoping in progress",
                        "collected_data": self.project_data.scope or {}
                    }
                    # Report partial success
                    response = ScopeResponse(
                        status="partial",
                        message="Progress saved, but complete scope document not available yet"
                    )
                    # Save what we have so far
                    self.save_project()
                    
                tool_outputs.append({
                    "tool_call_id": tool_call.id,
                    "output": json.dumps(response.model_dump())
                })

    def _process_suggestion_input(self, user_input: str) -> str:
        """Process user input that might be selecting from suggestions."""
        # If no suggestions are active, just return the original input
        if not self.current_suggestions:
            return user_input
            
        # Check if input is a number selecting from the list
        try:
            selection_idx = int(user_input) - 1
            if 0 <= selection_idx < len(self.current_suggestions):
                selected = self.current_suggestions[selection_idx]
                print(f"[Selected: {selected.text}]")
                
                # Special handling for project name selection
                if self.current_suggestion_category == "project_name" and not self.project_name:
                    # Remove quotes if present
                    project_name = selected.text.strip('"\'')
                    self.update_project_name(project_name)
                
                return selected.text
        except ValueError:
            pass
            
        # If this is a project name stage and we're processing a custom name
        if self.current_suggestion_category == "project_name" and not self.project_name:
            # User may be providing a custom project name
            project_name = user_input.strip('"\'')
            if project_name:
                self.update_project_name(project_name)
        
        # Input is not a selection number, treat as custom input
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
            self.current_suggestions = []
            self.current_suggestion_category = None
            
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
                    
                self.send_message(user_input)
        except KeyboardInterrupt:
            print("\n\nKeyboard interrupt detected. Cleaning up...")
        finally:
            # Save project data before exiting
            self.save_project()
            # Clean up resources when done - no longer deleting the assistant
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
