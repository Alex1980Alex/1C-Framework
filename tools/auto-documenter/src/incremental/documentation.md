# Incremental Documentation Module

This module provides functionality for incremental documentation generation, focusing on processing only files that have changed since the last run. It utilizes file hashing, modification timestamps, and optionally Git to detect changes.

## `change-tracker.ts`

This file defines the core logic for tracking file changes.

### Key Concepts and Types

*   **`ChangeStatus`**: An enum representing the status of a file change: `added`, `modified`, `deleted`, or `unchanged`.
*   **`TrackedFile`**: An interface describing the metadata stored for each tracked file, including its path, content hash, modification timestamp, and size.
*   **`FileChange`**: An interface detailing a detected file change, including its path, status, and relevant hash information.
*   **`TrackingState`**: An interface representing the persistent state of the change tracker, storing version information, project root, last full run timestamp, tracked files, and the current Git commit hash.
*   **`ChangeTrackerConfig`**: An interface for configuring the change tracker, specifying the state file name, whether to use Git, tracked file extensions, and ignore patterns.
*   **`DEFAULT_TRACKER_CONFIG`**: The default configuration object for the `ChangeTracker`.

### Core Class: `ChangeTracker`

The `ChangeTracker` class manages the process of detecting and tracking file modifications.

*   **Constructor**: Initializes the tracker with a root directory and optional configuration.
*   **`loadState()`**: Loads the tracking state from a JSON file. If the file is missing or corrupted, it initializes a new state.
*   **`saveState()`**: Saves the current tracking state to the state file.
*   **`getGitCommit()`**: Retrieves the current Git commit hash if Git integration is enabled.
*   **`getGitChangedFiles()`**: Identifies files that have been changed according to Git history.
*   **`hashFile()`**: Calculates the MD5 hash of a file's content.
*   **`shouldTrack()`**: Determines if a file should be tracked based on its extension.
*   **`getFileInfo()`**: Gathers current metadata (path, hash, mtime, size) for a given file.
*   **`scanDirectory()`**: Recursively scans a directory, identifying files that match the configured extensions and are not excluded by ignore patterns.
*   **`detectChanges()`**: The primary method for detecting changes. It compares the current file state against the loaded tracking state, considering file hashes and Git status, to produce a list of `FileChange` objects.
*   **`markProcessed()`**: Updates the tracking state for a given list of files, marking them as processed with the current timestamp and potentially updating the Git commit hash.
*   **`markAllProcessed()`**: Resets the state and marks all currently scanned files as processed, typically used for a full regeneration.
*   **`reset()`**: Deletes the tracking state file, effectively resetting the tracker.
*   **`getStats()`**: Returns statistics about the tracking state, such as the total number of tracked files and the last full run information.

### Utility Function: `runIncremental`

This asynchronous function orchestrates the incremental documentation generation process.

*   It initializes a `ChangeTracker`.
*   If `force` option is enabled, it performs a full regeneration by resetting the tracker, processing all files, and marking them as processed.
*   For incremental runs, it detects changes, processes only added or modified files, and then marks both processed and deleted files.
*   It supports `dryRun` to simulate the process without actual file processing and `verbose` for more detailed output (though not explicitly implemented in the provided snippet, it's part of the interface).
*   It returns a summary of processed and skipped files, along with the detected changes.

## `index.ts`

This file serves as the main entry point for the incremental documentation module, exporting all public components from `change-tracker.ts`.