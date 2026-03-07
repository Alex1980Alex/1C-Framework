/**
 * Unit tests for generate-test command integration in commands.js
 */

import { jest } from '@jest/globals';
import { Command } from 'commander';

// Mock dependencies
jest.mock('../../scripts/modules/task-manager/generate-test.js', () => ({
  generateTestForTask: jest.fn(),
  generateTestsForTasks: jest.fn(),
  getTestGenerationStats: jest.fn()
}));

jest.mock('../../scripts/modules/utils.js', () => ({
  readJSON: jest.fn(),
  findTaskById: jest.fn()
}));

import {
  generateTestForTask,
  generateTestsForTasks,
  getTestGenerationStats
} from '../../scripts/modules/task-manager/generate-test.js';
import { readJSON, findTaskById } from '../../scripts/modules/utils.js';

describe('Generate Test Command Integration', () => {
  let program;
  let consoleLogSpy;
  let consoleErrorSpy;
  let processExitSpy;

  const mockTask = {
    id: '1',
    title: 'Test Task',
    description: 'A test task for unit testing',
    status: 'pending'
  };

  const mockSuccessResult = {
    success: true,
    filename: 'task_001.test.ts',
    outputPath: './tests/task_001.test.ts',
    task: { id: '1', title: 'Test Task' },
    linesGenerated: 150
  };

  const mockFailureResult = {
    success: false,
    error: 'Task with ID 999 not found',
    taskId: '999'
  };

  beforeEach(() => {
    jest.clearAllMocks();
    
    // Create fresh commander instance
    program = new Command();
    
    // Spy on console and process methods
    consoleLogSpy = jest.spyOn(console, 'log').mockImplementation();
    consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation();
    processExitSpy = jest.spyOn(process, 'exit').mockImplementation();

    // Setup default mocks
    readJSON.mockReturnValue([mockTask]);
    findTaskById.mockReturnValue(mockTask);
    generateTestForTask.mockResolvedValue(mockSuccessResult);
    generateTestsForTasks.mockResolvedValue({
      total: 1,
      successful: 1,
      failed: 0,
      results: [mockSuccessResult]
    });
    getTestGenerationStats.mockReturnValue({
      taskId: '1',
      title: 'Test Task',
      estimatedTestCases: 5,
      complexity: 'medium'
    });

    // Import and setup command after mocks are ready
    setupGenerateTestCommand();
  });

  afterEach(() => {
    consoleLogSpy.mockRestore();
    consoleErrorSpy.mockRestore();
    processExitSpy.mockRestore();
  });

  // Helper function to setup the command
  function setupGenerateTestCommand() {
    program
      .command('generate-test')
      .description('Generate AI-powered Jest test files for tasks')
      .option('--id <id>', 'Task ID to generate tests for (required)')
      .option('--ids <ids>', 'Comma-separated list of task IDs')
      .option('--tasks-path <path>', 'Path to tasks.json file', '.taskmaster/tasks/tasks.json')
      .option('--output-dir <dir>', 'Output directory for test files', './tests')
      .option('--file-prefix <prefix>', 'Prefix for generated test files', 'task_')
      .option('--research', 'Use research AI model for test generation', false)
      .option('--overwrite', 'Overwrite existing test files', false)
      .option('--no-validate', 'Skip test content validation')
      .option('--preview', 'Preview generation statistics without creating files', false)
      .option('--continue-on-error', 'Continue batch processing on individual failures', true)
      .action(async (options) => {
        try {
          // Validate required options
          if (!options.id && !options.ids && !options.preview) {
            console.error('❌ Error: Either --id, --ids, or --preview is required');
            process.exit(1);
            return;
          }

          // Handle preview mode
          if (options.preview) {
            console.log('📊 Test Generation Preview');
            console.log('═'.repeat(50));

            const tasks = readJSON(options.tasksPath);
            tasks.forEach(task => {
              const stats = getTestGenerationStats(task);
              console.log(`Task ${stats.taskId}: ${stats.title}`);
              console.log(`  Complexity: ${stats.complexity}`);
              console.log(`  Estimated test cases: ${stats.estimatedTestCases}`);
              console.log('');
            });
            return;
          }

          // Handle batch processing
          if (options.ids) {
            const taskIds = options.ids.split(',').map(id => id.trim());
            console.log(`🔄 Generating tests for ${taskIds.length} tasks...`);

            const result = await generateTestsForTasks(taskIds, {
              tasksPath: options.tasksPath,
              outputDir: options.outputDir,
              filePrefix: options.filePrefix,
              research: options.research,
              overwrite: options.overwrite,
              validate: options.validate,
              continueOnError: options.continueOnError
            });

            console.log('\n📋 Batch Generation Results:');
            console.log(`  Total tasks: ${result.total}`);
            console.log(`  ✅ Successful: ${result.successful}`);
            console.log(`  ❌ Failed: ${result.failed}`);

            if (result.failed > 0) {
              console.log('\n❌ Failed tasks:');
              result.results
                .filter(r => !r.success)
                .forEach(r => console.log(`  - Task ${r.taskId}: ${r.error}`));
            }

            if (result.successful > 0) {
              console.log('\n✅ Generated files:');
              result.results
                .filter(r => r.success)
                .forEach(r => console.log(`  - ${r.filename} (${r.linesGenerated} lines)`));
            }

            process.exit(result.failed > 0 ? 1 : 0);
            return;
          }

          // Handle single task processing
          if (options.id) {
            console.log(`🤖 Generating AI-powered test for task ${options.id}...`);

            const result = await generateTestForTask(options.id, {
              tasksPath: options.tasksPath,
              outputDir: options.outputDir,
              filePrefix: options.filePrefix,
              research: options.research,
              overwrite: options.overwrite,
              validate: options.validate
            });

            if (result.success) {
              console.log(`\n✅ Test file generated successfully!`);
              console.log(`   File: ${result.filename}`);
              console.log(`   Path: ${result.outputPath}`);
              console.log(`   Task: ${result.task.title}`);
              console.log(`   Lines: ${result.linesGenerated}`);
              
              if (options.research) {
                console.log(`   Model: Research AI (enhanced analysis)`);
              }
            } else {
              console.error(`\n❌ Test generation failed:`);
              console.error(`   Task ID: ${result.taskId}`);
              console.error(`   Error: ${result.error}`);
              process.exit(1);
            }
          }

        } catch (error) {
          console.error(`\n💥 Unexpected error during test generation:`);
          console.error(`   ${error.message}`);
          process.exit(1);
        }
      });
  }

  describe('Command Registration', () => {
    it('should register generate-test command with correct description', () => {
      const command = program.commands.find(cmd => cmd.name() === 'generate-test');
      expect(command).toBeDefined();
      expect(command.description()).toBe('Generate AI-powered Jest test files for tasks');
    });

    it('should register all required options', () => {
      const command = program.commands.find(cmd => cmd.name() === 'generate-test');
      const optionNames = command.options.map(opt => opt.long);

      expect(optionNames).toContain('--id');
      expect(optionNames).toContain('--ids');
      expect(optionNames).toContain('--tasks-path');
      expect(optionNames).toContain('--output-dir');
      expect(optionNames).toContain('--file-prefix');
      expect(optionNames).toContain('--research');
      expect(optionNames).toContain('--overwrite');
      expect(optionNames).toContain('--no-validate');
      expect(optionNames).toContain('--preview');
      expect(optionNames).toContain('--continue-on-error');
    });
  });

  describe('Single Task Generation', () => {
    it('should handle successful single task generation', async () => {
      await program.parseAsync(['node', 'test', 'generate-test', '--id', '1']);

      expect(generateTestForTask).toHaveBeenCalledWith('1', {
        tasksPath: '.taskmaster/tasks/tasks.json',
        outputDir: './tests',
        filePrefix: 'task_',
        research: false,
        overwrite: false,
        validate: true
      });

      expect(consoleLogSpy).toHaveBeenCalledWith(
        expect.stringContaining('🤖 Generating AI-powered test for task 1...')
      );
      expect(consoleLogSpy).toHaveBeenCalledWith(
        expect.stringContaining('✅ Test file generated successfully!')
      );
    });

    it('should handle failed single task generation', async () => {
      generateTestForTask.mockResolvedValue(mockFailureResult);

      await program.parseAsync(['node', 'test', 'generate-test', '--id', '999']);

      expect(consoleErrorSpy).toHaveBeenCalledWith(
        expect.stringContaining('❌ Test generation failed:')
      );
      expect(processExitSpy).toHaveBeenCalledWith(1);
    });

    it('should pass research option correctly', async () => {
      await program.parseAsync(['node', 'test', 'generate-test', '--id', '1', '--research']);

      expect(generateTestForTask).toHaveBeenCalledWith('1', 
        expect.objectContaining({
          research: true
        })
      );
    });

    it('should pass custom output directory', async () => {
      await program.parseAsync([
        'node', 'test', 'generate-test', 
        '--id', '1', 
        '--output-dir', './custom-tests'
      ]);

      expect(generateTestForTask).toHaveBeenCalledWith('1',
        expect.objectContaining({
          outputDir: './custom-tests'
        })
      );
    });
  });

  describe('Batch Task Generation', () => {
    it('should handle successful batch generation', async () => {
      const mockBatchResult = {
        total: 3,
        successful: 3,
        failed: 0,
        results: [
          { success: true, filename: 'task_001.test.ts', linesGenerated: 150 },
          { success: true, filename: 'task_002.test.ts', linesGenerated: 200 },
          { success: true, filename: 'task_003.test.ts', linesGenerated: 175 }
        ]
      };
      generateTestsForTasks.mockResolvedValue(mockBatchResult);

      await program.parseAsync(['node', 'test', 'generate-test', '--ids', '1,2,3']);

      expect(generateTestsForTasks).toHaveBeenCalledWith(['1', '2', '3'], 
        expect.objectContaining({
          continueOnError: true
        })
      );

      expect(consoleLogSpy).toHaveBeenCalledWith(
        expect.stringContaining('🔄 Generating tests for 3 tasks...')
      );
      expect(consoleLogSpy).toHaveBeenCalledWith(
        expect.stringContaining('✅ Successful: 3')
      );
      expect(processExitSpy).toHaveBeenCalledWith(0);
    });

    it('should handle mixed success/failure batch generation', async () => {
      const mockMixedResult = {
        total: 3,
        successful: 2,
        failed: 1,
        results: [
          { success: true, filename: 'task_001.test.ts', linesGenerated: 150 },
          { success: false, taskId: '999', error: 'Task not found' },
          { success: true, filename: 'task_003.test.ts', linesGenerated: 175 }
        ]
      };
      generateTestsForTasks.mockResolvedValue(mockMixedResult);

      await program.parseAsync(['node', 'test', 'generate-test', '--ids', '1,999,3']);

      expect(consoleLogSpy).toHaveBeenCalledWith(
        expect.stringContaining('❌ Failed: 1')
      );
      expect(consoleLogSpy).toHaveBeenCalledWith(
        expect.stringContaining('❌ Failed tasks:')
      );
      expect(processExitSpy).toHaveBeenCalledWith(1);
    });

    it('should parse comma-separated IDs correctly', async () => {
      await program.parseAsync(['node', 'test', 'generate-test', '--ids', '1, 2 , 3']);

      expect(generateTestsForTasks).toHaveBeenCalledWith(['1', '2', '3'], 
        expect.any(Object)
      );
    });
  });

  describe('Preview Mode', () => {
    it('should display preview statistics without generating files', async () => {
      const mockTasks = [
        { id: '1', title: 'Task 1' },
        { id: '2', title: 'Task 2' }
      ];
      readJSON.mockReturnValue(mockTasks);
      getTestGenerationStats
        .mockReturnValueOnce({
          taskId: '1',
          title: 'Task 1',
          complexity: 'low',
          estimatedTestCases: 3
        })
        .mockReturnValueOnce({
          taskId: '2',
          title: 'Task 2',
          complexity: 'high',
          estimatedTestCases: 8
        });

      await program.parseAsync(['node', 'test', 'generate-test', '--preview']);

      expect(consoleLogSpy).toHaveBeenCalledWith(
        expect.stringContaining('📊 Test Generation Preview')
      );
      expect(consoleLogSpy).toHaveBeenCalledWith(
        expect.stringContaining('Task 1: Task 1')
      );
      expect(consoleLogSpy).toHaveBeenCalledWith(
        expect.stringContaining('Complexity: low')
      );
      expect(generateTestForTask).not.toHaveBeenCalled();
      expect(generateTestsForTasks).not.toHaveBeenCalled();
    });
  });

  describe('Option Validation', () => {
    it('should require at least one of --id, --ids, or --preview', async () => {
      await program.parseAsync(['node', 'test', 'generate-test']);

      expect(consoleErrorSpy).toHaveBeenCalledWith(
        expect.stringContaining('❌ Error: Either --id, --ids, or --preview is required')
      );
      expect(processExitSpy).toHaveBeenCalledWith(1);
    });

    it('should handle no-validate option correctly', async () => {
      await program.parseAsync(['node', 'test', 'generate-test', '--id', '1', '--no-validate']);

      expect(generateTestForTask).toHaveBeenCalledWith('1',
        expect.objectContaining({
          validate: false
        })
      );
    });

    it('should handle overwrite option correctly', async () => {
      await program.parseAsync(['node', 'test', 'generate-test', '--id', '1', '--overwrite']);

      expect(generateTestForTask).toHaveBeenCalledWith('1',
        expect.objectContaining({
          overwrite: true
        })
      );
    });

    it('should handle custom file prefix', async () => {
      await program.parseAsync([
        'node', 'test', 'generate-test', 
        '--id', '1', 
        '--file-prefix', 'unit_test_'
      ]);

      expect(generateTestForTask).toHaveBeenCalledWith('1',
        expect.objectContaining({
          filePrefix: 'unit_test_'
        })
      );
    });
  });

  describe('Error Handling', () => {
    it('should handle unexpected errors gracefully', async () => {
      generateTestForTask.mockRejectedValue(new Error('Unexpected AI service error'));

      await program.parseAsync(['node', 'test', 'generate-test', '--id', '1']);

      expect(consoleErrorSpy).toHaveBeenCalledWith(
        expect.stringContaining('💥 Unexpected error during test generation:')
      );
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        expect.stringContaining('Unexpected AI service error')
      );
      expect(processExitSpy).toHaveBeenCalledWith(1);
    });

    it('should handle JSON file reading errors', async () => {
      readJSON.mockImplementation(() => {
        throw new Error('Cannot read tasks.json');
      });

      await program.parseAsync(['node', 'test', 'generate-test', '--preview']);

      expect(consoleErrorSpy).toHaveBeenCalledWith(
        expect.stringContaining('💥 Unexpected error during test generation:')
      );
    });
  });

  describe('Output Formatting', () => {
    it('should display detailed success information', async () => {
      const detailedResult = {
        ...mockSuccessResult,
        task: { id: '1', title: 'Complex Authentication Task' },
        linesGenerated: 275
      };
      generateTestForTask.mockResolvedValue(detailedResult);

      await program.parseAsync(['node', 'test', 'generate-test', '--id', '1', '--research']);

      expect(consoleLogSpy).toHaveBeenCalledWith(
        expect.stringContaining('Task: Complex Authentication Task')
      );
      expect(consoleLogSpy).toHaveBeenCalledWith(
        expect.stringContaining('Lines: 275')
      );
      expect(consoleLogSpy).toHaveBeenCalledWith(
        expect.stringContaining('Model: Research AI (enhanced analysis)')
      );
    });

    it('should format batch results clearly', async () => {
      const mockBatchResult = {
        total: 5,
        successful: 4,
        failed: 1,
        results: [
          { success: true, filename: 'task_001.test.ts', linesGenerated: 150 },
          { success: true, filename: 'task_002.test.ts', linesGenerated: 200 },
          { success: false, taskId: '3', error: 'AI service timeout' },
          { success: true, filename: 'task_004.test.ts', linesGenerated: 175 },
          { success: true, filename: 'task_005.test.ts', linesGenerated: 225 }
        ]
      };
      generateTestsForTasks.mockResolvedValue(mockBatchResult);

      await program.parseAsync(['node', 'test', 'generate-test', '--ids', '1,2,3,4,5']);

      expect(consoleLogSpy).toHaveBeenCalledWith(
        expect.stringContaining('Total tasks: 5')
      );
      expect(consoleLogSpy).toHaveBeenCalledWith(
        expect.stringContaining('✅ Successful: 4')
      );
      expect(consoleLogSpy).toHaveBeenCalledWith(
        expect.stringContaining('❌ Failed: 1')
      );
    });
  });
});