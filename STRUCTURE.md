scope_agent/
├── __init__.py
├── main.py                  # Entry point
├── config.py                # Configuration settings
├── models/                  # Data models
│   ├── __init__.py
│   ├── interaction.py       # Interaction models
│   ├── project.py           # Project models
│   └── suggestions.py       # Suggestion models
├── managers/                # Core managers
│   ├── __init__.py
│   ├── assistant_manager.py # Manages LLM interactions
│   ├── data_manager.py      # Handles data persistence
│   ├── project_manager.py   # Orchestrates project workflow
│   ├── tool_manager.py      # Manages tool definitions/handling
│   └── ui_manager.py        # Handles user interface
├── utils/                   # Utility functions
│   ├── __init__.py
│   ├── format_utils.py      # Formatting helpers
│   └── progress.py          # Progress indicators
└── tests/                   # Unit tests
    ├── __init__.py
    └── test_*.py            # Test modules