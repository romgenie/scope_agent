# models/interaction.py
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from models.suggestions import SuggestionItem

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
            
            if interaction.is_custom:
                summary += f"  Custom Response: {interaction.custom_input}\n"
            else:
                summary += f"  Selected: {interaction.selection}\n"
            
            summary += "\n"
        return summary