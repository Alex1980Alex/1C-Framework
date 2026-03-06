# Documentation for Watch Mode Module

This module provides functionality for watching file system changes and triggering actions based on those changes, primarily for documentation regeneration in "watch mode."

## `file-watcher.ts`

This file contains the core logic for monitoring file system events.

### Key Classes:

*   **`FileWatcher`**:
    *   Manages the process of watching directories for file changes.
    *   Accepts configuration options for inclusion/exclusion patterns, debouncing, recursion, and polling.
    *   Emits events for individual file changes (`change`), batched changes (`batch`), errors (`error`), and readiness (`ready`).
    *   Provides `start()` and `stop()` methods to control the watching process.
    *   Includes a `shouldWatch()` method to determine if a file path matches the configured patterns.

*   **`WatchModeRunner`**:
    *   Orchestrates the watch mode experience.
    *   Initializes and manages a `FileWatcher` instance.
    *   Defines a `regenerate` callback function that is executed when file changes are detected.
    *   Logs watch mode status, detected changes, and regeneration progress to the console.
    *   Tracks the number of regenerations and the time of the last regeneration.
    *   Provides `start()` and `stop()` methods to control the watch mode.

### Key Interfaces:

*   **`WatchOptions`**: Defines the configuration parameters for the `FileWatcher`, including `include`, `exclude`, `debounceMs`, `recursive`, and `pollIntervalMs`.
*   **`FileChangeEvent`**: Represents a single file system event, including its `type` (`add`, `change`, `unlink`), `path`, and `timestamp`.
*   **`FileChangeBatch`**: Groups multiple `FileChangeEvent`s that occur within a debounced interval. It includes a list of all `changes`, unique `files` affected, and the `startTime` and `endTime` of the batch.
*   **`FileWatcherEvents`**: Defines the event types emitted by the `FileWatcher` class.
*   **`WatchHandler`**: An interface for consumers of the `FileWatcher` to define how they want to handle `batch`, `error`, and `ready` events.

### Key Functions:

*   **`createWatcher`**: A factory function that creates a `FileWatcher` instance and attaches event listeners to a provided `WatchHandler`. It simplifies the setup of a watcher with custom logic.

## `index.ts`

This file serves as the main entry point for the watch mode module. It re-exports all the necessary components from `file-watcher.ts`, making them available for import from the top-level module.