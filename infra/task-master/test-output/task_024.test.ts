/**
 * @file Jest test suite for the 'generate-test' command.
 * @description This file contains comprehensive tests for the AI-powered test generation command,
 * covering success scenarios, error handling, input validation, and interactions with mocked
 * external services like the Claude API and the file system.
 */

import { handleGenerateTestCommand } from '../src/commands/generateTestCommand'; // Assuming the handler is in this path
import { taskStore } from '../src/services/taskStore'; // Assuming a singleton task store
import { claudeApiService } from '../src/services/claudeApiService'; // Assuming Claude API service
import * as fs from 'fs';
import { Task, Subtask } from '../src/types'; // Assuming types are defined here

// Mock external dependencies
jest.mock('../src/services/taskStore');
jest.mock('../src/services/claudeApiService');
jest.mock('fs');

// Type-safe mock objects
const mockedTaskStore = taskStore as jest.Mocked<typeof taskStore>;
const mockedClaudeApiService = claudeApiService as jest.Mocked<typeof claudeApiService>;
const mockedFs = fs as jest.Mocked<typeof fs>;

// --- Test Fixtures ---

const sampleParentTask: Task = {
  id: 24,
  title: 'Implement AI-Powered Test Generation Command',
  status: 'in-progress',
  description: 'Create a new \'generate-test\' command in Task Master that leverages AI to automatically produce Jest test files for tasks based on their descriptions and subtasks, utilizing Claude API for AI integration.',
  implementationDetails: 'Implement a new command in the Task Master CLI...',
  dependencies: [22],
  subtasks: [
    { id: 1, title: 'Create command structure for \'generate-test\'', status: 'done' },
    { id: 2, title: 'Implement AI prompt construction and FastMCP integration', status: 'in-progress' },
  ],
};

const sampleSubtask: Subtask = {
  id: 1,
  parentId: 24,
  title: 'Create command structure for \'generate-test\'',
  status: 'done',
  description: 'Set up the basic command in the CLI framework, including argument parsing for the task ID.',
};

const aiGeneratedTestContent = `
import { someFunction } from './someModule';

describe('someFunction', () => {
  it('should do something correctly', () => {
    expect(someFunction()).toBe(true);
  });
});
`;

describe('generate-test Command', () => {
  let consoleLogSpy: jest.SpyInstance;
  let consoleErrorSpy: jest.SpyInstance;

  beforeEach(() => {
    // Reset mocks before each test to ensure isolation
    jest.clearAllMocks();

    // Spy on console methods to capture output without polluting test logs
    consoleLogSpy = jest.spyOn(console, 'log').mockImplementation(() => {});
    consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    // Restore original console methods
    jest.restoreAllMocks();
  });

  describe('Success Scenarios', () => {
    it('should generate a test file for a parent task successfully', async () => {
      // Arrange
      mockedTaskStore.getTaskById.mockReturnValue(sampleParentTask);
      mockedClaudeApiService.generateText.mockResolvedValue(aiGeneratedTestContent);

      // Act
      await handleGenerateTestCommand({ id: '24' });

      // Assert
      expect(mockedTaskStore.getTaskById).toHaveBeenCalledWith(24);
      expect(mockedClaudeApiService.generateText).toHaveBeenCalledTimes(1);

      // Verify prompt construction
      const prompt = mockedClaudeApiService.generateText.mock.calls[0][0];
      expect(prompt).toContain('Generate a comprehensive Jest test file');
      expect(prompt).toContain(sampleParentTask.title);
      expect(prompt).toContain(sampleParentTask.description);
      expect(prompt).toContain('Subtask 1: Create command structure');

      // Verify file system interaction
      expect(mockedFs.writeFileSync).toHaveBeenCalledWith(
        './tests/task_024.test.ts', // Assuming tests are generated in a 'tests' directory
        aiGeneratedTestContent
      );

      // Verify console output
      expect(consoleLogSpy).toHaveBeenCalledWith(
        expect.stringContaining('Successfully generated test file: ./tests/task_024.test.ts')
      );
      expect(consoleErrorSpy).not.toHaveBeenCalled();
    });

    it('should generate a test file for a subtask successfully', async () => {
      // Arrange
      mockedTaskStore.getSubtaskById.mockReturnValue({ parentTask: sampleParentTask, subtask: sampleSubtask });
      mockedClaudeApiService.generateText.mockResolvedValue(aiGeneratedTestContent);

      // Act
      await handleGenerateTestCommand({ id: '24.1' });

      // Assert
      expect(mockedTaskStore.getSubtaskById).toHaveBeenCalledWith(24, 1);
      expect(mockedClaudeApiService.generateText).toHaveBeenCalledTimes(1);

      // Verify prompt construction for subtask
      const prompt = mockedClaudeApiService.generateText.mock.calls[0][0];
      expect(prompt).toContain('Generate a comprehensive Jest test file for the following subtask');
      expect(prompt).toContain(`Parent Task Title: ${sampleParentTask.title}`);
      expect(prompt).toContain(`Subtask Title: ${sampleSubtask.title}`);
      expect(prompt).toContain(sampleSubtask.description);

      // Verify file system interaction with correct subtask naming convention
      expect(mockedFs.writeFileSync).toHaveBeenCalledWith(
        './tests/task_024_001.test.ts',
        aiGeneratedTestContent
      );

      // Verify console output
      expect(consoleLogSpy).toHaveBeenCalledWith(
        expect.stringContaining('Successfully generated test file: ./tests/task_024_001.test.ts')
      );
      expect(consoleErrorSpy).not.toHaveBeenCalled();
    });
  });

  describe('Error Handling and Edge Cases', () => {
    it('should show an error if the task ID is not provided', async () => {
      // Act
      await handleGenerateTestCommand({ id: undefined });

      // Assert
      expect(consoleErrorSpy).toHaveBeenCalledWith('Error: Task ID is required. Use --id=<task_id>.');
      expect(mockedTaskStore.getTaskById).not.toHaveBeenCalled();
      expect(mockedClaudeApiService.generateText).not.toHaveBeenCalled();
      expect(mockedFs.writeFileSync).not.toHaveBeenCalled();
    });

    it('should show an error for an invalid task ID format', async () => {
      // Act
      await handleGenerateTestCommand({ id: 'abc' });

      // Assert
      expect(consoleErrorSpy).toHaveBeenCalledWith('Error: Invalid ID format. Please use numbers (e.g., 24 or 24.1).');
      expect(mockedTaskStore.getTaskById).not.toHaveBeenCalled();
    });

    it('should show an error if the parent task is not found', async () => {
      // Arrange
      mockedTaskStore.getTaskById.mockReturnValue(null);

      // Act
      await handleGenerateTestCommand({ id: '999' });

      // Assert
      expect(mockedTaskStore.getTaskById).toHaveBeenCalledWith(999);
      expect(consoleErrorSpy).toHaveBeenCalledWith('Error: Task with ID 999 not found.');
      expect(mockedClaudeApiService.generateText).not.toHaveBeenCalled();
    });

    it('should show an error if the subtask is not found', async () => {
      // Arrange
      mockedTaskStore.getSubtaskById.mockReturnValue(null);

      // Act
      await handleGenerateTestCommand({ id: '24.99' });

      // Assert
      expect(mockedTaskStore.getSubtaskById).toHaveBeenCalledWith(24, 99);
      expect(consoleErrorSpy).toHaveBeenCalledWith('Error: Subtask 99 for task 24 not found.');
      expect(mockedClaudeApiService.generateText).not.toHaveBeenCalled();
    });

    it('should handle failures from the Claude API', async () => {
      // Arrange
      const apiError = new Error('Claude API Error: Rate limit exceeded');
      mockedTaskStore.getTaskById.mockReturnValue(sampleParentTask);
      mockedClaudeApiService.generateText.mockRejectedValue(apiError);

      // Act
      await handleGenerateTestCommand({ id: '24' });

      // Assert
      expect(mockedClaudeApiService.generateText).toHaveBeenCalled();
      expect(consoleErrorSpy).toHaveBeenCalledWith('Error generating test from AI service:', apiError);
      expect(mockedFs.writeFileSync).not.toHaveBeenCalled();
    });

    it('should handle malformed or empty responses from the AI', async () => {
      // Arrange
      mockedTaskStore.getTaskById.mockReturnValue(sampleParentTask);
      mockedClaudeApiService.generateText.mockResolvedValue(''); // Empty response

      // Act
      await handleGenerateTestCommand({ id: '24' });

      // Assert
      expect(consoleErrorSpy).toHaveBeenCalledWith('Error: AI service returned an empty or invalid response.');
      expect(mockedFs.writeFileSync).not.toHaveBeenCalled();
    });

    it('should handle file system permission errors during write', async () => {
      // Arrange
      const fsError = new Error('EACCES: permission denied');
      mockedTaskStore.getTaskById.mockReturnValue(sampleParentTask);
      mockedClaudeApiService.generateText.mockResolvedValue(aiGeneratedTestContent);
      mockedFs.writeFileSync.mockImplementation(() => {
        throw fsError;
      });

      // Act
      await handleGenerateTestCommand({ id: '24' });

      // Assert
      expect(mockedFs.writeFileSync).toHaveBeenCalled();
      expect(consoleErrorSpy).toHaveBeenCalledWith('Error writing test file:', fsError);
      expect(consoleLogSpy).not.toHaveBeenCalledWith(expect.stringContaining('Successfully generated'));
    });
  });

  describe('Utility Functions (within the command scope)', () => {
    // This assumes the file path generation logic is part of the command handler.
    // If it's a separate utility, it should have its own test file.
    it('should format file paths correctly with zero-padding', async () => {
      // Test padding for single-digit task and subtask
      mockedTaskStore.getSubtaskById.mockReturnValue({ parentTask: { id: 1 }, subtask: { id: 2 } });
      mockedClaudeApiService.generateText.mockResolvedValue(aiGeneratedTestContent);
      await handleGenerateTestCommand({ id: '1.2' });
      expect(mockedFs.writeFileSync).toHaveBeenCalledWith(
        './tests/task_001_002.test.ts',
        expect.any(String)
      );

      // Test padding for multi-digit task and subtask
      mockedTaskStore.getSubtaskById.mockReturnValue({ parentTask: { id: 123 }, subtask: { id: 45 } });
      await handleGenerateTestCommand({ id: '123.45' });
      expect(mockedFs.writeFileSync).toHaveBeenCalledWith(
        './tests/task_123_045.test.ts',
        expect.any(String)
      );
    });
  });
});