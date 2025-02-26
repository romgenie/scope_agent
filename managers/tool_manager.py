import json
from typing import List, Dict, Any, Optional, Callable, Protocol

from models.suggestions import (
    SuggestionItem, SuggestionRequest, ProjectNameRequest, SuggestionResponse,
    ScopeData, ScopeResponse
)

class ApiClient(Protocol):
    """Protocol defining the required methods for the API client."""
    def beta(self) -> Any:
        ...

class ToolManager:
    """Class to manage tool definitions and handling for the scoping assistant."""
    
    def __init__(self, client: Any, thread_id: str):
        """Initialize the tool manager with API client and thread ID."""
        self.client = client
        self.thread_id = thread_id
        self.current_suggestions: List[SuggestionItem] = []
        self.current_suggestion_category: Optional[str] = None
        
        # Callbacks that will be set by the agent
        self.on_scope_saved: Optional[Callable[[Dict[str, Any]], None]] = None
        self.on_suggestions_generated: Optional[Callable[[List[SuggestionItem], str], None]] = None
        self.on_project_names_generated: Optional[Callable[[List[SuggestionItem]], None]] = None
    
    @property
    def tool_definitions(self) -> List[Dict[str, Any]]:
        """Get the tool definitions for the assistant."""
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
        """Handle required actions from the assistant."""
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
                self.client.beta.threads.runs.submit_tool_outputs(
                    thread_id=self.thread_id,
                    run_id=run.id,
                    tool_outputs=tool_outputs
                )
            except Exception as e:
                print(f"Error submitting tool outputs: {e}")
    
    def _process_tool_call(self, function_name: str, function_args: Dict[str, Any]) -> Any:
        """Process a specific tool call and return the appropriate response."""
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
        """Handle the save_scope tool call."""
        try:
            # Parse and validate the scope data
            scope_data = ScopeData(**function_args)
            
            # Call the callback if set
            if self.on_scope_saved:
                self.on_scope_saved(scope_data.scope)
            
            print("\n=== PROJECT SCOPE DOCUMENT ===")
            print(json.dumps(scope_data.scope, indent=2))
            print("=== END OF SCOPE DOCUMENT ===\n")
            
            # Create and validate the response
            return ScopeResponse(
                status="success",
                message="Project scope saved successfully"
            )
        except Exception as e:
            # Handle validation error with a more graceful fallback
            print(f"\n[Warning] Cannot generate complete scope document yet: {e}")
            # Report partial success
            return ScopeResponse(
                status="partial",
                message="Progress saved, but complete scope document not available yet"
            )
    
    def _handle_generate_project_names(self, function_args: Dict[str, Any]) -> SuggestionResponse:
        """Handle the generate_project_names tool call."""
        try:
            # Parse request
            request = ProjectNameRequest(**function_args)
            
            # Store suggestions
            self.current_suggestion_category = "project_name"
            self.current_suggestions = request.suggestions
            
            # Call the callback if set
            if self.on_project_names_generated:
                self.on_project_names_generated(request.suggestions)
            
            # Don't print suggestions directly - let the assistant handle the display
            # The UI will get these from the assistant's response
            
            # Create response
            return SuggestionResponse(
                status="success",
                rendered=True,
                num_suggestions=len(self.current_suggestions)
            )
        except Exception as e:
            print(f"Error generating project names: {e}")
            return SuggestionResponse(
                status="error",
                rendered=False,
                num_suggestions=0
            )

    def _handle_generate_suggestions(self, function_args: Dict[str, Any]) -> SuggestionResponse:
        """Handle the generate_suggestions tool call."""
        try:
            # Parse request
            request = SuggestionRequest(**function_args)
            
            # Store suggestions
            self.current_suggestion_category = request.category
            self.current_suggestions = request.suggestions
            
            # Call the callback if set
            if self.on_suggestions_generated:
                self.on_suggestions_generated(request.suggestions, request.category)
            
            # Don't print suggestions directly - let the assistant handle the display
            # The UI will get these from the assistant's response
            
            # Create response
            return SuggestionResponse(
                status="success",
                rendered=True,
                num_suggestions=len(self.current_suggestions)
            )
        except Exception as e:
            print(f"Error generating suggestions: {e}")
            return SuggestionResponse(
                status="error",
                rendered=False,
                num_suggestions=0
            )


    
    def clear_suggestions(self) -> None:
        """Clear current suggestions."""
        self.current_suggestions = []
        self.current_suggestion_category = None