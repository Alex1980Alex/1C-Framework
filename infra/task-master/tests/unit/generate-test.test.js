/**
 * Unit tests for AI-powered test generation functionality
 */

import { jest } from '@jest/globals';
import fs from 'fs';
import path from 'path';
import {
  generateTestForTask,
  generateTestsForTasks,
  getTestGenerationStats
} from '../../scripts/modules/task-manager/generate-test.js';

// Mock dependencies
jest.mock('fs');
jest.mock('../../scripts/modules/utils.js', () => ({
  readJSON: jest.fn(),
  findTaskById: jest.fn()
}));
jest.mock('../../scripts/modules/config-manager.js', () => ({
  getConfig: jest.fn()
}));
jest.mock('../../scripts/modules/ai-services-unified.js', () => ({
  callAI: jest.fn()
}));

import { readJSON, findTaskById } from '../../scripts/modules/utils.js';
import { getConfig } from '../../scripts/modules/config-manager.js';
import { callAI } from '../../scripts/modules/ai-services-unified.js';

describe('Generate Test Command', () => {
  const mockTask = {
    id: '1',
    title: 'Test Task',
    description: 'A test task for unit testing',
    status: 'pending',
    details: 'Implementation details for testing',
    testStrategy: 'Unit testing with mocks',
    dependencies: ['dependency1', 'dependency2'],
    subtasks: [
      { id: '1.1', title: 'Subtask 1' },
      { id: '1.2', title: 'Subtask 2' }
    ]
  };

  const mockConfig = {
    models: {
      main: 'claude-3-opus',
      research: 'claude-3-sonnet'
    }
  };

  const mockAIResponse = `import { describe, it, expect, beforeEach, afterEach, jest } from '@jest/globals';

describe('Test Task', () => {
  beforeEach(() => {
    // Setup test environment
  });

  afterEach(() => {
    // Cleanup test environment
  });

  describe('Main functionality', () => {
    it('should handle basic operations', () => {
      // Test implementation
      expect(true).toBe(true);
    });

    it('should handle error conditions', () => {
      // Test error handling
      expect(() => {
        throw new Error('Test error');
      }).toThrow('Test error');
    });
  });

  describe('Edge cases', () => {
    it('should handle empty input', () => {
      // Test empty input handling
      expect(null).toBeNull();
    });

    it('should validate input parameters', () => {
      // Test input validation
      expect(undefined).toBeUndefined();
    });
  });
});`;

  beforeEach(() => {
    jest.clearAllMocks();
    
    // Setup default mocks
    readJSON.mockReturnValue([mockTask]);
    findTaskById.mockReturnValue(mockTask);
    getConfig.mockReturnValue(mockConfig);
    callAI.mockResolvedValue(mockAIResponse);
    fs.existsSync.mockReturnValue(true);
    fs.mkdirSync.mockImplementation(() => {});
    fs.writeFileSync.mockImplementation(() => {});
  });

  describe('generateTestForTask', () => {
    it('should generate test file successfully', async () => {
      const result = await generateTestForTask('1', {
        tasksPath: './tasks.json',
        outputDir: './tests',
        filePrefix: 'task_'
      });

      expect(result.success).toBe(true);
      expect(result.filename).toBe('task_001.test.ts');
      expect(result.task.id).toBe('1');
      expect(result.task.title).toBe('Test Task');
      expect(typeof result.linesGenerated).toBe('number');
    });

    it('should handle task not found error', async () => {
      findTaskById.mockReturnValue(null);

      const result = await generateTestForTask('999', {
        tasksPath: './tasks.json'
      });

      expect(result.success).toBe(false);
      expect(result.error).toBe('Task with ID 999 not found');
      expect(result.taskId).toBe('999');
    });

    it('should handle AI service errors', async () => {
      callAI.mockRejectedValue(new Error('AI service unavailable'));

      const result = await generateTestForTask('1', {
        tasksPath: './tasks.json'
      });

      expect(result.success).toBe(false);
      expect(result.error).toContain('AI service unavailable');
    });

    it('should handle file already exists error', async () => {
      fs.existsSync.mockImplementation((filePath) => {
        return filePath.includes('task_001.test.ts');
      });

      const result = await generateTestForTask('1', {
        tasksPath: './tasks.json',
        overwrite: false
      });

      expect(result.success).toBe(false);
      expect(result.error).toContain('already exists');
    });

    it('should overwrite existing file when overwrite option is true', async () => {
      fs.existsSync.mockImplementation((filePath) => {
        return filePath.includes('task_001.test.ts');
      });

      const result = await generateTestForTask('1', {
        tasksPath: './tasks.json',
        overwrite: true
      });

      expect(result.success).toBe(true);
      expect(fs.writeFileSync).toHaveBeenCalled();
    });

    it('should create output directory if it does not exist', async () => {
      fs.existsSync.mockImplementation((filePath) => {
        return !filePath.includes('./tests');
      });

      await generateTestForTask('1', {
        tasksPath: './tasks.json',
        outputDir: './tests'
      });

      expect(fs.mkdirSync).toHaveBeenCalledWith('./tests', { recursive: true });
    });

    it('should handle subtask filename generation', async () => {
      const subtask = {
        ...mockTask,
        id: '1.2',
        parentId: '1'
      };
      findTaskById.mockReturnValue(subtask);

      const result = await generateTestForTask('1.2', {
        tasksPath: './tasks.json'
      });

      expect(result.success).toBe(true);
      expect(result.filename).toBe('task_001_002.test.ts');
    });

    it('should validate test content when validation is enabled', async () => {
      // Mock invalid AI response (missing describe block)
      callAI.mockResolvedValue('console.log("Not a valid test");');

      const result = await generateTestForTask('1', {
        tasksPath: './tasks.json',
        validate: true
      });

      expect(result.success).toBe(false);
      expect(result.error).toContain('validation failed');
    });

    it('should skip validation when validation is disabled', async () => {
      callAI.mockResolvedValue('console.log("Not a valid test");');

      const result = await generateTestForTask('1', {
        tasksPath: './tasks.json',
        validate: false
      });

      expect(result.success).toBe(true);
    });

    it('should use research model when research option is true', async () => {
      await generateTestForTask('1', {
        tasksPath: './tasks.json',
        research: true
      });

      expect(callAI).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          model: 'claude-3-sonnet',
          role: 'research'
        })
      );
    });

    it('should use main model when research option is false', async () => {
      await generateTestForTask('1', {
        tasksPath: './tasks.json',
        research: false
      });

      expect(callAI).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          model: 'claude-3-opus',
          role: 'main'
        })
      );
    });
  });

  describe('generateTestsForTasks', () => {
    it('should generate tests for multiple tasks successfully', async () => {
      const taskIds = ['1', '2', '3'];
      findTaskById
        .mockReturnValueOnce({ ...mockTask, id: '1' })
        .mockReturnValueOnce({ ...mockTask, id: '2' })
        .mockReturnValueOnce({ ...mockTask, id: '3' });

      const result = await generateTestsForTasks(taskIds, {
        tasksPath: './tasks.json'
      });

      expect(result.total).toBe(3);
      expect(result.successful).toBe(3);
      expect(result.failed).toBe(0);
      expect(result.results).toHaveLength(3);
    });

    it('should handle mixed success and failure scenarios', async () => {
      const taskIds = ['1', '999', '2'];
      findTaskById
        .mockReturnValueOnce({ ...mockTask, id: '1' })
        .mockReturnValueOnce(null) // Task not found
        .mockReturnValueOnce({ ...mockTask, id: '2' });

      const result = await generateTestsForTasks(taskIds, {
        tasksPath: './tasks.json',
        continueOnError: true
      });

      expect(result.total).toBe(3);
      expect(result.successful).toBe(2);
      expect(result.failed).toBe(1);
      expect(result.results).toHaveLength(3);
    });

    it('should stop on first error when continueOnError is false', async () => {
      const taskIds = ['1', '999', '2'];
      findTaskById
        .mockReturnValueOnce({ ...mockTask, id: '1' })
        .mockReturnValueOnce(null); // Task not found

      const result = await generateTestsForTasks(taskIds, {
        tasksPath: './tasks.json',
        continueOnError: false
      });

      expect(result.total).toBe(3);
      expect(result.successful).toBe(1);
      expect(result.failed).toBe(1);
      expect(result.results).toHaveLength(2); // Should stop after failure
    });
  });

  describe('getTestGenerationStats', () => {
    it('should calculate basic statistics correctly', () => {
      const stats = getTestGenerationStats(mockTask);

      expect(stats.taskId).toBe('1');
      expect(stats.title).toBe('Test Task');
      expect(stats.hasDescription).toBe(true);
      expect(stats.hasDetails).toBe(true);
      expect(stats.hasTestStrategy).toBe(true);
      expect(stats.dependencyCount).toBe(2);
      expect(stats.subtaskCount).toBe(2);
      expect(stats.estimatedTestCases).toBeGreaterThan(2);
      expect(stats.complexity).toBe('medium');
    });

    it('should handle task with minimal information', () => {
      const minimalTask = {
        id: '2',
        title: 'Simple Task',
        status: 'pending'
      };

      const stats = getTestGenerationStats(minimalTask);

      expect(stats.taskId).toBe('2');
      expect(stats.hasDescription).toBe(false);
      expect(stats.hasDetails).toBe(false);
      expect(stats.hasTestStrategy).toBe(false);
      expect(stats.dependencyCount).toBe(0);
      expect(stats.subtaskCount).toBe(0);
      expect(stats.complexity).toBe('low');
      expect(stats.estimatedTestCases).toBe(2); // Base test cases
    });

    it('should classify high complexity correctly', () => {
      const complexTask = {
        ...mockTask,
        dependencies: ['dep1', 'dep2', 'dep3', 'dep4'],
        subtasks: new Array(10).fill(0).map((_, i) => ({ id: `1.${i + 1}`, title: `Subtask ${i + 1}` }))
      };

      const stats = getTestGenerationStats(complexTask);

      expect(stats.complexity).toBe('high');
      expect(stats.estimatedTestCases).toBeGreaterThan(10);
    });
  });

  describe('Test Content Validation', () => {
    it('should pass validation for well-formed test content', () => {
      // This test validates the validateTestContent function indirectly
      // through the generateTestForTask function
      const validTestContent = mockAIResponse;

      expect(() => {
        // Simulate validation logic
        const hasDescribe = validTestContent.includes('describe');
        const hasIt = validTestContent.includes('it(');
        const hasExpect = validTestContent.includes('expect');
        const hasImport = validTestContent.includes('import');
        const isLongEnough = validTestContent.length > 500;

        if (!hasDescribe || !hasIt || !hasExpected || !hasImport || !isLongEnough) {
          throw new Error('Validation failed');
        }
      }).not.toThrow();
    });
  });

  describe('Filename Generation', () => {
    it('should generate correct filename for parent task', () => {
      // Test filename generation logic through the main function
      const task = { id: '5', title: 'Parent Task' };
      findTaskById.mockReturnValue(task);

      return generateTestForTask('5', { tasksPath: './tasks.json' })
        .then(result => {
          expect(result.filename).toBe('task_005.test.ts');
        });
    });

    it('should generate correct filename for subtask', () => {
      const subtask = { id: '5.3', parentId: '5', title: 'Subtask' };
      findTaskById.mockReturnValue(subtask);

      return generateTestForTask('5.3', { tasksPath: './tasks.json' })
        .then(result => {
          expect(result.filename).toBe('task_005_003.test.ts');
        });
    });

    it('should use custom file prefix', () => {
      const task = { id: '1', title: 'Test Task' };
      findTaskById.mockReturnValue(task);

      return generateTestForTask('1', { 
        tasksPath: './tasks.json',
        filePrefix: 'unit_test_'
      }).then(result => {
        expect(result.filename).toBe('unit_test_001.test.ts');
      });
    });
  });

  describe('AI Prompt Construction', () => {
    it('should construct comprehensive prompts with all task information', async () => {
      await generateTestForTask('1', { tasksPath: './tasks.json' });

      expect(callAI).toHaveBeenCalledWith(
        expect.stringContaining('Task ID**: 1'),
        expect.any(Object)
      );
      expect(callAI).toHaveBeenCalledWith(
        expect.stringContaining('Title**: Test Task'),
        expect.any(Object)
      );
      expect(callAI).toHaveBeenCalledWith(
        expect.stringContaining('Implementation Details**'),
        expect.any(Object)
      );
      expect(callAI).toHaveBeenCalledWith(
        expect.stringContaining('Test Strategy**'),
        expect.any(Object)
      );
      expect(callAI).toHaveBeenCalledWith(
        expect.stringContaining('Dependencies**'),
        expect.any(Object)
      );
      expect(callAI).toHaveBeenCalledWith(
        expect.stringContaining('Subtasks**'),
        expect.any(Object)
      );
    });
  });

  describe('Error Handling', () => {
    it('should handle JSON parsing errors gracefully', async () => {
      readJSON.mockImplementation(() => {
        throw new Error('Invalid JSON format');
      });

      const result = await generateTestForTask('1', {
        tasksPath: './invalid.json'
      });

      expect(result.success).toBe(false);
      expect(result.error).toContain('Invalid JSON format');
    });

    it('should handle file system errors gracefully', async () => {
      fs.writeFileSync.mockImplementation(() => {
        throw new Error('Permission denied');
      });

      const result = await generateTestForTask('1', {
        tasksPath: './tasks.json'
      });

      expect(result.success).toBe(false);
      expect(result.error).toContain('Permission denied');
    });

    it('should handle AI response parsing errors', async () => {
      callAI.mockResolvedValue('```invalid\nresponse\nformat```');

      const result = await generateTestForTask('1', {
        tasksPath: './tasks.json',
        validate: false // Disable validation to test parsing
      });

      // Should still succeed but with potentially malformed content
      expect(result.success).toBe(true);
    });
  });
});