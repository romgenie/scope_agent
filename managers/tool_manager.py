# managers/tool_coordinator.py
import json
import logging
from typing import List, Dict, Any, Optional, Callable

from models.suggestions import (
    SuggestionItem, SuggestionRequest, ProjectNameRequest, SuggestionResponse,
    ScopeData, ScopeResponse
)
from utils.event_bus import EventBus

logger = logging.getLogger(__name__)

class ApiClient:
    """Protocol defining the required methods for the API client."""
    def beta(self) -> Any:
        ...

class ToolCoordinator:
    """
    Coordinates tool usage and handles tool calls from the assistant.
    
    This class centralizes all tool-related functionality and provides
    a clean interface for handling tool calls.
    """
    
    def __init__(self, api_client: Any, event_bus: Optional[EventBus] = None):
        """
        Initialize the tool coordinator.
        
        Args:
            api_client: API client for OpenAI
            event_bus: Optional event bus for publishing events
        """
        self.api_client = api_client
        self.event_bus = event_bus
        self.thread_id = None
        self.current_suggestions: List[SuggestionItem] = []
        self.current_suggestion_category: Optional[str] = None
    
    def initialize_tools(self, thread_id: Optional[str] = None) -> None:
        """
        Initialize tools with the given thread ID.
        
        Args:
            thread_id: The thread ID to use for tool calls
        """
        if thread_id:
            self.thread_id = thread_id
        
        logger.info("Tools initialized")
    
    @property
    def tool_definitions(self) -> List[Dict[str, Any]]:
        """
        Get the tool definitions for the assistant.
        
        Returns:
            List of tool definition dictionaries
        """
        return [
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
    
    def handle_required_actions(self, run) -> None:
        """
        Handle required actions from the assistant.
        
        Args:
            run: The run object from the assistant API
        """
        tool_outputs = []
        
        # Process each tool call
        for tool_call in run.required_action.submit_tool_outputs.tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            
            # Process based on the tool type
            output = self._process_tool_call(function_name, function_args)
            
            tool_outputs.append({
                "tool_call_id": tool_call.id,
                "output": json.dumps(output.model_dump())
            })
        
        # Submit tool outputs back to the API
        if tool_outputs:
            try:
                self.api_client.beta.threads.runs.submit_tool_outputs(
                    thread_id=self.thread_id,
                    run_id=run.id,
                    tool_outputs=tool_outputs
                )
            except Exception as e:
                logger.error(f"Error submitting tool outputs: {e}")
                print(f"Error submitting tool outputs: {e}")
    
    def _process_tool_call(self, function_name: str, function_args: Dict[str, Any]) -> Any:
        """
        Process a specific tool call and return the appropriate response.
        
        Args:
            function_name: The name of the function to call
            function_args: The arguments to pass to the function
            
        Returns:
            Response object
        """
        if function_name == "save_scope":
            return self._handle_save_scope(function_args)
        elif function_name == "generate_project_names":
            return self._handle_generate_project_names(function_args)
        elif function_name == "generate_suggestions":
            return self._handle_generate_suggestions(function_args)
        else:
            # Unknown function
            return SuggestionResponse(
                status="error",
                rendered=False,
                num_suggestions=0
            )
    
    def _handle_save_scope(self, function_args: Dict[str, Any]) -> ScopeResponse:
        """
        Handle the save_scope tool call.
        
        Args:
            function_args: The arguments for the save_scope function
            
        Returns:
            Scope response object
        """
        try:
            # Parse and validate the scope data
            scope_data = ScopeData(**function_args)
            
            # Publish event if event bus exists
            if self.event_bus:
                self.event_bus.publish("scope_saved", scope_data.scope)
            
            print("\n=== PROJECT SCOPE DOCUMENT ===")
            print(json.dumps(scope_data.scope, indent=2))
            print("=== END OF SCOPE DOCUMENT ===\n")
            
            # Create and validate the response
            return ScopeResponse(
                status="success",
                message="Project scope saved successfully"
            )
        except Exception as e:
            logger.error(f"Error saving scope: {e}")
            # Handle validation error with a more graceful fallback
            print(f"\n[Warning] Cannot generate complete scope document yet: {e}")
            # Report partial success
            return ScopeResponse(
                status="partial",
                message="Progress saved, but complete scope document not available yet"
            )
    
    def _handle_generate_project_names(self, function_args: Dict[str, Any]) -> SuggestionResponse:
        """
        Handle the generate_project_names tool call.
        
        Args:
            function_args: The arguments for the generate_project_names function
            
        Returns:
            Suggestion response object
        """
        try:
            # Parse request
            request = ProjectNameRequest(**function_args)
            
            # Store suggestions
            self.current_suggestion_category = "project_name"
            self.current_suggestions = request.suggestions
            
            # Publish event if event bus exists
            if self.event_bus:
                self.event_bus.publish("project_names_generated", {
                    "suggestions": request.suggestions,
                    "allow_custom": request.allow_custom_input
                })
            
            # Create response
            return SuggestionResponse(
                status="success",
                rendered=True,
                num_suggestions=len(self.current_suggestions)
            )
        except Exception as e:
            logger.error(f"Error generating project names: {e}")
            return SuggestionResponse(
                status="error",
                rendered=False,
                num_suggestions=0
            )

    def _handle_generate_suggestions(self, function_args: Dict[str, Any]) -> SuggestionResponse:
        """
        Handle the generate_suggestions tool call.
        
        Args:
            function_args: The arguments for the generate_suggestions function
            
        Returns:
            Suggestion response object
        """
        try:
            # Parse request
            request = SuggestionRequest(**function_args)
            
            # Store suggestions
            self.current_suggestion_category = request.category
            self.current_suggestions = request.suggestions
            
            # Publish event if event bus exists
            if self.event_bus:
                self.event_bus.publish("suggestions_generated", {
                    "suggestions": request.suggestions,
                    "category": request.category,
                    "allow_custom": request.allow_custom_input
                })
            
            # Create response
            return SuggestionResponse(
                status="success",
                rendered=True,
                num_suggestions=len(self.current_suggestions)
            )
        except Exception as e:
            logger.error(f"Error generating suggestions: {e}")
            return SuggestionResponse(
                status="error",
                rendered=False,
                num_suggestions=0
            )
    
    def clear_suggestions(self) -> None:
        """Clear current suggestions."""
        self.current_suggestions = []
        self.current_suggestion_category = None
    
    def get_current_suggestions(self) -> List[SuggestionItem]:
        """
        Get the current suggestions.
        
        Returns:
            List of current suggestion items
        """
        return self.current_suggestions
    
    def get_current_category(self) -> Optional[str]:
        """
        Get the current suggestion category.
        
        Returns:
            Current category or None
        """
        return self.current_suggestion_category
    
    def set_thread_id(self, thread_id: str) -> None:
        """
        Set the thread ID for tool calls.
        
        Args:
            thread_id: The thread ID to use
        """
        self.thread_id = thread_id