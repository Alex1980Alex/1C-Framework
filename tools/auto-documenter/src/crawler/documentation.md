# Code Documentation

This document provides an overview of the code files in this directory, explaining their functionality and relationships.

## `gitignore.ts`

This file defines a `GitIgnoreParser` class responsible for parsing and applying `.gitignore` rules.

### Key Functionality:

*   **Loading Rules**: Reads the `.gitignore` file from a specified root path and parses its content to establish ignore patterns.
*   **Ignoring Paths**: Provides a method to check if a given file path should be ignored based on the loaded `.gitignore` rules.
*   **Filtering Paths**: Offers a utility to filter an array of file paths, returning only those that are not ignored.

### Relationships:

*   This class is used by `DirectoryCrawler` when the `respectGitignore` option is enabled to avoid processing ignored files and directories.

## `index.ts`

This file contains the `DirectoryCrawler` class, which is the main component for traversing file system directories and gathering information about their structure and content.

### Key Functionality:

*   **Directory Scanning**: Recursively scans a given directory, building a tree structure (`Directory` interface) that represents subdirectories and files. It respects `.gitignore` rules and can optionally include hidden files.
*   **Leaf Directory Identification**: Finds and returns a list of all directories that contain no subdirectories.
*   **Bottom-Up Order**: Generates an ordered list of directories, processing child directories before their parents.
*   **Code File Extraction**: Identifies and returns files within a directory that match configured code extensions, while also respecting `.gitignore` and hidden file rules.
*   **Documentation File Retrieval**: Checks for and returns the path to a documentation file (based on configuration) within a given directory.
*   **Subdirectory Checks**: Determines if a directory contains any subdirectories and identifies "single-file" subdirectories (those containing only one code file).
*   **Subdirectory Documentation Retrieval**: Collects documentation content from any subdirectories that have their own documentation files.
*   **File Content Reading**: Reads the content of a specified file, with a safeguard against excessively large files.

### Interfaces:

*   **`Directory`**: Defines the structure for representing a directory in the file system, including its path, name, subdirectories, files, and a flag indicating if it's a leaf directory.
*   **`CrawlerOptions`**: Specifies configuration options for the `DirectoryCrawler`, such as whether to respect `.gitignore` and whether to include hidden files.

### Relationships:

*   This class orchestrates the directory traversal and file analysis.
*   It utilizes the `GitIgnoreParser` from `gitignore.ts` when configured to respect `.gitignore` rules.
*   It relies on configuration settings obtained from `../config.js` (not detailed here).