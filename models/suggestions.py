# models/suggestions.py
import uuid
from typing import List, Dict, Any, Optional, Union, Literal
from pydantic import BaseModel, Field

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