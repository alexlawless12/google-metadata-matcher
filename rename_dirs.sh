#!/bin/bash

# Ensure the user provides a directory as an argument
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <directory>"
    exit 1
fi

# Get the input directory
input_dir="$1"

# Verify the directory exists
if [ ! -d "$input_dir" ]; then
    echo "Directory does not exist: $input_dir"
    exit 1
fi

# Find all subdirectories within the input directory
find "$input_dir" -type d -not -path "$input_dir" | while read -r dir; do
    # Extract the directory name
    dir_name=$(basename "$dir")
    
    # Check if the directory name ends with a year (2002-2024)
    if [[ "$dir_name" =~ ^.*(200[2-9]|20[1-9][0-9])$ ]]; then
        # Extract the year from the directory name
        year="${dir_name: -4}"
        
        # Determine the parent directory
        parent_dir=$(dirname "$dir")
        
        # Construct the new directory path
        new_dir="$parent_dir/$year"
        
        # Rename the directory
        if [ "$dir" != "$new_dir" ]; then
            mv "$dir" "$new_dir"
            echo "Renamed '$dir' to '$new_dir'"
        fi
    fi
done
