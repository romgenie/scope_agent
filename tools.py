import json
from typing import List, Dict, Any, Optional, Callable
from openai import OpenAI
from models import (
    SuggestionItem, SuggestionRequest, ProjectNameRequest, SuggestionResponse,
    ScopeData, ScopeResponse
)
