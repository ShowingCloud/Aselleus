#!/usr/bin/env python

# Thanks to Perplexity

import os
import sys
import json
import hashlib
import tarfile

def gather_metadata(directory):
    metadata = []
    olddir = os.getcwd()
    os.chdir(directory)
    for root, dirs, files in os.walk('.'):
        for file in files:
            path = os.path.join(root, file)
            stats = os.stat(path)
            # Calculate a hash of the file content for unique identification
            with open(path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
            metadata.append({
                "file_name": os.path.relpath(path),
                "size": stats.st_size,
                "last_modified": stats.st_mtime,
                "hash": file_hash  # Store the hash for comparison
            })
    os.chdir(olddir)
    return metadata

def save_metadata(metadata, filename):
    with open(filename, 'w') as f:
        json.dump(metadata, f)

def compare_metadata(old_file, new_file):
    with open(old_file) as f:
        old_data = json.load(f)
    with open(new_file) as f:
        new_data = json.load(f)

    # Create dictionaries to map file names and hashes
    old_names = {file['file_name']: file for file in old_data}
    new_names = {file['file_name']: file for file in new_data}

    added_files = set(new_names) - set(old_names)
    removed_files = set(old_names) - set(new_names)

    # Detect modified or renamed files
    modified_files = {}
    renamed_files = {}

    for name in new_names:
        if name in old_names:
            # Check if the hash has changed (indicating content change)
            if old_names[name]['hash'] != new_names[name]['hash']:
                modified_files[name] = new_names[name]
        else:
            # If the name is not found in old_names, check if the hash matches any old file
            for old_name, old_file in old_names.items():
                if new_names[name]['hash'] == old_file['hash']:
                    renamed_files[old_name] = name  # Old name to new name mapping

    return added_files, removed_files, modified_files, renamed_files

def pack_modified_files(directory, output_filename, added_files, modified_files):
    with tarfile.open(output_filename, 'w:gz') as tar:
        # Pack added files
        for file_name in added_files:
            full_path = os.path.join(directory, file_name)
            tar.add(full_path, arcname=file_name)  # Keep relative path

        # Pack modified files
        for file_name in modified_files.keys():
            full_path = os.path.join(directory, file_name)
            tar.add(full_path, arcname=file_name)  # Keep relative path


if __name__ == '__main__':
    # Usage
    directory_path = sys.argv[1]
    metadata = gather_metadata(directory_path)
    if (directory_path[-1] == '/'):
        directory_path = directory_path[:-1]
    save_metadata(metadata, directory_path + '.json')

    if (len(sys.argv) > 2):
        # Compare with previous metadata
        added, removed, modified, renamed = compare_metadata(sys.argv[2], directory_path + '.json')

        print("Added files:", added)
        print("Removed files:", removed)
        print("Modified files:", modified)
        print("Renamed files:", renamed)

    if (len(sys.argv) > 3):
        pack_modified_files(directory_path, sys.argv[3], added, modified)
