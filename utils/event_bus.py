# utils/event_bus.py
import logging
from typing import Dict, List, Any, Callable

logger = logging.getLogger(__name__)

class EventBus:
    """
    Facilitates event-based communication between components.
    
    This allows for loose coupling between components - publishers don't need
    to know about subscribers and vice versa.
    """
    
    def __init__(self):
        """Initialize an empty event bus."""
        self.handlers: Dict[str, List[Callable]] = {}
    
    def register(self, event_type: str, handler: Callable) -> None:
        """
        Register a handler for an event type.
        
        Args:
            event_type: The type of event to handle
            handler: The function to call when the event occurs
        """
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        
        self.handlers[event_type].append(handler)
        logger.debug(f"Registered handler for event: {event_type}")
    
    def publish(self, event_type: str, data: Any = None) -> None:
        """
        Publish an event to all registered handlers.
        
        Args:
            event_type: The type of event being published
            data: Data associated with the event
        """
        if event_type not in self.handlers:
            logger.debug(f"No handlers registered for event: {event_type}")
            return
        
        for handler in self.handlers[event_type]:
            try:
                handler(data)
            except Exception as e:
                logger.error(f"Error in event handler for {event_type}: {e}")
    
    def unregister(self, event_type: str, handler: Callable) -> bool:
        """
        Unregister a handler for an event type.
        
        Args:
            event_type: The type of event
            handler: The handler to remove
            
        Returns:
            True if the handler was removed, False otherwise
        """
        if event_type not in self.handlers:
            return False
        
        try:
            self.handlers[event_type].remove(handler)
            return True
        except ValueError:
            return False