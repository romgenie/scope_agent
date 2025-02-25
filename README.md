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

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/scope_agent.git
   cd scope_agent
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set up your OpenAI API key:
   ```
   export OPENAI_API_KEY=your_api_key_here
   ```

## Usage

Run the scope agent:

```
python scope_agent.py
```

The tool will:
1. Prompt you to select an existing project or create a new one
2. Guide you through the project scoping process
3. Save project data automatically after each interaction
4. Generate a final scope document when complete

## Requirements

- Python 3.7+
- OpenAI API key
- Required packages:
  - openai
  - pydantic

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Author

© 2025 CompleteTech LLC
