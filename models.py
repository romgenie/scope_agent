from datetime import datetime
import uuid
from typing import List, Dict, Any, Optional, Union, Literal
from pydantic import BaseModel, Field, validator

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

class InteractionRecord(BaseModel):
    """Model for tracking a single interaction between assistant and user."""
    timestamp: str = Field(default_factory=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    question: str
    category: Optional[str] = None
    suggestions: List[SuggestionItem] = Field(default_factory=list)
    selection: Optional[str] = None  # The text of the selected suggestion
    selection_id: Optional[str] = None  # The ID of the selected suggestion
    custom_input: Optional[str] = None  # Custom input if not selecting from suggestions
    is_custom: bool = False  # Flag to indicate if user entered custom input vs selection

class InteractionHistory(BaseModel):
    """Model for storing the history of all interactions."""
    interactions: List[InteractionRecord] = Field(default_factory=list)

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
    interaction_history: InteractionHistory = Field(default_factory=InteractionHistory)
    
    class Config:
        validate_assignment = True
