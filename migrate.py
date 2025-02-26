#!/usr/bin/env python3
"""
Migration tool to convert existing project JSON files to the new enhanced format.
"""

import os
import json
import glob
import shutil
from datetime import datetime
from typing import List, Dict, Any

def backup_projects_directory(projects_dir: str) -> str:
    """Create a backup of the projects directory."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = f"{projects_dir}_backup_{timestamp}"
    
    # Create backup by copying the directory
    shutil.copytree(projects_dir, backup_dir)
    print(f"Backup created at: {backup_dir}")
    
    return backup_dir

def migrate_project_file(file_path: str) -> bool:
    """Migrate a single project file to the new format."""
    try:
        with open(file_path, 'r') as f:
            project_data = json.load(f)
        
        # Check if already migrated
        if "enhanced_scope" in project_data:
            print(f"Project already migrated: {file_path}")
            return True
        
        # Create enhanced scope structure
        enhanced_scope = {
            "metadata": {
                "last_updated": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "completion_percentage": 0,
                "completion_status": {},
                "version": 1
            },
            "categories": {}
        }
        
        # Migrate interaction history to enhanced scope
        if "interaction_history" in project_data and "interactions" in project_data["interaction_history"]:
            for interaction in project_data["interaction_history"]["interactions"]:
                category = interaction.get("category")
                
                if not category:
                    continue
                
                # Initialize category data
                if category not in enhanced_scope["categories"]:
                    enhanced_scope["categories"][category] = {
                        "value": None,
                        "description": None,
                        "timestamp": interaction.get("timestamp"),
                        "raw_input": None,
                        "selected_suggestion": None
                    }
                
                # Update with interaction data
                category_data = enhanced_scope["categories"][category]
                
                if interaction.get("is_custom") and interaction.get("custom_input"):
                    category_data["value"] = interaction["custom_input"]
                    category_data["raw_input"] = interaction["custom_input"]
                elif interaction.get("selection"):
                    category_data["value"] = interaction["selection"]
                    category_data["selected_suggestion"] = {
                        "id": interaction.get("selection_id", ""),
                        "text": interaction["selection"]
                    }
                    
                    # Look for additional data in suggestions
                    for suggestion in interaction.get("suggestions", []):
                        if suggestion.get("id") == interaction.get("selection_id"):
                            if suggestion.get("description"):
                                category_data["description"] = suggestion["description"]
                            break
                
                # Update timestamp if newer
                if interaction.get("timestamp"):
                    if not category_data["timestamp"] or interaction["timestamp"] > category_data["timestamp"]:
                        category_data["timestamp"] = interaction["timestamp"]
        
        # Calculate completion status
        required_categories = [
            "project_name", "objective", "audience", "deliverable", 
            "timeline", "resource", "risk", "success_metric"
        ]
        
        completion_status = {}
        completed_count = 0
        
        for category in required_categories:
            if category in enhanced_scope["categories"] and enhanced_scope["categories"][category]["value"]:
                completion_status[category] = "completed"
                completed_count += 1
            else:
                completion_status[category] = "incomplete"
        
        # Update completion percentage
        if required_categories:
            completion_percentage = (completed_count / len(required_categories)) * 100
            enhanced_scope["metadata"]["completion_percentage"] = round(completion_percentage, 2)
        
        enhanced_scope["metadata"]["completion_status"] = completion_status
        
        # Add enhanced scope to project data
        project_data["enhanced_scope"] = enhanced_scope
        
        # Save updated project file
        with open(file_path, 'w') as f:
            json.dump(project_data, f, indent=2)
        
        print(f"Successfully migrated: {file_path}")
        return True
    
    except Exception as e:
        print(f"Error migrating {file_path}: {e}")
        return False

def migrate_all_projects(projects_dir: str) -> None:
    """Migrate all project files in the directory."""
    # Create backup
    backup_projects_directory(projects_dir)
    
    # Get all project files
    project_files = glob.glob(os.path.join(projects_dir, "*.json"))
    
    if not project_files:
        print(f"No project files found in {projects_dir}")
        return
    
    print(f"Found {len(project_files)} project files to migrate")
    
    # Migrate each file
    success_count = 0
    for file_path in project_files:
        if migrate_project_file(file_path):
            success_count += 1
    
    print(f"\nMigration complete: {success_count} of {len(project_files)} files successfully migrated")

def main():
    """Main function to run the migration tool."""
    projects_dir = input("Enter the projects directory path (default: 'projects'): ") or "projects"
    
    if not os.path.exists(projects_dir):
        print(f"Directory not found: {projects_dir}")
        return
    
    confirm = input(f"This will update all project files in '{projects_dir}'. A backup will be created first. Continue? (y/n): ")
    
    if confirm.lower() != 'y':
        print("Migration cancelled")
        return
    
    migrate_all_projects(projects_dir)

if __name__ == "__main__":
    main()