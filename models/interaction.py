# models/interaction.py
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator

from models.suggestions import SuggestionItem

class InteractionRecord(BaseModel):
    """Enhanced model for tracking interactions between assistant and user."""
    timestamp: str = Field(default_factory=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    question: str
    category: Optional[str] = None
    context: Optional[str] = None  # Provides additional context about this question
    suggestions: List[SuggestionItem] = Field(default_factory=list)
    selection: Optional[str] = None  # The text of the selected suggestion
    selection_id: Optional[str] = None  # The ID of the selected suggestion
    custom_input: Optional[str] = None  # Custom input if not selecting from suggestions
    is_custom: bool = False  # Flag to indicate if user entered custom input vs selection
    
    @validator('question', pre=True)
    def validate_question(cls, v):
        """Ensure question is meaningful and not just a placeholder."""
        if not v or v == "." or not v.strip():
            return "No specific question recorded"
        return v

class InteractionHistory(BaseModel):
    """Enhanced model for storing interaction history with better querying capabilities."""
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
            summary += f"Interaction {i}:\n"
            summary += f"  Question: {interaction.question}\n"
            
            if interaction.category:
                summary += f"  Category: {interaction.category}\n"
                
            if interaction.is_custom:
                summary += f"  Custom Response: {interaction.custom_input}\n"
            else:
                summary += f"  Selected: {interaction.selection}\n"
            
            summary += f"  Timestamp: {interaction.timestamp}\n\n"
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