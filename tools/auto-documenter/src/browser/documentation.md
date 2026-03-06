# Documentation Browser Codebase Documentation

This document provides an overview of the files within this directory, explaining their purpose and how they interact to form the documentation browser.

## `index.ts`

This file serves as the main entry point and public API for the documentation browser library. It exports key components that users will interact with to start and manage the documentation server, scan for files, and render HTML content.

### Key Exports:

*   **`DocumentationServer`**: The primary class for creating and managing the HTTP server that serves the documentation.
*   **`ServerConfig`**: An interface defining the configuration options for the `DocumentationServer`.
*   **`DocumentationScanner`**: A class responsible for discovering and indexing documentation files within a specified directory.
*   **`DocFile`**: An interface representing metadata for each discovered documentation file.
*   **`HtmlRenderer`**: A class responsible for converting markdown content to HTML and generating the overall page structure.

## `renderer.ts`

This file contains the logic for transforming markdown content into HTML and for constructing the complete HTML pages that are served to the browser. It includes styling to present the documentation in a user-friendly format.

### Key Functionality:

*   **`markdownToHtml` function**: A utility function that performs a basic conversion of markdown syntax (headers, bold, italic, code blocks, links, lists, etc.) into corresponding HTML tags.
*   **`HtmlRenderer` class**:
    *   Manages the generation of HTML for different pages: the index, individual documentation files, search results, and 404 pages.
    *   Includes a `getStyles` method to provide the CSS for the documentation browser's appearance.
    *   Features a `renderTree` method to generate the navigation sidebar based on the directory structure.
    *   Provides methods like `renderIndex`, `renderDoc`, `renderSearch`, and `render404` to create the final HTML output for various scenarios.

## `scanner.ts`

This file is responsible for locating and gathering information about documentation files within a given directory structure. It scans the file system, identifies files based on specific patterns, and extracts relevant metadata.

### Key Components:

*   **`DocFile` interface**: Defines the structure for storing information about each documentation file, including its path, name, type, modification date, and extracted title.
*   **`DirNode` interface**: Represents a node in the directory tree structure, used for building the navigation sidebar.
*   **`DocumentationScanner` class**:
    *   The core class for the scanning process.
    *   The `scan` method initiates the discovery of documentation files.
    *   `scanDirectory` recursively traverses directories.
    *   `isDocFile` determines if a file matches the criteria for being a documentation file.
    *   `createDocFile` processes a discovered file to extract its metadata.
    *   `buildTree` constructs a hierarchical representation of the directories and files.
    *   Provides methods to retrieve the list of found files (`getDocFiles`), the directory tree (`getDirTree`), find a specific file by path (`findByPath`), perform searches (`search`), and get overall statistics (`getStats`).

## `server.ts`

This file implements the HTTP server that hosts the documentation browser. It uses the `DocumentationScanner` to find files and the `HtmlRenderer` to generate the web pages.

### Key Components:

*   **`ServerConfig` interface**: Defines the configuration options for the server, such as the root path, port, host, and browser title.
*   **`DocumentationServer` class**:
    *   The main class for the server.
    *   The `start` method initializes the scanner, builds the file tree, creates the HTTP server, and begins listening for requests.
    *   The `stop` method gracefully shuts down the server.
    *   `handleRequest` is the core request handler, routing incoming HTTP requests to the appropriate logic (serving the index, documentation files, search results, or API endpoints).
    *   Includes helper methods for sending HTML responses (`sendHtml`) and automatically opening the browser (`openBrowser`).
    *   Exposes methods to get the server URL (`getUrl`), check its status (`isRunning`), and retrieve scanned files and statistics.

### File Relationships:

*   `index.ts` acts as the main export point, providing access to `DocumentationServer`, `DocumentationScanner`, and `HtmlRenderer`.
*   `server.ts` utilizes `DocumentationScanner` to gather file information and `HtmlRenderer` to generate the HTML content for the web pages it serves.
*   `scanner.ts` provides the data (files and directory structure) that `server.ts` and `renderer.ts` consume.
*   `renderer.ts` takes the data from `scanner.ts` and transforms it into user-facing HTML, which is then served by `server.ts`.