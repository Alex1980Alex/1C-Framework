/**
 * @file Jest test suite for Task ID 1: Implement Task Data Structure.
 * @description This file contains comprehensive tests for the task data model,
 * validation functions, and file system operations (read/write) related to `tasks.json`.
 * It uses Jest and mocks the 'fs' module to isolate file operations for testing.
 */

// Import Jest functions and types
import { describe, it, expect, jest, beforeEach, afterEach } from '@jest/globals';

// Import Node.js 'fs' module for mocking
import * as fs from 'fs';

// --- Hypothetical Module Imports ---
// These would be the actual modules implemented for the task.
// For this test file to be self-contained, we'll define placeholder
// interfaces and functions below, as if they were imported.

/*
// Example of real imports:
import {
  Task,
  TaskStatus,
  TaskPriority,
  Subtask,
  validateTask,
  validateTasks,
  readTasksFromFile,
  writeTasksToFile,
} from '../src/task-management';
*/

// --- Start: Placeholder Implementations for Demonstration ---
// In a real project, these types and functions would be in separate source files.

type TaskStatus = 'todo' | 'in-progress' | 'done' | 'blocked';
type TaskPriority = 'low' | 'medium' | 'high' | 'critical';

interface Subtask {
  id: number;
  title: string;
  completed: boolean;
}

interface Task {
  id: number;
  title: string;
  description: string;
  status: TaskStatus;
  dependencies: number[];
  priority: TaskPriority;
  details?: Record<string, any>;
  testStrategy: string;
  subtasks: Subtask[];
}

/**
 * Validates a single task object.
 * This is a simplified validator for demonstration. A real implementation
 * would likely use a schema validation library like Zod or Ajv.
 */
function validateTask(task: any): task is Task {
  if (!task || typeof task !== 'object') return false;
  const hasId = typeof task.id === 'number';
  const hasTitle = typeof task.title === 'string' && task.title.length > 0;
  const hasDescription = typeof task.description === 'string';
  const hasStatus = ['todo', 'in-progress', 'done', 'blocked'].includes(task.status);
  const hasDependencies = Array.isArray(task.dependencies) && task.dependencies.every((d: any) => typeof d === 'number');
  const hasPriority = ['low', 'medium', 'high', 'critical'].includes(task.priority);
  const hasTestStrategy = typeof task.testStrategy === 'string';
  const hasSubtasks = Array.isArray(task.subtasks);

  return hasId && hasTitle && hasDescription && hasStatus && hasDependencies && hasPriority && hasTestStrategy && hasSubtasks;
}

/**
 * Validates an array of task objects.
 */
function validateTasks(tasks: any): tasks is Task[] {
  if (!Array.isArray(tasks)) return false;
  return tasks.every(validateTask);
}

const TASKS_FILE_PATH = 'tasks.json';

/**
 * Reads and validates tasks from a JSON file.
 */
function readTasksFromFile(filePath: string): Task[] {
  if (!fs.existsSync(filePath)) {
    throw new Error(`File not found: ${filePath}`);
  }
  const fileContent = fs.readFileSync(filePath, 'utf-8');
  if (fileContent.trim() === '') {
    return [];
  }
  const data = JSON.parse(fileContent);
  if (!validateTasks(data)) {
    throw new Error('Invalid task data structure in file.');
  }
  return data;
}

/**
 * Writes an array of tasks to a JSON file after validation.
 */
function writeTasksToFile(filePath: string, tasks: Task[]): void {
  if (!validateTasks(tasks)) {
    throw new Error('Attempted to write invalid task data.');
  }
  const data = JSON.stringify(tasks, null, 2);
  fs.writeFileSync(filePath, data, 'utf-8');
}

// --- End: Placeholder Implementations ---


// Mock the entire 'fs' module.
jest.mock('fs');

// Create a typed mock object for 'fs' to provide type-safe mock implementations.
const mockedFs = fs as jest.Mocked<typeof fs>;

// Main test suite for the Task Data Structure implementation.
describe('Task Data Structure and File Operations (Task ID: 1)', () => {
  // --- Test Data Setup ---
  const validTask1: Task = {
    id: 1,
    title: 'Implement Task Data Structure',
    description: 'Design and implement the core tasks.json structure.',
    status: 'done',
    dependencies: [],
    priority: 'high',
    details: {
      schemaVersion: '1.0.0',
    },
    testStrategy: 'Verify creation, reading, and validation of tasks.json.',
    subtasks: [
      { id: 101, title: 'Define JSON schema', completed: true },
      { id: 102, title: 'Create Task model', completed: true },
    ],
  };

  const validTask2: Task = {
    id: 2,
    title: 'Develop API Endpoints',
    description: 'Create REST API endpoints for tasks.',
    status: 'todo',
    dependencies: [1],
    priority: 'medium',
    testStrategy: 'Integration tests for all CRUD operations.',
    subtasks: [],
  };

  const validTasksArray: Task[] = [validTask1, validTask2];

  // Reset mocks before each test to ensure test isolation.
  beforeEach(() => {
    jest.resetAllMocks();
  });

  // --- Test Suite for Model Validation ---
  describe('Task Model Validation', () => {
    it('should return true for a valid task object', () => {
      expect(validateTask(validTask1)).toBe(true);
    });

    it('should return true for a valid array of tasks', () => {
      expect(validateTasks(validTasksArray)).toBe(true);
    });

    it('should return false for a task with a missing required field (title)', () => {
      const invalidTask = { ...validTask1, title: undefined };
      expect(validateTask(invalidTask)).toBe(false);
    });

    it('should return false for a task with an invalid status value', () => {
      const invalidTask = { ...validTask1, status: 'pending' };
      expect(validateTask(invalidTask)).toBe(false);
    });

    it('should return false for a task with an incorrect data type for a field (id)', () => {
      const invalidTask = { ...validTask1, id: 'task-1' };
      expect(validateTask(invalidTask)).toBe(false);
    });

    it('should return false for an array containing an invalid task', () => {
      const invalidTask = { ...validTask1, priority: 'urgent' };
      const invalidArray = [validTask2, invalidTask];
      expect(validateTasks(invalidArray)).toBe(false);
    });

    it('should return false for a non-array input to validateTasks', () => {
      expect(validateTasks({ task: 1 })).toBe(false);
    });

    it('should return false for a non-object input to validateTask', () => {
      expect(validateTask(null)).toBe(false);
      expect(validateTask(123)).toBe(false);
    });
  });

  // --- Test Suite for File System Read Operations ---
  describe('readTasksFromFile', () => {
    it('should correctly read and parse a valid tasks.json file', () => {
      // Arrange: Mock file system to simulate an existing, valid file.
      mockedFs.existsSync.mockReturnValue(true);
      mockedFs.readFileSync.mockReturnValue(JSON.stringify(validTasksArray));

      // Act: Call the function to read tasks.
      const tasks = readTasksFromFile(TASKS_FILE_PATH);

      // Assert: Verify the file was read and the data is correct.
      expect(mockedFs.readFileSync).toHaveBeenCalledWith(TASKS_FILE_PATH, 'utf-8');
      expect(tasks).toEqual(validTasksArray);
    });

    it('should throw an error if the file does not exist', () => {
      // Arrange: Mock file system to simulate a non-existent file.
      mockedFs.existsSync.mockReturnValue(false);

      // Act & Assert: Expect the function to throw a specific error.
      expect(() => readTasksFromFile(TASKS_FILE_PATH)).toThrow(`File not found: ${TASKS_FILE_PATH}`);
    });

    it('should throw an error if the file content is not valid JSON', () => {
      // Arrange: Mock an existing file with malformed JSON content.
      mockedFs.existsSync.mockReturnValue(true);
      mockedFs.readFileSync.mockReturnValue('{ "id": 1, "title": "Incomplete JSON"');

      // Act & Assert: Expect a JSON parsing error.
      expect(() => readTasksFromFile(TASKS_FILE_PATH)).toThrow(SyntaxError);
    });

    it('should throw a validation error if file content does not match the task schema', () => {
      // Arrange: Mock a file with valid JSON but an invalid task structure.
      const invalidData = [{ ...validTask1, status: 'invalid-status' }];
      mockedFs.existsSync.mockReturnValue(true);
      mockedFs.readFileSync.mockReturnValue(JSON.stringify(invalidData));

      // Act & Assert: Expect a custom validation error.
      expect(() => readTasksFromFile(TASKS_FILE_PATH)).toThrow('Invalid task data structure in file.');
    });

    it('should return an empty array if the file exists but is empty', () => {
      // Arrange: Mock an existing but empty file.
      mockedFs.existsSync.mockReturnValue(true);
      mockedFs.readFileSync.mockReturnValue('');

      // Act: Read the empty file.
      const tasks = readTasksFromFile(TASKS_FILE_PATH);

      // Assert: The result should be an empty array.
      expect(tasks).toEqual([]);
    });
  });

  // --- Test Suite for File System Write Operations ---
  describe('writeTasksToFile', () => {
    it('should write the tasks array to a file with correct formatting', () => {
      // Arrange: Prepare the data to be written.
      const expectedJsonString = JSON.stringify(validTasksArray, null, 2);

      // Act: Call the function to write tasks.
      writeTasksToFile(TASKS_FILE_PATH, validTasksArray);

      // Assert: Verify that writeFileSync was called with the correct path and data.
      expect(mockedFs.writeFileSync).toHaveBeenCalledTimes(1);
      expect(mockedFs.writeFileSync).toHaveBeenCalledWith(TASKS_FILE_PATH, expectedJsonString, 'utf-8');
    });

    it('should throw an error if the provided task data is invalid', () => {
      // Arrange: Create an array with an invalid task.
      const invalidData = [{ ...validTask1, title: '' }]; // Invalid title

      // Act & Assert: Expect a validation error and ensure file is not written.
      expect(() => writeTasksToFile(TASKS_FILE_PATH, invalidData as any)).toThrow('Attempted to write invalid task data.');
      expect(mockedFs.writeFileSync).not.toHaveBeenCalled();
    });

    it('should propagate errors from the file system during write', () => {
      // Arrange: Mock writeFileSync to throw a permission error.
      const writeError = new Error('EACCES: permission denied');
      mockedFs.writeFileSync.mockImplementation(() => {
        throw writeError;
      });

      // Act & Assert: Ensure the error from fs is thrown by the function.
      expect(() => writeTasksToFile(TASKS_FILE_PATH, validTasksArray)).toThrow(writeError);
    });
  });
});