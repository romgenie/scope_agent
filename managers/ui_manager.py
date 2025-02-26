import sys
from typing import List, Dict, Any, Optional, Callable, Union

from models.project import ProjectData
from models.suggestions import SuggestionItem

class UIManager:
    """Manages user interface interactions."""
    
    def __init__(self):
        """Initialize the UI manager."""
        self.current_project: Optional[ProjectData] = None
        
        # Callbacks
        self.on_project_selected: Optional[Callable[[str], None]] = None
        self.on_new_project: Optional[Callable[[str], None]] = None
        self.on_message_sent: Optional[Callable[[str], None]] = None
        self.on_exit: Optional[Callable[[], None]] = None
    
    def display_welcome(self) -> None:
        """Display welcome message."""
        print("\n\n" + "="*50)
        print("   PROJECT SCOPING ASSISTANT")
        print("="*50)
        print("\nWelcome! This assistant will help you define and plan your project")
        print("through an interactive conversation.")
        print("\nAvailable commands:")
        print("  - 'exit' or 'quit': End the session")
        print("  - 'save progress': Save current progress")
        print("  - 'history': Show conversation history")
        print("\n")
    
    def display_project_info(self, project: ProjectData) -> None:
        """Display information about the current project."""
        print("\n" + "="*50)
        print(f"   PROJECT: {project.name}")
        print("="*50)
        
        print(f"Status: {project.status}")
        print(f"Stage: {project.stage}")
        
        if project.description:
            print("\nDescription:")
            print(f"  {project.description}")
        
        # Show current progress
        if project.stage != "initial" and project.interaction_history:
            print("\nProgress:")
            num_interactions = len(project.interaction_history.interactions)
            print(f"  {num_interactions} questions answered")
        
        # Show scope summary if we have data
        if project.scope:
            print("\nScope Data Collected:")
            for key, value in project.scope.items():
                if isinstance(value, str):
                    print(f"  {key.replace('_', ' ').title()}: {value[:50]}{'...' if len(value) > 50 else ''}")
                else:
                    print(f"  {key.replace('_', ' ').title()}: [Data collected]")
        
        print("\nCreated: " + project.created_at)
        print("Last Modified: " + project.last_modified)
        print("="*50 + "\n")
    
    def display_projects_list(self, projects: List[Dict[str, str]]) -> None:
        """Display list of available projects."""
        if not projects:
            print("No existing projects found.")
            return
        
        print("=== Existing Projects ===")
        for i, project in enumerate(projects, 1):
            # Format dates for better readability
            created = project['created_at'].split()[0] if ' ' in project['created_at'] else project['created_at']
            modified = project['last_modified'].split()[0] if ' ' in project['last_modified'] else project['last_modified']
            
            print(f"{i}. {project['name']}")
            print(f"   Created: {created} | Last modified: {modified}")
    
    def select_project_prompt(self, projects: List[Dict[str, str]]) -> Optional[str]:
        """Prompt user to select a project and return file path or None for new project."""
        # Add new project and exit options
        print(f"\n{len(projects) + 1}. Create a new project")
        print(f"{len(projects) + 2}. Exit")
        
        while True:
            try:
                choice = input("\nSelect an option (enter number): ")
                choice_idx = int(choice) - 1
                
                if choice_idx == len(projects):
                    # New project
                    description = self.new_project_prompt()
                    if self.on_new_project:
                        self.on_new_project(description)
                    return None
                elif choice_idx == len(projects) + 1:
                    # Exit
                    print("Exiting application.")
                    if self.on_exit:
                        self.on_exit()
                    sys.exit(0)
                elif 0 <= choice_idx < len(projects):
                    # Existing project
                    file_path = projects[choice_idx]['file_path']
                    if self.on_project_selected:
                        self.on_project_selected(file_path)
                    return file_path
                else:
                    print("Invalid selection. Please try again.")
            except ValueError:
                print("Please enter a valid number.")
            except KeyboardInterrupt:
                print("\nExiting application.")
                if self.on_exit:
                    self.on_exit()
                sys.exit(0)
        
        return None
    
    def new_project_prompt(self) -> str:
        """Prompt for new project description and return it."""
        print("\n=== Creating New Project ===")
        print("\nPlease provide a brief description of your project.")
        print("This will help me understand what you want to build.")
        print("Example: 'A mobile app for tracking daily expenses' or 'An e-commerce website for selling handmade crafts'")
        try:
            description = input("\n> ")
            return description
        except KeyboardInterrupt:
            print("\nExiting application.")
            if self.on_exit:
                self.on_exit()
            sys.exit(0)
    
    def display_suggestions(self, suggestions: List[SuggestionItem], category: str, allow_custom: bool = True) -> None:
        """Display a list of suggestions to the user."""
        print(f"\n📌 {category.title()} Options:")
        
        for i, suggestion in enumerate(suggestions, 1):
            print(f"\n{i}. {suggestion.text}")
            if suggestion.description:
                print(f"   ▪ {suggestion.description}")
        
        if allow_custom:
            print(f"\nEnter 1-{len(suggestions)} to select an option, or type your own {category}.")
    
    def get_user_input(self, prompt: str = "Your input (or type 'help' for commands): ") -> str:
        """Get input from the user with standard commands."""
        try:
            # Show context-aware prompt based on stage
            if self.current_project and self.current_project.stage == "initial":
                print("\nℹ️  Tell me about your project ideas and goals. I'll guide you through the scoping process.")
            
            user_input = input(f"\n> ")
            
            # Handle special commands
            if user_input.lower() == "help":
                print("\nAvailable commands:")
                print("  - 'exit' or 'quit': End the session")
                print("  - 'save progress': Save current progress")
                print("  - 'history': Show conversation history")
                print("  - 'help': Show this help message")
                return "help"
                
            if user_input.lower() in ["exit", "quit", "bye"]:
                print("\n--- Project Scoping Conversation Ended ---")
                if self.on_exit:
                    self.on_exit()
                return "exit"
            
            if user_input.lower() in ["save progress", "save our progress"]:
                print("\n[System] Progress saved. You can continue this session later by selecting this project.")
                return "save"
            
            if user_input.lower() in ["history", "show history"]:
                if self.current_project and self.current_project.interaction_history:
                    print("\n--- Interaction History ---")
                    print(self.current_project.interaction_history.get_summary())
                else:
                    print("\nNo interaction history available.")
                return "history"
            
            # Regular input - call callback and return
            if self.on_message_sent:
                print("\n⏳ Processing your response...")
                self.on_message_sent(user_input)
            
            return user_input
            
        except KeyboardInterrupt:
            print("\n\nKeyboard interrupt detected.")
            if self.on_exit:
                self.on_exit()
            return "exit"