import time
from typing import List, Dict, Any, Optional, Callable, Protocol

from utils.progress import ProgressIndicator

class ApiClient(Protocol):
    """Protocol defining the required methods for the API client."""
    def beta(self) -> Any:
        ...

class AssistantManager:
    """Manages interactions with the OpenAI Assistant API."""
    
    def __init__(self, client: Any):
        """Initialize the assistant manager with the API client."""
        self.client = client
        self.assistant = None
        self.thread_id = None
        self.progress = ProgressIndicator()
        
        # Callbacks
        self.on_message_received: Optional[Callable[[str], None]] = None
        self.on_run_completed: Optional[Callable[[Any], None]] = None
    
    def create_assistant(self, name: str, instructions: str, tools: List[Dict[str, Any]], model: str = "gpt-4o") -> str:
        """Create a new assistant and return its ID."""
        self.progress.start("Creating assistant")
        
        try:
            self.assistant = self.client.beta.assistants.create(
                name=name,
                instructions=instructions,
                tools=tools,
                model=model
            )
            self.progress.stop()
            print(f"Assistant created with ID: {self.assistant.id}")
            return self.assistant.id
        except Exception as e:
            self.progress.stop()
            print(f"Error creating assistant: {e}")
            return ""
    
    def get_assistant(self, assistant_id: str) -> bool:
        """Retrieve an existing assistant by ID."""
        self.progress.start("Retrieving assistant")
        
        try:
            self.assistant = self.client.beta.assistants.retrieve(
                assistant_id=assistant_id
            )
            self.progress.stop()
            print(f"Retrieved assistant: {self.assistant.id}")
            return True
        except Exception as e:
            self.progress.stop()
            print(f"Error retrieving assistant: {e}")
            return False
    
    def create_thread(self) -> str:
        """Create a new thread and return its ID."""
        try:
            thread = self.client.beta.threads.create()
            self.thread_id = thread.id
            print(f"Thread created with ID: {self.thread_id}")
            return self.thread_id
        except Exception as e:
            print(f"Error creating thread: {e}")
            return ""
    
    def get_thread(self, thread_id: str) -> bool:
        """Verify and set an existing thread by ID."""
        try:
            self.progress.start("Verifying thread")
            # Test if thread exists by listing messages
            self.client.beta.threads.messages.list(
                thread_id=thread_id
            )
            self.thread_id = thread_id
            self.progress.stop()
            print(f"Thread verified: {self.thread_id}")
            return True
        except Exception as e:
            self.progress.stop()
            print(f"Error verifying thread: {e}")
            return False
    
    def send_message(self, content: str) -> bool:
        """Send a message to the thread."""
        if not self.thread_id:
            print("Error: No active thread.")
            return False
        
        try:
            self.client.beta.threads.messages.create(
                thread_id=self.thread_id,
                role="user",
                content=content
            )
            return True
        except Exception as e:
            print(f"Error sending message: {e}")
            return False
    
    def run_assistant(self, tool_handler: Optional[Callable[[Any], None]] = None) -> bool:
        """Run the assistant on the thread and handle responses."""
        if not self.assistant or not self.thread_id:
            print("Error: Assistant or thread not initialized.")
            return False
        
        try:
            self.progress.start("⏳ Processing...")
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
                
                # Only report status changes, with simplified messages
                if run.status not in status_reported:
                    if run.status == "queued":
                        # Skip queued status - too brief to be meaningful
                        pass
                    elif run.status == "in_progress":
                        self.progress.update("⏳ Thinking...")
                    elif run.status == "requires_action":
                        self.progress.update("⚙️ Processing...")
                    status_reported.add(run.status)
                
                if run.status == "completed":
                    break
                elif run.status == "requires_action":
                    # Handle tool calls
                    self.progress.stop()
                    if tool_handler:
                        tool_handler(run)
                    # Reset status tracking
                    status_reported = set()
                elif run.status in ["failed", "expired", "cancelled"]:
                    self.progress.stop()
                    print(f"❌ Request failed: {run.status}")
                    return False
                
                time.sleep(0.5)
            
            self.progress.stop()
            
            # Get the latest assistant message
            messages = self.client.beta.threads.messages.list(
                thread_id=self.thread_id,
                order="desc",
                limit=1
            )
            
            latest_message = messages.data[0]
            if latest_message.role == "assistant":
                message_content = latest_message.content[0].text.value
                print("\nAssistant:", message_content)
                
                # Call message received callback
                if self.on_message_received:
                    self.on_message_received(message_content)
            
            # Call run completed callback
            if self.on_run_completed:
                self.on_run_completed(run)
            
            return True
            
        except Exception as e:
            self.progress.stop()
            print(f"Error running assistant: {e}")
            return False
    
    def cancel_active_runs(self) -> bool:
        """Cancel any active runs on the current thread."""
        if not self.thread_id:
            return False
        
        try:
            self.progress.start("Checking for active runs")
            # List all runs for the thread
            runs = self.client.beta.threads.runs.list(thread_id=self.thread_id)
            
            # Check for runs not in terminal state
            active_runs = []
            for run in runs.data:
                if run.status not in ["completed", "failed", "cancelled", "expired"]:
                    active_runs.append(run.id)
            
            # Cancel active runs
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
            
            # Wait for cancellations to complete
            if active_runs:
                print("Waiting for run cancellation to complete...")
                time.sleep(2)
            
            self.progress.stop()
            return True
            
        except Exception as e:
            self.progress.stop()
            print(f"Error checking for active runs: {e}")
            return False