#!/usr/bin/env python3
"""
Script to fix truncated dictionary names in existing model metadata files.
This fixes the issue where "dict_ehoo" was truncated to "dict_eho" in model names.
"""

import json
import os
from pathlib import Path
import re

def fix_model_metadata():
    """Fix truncated dictionary names in model metadata files."""
    
    # Path to the metadata directory
    base_path = Path(__file__).parent / "data" / "metadata" / "models"
    
    if not base_path.exists():
        print(f"Metadata path does not exist: {base_path}")
        return
    
    fixed_count = 0
    
    # Walk through all user directories
    for user_dir in base_path.iterdir():
        if not user_dir.is_dir():
            continue
            
        # Walk through all dictionary directories
        for dict_dir in user_dir.iterdir():
            if not dict_dir.is_dir():
                continue
            
            dict_name = dict_dir.name
            
            # Process all JSON files in this dictionary directory
            for json_file in dict_dir.glob("*.json"):
                try:
                    # Read the metadata file
                    with open(json_file, 'r') as f:
                        metadata = json.load(f)
                    
                    # Check if the name field needs fixing
                    if 'name' in metadata:
                        original_name = metadata['name']
                        
                        # Check for truncated dictionary names
                        # Pattern: "MODEL_TYPE - dict_xxx" where xxx might be truncated
                        pattern = r'^(\w+)\s*-\s*dict_(\w+)$'
                        match = re.match(pattern, original_name)
                        
                        if match:
                            model_type = match.group(1)
                            truncated_dict = match.group(2)
                            
                            # If the dictionary directory name is longer than what's in the metadata
                            # and the metadata name appears to be a truncation, fix it
                            if dict_name.startswith("dict_") and len(dict_name) > len(f"dict_{truncated_dict}"):
                                if dict_name.startswith(f"dict_{truncated_dict}"):
                                    # This looks like a truncation - fix it
                                    new_name = f"{model_type} - {dict_name}"
                                    metadata['name'] = new_name
                                    
                                    # Write the fixed metadata back
                                    with open(json_file, 'w') as f:
                                        json.dump(metadata, f, indent=2)
                                    
                                    print(f"Fixed: {json_file.name}")
                                    print(f"  Old name: {original_name}")
                                    print(f"  New name: {new_name}")
                                    fixed_count += 1
                
                except Exception as e:
                    print(f"Error processing {json_file}: {e}")
    
    print(f"\nFixed {fixed_count} model metadata files")

def fix_specific_dictionary(dict_id="dict_ehoo"):
    """Fix a specific dictionary's model names."""
    
    # Path to the metadata directory
    base_path = Path(__file__).parent / "data" / "metadata" / "models"
    
    if not base_path.exists():
        print(f"Metadata path does not exist: {base_path}")
        return
    
    fixed_count = 0
    
    # Walk through all user directories
    for user_dir in base_path.iterdir():
        if not user_dir.is_dir():
            continue
        
        # Look for the specific dictionary directory
        dict_dir = user_dir / dict_id
        if not dict_dir.exists():
            continue
        
        print(f"Processing models in {dict_dir}")
        
        # Process all JSON files in this dictionary directory
        for json_file in dict_dir.glob("*.json"):
            try:
                # Read the metadata file
                with open(json_file, 'r') as f:
                    metadata = json.load(f)
                
                # Check if the name field needs fixing
                if 'name' in metadata:
                    original_name = metadata['name']
                    
                    # Replace any occurrence of truncated dict name
                    if "dict_eho" in original_name and "dict_ehoo" not in original_name:
                        new_name = original_name.replace("dict_eho", "dict_ehoo")
                        metadata['name'] = new_name
                        
                        # Write the fixed metadata back
                        with open(json_file, 'w') as f:
                            json.dump(metadata, f, indent=2)
                        
                        print(f"Fixed: {json_file.name}")
                        print(f"  Old name: {original_name}")
                        print(f"  New name: {new_name}")
                        fixed_count += 1
            
            except Exception as e:
                print(f"Error processing {json_file}: {e}")
    
    print(f"\nFixed {fixed_count} model metadata files for dictionary {dict_id}")

if __name__ == "__main__":
    print("Fixing truncated dictionary names in model metadata...")
    print("=" * 60)
    
    # Fix specifically dict_ehoo models
    fix_specific_dictionary("dict_ehoo")
    
    print("\nDone!")