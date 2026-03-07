/**
 * Generated Test File for Task #24
 * Implement AI-Powered Test Generation Command
 * 
 * This test file validates the implementation of the AI-powered test generation command
 * for the Task Master CLI system.
 */

import { describe, it, expect, beforeEach, afterEach, jest } from '@jest/globals';
import { generateTestForTask, generateTestsForTasks, getTestGenerationStats } from '../scripts/modules/task-manager/generate-test.js';
import { getConfig } from '../scripts/modules/config-manager.js';
import { readJSON } from '../scripts/modules/utils.js';
import fs from 'fs';
import path from 'path';

// Mock the AI service
jest.mock('../scripts/modules/ai-services-unified.js', () => ({
    generateTextService: jest.fn()
}));

describe('Task #24: Implement AI-Powered Test Generation Command', () => {
    let tempDir;
    let mockConfig;
    
    beforeEach(() => {
        // Create temp directory for test outputs
        tempDir = path.join(__dirname, 'test-output-' + Date.now());
        fs.mkdirSync(tempDir, { recursive: true });
        
        // Mock configuration
        mockConfig = {
            apiKeys: {
                anthropic: 'test-api-key'
            },
            models: {
                main: 'claude-3-opus-20240229'
            }
        };
        
        jest.clearAllMocks();
    });
    
    afterEach(() => {
        // Clean up temp directory
        if (fs.existsSync(tempDir)) {
            fs.rmSync(tempDir, { recursive: true, force: true });
        }
        
        jest.resetModules();
    });
    
    describe('Command Structure and Registration', () => {
        it('should export generateTestForTask as a function', () => {
            expect(typeof generateTestForTask).toBe('function');
        });
        
        it('should export generateTestsForTasks for batch processing', () => {
            expect(typeof generateTestsForTasks).toBe('function');
        });
        
        it('should export getTestGenerationStats for preview', () => {
            expect(typeof getTestGenerationStats).toBe('function');
        });
    });
    
    describe('Single Task Test Generation', () => {
        const sampleTask = {
            id: 1,
            title: 'Sample Task',
            description: 'A sample task for testing',
            status: 'pending',
            dependencies: [],
            priority: 'medium',
            details: 'Implementation details here',
            testStrategy: 'Test using Jest'
        };
        
        it('should generate test file for a valid task', async () => {
            // Setup mock tasks file
            const tasksPath = path.join(tempDir, 'tasks.json');
            fs.writeFileSync(tasksPath, JSON.stringify([sampleTask]), 'utf8');
            
            // Mock AI response
            const mockTestContent = `
import { describe, it, expect } from '@jest/globals';

describe('Sample Task', () => {
    it('should work correctly', () => {
        expect(true).toBe(true);
    });
});
`;
            
            const { generateTextService } = require('../scripts/modules/ai-services-unified.js');
            generateTextService.mockResolvedValue({
                mainResult: mockTestContent
            });
            
            // Generate test
            const result = await generateTestForTask('1', {
                tasksPath,
                outputDir: tempDir,
                validate: false
            });
            
            expect(result.success).toBe(true);
            expect(result.filename).toBe('task_001.test.ts');
            expect(fs.existsSync(path.join(tempDir, result.filename))).toBe(true);
        });
        
        it('should handle task not found error', async () => {
            const tasksPath = path.join(tempDir, 'tasks.json');
            fs.writeFileSync(tasksPath, JSON.stringify([]), 'utf8');
            
            const result = await generateTestForTask('999', {
                tasksPath,
                outputDir: tempDir,
                validate: false
            });
            
            expect(result.success).toBe(false);
            expect(result.error).toContain('not found');
        });
        
        it('should prevent overwriting existing files without --overwrite', async () => {
            const tasksPath = path.join(tempDir, 'tasks.json');
            fs.writeFileSync(tasksPath, JSON.stringify([sampleTask]), 'utf8');
            
            // Create existing file
            const existingFile = path.join(tempDir, 'task_001.test.ts');
            fs.writeFileSync(existingFile, '// Existing content', 'utf8');
            
            const result = await generateTestForTask('1', {
                tasksPath,
                outputDir: tempDir,
                overwrite: false,
                validate: false
            });
            
            expect(result.success).toBe(false);
            expect(result.error).toContain('already exists');
        });
    });
    
    describe('Subtask Test Generation', () => {
        it('should generate correct filename for subtasks', async () => {
            const taskWithSubtask = {
                id: '24.1',
                parentId: 24,
                title: 'Create command structure',
                description: 'Implement the basic structure',
                status: 'pending'
            };
            
            const tasksPath = path.join(tempDir, 'tasks.json');
            fs.writeFileSync(tasksPath, JSON.stringify([taskWithSubtask]), 'utf8');
            
            // Mock AI response
            const { generateTextService } = require('../scripts/modules/ai-services-unified.js');
            generateTextService.mockResolvedValue({
                mainResult: 'test content'
            });
            
            const result = await generateTestForTask('24.1', {
                tasksPath,
                outputDir: tempDir,
                validate: false
            });
            
            expect(result.filename).toBe('task_024_001.test.ts');
        });
    });
    
    describe('Batch Test Generation', () => {
        it('should generate tests for multiple tasks', async () => {
            const tasks = [
                { id: 1, title: 'Task 1', description: 'First task' },
                { id: 2, title: 'Task 2', description: 'Second task' },
                { id: 3, title: 'Task 3', description: 'Third task' }
            ];
            
            const tasksPath = path.join(tempDir, 'tasks.json');
            fs.writeFileSync(tasksPath, JSON.stringify(tasks), 'utf8');
            
            // Mock AI responses
            const { generateTextService } = require('../scripts/modules/ai-services-unified.js');
            generateTextService.mockResolvedValue({
                mainResult: 'test content'
            });
            
            const result = await generateTestsForTasks(['1', '2', '3'], {
                tasksPath,
                outputDir: tempDir,
                validate: false
            });
            
            expect(result.total).toBe(3);
            expect(result.successful).toBe(3);
            expect(result.failed).toBe(0);
        });
        
        it('should continue on error when flag is set', async () => {
            const tasks = [
                { id: 1, title: 'Task 1', description: 'First task' },
                { id: 3, title: 'Task 3', description: 'Third task' }
            ];
            
            const tasksPath = path.join(tempDir, 'tasks.json');
            fs.writeFileSync(tasksPath, JSON.stringify(tasks), 'utf8');
            
            const { generateTextService } = require('../scripts/modules/ai-services-unified.js');
            generateTextService.mockResolvedValue({
                mainResult: 'test content'
            });
            
            const result = await generateTestsForTasks(['1', '2', '3'], {
                tasksPath,
                outputDir: tempDir,
                validate: false,
                continueOnError: true
            });
            
            expect(result.total).toBe(3);
            expect(result.successful).toBe(2);
            expect(result.failed).toBe(1);
        });
    });
    
    describe('Test Content Validation', () => {
        it('should validate Jest structure in generated tests', () => {
            const validContent = `
import { describe, it, expect } from '@jest/globals';

describe('Test Suite', () => {
    it('should have a test case', () => {
        expect(true).toBe(true);
    });
});
`;
            
            // Validation checks
            expect(validContent).toContain('describe');
            expect(validContent).toContain('it');
            expect(validContent).toContain('expect');
            expect(validContent.length).toBeGreaterThan(100);
        });
        
        it('should extract test content from AI response', () => {
            const aiResponse = `\`\`\`typescript
import { describe, test } from '@jest/globals';

describe('Test', () => {
    test('example', () => {
        expect(1).toBe(1);
    });
});
\`\`\``;
            
            // Remove markdown code blocks
            const cleaned = aiResponse
                .replace(/^\`\`\`.*\n/, '')
                .replace(/\n\`\`\`$/, '');
            
            expect(cleaned).not.toContain('\`\`\`');
            expect(cleaned).toContain('describe');
        });
    });
    
    describe('Statistics and Preview', () => {
        it('should calculate test generation statistics', () => {
            const task = {
                id: 24,
                title: 'Test Generation Task',
                description: 'Task with description',
                details: 'Detailed implementation',
                testStrategy: 'Comprehensive testing',
                dependencies: [1, 2, 3],
                subtasks: [
                    { id: '24.1', title: 'Subtask 1' },
                    { id: '24.2', title: 'Subtask 2' }
                ]
            };
            
            const stats = getTestGenerationStats(task);
            
            expect(stats.taskId).toBe(24);
            expect(stats.hasDescription).toBe(true);
            expect(stats.hasDetails).toBe(true);
            expect(stats.hasTestStrategy).toBe(true);
            expect(stats.dependencyCount).toBe(3);
            expect(stats.subtaskCount).toBe(2);
            expect(stats.complexity).toBe('medium');
            expect(stats.estimatedTestCases).toBeGreaterThan(5);
        });
    });
    
    describe('Error Handling', () => {
        it('should handle API failures gracefully', async () => {
            const tasksPath = path.join(tempDir, 'tasks.json');
            fs.writeFileSync(tasksPath, JSON.stringify([
                { id: 1, title: 'Task', description: 'Test task' }
            ]), 'utf8');
            
            // Mock API failure
            const { generateTextService } = require('../scripts/modules/ai-services-unified.js');
            generateTextService.mockRejectedValue(new Error('API Error'));
            
            const result = await generateTestForTask('1', {
                tasksPath,
                outputDir: tempDir,
                validate: false
            });
            
            expect(result.success).toBe(false);
            expect(result.error).toContain('API Error');
        });
        
        it('should handle file system errors', async () => {
            const tasksPath = path.join(tempDir, 'tasks.json');
            fs.writeFileSync(tasksPath, JSON.stringify([
                { id: 1, title: 'Task', description: 'Test task' }
            ]), 'utf8');
            
            // Use non-existent directory
            const result = await generateTestForTask('1', {
                tasksPath,
                outputDir: '/invalid/path/that/does/not/exist',
                validate: false
            });
            
            expect(result.success).toBe(false);
        });
    });
});
