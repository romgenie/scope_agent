# models/project.py
from datetime import datetime
from typing import List, Dict, Any, Optional, Union, Literal, TYPE_CHECKING
from pydantic import BaseModel, Field, validator

if TYPE_CHECKING:
    from models.interaction import InteractionHistory

class ScopeMetadata(BaseModel):
    """Model for scope metadata."""
    last_updated: str = Field(default_factory=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    completion_percentage: float = 0
    completion_status: Dict[str, str] = Field(default_factory=dict)
    version: int = 1

class CategoryData(BaseModel):
    """Model for category data within a scope."""
    value: Optional[str] = None
    description: Optional[str] = None
    timestamp: Optional[str] = None
    raw_input: Optional[str] = None
    selected_suggestion: Optional[Dict[str, str]] = None

class ScopeData(BaseModel):
    """Enhanced model for project scope data."""
    metadata: ScopeMetadata = Field(default_factory=ScopeMetadata)
    categories: Dict[str, CategoryData] = Field(default_factory=dict)

class ProjectData(BaseModel):
    """Enhanced model for project data with better scope tracking."""
    name: str
    created_at: str = Field(default_factory=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    last_modified: str = Field(default_factory=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    status: str = "new"
    stage: Literal["initial", "naming", "scoping", "complete"] = "initial"
    assistant_id: Optional[str] = None
    thread_id: Optional[str] = None
    scope: Dict[str, Any] = Field(default_factory=dict)  # Keep this for backward compatibility
    enhanced_scope: Optional[ScopeData] = None  # New structured scope data
    description: Optional[str] = None
    interaction_history: Optional["InteractionHistory"] = None
    
    class Config:
        validate_assignment = True
        
    def __init__(self, **data):
        """Initialize project data with an empty interaction history if none provided."""
        if "interaction_history" not in data:
            from models.interaction import InteractionHistory
            data["interaction_history"] = InteractionHistory()
        
        # Initialize enhanced scope if not present
        if "enhanced_scope" not in data:
            data["enhanced_scope"] = ScopeData()
            
        super().__init__(**data)
    
    def update_last_modified(self) -> None:
        """Update the last modified timestamp."""
        self.last_modified = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    def get_completion_percentage(self) -> float:
        """Get the project completion percentage."""
        if self.enhanced_scope and self.enhanced_scope.metadata:
            return self.enhanced_scope.metadata.completion_percentage
        return 0
    
    def update_category_from_interaction(self, category: str, interaction_data: dict) -> None:
        """Update a scope category from interaction data."""
        if not self.enhanced_scope:
            self.enhanced_scope = ScopeData()
            
        if category not in self.enhanced_scope.categories:
            self.enhanced_scope.categories[category] = CategoryData()
        
        category_data = self.enhanced_scope.categories[category]
        
        # Update with interaction data
        if 'selection' in interaction_data and interaction_data['selection']:
            category_data.value = interaction_data['selection']
            category_data.selected_suggestion = {
                'id': interaction_data.get('selection_id', ''),
                'text': interaction_data['selection']
            }
        elif 'custom_input' in interaction_data and interaction_data['custom_input']:
            category_data.value = interaction_data['custom_input']
            category_data.raw_input = interaction_data['custom_input']
        
        if 'timestamp' in interaction_data:
            category_data.timestamp = interaction_data['timestamp']
            
        # Update completion status
        self._update_completion_status()
    
    def _update_completion_status(self) -> None:
        """Update the completion status based on category values."""
        if not self.enhanced_scope:
            return
            
        completion_status = {}
        required_categories = [
            "project_name", "objective", "audience", "deliverable", 
            "timeline", "resource", "risk", "success_metric"
        ]
        
        # Check each required category
        for category in required_categories:
            if category in self.enhanced_scope.categories and self.enhanced_scope.categories[category].value:
                completion_status[category] = "completed"
            else:
                completion_status[category] = "incomplete"
        
        # Calculate percentage
        completed = sum(1 for status in completion_status.values() if status == "completed")
        total = len(required_categories)
        completion_percentage = (completed / total) * 100 if total > 0 else 0
        
        # Update metadata
        self.enhanced_scope.metadata.completion_status = completion_status
        self.enhanced_scope.metadata.completion_percentage = round(completion_percentage, 2)
        self.enhanced_scope.metadata.last_updated = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.enhanced_scope.metadata.version += 1

from models.interaction import InteractionHistory
ProjectData.model_rebuild()