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

class ScopeResponse(BaseModel):
    """Model for scope saving response."""
    status: Literal["success", "error", "partial"]
    message: str

# models/interaction.py
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator

from models.suggestions import SuggestionItem

class InteractionRecord(BaseModel):
    """Model for tracking a single interaction between assistant and user."""
    timestamp: str = Field(default_factory=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    question: str
    category: Optional[str] = None
    context: Optional[str] = None  # New: provides additional context
    suggestions: List[SuggestionItem] = Field(default_factory=list)
    selection: Optional[str] = None  # The text of the selected suggestion
    selection_id: Optional[str] = None  # The ID of the selected suggestion
    custom_input: Optional[str] = None  # Custom input if not selecting from suggestions
    is_custom: bool = False  # Flag to indicate if user entered custom input vs selection
    
    @validator('question')
    def ensure_valid_question(cls, v):
        """Ensure question is meaningful and not just a placeholder."""
        if not v or v == "." or not v.strip():
            return "No specific question recorded"
        return v

class InteractionHistory(BaseModel):
    """Model for storing the history of all interactions."""
    interactions: List[InteractionRecord] = Field(default_factory=list)
    
    def add_interaction(self, interaction: InteractionRecord) -> int:
        """Add an interaction and return its index."""
        self.interactions.append(interaction)
        return len(self.interactions) - 1
    
    def update_interaction(self, index: int, **updates) -> bool:
        """Update an interaction at the given index."""
        if 0 <= index < len(self.interactions):
            interaction = self.interactions[index]
            for key, value in updates.items():
                setattr(interaction, key, value)
            return True
        return False
    
    def get_summary(self) -> str:
        """Get a human-readable summary of the interaction history."""
        summary = "Interaction History:\n\n"
        for i, interaction in enumerate(self.interactions, 1):
            summary += f"Interaction {i} ({interaction.timestamp}):\n"
            summary += f"  Question: {interaction.question}\n"
            
            if interaction.category:
                summary += f"  Category: {interaction.category}\n"
                
            if interaction.is_custom:
                summary += f"  Custom Response: {interaction.custom_input}\n"
            elif interaction.selection:
                summary += f"  Selected: {interaction.selection}\n"
            else:
                summary += f"  No response recorded\n"
            
            summary += "\n"
        return summary
    
    def get_interactions_by_category(self, category: str) -> List[InteractionRecord]:
        """Get all interactions for a specific category."""
        return [i for i in self.interactions if i.category == category]
        
    def get_latest_by_category(self, category: str) -> Optional[InteractionRecord]:
        """Get the most recent interaction for a specific category."""
        matching = self.get_interactions_by_category(category)
        if matching:
            # Sort by timestamp descending
            return sorted(matching, key=lambda x: x.timestamp, reverse=True)[0]
        return None

# models/project.py
from datetime import datetime
from typing import List, Dict, Any, Optional, Union, Literal
from pydantic import BaseModel, Field, ConfigDict

class CategoryData(BaseModel):
    """Model for a category's data within a project scope."""
    value: Optional[str] = None
    description: Optional[str] = None
    timestamp: Optional[str] = None
    notes: Optional[str] = None
    raw_input: Optional[str] = None
    selected_suggestion: Optional[Dict[str, str]] = None
    
    def is_complete(self) -> bool:
        """Check if this category has a value set."""
        return self.value is not None and bool(self.value.strip()) if isinstance(self.value, str) else self.value is not None

class ScopeData(BaseModel):
    """Model for project scope data."""
    # Core scope categories
    project_name: CategoryData = Field(default_factory=CategoryData)
    objective: CategoryData = Field(default_factory=CategoryData)
    audience: CategoryData = Field(default_factory=CategoryData)
    deliverable: CategoryData = Field(default_factory=CategoryData)
    timeline: CategoryData = Field(default_factory=CategoryData)
    resource: CategoryData = Field(default_factory=CategoryData)
    risk: CategoryData = Field(default_factory=CategoryData)
    success_metric: CategoryData = Field(default_factory=CategoryData)
    
    # Optional additional categories
    additional_categories: Dict[str, CategoryData] = Field(default_factory=dict)
    
    # Metadata
    last_updated: str = Field(default_factory=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    version: int = 1
    
    def get_completion_percentage(self) -> float:
        """Calculate the completion percentage based on required fields."""
        # Core fields that must be completed
        core_fields = [
            self.project_name,
            self.objective,
            self.audience,
            self.deliverable,
            self.timeline,
            self.resource,
            self.risk,
            self.success_metric
        ]
        
        completed = sum(1 for field in core_fields if field.is_complete())
        return round((completed / len(core_fields)) * 100, 2)
    
    def get_completion_status(self) -> Dict[str, str]:
        """Get a dictionary of completion status for each category."""
        status = {}
        
        # Check core fields
        status["project_name"] = "completed" if self.project_name.is_complete() else "incomplete"
        status["objective"] = "completed" if self.objective.is_complete() else "incomplete"
        status["audience"] = "completed" if self.audience.is_complete() else "incomplete"
        status["deliverable"] = "completed" if self.deliverable.is_complete() else "incomplete"
        status["timeline"] = "completed" if self.timeline.is_complete() else "incomplete"
        status["resource"] = "completed" if self.resource.is_complete() else "incomplete"
        status["risk"] = "completed" if self.risk.is_complete() else "incomplete"
        status["success_metric"] = "completed" if self.success_metric.is_complete() else "incomplete"
        
        # Check additional categories
        for key, category in self.additional_categories.items():
            status[key] = "completed" if category.is_complete() else "incomplete"
            
        return status
    
    def update_timestamp(self) -> None:
        """Update the last_updated timestamp."""
        self.last_updated = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.version += 1
    
    def update_category(self, category: str, value: str, description: Optional[str] = None, 
                        suggestion_id: Optional[str] = None, timestamp: Optional[str] = None,
                        is_custom: bool = False) -> None:
        """Update a specific category with new information."""
        # Determine which field to update
        if hasattr(self, category):
            target = getattr(self, category)
        elif category in self.additional_categories:
            target = self.additional_categories[category]
        else:
            # Create new additional category
            target = CategoryData()
            self.additional_categories[category] = target
        
        # Update the category data
        target.value = value
        if description:
            target.description = description
        
        if timestamp:
            target.timestamp = timestamp
        else:
            target.timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if is_custom:
            target.raw_input = value
            target.selected_suggestion = None
        elif suggestion_id:
            target.selected_suggestion = {"id": suggestion_id, "text": value}
            target.raw_input = None
        
        # Update metadata
        self.update_timestamp()

class ProjectData(BaseModel):
    """Streamlined model for project data with integrated scope."""
    model_config = ConfigDict(validate_assignment=True)
    
    # Project metadata
    name: str
    created_at: str = Field(default_factory=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    last_modified: str = Field(default_factory=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    status: str = "new"
    stage: Literal["initial", "naming", "scoping", "complete"] = "initial"
    description: Optional[str] = None
    
    # API connection info
    assistant_id: Optional[str] = None
    thread_id: Optional[str] = None
    
    # Project data
    scope: ScopeData = Field(default_factory=ScopeData)
    interaction_history: InteractionHistory = Field(default_factory=InteractionHistory)
    
    def update_last_modified(self) -> None:
        """Update the last modified timestamp."""
        self.last_modified = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    def get_completion_percentage(self) -> float:
        """Get the project completion percentage."""
        return self.scope.get_completion_percentage()
    
    def update_category_from_interaction(self, category: str, interaction_record: InteractionRecord) -> None:
        """Update scope based on an interaction."""
        if not category:
            return
            
        # Extract data from interaction
        if interaction_record.is_custom and interaction_record.custom_input:
            value = interaction_record.custom_input
            is_custom = True
            suggestion_id = None
        elif interaction_record.selection:
            value = interaction_record.selection
            is_custom = False
            suggestion_id = interaction_record.selection_id
        else:
            # No data to update
            return
            
        # Find description in suggestions if available
        description = None
        if not is_custom and suggestion_id:
            for suggestion in interaction_record.suggestions:
                if suggestion.id == suggestion_id and suggestion.description:
                    description = suggestion.description
                    break
                    
        # Update the scope
        self.scope.update_category(
            category=category,
            value=value,
            description=description,
            suggestion_id=suggestion_id,
            timestamp=interaction_record.timestamp,
            is_custom=is_custom
        )
        
        # Update project metadata based on category
        if category == "project_name":
            self.name = value
            self.stage = "scoping"
        
        # If we're updating any category, we're in scoping stage at minimum
        if self.stage == "initial":
            self.stage = "scoping"
            
        # Check if we're complete
        if self.get_completion_percentage() == 100:
            self.stage = "complete"
            self.status = "complete"
            
        self.update_last_modified()