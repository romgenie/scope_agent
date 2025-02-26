# models/project.py
from datetime import datetime
from typing import List, Dict, Any, Optional, Union, Literal, TYPE_CHECKING, Annotated
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from models.interaction import InteractionHistory

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
    interaction_history: Optional["InteractionHistory"] = None
    
    class Config:
        validate_assignment = True
        
    def __init__(self, **data):
        """Initialize project data with an empty interaction history if none provided."""
        if "interaction_history" not in data:
            from models.interaction import InteractionHistory
            data["interaction_history"] = InteractionHistory()
        super().__init__(**data)
    
    def update_last_modified(self) -> None:
        """Update the last modified timestamp."""
        self.last_modified = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

from models.interaction import InteractionHistory
ProjectData.model_rebuild()