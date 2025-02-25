# Scope Agent

A CLI-based project scoping assistant powered by OpenAI that helps you define and plan projects through a guided conversation.

## Overview

Scope Agent is an interactive tool that walks you through the process of scoping a project from start to finish. It leverages AI to guide you through important project considerations and generates a structured scope document that can be saved and referenced later.

## Features

- **Interactive Conversation**: Engage in a natural dialogue with an AI assistant specialized in project scoping
- **Project Name Generation**: Get suggestions for compelling project names based on your project description
- **Guided Scoping Process**: Step-by-step guidance through key project elements:
  - Project objectives and goals
  - Target audience
  - Key deliverables
  - Timeline and milestones
  - Budget and resource allocation
  - Risk identification
  - Success metrics
- **Project Management**: Create, save, and continue working on multiple projects
- **Scope Document Generation**: Export complete project scope as a structured document
- **Interaction History**: Track and review your responses throughout the project scoping process

## Installation

### From PyPI (Recommended)
```
pip install scope-agent
```

### From Source
1. Clone this repository:
   ```
   git clone https://github.com/completetech/scope_agent.git
   cd scope_agent
   ```

2. Install the package:
   ```
   pip install -e .
   ```

## Usage

### Running the application
```
scope-agent
```

Or if installed from source:
```
python -m main
```

### Configuration
Configure Scope Agent by setting environment variables:
```
export OPENAI_API_KEY=your_api_key_here
export SCOPE_AGENT_PROJECTS_DIR=path/to/projects
```

## Project Structure

The codebase follows a modular architecture to promote maintainability and extensibility:

```
scope_agent/
├── models/           # Data models using Pydantic
├── managers/         # Core component managers 
├── utils/            # Utility functions and helpers
├── config.py         # Configuration handling
└── main.py           # Application entry point
```

## Requirements

- Python 3.8+
- OpenAI API key
- Required packages:
  - openai>=1.0.0
  - pydantic>=2.0.0

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Author

© 2025 CompleteTech LLC