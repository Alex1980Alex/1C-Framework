/**
 * @file Jest tests for Task 1: Implement Task Data Structure.
 * @description This test file covers the validation, reading, and writing of the core task data structure.
 * It mocks the file system to test file operations in isolation and ensures that the data model
 * validation logic correctly identifies both valid and invalid task objects.
 */

import * as fs from 'fs';
import {
  // Assuming these are the interfaces and types defined in the implementation
  Task,
  TaskStatus,
  TaskPriority,
  // Assuming these are the functions exported by the implementation module
  validateTask,
  validateTasks,
  readTasksFromFile,
  writeTasksToFile,
} from './taskData'; // The module to be tested

// Mock the entire 'fs' module.
// This allows us to control the behavior of file system operations like readFileSync and writeFileSync
// without actually touching the disk.
jest.mock('fs');

// Type-safe mock for the fs module
const mockedFs = fs as jest.Mocked<typeof fs>;

// --- Test Data ---

const validSubtask: Task = {
  id: 'sub-001',
  title: 'Implement subtask validation',
  description: 'Write validation logic for subtasks.',
  status: 'todo',
  dependencies: [],
  priority: 'medium',
  details: 'Subtasks should have a simplified structure.',
  testStrategy: 'Unit tests for subtask validation function.',
  subtasks: [],
};

const validTask: Task = {
  id: 'task-001',
  title: 'Implement Core Authentication',
  description: 'Set up JWT-based authentication for the API.',
  status: 'in-progress',
  dependencies: ['task-000'],
  priority: 'high',
  details: 'Use passport-jwt strategy. Store secrets in environment variables.',
  testStrategy: 'Integration tests for login and protected endpoints.',
  subtasks: [validSubtask],
};

const validTasksArray: Task[] = [
  {
    id: 'task-002',
    title: 'Setup Database Schema',
    description: 'Define and migrate the initial database schema.',
    status: 'done',
    dependencies: [],
    priority: 'critical',
    details: 'Use PostgreSQL as the database.',
    testStrategy: 'Verify schema migration scripts run successfully.',
    subtasks: [],
  },
  validTask,
];

// --- Test Suites ---

describe('Task 1: Task Data Structure and Operations', () => {
  beforeEach(() => {
    // Clear all mock implementations and call history before each test
    jest.clearAllMocks();
  });

  describe('Task Model Validation (validateTask)', () => {
    it('should return true for a completely valid task object', () => {
      expect(validateTask(validTask)).toBe(true);
    });

    it('should return true for a minimal valid task object', () => {
      const minimalTask: Task = {
        id: 'min-01',
        title: 'Minimal Task',
        description: '',
        status: 'todo',
        dependencies: [],
        priority: 'low',
        details: '',
        testStrategy: '',
        subtasks: [],
      };
      expect(validateTask(minimalTask)).toBe(true);
    });

    // Test for invalid or missing fields
    const requiredFields: (keyof Task)[] = ['id', 'title', 'status', 'priority'];
    requiredFields.forEach((field) => {
      it(`should return false if required field "${field}" is missing`, () => {
        const invalidTask = { ...validTask };
        delete invalidTask[field];
        expect(validateTask(invalidTask)).toBe(false);
      });
    });

    // Test for incorrect data types
    it('should return false if "id" is not a string', () => {
      const invalidTask = { ...validTask, id: 123 };
      expect(validateTask(invalidTask)).toBe(false);
    });

    it('should return false if "dependencies" is not an array of strings', () => {
      const invalidTask = { ...validTask, dependencies: [123] };
      expect(validateTask(invalidTask)).toBe(false);
    });

    it('should return false if "subtasks" is not an array of task objects', () => {
      const invalidTask = { ...validTask, subtasks: [{ id: 'sub-01' }] }; // Missing fields in subtask
      expect(validateTask(invalidTask)).toBe(false);
    });

    // Test for invalid enum values
    it('should return false for an invalid "status" value', () => {
      const invalidTask = { ...validTask, status: 'pending_review' as TaskStatus };
      expect(validateTask(invalidTask)).toBe(false);
    });

    it('should return false for an invalid "priority" value', () => {
      const invalidTask = { ...validTask, priority: 'urgent' as TaskPriority };
      expect(validateTask(invalidTask)).toBe(false);
    });

    it('should return false for a non-object input', () => {
      expect(validateTask(null)).toBe(false);
      expect(validateTask(undefined)).toBe(false);
      expect(validateTask('a string')).toBe(false);
      expect(validateTask(123)).toBe(false);
    });
  });

  describe('Task Array Validation (validateTasks)', () => {
    it('should return true for a valid array of task objects', () => {
      expect(validateTasks(validTasksArray)).toBe(true);
    });

    it('should return true for an empty array', () => {
      expect(validateTasks([])).toBe(true);
    });

    it('should return false if the array contains an invalid task object', () => {
      const invalidArray = [...validTasksArray];
      const invalidTask = { ...validTask, title: undefined }; // Make one task invalid
      invalidArray.push(invalidTask as Task);
      expect(validateTasks(invalidArray)).toBe(false);
    });

    it('should return false for a non-array input', () => {
      expect(validateTasks(validTask)).toBe(false);
      expect(validateTasks(null)).toBe(false);
      expect(validateTasks({})).toBe(false);
    });
  });

  describe('File System Operations', () => {
    const filePath = 'tasks.json';

    describe('readTasksFromFile', () => {
      it('should correctly read and parse a valid tasks.json file', async () => {
        const fileContent = JSON.stringify(validTasksArray);
        mockedFs.readFileSync.mockReturnValue(fileContent);

        const tasks = await readTasksFromFile(filePath);
        expect(tasks).toEqual(validTasksArray);
        expect(mockedFs.readFileSync).toHaveBeenCalledWith(filePath, 'utf-8');
      });

      it('should throw an error if the file content is not valid JSON', async () => {
        const invalidJson = '{ "id": "task-001", "title": "Unclosed quote... }';
        mockedFs.readFileSync.mockReturnValue(invalidJson);

        await expect(readTasksFromFile(filePath)).rejects.toThrow(
          'Failed to parse JSON from tasks.json: Unexpected token } in JSON at position 50'
        );
      });

      it('should throw a validation error if JSON is valid but task structure is not', async () => {
        const invalidTaskData = [{ id: 'task-001', title: 'Incomplete Task' }]; // Missing fields
        const fileContent = JSON.stringify(invalidTaskData);
        mockedFs.readFileSync.mockReturnValue(fileContent);

        await expect(readTasksFromFile(filePath)).rejects.toThrow(
          'Data in tasks.json is not a valid task array.'
        );
      });

      it('should throw an error if the file does not exist', async () => {
        const fileNotFoundError = new Error("ENOENT: no such file or directory, open 'tasks.json'");
        (fileNotFoundError as any).code = 'ENOENT';
        mockedFs.readFileSync.mockImplementation(() => {
          throw fileNotFoundError;
        });

        await expect(readTasksFromFile(filePath)).rejects.toThrow(
          "File not found at tasks.json"
        );
      });

      it('should propagate other file system errors', async () => {
        const permissionError = new Error("EACCES: permission denied, open 'tasks.json'");
        (permissionError as any).code = 'EACCES';
        mockedFs.readFileSync.mockImplementation(() => {
          throw permissionError;
        });

        await expect(readTasksFromFile(filePath)).rejects.toThrow(permissionError);
      });
    });

    describe('writeTasksToFile', () => {
      it('should stringify and write valid task data to the specified file', async () => {
        // We don't need a return value for writeFileSync, just to check if it was called correctly.
        mockedFs.writeFileSync.mockImplementation(() => {});

        await writeTasksToFile(filePath, validTasksArray);

        const expectedFileContent = JSON.stringify(validTasksArray, null, 2);

        expect(mockedFs.writeFileSync).toHaveBeenCalledTimes(1);
        expect(mockedFs.writeFileSync).toHaveBeenCalledWith(
          filePath,
          expectedFileContent,
          'utf-8'
        );
      });

      it('should throw a validation error before writing if data is invalid', async () => {
        const invalidData = [{ id: 'invalid' }]; // Not a valid Task array

        await expect(writeTasksToFile(filePath, invalidData as Task[])).rejects.toThrow(
          'Attempted to write invalid task data.'
        );

        // Crucially, ensure no attempt was made to write to the file system
        expect(mockedFs.writeFileSync).not.toHaveBeenCalled();
      });

      it('should throw an error if the file system write operation fails', async () => {
        const permissionError = new Error('EACCES: permission denied');
        mockedFs.writeFileSync.mockImplementation(() => {
          throw permissionError;
        });

        await expect(writeTasksToFile(filePath, validTasksArray)).rejects.toThrow(
          permissionError
        );

        expect(mockedFs.writeFileSync).toHaveBeenCalledTimes(1);
      });
    });
  });
});