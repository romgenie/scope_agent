#!/usr/bin/env python3
"""
Scope Agent - A CLI-based project scoping assistant powered by OpenAI.
"""

import os
import sys
import signal
import logging
from openai import OpenAI

from config import Config
from managers.ui_manager import UIManager
from managers.data_manager import DataManager
from managers.project_manager import ProjectManager
from managers.assistant_manager import AssistantManager
from managers.conversation_manager import ConversationManager
from managers.interaction_recorder import InteractionRecorder

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scope_agent.log"),
        logging.StreamHandler(stream=sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def signal_handler(sig, frame) -> None:
    """Handle keyboard interrupts gracefully."""
    logger.info("Keyboard interrupt detected")
    print("\n\nKeyboard interrupt detected. Cleaning up...")
    if 'project_manager' in globals() and project_manager is not None:
        project_manager.cleanup()
    print("Exiting...")
    sys.exit(0)

def setup_api_client() -> OpenAI:
    """Set up and return the OpenAI API client."""
    # Check for API key
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        api_key = input("Please enter your OpenAI API key: ")
        os.environ["OPENAI_API_KEY"] = api_key
    
    return OpenAI(api_key=api_key)

def main() -> None:
    """Main function to run the Project Scoping Agent."""
    logger.info("Starting Scope Agent application")
    
    # Set up signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Load configuration
        config = Config()
        
        # Set up API client
        api_client = setup_api_client()
        
        # Set up core managers
        ui_manager = UIManager()
        data_manager = DataManager(projects_dir=config.get("projects_dir"))
        assistant_manager = AssistantManager(api_client)
        interaction_recorder = InteractionRecorder()
        
        # Set up conversation manager
        conversation_manager = ConversationManager(
            assistant_manager=assistant_manager,
            tool_manager=None,  # Will be set by ProjectManager
            interaction_recorder=interaction_recorder
        )
        
        # Set up project manager (controller)
        global project_manager  # Make it global so signal handler can access it
        project_manager = ProjectManager(
            api_client=api_client, 
            ui_manager=ui_manager, 
            data_manager=data_manager,
            assistant_manager=assistant_manager,
            conversation_manager=conversation_manager,
            interaction_recorder=interaction_recorder
        )
        
        # Initialize and run the application
        project_manager.initialize()
        
    except Exception as e:
        logger.error(f"Unhandled exception in main: {e}", exc_info=True)
        print(f"An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()