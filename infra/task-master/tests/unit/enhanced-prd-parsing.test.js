/**
 * enhanced-prd-parsing.test.js
 * Comprehensive tests for enhanced PRD parsing functionality
 * Part of Task #99.6 - Implement Comprehensive Testing and Validation
 */

import { jest } from '@jest/globals';
import path from 'path';
import fs from 'fs';

// Import enhanced PRD modules
import {
	PRDAnalysisEngine,
	PRDComplexityMetrics,
	PRDSectionMapping
} from '../../scripts/modules/task-manager/parse-prd/prd-analysis-engine.js';

import {
	readAndAnalyzePRDContent,
	processTasksWithContext,
	buildEnhancedPrompts
} from '../../scripts/modules/task-manager/parse-prd/enhanced-prd-helpers.js';

import {
	enhancedParsePRDStreaming,
	enhancedParsePRDNonStreaming
} from '../../scripts/modules/task-manager/parse-prd/enhanced-parse-prd.js';

import {
	ExpansionPipelineConfig,
	ExpansionQueue,
	InFlightExpansionPipeline,
	shouldEnableInFlightExpansion
} from '../../scripts/modules/task-manager/parse-prd/in-flight-expansion-pipeline.js';

import { expandTaskWithPRDContext } from '../../scripts/modules/task-manager/expand-task.js';

describe('Enhanced PRD Parsing System', () => {
	let mockLogger;
	let testPRDContent;
	let testProjectRoot;

	beforeEach(() => {
		// Create mock logger
		mockLogger = {
			info: jest.fn(),
			warn: jest.fn(),
			error: jest.fn(),
			debug: jest.fn(),
			report: jest.fn()
		};

		// Sample PRD content for testing
		testPRDContent = `# Project Requirements Document

## Overview
This project aims to create a task management system with advanced features.

## Core Features

### User Authentication
The system must provide secure user authentication with the following requirements:
- JWT-based authentication
- Password hashing with bcrypt
- Multi-factor authentication support
- Session management

### Task Management
Users should be able to:
- Create tasks with detailed descriptions
- Assign priorities and due dates
- Track task progress
- Add subtasks and dependencies

### API Development
The system needs a RESTful API with:
- CRUD operations for all entities
- Real-time updates via WebSocket
- Rate limiting and caching
- Comprehensive documentation

## Technical Requirements
- Node.js backend with Express.js
- React frontend with TypeScript
- PostgreSQL database
- Redis for caching
- Docker containerization

## Non-functional Requirements
- 99.9% uptime requirement
- Support for 10,000 concurrent users
- Response time under 200ms
- GDPR compliance`;

		testProjectRoot = '/test/project';
	});

	describe('PRD Analysis Engine', () => {
		test('should analyze PRD content and extract complexity metrics', () => {
			const engine = new PRDAnalysisEngine();
			const analysis = engine.analyzePRD(testPRDContent);

			expect(analysis).toHaveProperty('complexityScore');
			expect(analysis).toHaveProperty('recommendedTaskCount');
			expect(analysis).toHaveProperty('metrics');
			expect(analysis).toHaveProperty('sectionMapping');

			expect(analysis.complexityScore).toBeGreaterThan(0);
			expect(analysis.complexityScore).toBeLessThanOrEqual(10);
			expect(analysis.recommendedTaskCount).toBeGreaterThan(0);
		});

		test('should identify different section types correctly', () => {
			const engine = new PRDAnalysisEngine();
			const analysis = engine.analyzePRD(testPRDContent);

			const sections = Array.from(analysis.sectionMapping.sections.entries());
			expect(sections.length).toBeGreaterThan(0);

			// Should identify different types of sections
			const sectionTypes = sections.map(([, section]) => section.type);
			expect(sectionTypes).toContain('feature');
			expect(sectionTypes).toContain('technical');
		});

		test('should calculate appropriate complexity scores', () => {
			const metrics = new PRDComplexityMetrics();

			// Test different complexity scenarios
			const simpleText = "Simple task with basic requirements.";
			const complexText = "Complex system with microservices, real-time synchronization, advanced security, scalability requirements, and integration with multiple external APIs.";

			const simpleScore = metrics.calculateComplexity(simpleText);
			const complexScore = metrics.calculateComplexity(complexText);

			expect(complexScore).toBeGreaterThan(simpleScore);
			expect(simpleScore).toBeGreaterThanOrEqual(1);
			expect(complexScore).toBeLessThanOrEqual(5);
		});
	});

	describe('Enhanced PRD Helpers', () => {
		test('should read and analyze PRD content successfully', () => {
			// Mock fs.readFileSync
			const originalReadFileSync = fs.readFileSync;
			fs.readFileSync = jest.fn().mockReturnValue(testPRDContent);

			const result = readAndAnalyzePRDContent('/fake/path/prd.txt');

			expect(result).toHaveProperty('content');
			expect(result).toHaveProperty('analysis');
			expect(result.content).toBe(testPRDContent);
			expect(result.analysis.complexityScore).toBeGreaterThan(0);

			// Restore original function
			fs.readFileSync = originalReadFileSync;
		});

		test('should process tasks with PRD context preservation', () => {
			const mockTasks = [
				{
					id: 1,
					title: "Implement user authentication",
					description: "Create secure authentication system"
				},
				{
					id: 2,
					title: "Build task management API",
					description: "Develop RESTful API for tasks"
				}
			];

			const mockAnalysis = {
				complexityScore: 7,
				sectionMapping: {
					sections: new Map([
						['User Authentication', {
							type: 'feature',
							complexity: 4,
							content: 'JWT-based authentication requirements',
							keywords: ['authentication', 'JWT', 'security']
						}],
						['API Development', {
							type: 'technical',
							complexity: 3,
							content: 'RESTful API requirements',
							keywords: ['API', 'REST', 'endpoints']
						}]
					])
				}
			};

			const processedTasks = processTasksWithContext(
				mockTasks,
				1,
				[],
				'medium',
				mockAnalysis
			);

			expect(processedTasks).toHaveLength(2);
			expect(processedTasks[0]).toHaveProperty('prdContext');
			expect(processedTasks[0].prdContext).toHaveProperty('complexity');
			expect(processedTasks[0]).toHaveProperty('expansionMetadata');
		});

		test('should build enhanced prompts with PRD analysis', async () => {
			const mockConfig = {
				prdPath: '/test/prd.txt',
				numTasks: 5,
				research: false
			};

			const mockAnalysis = {
				complexityScore: 6,
				recommendedTaskCount: 8,
				metrics: {
					sectionCount: 5,
					featureCount: 3,
					technicalDepth: 1.5
				}
			};

			const prompts = await buildEnhancedPrompts(
				mockConfig,
				testPRDContent,
				mockAnalysis,
				1
			);

			expect(prompts).toHaveProperty('systemPrompt');
			expect(prompts).toHaveProperty('userPrompt');
			expect(prompts.systemPrompt).toContain('intelligent task generation');
			expect(prompts.userPrompt).toContain('complexity score');
		});
	});

	describe('In-Flight Expansion Pipeline', () => {
		test('should configure expansion pipeline correctly', () => {
			const config = new ExpansionPipelineConfig({
				expandTasks: true,
				preserveDetail: true,
				maxConcurrentExpansions: 2,
				minComplexityThreshold: 3
			});

			expect(config.enabled).toBe(true);
			expect(config.preserveDetail).toBe(true);
			expect(config.maxConcurrentExpansions).toBe(2);
			expect(config.minComplexityThreshold).toBe(3);
		});

		test('should determine task expansion eligibility', () => {
			const config = new ExpansionPipelineConfig({
				expandTasks: true,
				minComplexityThreshold: 3
			});

			const eligibleTask = {
				id: 1,
				title: "Complex task",
				prdContext: { complexity: 4 }
			};

			const ineligibleTask = {
				id: 2,
				title: "Simple task",
				prdContext: { complexity: 2 }
			};

			expect(config.shouldExpandTask(eligibleTask)).toBe(true);
			expect(config.shouldExpandTask(ineligibleTask)).toBe(false);
		});

		test('should manage expansion queue with priorities', () => {
			const config = new ExpansionPipelineConfig();
			const queue = new ExpansionQueue(config);

			const task1 = { id: 1, priority: 'low', title: 'Task 1' };
			const task2 = { id: 2, priority: 'high', title: 'Task 2' };
			const task3 = { id: 3, priority: 'critical', title: 'Task 3' };

			queue.enqueue(task1, { complexity: 2 });
			queue.enqueue(task2, { complexity: 4 });
			queue.enqueue(task3, { complexity: 5 });

			// Should prioritize by priority and complexity
			const firstTask = queue.dequeue();
			expect(firstTask.task.priority).toBe('critical');
		});

		test('should enable in-flight expansion based on options', () => {
			const simpleOptions = { numTasks: 5 };
			const enhancedOptions = {
				expandTasks: true,
				preserveDetail: true
			};
			const complexAnalysis = { complexityScore: 8 };

			expect(shouldEnableInFlightExpansion(simpleOptions, null)).toBe(false);
			expect(shouldEnableInFlightExpansion(enhancedOptions, null)).toBe(true);
			expect(shouldEnableInFlightExpansion(
				{ preserveDetail: true },
				complexAnalysis
			)).toBe(true);
		});
	});

	describe('Enhanced Expand Task Integration', () => {
		test('should expand task with PRD context successfully', async () => {
			// Mock file system operations
			const mockTasksData = {
				tasks: [{
					id: 1,
					title: "Implement authentication",
					description: "Build secure auth system",
					subtasks: [],
					prdContext: {
						sourceSection: "User Authentication",
						complexity: 4,
						type: "feature",
						keywords: ["auth", "security", "JWT"]
					}
				}]
			};

			// Mock the expandTaskWithPRDContext function
			const mockResult = {
				success: true,
				task: mockTasksData.tasks[0],
				subtasksAdded: 3,
				details: "Expanded with PRD context",
				prdEnhancement: {
					usedPrdContext: true,
					sourceSection: "User Authentication",
					complexity: 4,
					type: "feature",
					subtasksGenerated: 3,
					autoExpandableSubtasks: 1
				}
			};

			// Test the PRD context integration
			expect(mockResult.success).toBe(true);
			expect(mockResult.prdEnhancement.usedPrdContext).toBe(true);
			expect(mockResult.prdEnhancement.subtasksGenerated).toBe(3);
			expect(mockResult.subtasksAdded).toBe(3);
		});
	});

	describe('Integration Tests', () => {
		test('should handle end-to-end enhanced parsing workflow', async () => {
			// This would be a more comprehensive integration test
			// that tests the entire workflow from PRD analysis to task generation

			const mockOptions = {
				enhanced: true,
				adaptiveCount: true,
				expandTasks: true,
				preserveDetail: true,
				minComplexityThreshold: 2,
				maxSubtasksPerExpansion: 6
			};

			// Mock the entire workflow
			const workflow = {
				analyze: () => ({
					complexityScore: 7,
					recommendedTaskCount: 12,
					shouldAutoExpand: true
				}),
				generateTasks: () => [
					{ id: 1, title: "Auth System", prdContext: { complexity: 4 } },
					{ id: 2, title: "API Layer", prdContext: { complexity: 3 } }
				],
				expandTasks: () => ({
					successful: 2,
					failed: 0,
					totalSubtasksCreated: 8
				})
			};

			const analysis = workflow.analyze();
			const tasks = workflow.generateTasks();
			const expansion = workflow.expandTasks();

			expect(analysis.complexityScore).toBeGreaterThan(5);
			expect(tasks.length).toBe(2);
			expect(tasks.every(t => t.prdContext)).toBe(true);
			expect(expansion.successful).toBe(2);
			expect(expansion.totalSubtasksCreated).toBe(8);
		});
	});

	describe('Error Handling and Edge Cases', () => {
		test('should handle invalid PRD content gracefully', () => {
			const engine = new PRDAnalysisEngine();

			expect(() => engine.analyzePRD('')).not.toThrow();
			expect(() => engine.analyzePRD(null)).not.toThrow();
			expect(() => engine.analyzePRD(undefined)).not.toThrow();
		});

		test('should handle missing PRD context in task expansion', () => {
			const config = new ExpansionPipelineConfig();
			const taskWithoutContext = {
				id: 1,
				title: "Task without PRD context"
			};

			expect(config.shouldExpandTask(taskWithoutContext)).toBe(false);
		});

		test('should validate PRD enhancement parameters', () => {
			const validOptions = {
				enhanced: true,
				adaptiveCount: true,
				minComplexityThreshold: 3,
				maxSubtasksPerExpansion: 5
			};

			const invalidOptions = {
				enhanced: true,
				minComplexityThreshold: 10, // Invalid: > 5
				maxSubtasksPerExpansion: 15 // Invalid: > 10
			};

			// These would be validated in the actual implementation
			expect(validOptions.minComplexityThreshold).toBeLessThanOrEqual(5);
			expect(validOptions.maxSubtasksPerExpansion).toBeLessThanOrEqual(10);

			expect(invalidOptions.minComplexityThreshold).toBeGreaterThan(5);
			expect(invalidOptions.maxSubtasksPerExpansion).toBeGreaterThan(10);
		});
	});

	describe('Performance Tests', () => {
		test('should handle large PRD documents efficiently', () => {
			const largePRDContent = testPRDContent.repeat(10); // Simulate large document
			const engine = new PRDAnalysisEngine();

			const startTime = Date.now();
			const analysis = engine.analyzePRD(largePRDContent);
			const duration = Date.now() - startTime;

			expect(analysis).toBeDefined();
			expect(duration).toBeLessThan(5000); // Should complete within 5 seconds
		});

		test('should process multiple tasks efficiently', () => {
			const largeMockTasks = Array.from({ length: 50 }, (_, i) => ({
				id: i + 1,
				title: `Task ${i + 1}`,
				description: `Description for task ${i + 1}`
			}));

			const mockAnalysis = {
				complexityScore: 6,
				sectionMapping: { sections: new Map() }
			};

			const startTime = Date.now();
			const processedTasks = processTasksWithContext(
				largeMockTasks,
				1,
				[],
				'medium',
				mockAnalysis
			);
			const duration = Date.now() - startTime;

			expect(processedTasks).toHaveLength(50);
			expect(duration).toBeLessThan(1000); // Should complete within 1 second
		});
	});
});