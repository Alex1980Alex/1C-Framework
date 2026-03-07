/**
 * @file Jest test suite for Task Data Structure (Task ID: 1)
 * @description This file contains tests for the core task data structure,
 * including model validation, and file system operations for reading and writing
 * the tasks.json file. It utilizes mocking for the 'fs/promises' module to
 * isolate tests from the actual file system.
 */

// Import Jest functions
import { describe, it, expect, jest, beforeEach, afterEach } from '@jest/globals';

// Mock the 'fs/promises' module before any imports that might use it.
// This is crucial for ensuring our tests don't perform real file I/O.
import * as fs from 'fs/promises';
jest.mock('fs/promises');

// Import the functions and types to be tested.
// NOTE: These are assumed to exist in a './taskData' file based on the task description.
import {
  Task,
  Status,
  Priority,
  validateTask,
  validateTasks,
  readTasks,
  writeTasks,
} from './taskData';

// Cast the mocked fs module to its mocked type to allow for mock function assertions.
const mockedFs = fs as jest.Mocked<typeof fs>;

// --- Test Data ---

const validSubtask: Task = {
  id: 101,
  title: 'Subtask 1',
  description: 'A nested subtask.',
  status: Status.ToDo,
  dependencies: [],
  priority: Priority.Medium,
  details: 'Subtask details here.',
  testStrategy: 'Unit test the subtask logic.',
  subtasks: [],
};

const validTask: Task = {
  id: 1,
  title: 'Implement Task Data Structure',
  description: 'Design and implement the core tasks.json structure.',
  status: Status.Done,
  dependencies: [],
  priority: Priority.High,
  details: 'Create the foundational data structure including schema, model, validation, and file operations.',
  testStrategy: 'Verify that the tasks.json structure can be created, read, and validated.',
  subtasks: [validSubtask],
};

const minimalValidTask: Task = {
  id: 2,
  title: 'Minimal Task',
  description: '',
  status: Status.InProgress,
  dependencies: [],
  priority: Priority.Low,
  details: '',
  testStrategy: '',
  subtasks: [],
};

const validTasksArray: Task[] = [validTask, minimalValidTask];

// --- Test Suite ---

describe('Task Data Structure and Operations (Task ID: 1)', () => {
  // Reset mocks before each test to ensure a clean state.
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Task Model Validation', () => {
    describe('validateTask', () => {
      it('should return true for a complete and valid task object', () => {
        expect(() => validateTask(validTask)).not.toThrow();
      });

      it('should return true for a minimal but valid task object', () => {
        expect(() => validateTask(minimalValidTask)).not.toThrow();
      });

      it('should throw an error if the id is missing', () => {
        const invalid = { ...validTask, id: undefined } as any;
        expect(() => validateTask(invalid)).toThrow('Task validation failed: "id" is required');
      });

      it('should throw an error if the title is missing', () => {
        const invalid = { ...validTask, title: undefined } as any;
        expect(() => validateTask(invalid)).toThrow('Task validation failed: "title" is required');
      });

      it('should throw an error if the status is invalid', () => {
        const invalid = { ...validTask, status: 'Pending Review' } as any;
        expect(() => validateTask(invalid)).toThrow('Task validation failed: "status" must be one of [todo, in-progress, done, blocked]');
      });

      it('should throw an error if a field has an incorrect type', () => {
        const invalid = { ...validTask, priority: 'High' } as any;
        expect(() => validateTask(invalid)).toThrow('Task validation failed: "priority" must be a number');
      });

      it('should throw an error if dependencies is not an array of numbers', () => {
        const invalid = { ...validTask, dependencies: ['task-2'] } as any;
        expect(() => validateTask(invalid)).toThrow('Task validation failed: "dependencies[0]" must be a number');
      });

      it('should recursively validate subtasks and throw on invalid subtask', () => {
        const invalidSubtask = { ...validSubtask, title: null } as any;
        const taskWithInvalidSubtask = { ...validTask, subtasks: [invalidSubtask] };
        expect(() => validateTask(taskWithInvalidSubtask)).toThrow('Task validation failed: "subtasks[0].title" must be a string');
      });
    });

    describe('validateTasks (Array Validation)', () => {
      it('should not throw for a valid array of tasks', () => {
        expect(() => validateTasks(validTasksArray)).not.toThrow();
      });

      it('should not throw for an empty array', () => {
        expect(() => validateTasks([])).not.toThrow();
      });

      it('should throw an error if the input is not an array', () => {
        expect(() => validateTasks({} as any)).toThrow('Input must be an array of tasks.');
      });

      it('should throw an error if any task in the array is invalid', () => {
        const invalid = { ...validTask, id: undefined } as any;
        const invalidArray = [validTask, invalid];
        expect(() => validateTasks(invalidArray)).toThrow('Task validation failed for task at index 1: "id" is required');
      });
    });
  });

  describe('File System Operations - readTasks', () => {
    const filePath = 'data/tasks.json';

    it('should correctly read, parse, and validate tasks from a file', async () => {
      const fileContent = JSON.stringify(validTasksArray);
      mockedFs.readFile.mockResolvedValue(fileContent);

      const tasks = await readTasks(filePath);

      expect(mockedFs.readFile).toHaveBeenCalledWith(filePath, 'utf-8');
      expect(tasks).toEqual(validTasksArray);
    });

    it('should throw an error if the file does not exist', async () => {
      const error = new Error('ENOENT: no such file or directory');
      mockedFs.readFile.mockRejectedValue(error);

      await expect(readTasks(filePath)).rejects.toThrow('Error reading file data/tasks.json: ENOENT: no such file or directory');
    });

    it('should throw an error for malformed JSON content', async () => {
      const malformedJson = '[{"id": 1, "title": "Incomplete"}]'; // Missing closing brace
      mockedFs.readFile.mockResolvedValue(malformedJson);

      await expect(readTasks(filePath)).rejects.toThrow(/Unexpected end of JSON input/);
    });

    it('should throw a validation error if file content is valid JSON but invalid task data', async () => {
      const invalidTaskData = [{ ...validTask, status: 'invalid_status' }];
      const fileContent = JSON.stringify(invalidTaskData);
      mockedFs.readFile.mockResolvedValue(fileContent);

      // This assumes readTasks calls the validation function internally.
      await expect(readTasks(filePath)).rejects.toThrow('Task validation failed for task at index 0: "status" must be one of [todo, in-progress, done, blocked]');
    });
  });

  describe('File System Operations - writeTasks', () => {
    const filePath = 'data/tasks.json';

    it('should stringify and write an array of tasks to a file', async () => {
      // Mock writeFile to resolve successfully, indicating the write was successful.
      mockedFs.writeFile.mockResolvedValue(undefined);

      await writeTasks(filePath, validTasksArray);

      // Verify that writeFile was called exactly once.
      expect(mockedFs.writeFile).toHaveBeenCalledTimes(1);

      // Verify the arguments passed to writeFile.
      // The data should be pretty-printed JSON (indentation of 2 spaces).
      const expectedContent = JSON.stringify(validTasksArray, null, 2);
      expect(mockedFs.writeFile).toHaveBeenCalledWith(filePath, expectedContent, 'utf-8');
    });

    it('should throw a validation error before writing if task data is invalid', async () => {
      const invalidArray = [{ ...validTask, id: 'task-1' } as any];

      // We expect writeTasks to throw a validation error.
      await expect(writeTasks(filePath, invalidArray)).rejects.toThrow('Task validation failed for task at index 0: "id" must be a number');

      // Crucially, we assert that the file system write operation was never attempted.
      expect(mockedFs.writeFile).not.toHaveBeenCalled();
    });

    it('should throw an error if writing to the file system fails', async () => {
      const writeError = new Error('EACCES: permission denied');
      mockedFs.writeFile.mockRejectedValue(writeError);

      await expect(writeTasks(filePath, validTasksArray)).rejects.toThrow('Error writing file data/tasks.json: EACCES: permission denied');

      // Verify that we did attempt to write the file.
      expect(mockedFs.writeFile).toHaveBeenCalledTimes(1);
    });
  });
});