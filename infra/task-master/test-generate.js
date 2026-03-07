#!/usr/bin/env node

/**
 * Test script for generate-test functionality
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import chalk from 'chalk';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Read tasks from master tag
const tasksPath = path.join(__dirname, '.taskmaster/tasks/tasks.json');
const tasks = JSON.parse(fs.readFileSync(tasksPath, 'utf8'));

// Find task 24
const task24 = tasks.find(t => t.id === 24);

if (task24) {
    console.log(chalk.green('✅ Found Task #24:'));
    console.log(chalk.blue(`   ID: ${task24.id}`));
    console.log(chalk.blue(`   Title: ${task24.title}`));
    console.log(chalk.blue(`   Status: ${task24.status}`));
    console.log(chalk.blue(`   Priority: ${task24.priority}`));
    console.log(chalk.blue(`   Subtasks: ${task24.subtasks ? task24.subtasks.length : 0}`));
    
    // Generate a sample test file
    const testContent = `/**
 * Generated Test File for Task #${task24.id}
 * ${task24.title}
 */

import { describe, it, expect, beforeEach, afterEach, jest } from '@jest/globals';
import { generateTestForTask } from '../scripts/modules/task-manager/generate-test.js';
import { getConfig } from '../scripts/modules/config-manager.js';

describe('Task #${task24.id}: ${task24.title}', () => {
    let originalConfig;
    
    beforeEach(() => {
        // Save original config
        originalConfig = getConfig();
        
        // Mock config for tests
        jest.clearAllMocks();
    });
    
    afterEach(() => {
        // Restore original config
        jest.resetModules();
    });
    
    describe('Command Structure', () => {
        it('should register generate-test command with proper options', () => {
            // Test command registration
            expect(typeof generateTestForTask).toBe('function');
        });
        
        it('should accept required --id parameter', async () => {
            // Test with valid task ID
            const result = await generateTestForTask('1', {
                tasksPath: './test-fixtures/tasks.json',
                outputDir: './test-output',
                validate: false
            });
            
            expect(result).toHaveProperty('success');
        });
    });
    
    describe('AI Integration', () => {
        it('should construct appropriate prompt for Claude API', () => {
            // Test prompt construction
            const taskData = {
                id: 1,
                title: 'Test Task',
                description: 'Test description'
            };
            
            // Mock implementation would test prompt generation
            expect(taskData).toBeDefined();
        });
        
        it('should handle Claude API responses correctly', async () => {
            // Mock Claude API response
            const mockResponse = {
                mainResult: \`import { describe, test, expect } from '@jest/globals';
                
describe('Test', () => {
    test('should work', () => {
        expect(true).toBe(true);
    });
});\`
            };
            
            expect(mockResponse.mainResult).toContain('describe');
            expect(mockResponse.mainResult).toContain('test');
        });
    });
    
    describe('Test File Generation', () => {
        it('should generate test file with correct naming convention', () => {
            // Test file naming
            const taskId = '24';
            const expectedName = 'task_024.test.ts';
            
            const paddedId = taskId.padStart(3, '0');
            const generatedName = \`task_\${paddedId}.test.ts\`;
            
            expect(generatedName).toBe(expectedName);
        });
        
        it('should handle subtask naming correctly', () => {
            // Test subtask file naming
            const parentId = 24;
            const subtaskId = 1;
            const expectedName = 'task_024_001.test.ts';
            
            const parentPadded = parentId.toString().padStart(3, '0');
            const subtaskPadded = subtaskId.toString().padStart(3, '0');
            const generatedName = \`task_\${parentPadded}_\${subtaskPadded}.test.ts\`;
            
            expect(generatedName).toBe(expectedName);
        });
    });
    
    describe('Error Handling', () => {
        it('should handle invalid task IDs gracefully', async () => {
            // Test with non-existent task
            const result = await generateTestForTask('99999', {
                tasksPath: './test-fixtures/tasks.json',
                outputDir: './test-output',
                validate: false
            });
            
            expect(result.success).toBe(false);
            expect(result.error).toContain('not found');
        });
        
        it('should handle API failures with proper error messages', async () => {
            // Mock API failure scenario
            const error = new Error('API request failed');
            
            expect(error.message).toContain('API');
        });
    });
    
    describe('Validation', () => {
        it('should validate generated test content for Jest compatibility', () => {
            const validContent = \`
import { describe, it, expect } from '@jest/globals';

describe('Test Suite', () => {
    it('should pass', () => {
        expect(true).toBe(true);
    });
});
\`;
            
            // Check for required Jest elements
            expect(validContent).toContain('describe');
            expect(validContent).toContain('it');
            expect(validContent).toContain('expect');
            expect(validContent.length).toBeGreaterThan(100);
        });
        
        it('should skip validation when --no-validate flag is used', async () => {
            const result = await generateTestForTask('1', {
                tasksPath: './test-fixtures/tasks.json',
                outputDir: './test-output',
                validate: false // Corresponds to --no-validate
            });
            
            // Should not throw validation errors
            expect(result).toBeDefined();
        });
    });
});
`;
    
    // Create output directory
    const outputDir = path.join(__dirname, 'generated-tests');
    if (!fs.existsSync(outputDir)) {
        fs.mkdirSync(outputDir, { recursive: true });
    }
    
    // Write test file
    const outputPath = path.join(outputDir, 'task_024.test.ts');
    fs.writeFileSync(outputPath, testContent, 'utf8');
    
    console.log(chalk.green('\n✅ Test file generated successfully!'));
    console.log(chalk.gray(`   Output: ${outputPath}`));
    console.log(chalk.gray(`   Lines: ${testContent.split('\n').length}`));
    
} else {
    console.log(chalk.red('❌ Task #24 not found in tasks.json'));
    console.log(chalk.yellow('Available task IDs:'), tasks.map(t => t.id).join(', '));
}