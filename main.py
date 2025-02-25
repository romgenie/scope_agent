#!/usr/bin/env python3
"""
Scope Agent - A CLI-based project scoping assistant powered by OpenAI.
"""

import os
import sys
import signal
from openai import OpenAI

from config import Config
from managers.ui_manager import UIManager
from managers.data_manager import DataManager
from managers.project_manager import ProjectManager

def signal_handler(sig, frame) -> None:
    """Handle keyboard interrupts gracefully."""
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
    # Set up signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    # Load configuration
    config = Config()
    
    # Set up API client
    api_client = setup_api_client()
    
    # Set up managers
    ui_manager = UIManager()
    data_manager = DataManager(projects_dir=config.get("projects_dir"))
    
    # Set up project manager (controller)
    global project_manager  # Make it global so signal handler can access it
    project_manager = ProjectManager(api_client, ui_manager, data_manager)
    
    # Initialize and run the application
    project_manager.initialize()

if __name__ == "__main__":
    main()