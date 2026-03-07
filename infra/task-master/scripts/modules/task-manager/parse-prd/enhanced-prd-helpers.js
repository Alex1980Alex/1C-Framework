/**
 * enhanced-prd-helpers.js
 * Enhanced helper functions for PRD parsing with context preservation
 * Part of Task #99.2 - Enhance Task Generation with PRD Context Preservation
 */

import fs from 'fs';
import path from 'path';
import chalk from 'chalk';
import { analyzePRDContent, shouldExpandTasks, getPRDContextForTask } from './prd-analysis-engine.js';
import { findTaskById } from '../../utils.js';
import { getPromptManager } from '../../prompt-manager.js';

/**
 * Enhanced PRD content reader with analysis
 * @param {string} prdPath - Path to PRD file
 * @param {Object} options - Analysis options
 * @returns {Object} PRD content and analysis results
 * @throws {Error} If file is empty or cannot be read
 */
export function readAndAnalyzePRDContent(prdPath, options = {}) {
	const prdContent = fs.readFileSync(prdPath, 'utf8');
	if (!prdContent) {
		throw new Error(`Input file ${prdPath} is empty or could not be read.`);
	}

	// Perform intelligent analysis
	const analysisResults = analyzePRDContent(prdContent, options);

	return {
		content: prdContent,
		analysis: analysisResults,
		shouldAutoExpand: shouldExpandTasks(analysisResults),
		estimatedTokens: Math.ceil(prdContent.length / 4)
	};
}

/**
 * Enhanced task processing with PRD context preservation
 * @param {Array} rawTasks - Raw tasks from AI
 * @param {number} startId - Starting ID for new tasks
 * @param {Array} existingTasks - Existing tasks for dependency validation
 * @param {string} defaultPriority - Default priority for tasks
 * @param {Object} prdAnalysis - PRD analysis results
 * @returns {Array} Processed tasks with PRD context
 */
export function processTasksWithContext(
	rawTasks,
	startId,
	existingTasks,
	defaultPriority,
	prdAnalysis
) {
	let currentId = startId;
	const taskMap = new Map();

	// First pass: assign new IDs and create mapping with PRD context
	const processedTasks = rawTasks.map((task) => {
		const newId = currentId++;
		taskMap.set(task.id, newId);

		// Generate PRD context for this task
		const prdContext = generatePRDContextForTask(task, prdAnalysis);

		// Calculate adaptive priority based on PRD analysis
		const adaptivePriority = calculateAdaptivePriority(task, prdContext, defaultPriority);

		return {
			...task,
			id: newId,
			status: task.status || 'pending',
			priority: adaptivePriority,
			dependencies: Array.isArray(task.dependencies) ? task.dependencies : [],
			subtasks: task.subtasks || [],
			// Enhanced fields with PRD context
			title: task.title || '',
			description: task.description || '',
			details: task.details || '',
			testStrategy: task.testStrategy || '',
			// NEW: PRD context preservation
			prdContext: prdContext,
			// NEW: Expansion metadata
			expansionMetadata: {
				analysisComplexity: prdContext?.complexity || 1,
				recommendedSubtasks: prdContext?.suggestedSubtasks?.length || 0,
				autoExpandable: shouldAutoExpandTask(task, prdContext),
				originalSection: prdContext?.sourceSection || null
			}
		};
	});

	// Second pass: remap dependencies
	processedTasks.forEach((task) => {
		task.dependencies = task.dependencies
			.map((depId) => taskMap.get(depId))
			.filter(
				(newDepId) =>
					newDepId != null &&
					newDepId < task.id &&
					(findTaskById(existingTasks, newDepId) ||
						processedTasks.some((t) => t.id === newDepId))
			);
	});

	return processedTasks;
}

/**
 * Generate PRD context for a specific task
 * @param {Object} task - Task object
 * @param {Object} prdAnalysis - PRD analysis results
 * @returns {Object|null} PRD context object
 */
function generatePRDContextForTask(task, prdAnalysis) {
	if (!prdAnalysis || !prdAnalysis.sectionMapping) {
		return null;
	}

	// Try to find matching section by title similarity
	const taskTitle = task.title?.toLowerCase() || '';
	const taskDescription = task.description?.toLowerCase() || '';

	let bestMatch = null;
	let bestScore = 0;

	prdAnalysis.sectionMapping.sections.forEach((section, sectionTitle) => {
		const sectionTitleLower = sectionTitle.toLowerCase();

		// Calculate similarity score
		let score = 0;

		// Direct title match
		if (sectionTitleLower.includes(taskTitle) || taskTitle.includes(sectionTitleLower)) {
			score += 5;
		}

		// Description match
		if (taskDescription && section.content.toLowerCase().includes(taskDescription)) {
			score += 3;
		}

		// Keyword matching
		const taskKeywords = extractKeywords(taskTitle + ' ' + taskDescription);
		const sectionKeywords = section.keywords || prdAnalysis.sectionMapping.extractKeywords(section.content);
		const commonKeywords = taskKeywords.filter(keyword => sectionKeywords.includes(keyword));
		score += commonKeywords.length;

		// Type-based matching
		if (section.type === 'feature' && (taskTitle.includes('implement') || taskTitle.includes('develop'))) {
			score += 2;
		}
		if (section.type === 'api' && taskTitle.includes('api')) {
			score += 3;
		}
		if (section.type === 'ui' && (taskTitle.includes('ui') || taskTitle.includes('interface'))) {
			score += 3;
		}

		if (score > bestScore) {
			bestScore = score;
			bestMatch = {
				sectionTitle,
				section,
				score
			};
		}
	});

	if (bestMatch && bestScore > 1) {
		const section = bestMatch.section;
		const relatedSections = prdAnalysis.sectionMapping.findRelatedSections(bestMatch.sectionTitle);

		return {
			sourceSection: `${bestMatch.sectionTitle} (Lines ${section.startLine}-${section.endLine})`,
			originalText: section.content,
			relatedSections: relatedSections,
			contextWindow: prdAnalysis.sectionMapping.createContextWindow(bestMatch.sectionTitle),
			complexity: section.complexity,
			type: section.type,
			keywords: prdAnalysis.sectionMapping.extractKeywords(section.content),
			suggestedSubtasks: getSuggestedSubtasksForSection(section),
			matchScore: bestScore
		};
	}

	return null;
}

/**
 * Extract keywords from text
 * @param {string} text - Text to extract keywords from
 * @returns {Array<string>} Array of keywords
 */
function extractKeywords(text) {
	const stopWords = new Set(['the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should']);

	return text
		.toLowerCase()
		.match(/\b[a-z]{3,}\b/g) // Words 3+ characters
		?.filter(word => !stopWords.has(word))
		?.filter((word, index, arr) => arr.indexOf(word) === index) // Remove duplicates
		|| [];
}

/**
 * Calculate adaptive priority based on PRD context
 * @param {Object} task - Task object
 * @param {Object} prdContext - PRD context
 * @param {string} defaultPriority - Default priority
 * @returns {string} Calculated priority
 */
function calculateAdaptivePriority(task, prdContext, defaultPriority) {
	if (!prdContext) {
		return task.priority || defaultPriority;
	}

	// Base priority mapping
	const priorityScores = {
		'low': 1,
		'medium': 2,
		'high': 3,
		'critical': 4
	};

	let score = priorityScores[task.priority || defaultPriority] || 2;

	// Adjust based on PRD context
	if (prdContext.complexity >= 4) {
		score += 1; // High complexity sections get higher priority
	}

	if (prdContext.type === 'requirement' || prdContext.type === 'api') {
		score += 1; // Requirements and APIs are typically high priority
	}

	if (prdContext.matchScore >= 4) {
		score += 1; // Strong matches to PRD sections get higher priority
	}

	// Map back to priority string
	if (score >= 4) return 'critical';
	if (score >= 3) return 'high';
	if (score >= 2) return 'medium';
	return 'low';
}

/**
 * Determine if a task should be auto-expanded
 * @param {Object} task - Task object
 * @param {Object} prdContext - PRD context
 * @returns {boolean} True if task should be auto-expanded
 */
function shouldAutoExpandTask(task, prdContext) {
	if (!prdContext) return false;

	// Auto-expand high complexity sections
	if (prdContext.complexity >= 3) return true;

	// Auto-expand if many suggested subtasks
	if (prdContext.suggestedSubtasks?.length >= 4) return true;

	// Auto-expand feature and API sections
	if (['feature', 'api', 'technical'].includes(prdContext.type)) return true;

	return false;
}

/**
 * Get suggested subtasks for a section
 * @param {Object} section - Section object
 * @returns {Array<string>} Array of suggested subtask titles
 */
function getSuggestedSubtasksForSection(section) {
	const subtasks = [];

	switch (section.type) {
		case 'feature':
			subtasks.push('Design feature specifications');
			subtasks.push('Implement core functionality');
			subtasks.push('Add input validation');
			subtasks.push('Write unit tests');
			subtasks.push('Integration testing');
			break;

		case 'api':
			subtasks.push('Design API endpoints');
			subtasks.push('Implement request/response handling');
			subtasks.push('Add authentication middleware');
			subtasks.push('Write API documentation');
			subtasks.push('Create integration tests');
			break;

		case 'ui':
			subtasks.push('Create UI mockups');
			subtasks.push('Implement components');
			subtasks.push('Add responsive design');
			subtasks.push('Implement user interactions');
			subtasks.push('Accessibility testing');
			break;

		case 'technical':
			subtasks.push('Technical research and planning');
			subtasks.push('Architecture implementation');
			subtasks.push('Performance optimization');
			subtasks.push('Security considerations');
			subtasks.push('Documentation');
			break;

		default:
			subtasks.push('Analysis and planning');
			subtasks.push('Implementation');
			subtasks.push('Testing and validation');
			break;
	}

	return subtasks;
}

/**
 * Build enhanced prompts with PRD analysis context
 * @param {Object} config - Parse configuration
 * @param {string} prdContent - PRD content
 * @param {Object} prdAnalysis - PRD analysis results
 * @param {number} nextId - Next task ID
 * @returns {Promise<Object>} Enhanced prompts
 */
export async function buildEnhancedPrompts(config, prdContent, prdAnalysis, nextId) {
	const promptManager = await getPromptManager();

	// Build context-aware system prompt
	const systemPrompt = buildContextAwareSystemPrompt(prdAnalysis);

	// Build enhanced user prompt with analysis insights
	const userPrompt = buildEnhancedUserPrompt(
		prdContent,
		prdAnalysis,
		config.numTasks,
		nextId,
		config.targetTag
	);

	return {
		systemPrompt,
		userPrompt,
		analysisMetadata: {
			complexityScore: prdAnalysis.complexityScore,
			recommendedTaskCount: prdAnalysis.recommendedTaskCount,
			shouldAutoExpand: shouldExpandTasks(prdAnalysis),
			sectionCount: prdAnalysis.metrics.sectionCount,
			featureCount: prdAnalysis.metrics.featureCount
		}
	};
}

/**
 * Build context-aware system prompt
 * @param {Object} prdAnalysis - PRD analysis results
 * @returns {string} Enhanced system prompt
 */
function buildContextAwareSystemPrompt(prdAnalysis) {
	const basePrompt = `You are an AI assistant specialized in analyzing Product Requirements Documents (PRDs) and generating structured development tasks with context preservation.

## Enhanced Analysis Context

**PRD Complexity**: ${prdAnalysis.complexityScore}/10
**Recommended Tasks**: ${prdAnalysis.recommendedTaskCount}
**Features Identified**: ${prdAnalysis.metrics.featureCount}
**Technical Depth**: ${prdAnalysis.metrics.technicalDepth.toFixed(1)}/2.0

## Section Analysis
The PRD has been analyzed and segmented into ${prdAnalysis.metrics.sectionCount} logical sections:
${Array.from(prdAnalysis.sectionMapping.sections.entries())
	.map(([title, section]) => `- **${title}** (${section.type}, complexity: ${section.complexity}/5)`)
	.join('\n')}

## Task Generation Guidelines

1. **Context Preservation**: Each task should include specific references to the PRD sections it implements
2. **Adaptive Granularity**: Adjust task granularity based on section complexity and type
3. **Natural Boundaries**: Respect the natural section boundaries identified in the analysis
4. **Technical Accuracy**: Maintain fidelity to the original PRD specifications
5. **Expansion Readiness**: Structure tasks to support context-aware expansion

## Required Task Structure

Each task must include:
- **title**: Clear, actionable task title
- **description**: Brief description linking to PRD requirements
- **details**: Specific implementation details from the PRD
- **testStrategy**: Testing approach based on requirements
- **priority**: Adaptive priority based on PRD analysis
- **dependencies**: Valid task dependencies`;

	return basePrompt;
}

/**
 * Build enhanced user prompt with analysis insights
 * @param {string} prdContent - PRD content
 * @param {Object} prdAnalysis - PRD analysis results
 * @param {number} numTasks - Requested number of tasks
 * @param {number} nextId - Next task ID
 * @param {string} targetTag - Target tag
 * @returns {string} Enhanced user prompt
 */
function buildEnhancedUserPrompt(prdContent, prdAnalysis, numTasks, nextId, targetTag) {
	const adaptiveTaskCount = numTasks === 0 ? prdAnalysis.recommendedTaskCount : numTasks;

	const prompt = `## PRD Analysis & Task Generation Request

### Analysis Summary
- **Complexity Score**: ${prdAnalysis.complexityScore}/10
- **Natural Sections**: ${prdAnalysis.metrics.sectionCount}
- **Identified Features**: ${prdAnalysis.metrics.featureCount}
- **Task Count**: Generate ${adaptiveTaskCount} tasks (${numTasks === 0 ? 'auto-determined' : 'specified'})

### Task Boundaries Identified
${prdAnalysis.taskBoundaries.map(boundary =>
	`**${boundary.title}** (${boundary.type}, complexity: ${boundary.complexity})`
).join('\n')}

### Context Preservation Requirements
Each generated task should:
1. Map to specific PRD sections when possible
2. Include original text references for expansion context
3. Preserve technical specifications and requirements
4. Maintain relationships between related sections

### PRD Content
\`\`\`
${prdContent}
\`\`\`

### Generation Instructions
1. Generate ${adaptiveTaskCount} well-structured tasks starting from ID ${nextId}
2. Each task should correspond to natural section boundaries where possible
3. Include detailed implementation guidance from the PRD
4. Set appropriate priorities based on complexity analysis
5. Create logical dependencies between related tasks

Please generate the tasks as a JSON array following the specified structure, ensuring each task preserves context from its corresponding PRD sections.`;

	return prompt;
}

/**
 * Enhanced save function with PRD context metadata
 * @param {string} tasksPath - Path to save tasks
 * @param {Array} tasks - Tasks to save with PRD context
 * @param {string} targetTag - Target tag
 * @param {Object} logger - Logger instance
 * @param {Object} prdAnalysis - PRD analysis results
 */
export function saveTasksWithPRDContext(tasksPath, tasks, targetTag, logger, prdAnalysis) {
	// Create directory if it doesn't exist
	const tasksDir = path.dirname(tasksPath);
	if (!fs.existsSync(tasksDir)) {
		fs.mkdirSync(tasksDir, { recursive: true });
	}

	// Read existing file to preserve other tags
	let outputData = {};
	if (fs.existsSync(tasksPath)) {
		try {
			const existingFileContent = fs.readFileSync(tasksPath, 'utf8');
			outputData = JSON.parse(existingFileContent);
		} catch (error) {
			outputData = {};
		}
	}

	// Ensure tag structure exists with enhanced metadata
	if (!outputData[targetTag]) {
		outputData[targetTag] = {
			tasks: [],
			metadata: {
				createdAt: new Date().toISOString(),
				version: '2.0.0' // Version 2.0 includes PRD context
			}
		};
	}

	// Add PRD analysis metadata to tag
	outputData[targetTag].metadata = {
		...outputData[targetTag].metadata,
		lastUpdated: new Date().toISOString(),
		prdAnalysis: {
			complexityScore: prdAnalysis.complexityScore,
			sectionCount: prdAnalysis.metrics.sectionCount,
			featureCount: prdAnalysis.metrics.featureCount,
			technicalDepth: prdAnalysis.metrics.technicalDepth,
			recommendedTaskCount: prdAnalysis.recommendedTaskCount,
			analysisVersion: '1.0.0'
		},
		generationMode: 'enhanced_context_preservation'
	};

	// Update tasks
	outputData[targetTag].tasks = tasks;

	// Write file
	fs.writeFileSync(tasksPath, JSON.stringify(outputData, null, 2));

	logger.report(
		`Saved ${tasks.length} tasks with PRD context to ${tasksPath} under tag '${targetTag}'`,
		'info'
	);

	// Log enhancement statistics
	const tasksWithContext = tasks.filter(task => task.prdContext);
	const autoExpandableTasks = tasks.filter(task => task.expansionMetadata?.autoExpandable);

	logger.report(
		`PRD Context Enhancement: ${tasksWithContext.length}/${tasks.length} tasks with context, ${autoExpandableTasks.length} auto-expandable`,
		'debug'
	);
}

/**
 * Validate enhanced task structure
 * @param {Array} tasks - Tasks to validate
 * @param {Object} logger - Logger instance
 * @returns {boolean} True if all tasks are valid
 */
export function validateEnhancedTasks(tasks, logger) {
	const requiredFields = ['id', 'title', 'description', 'status', 'priority'];
	const enhancedFields = ['prdContext', 'expansionMetadata'];

	let isValid = true;

	tasks.forEach((task, index) => {
		// Check required fields
		for (const field of requiredFields) {
			if (!task[field]) {
				logger.report(`Task ${index + 1}: Missing required field '${field}'`, 'error');
				isValid = false;
			}
		}

		// Check enhanced structure
		if (task.prdContext) {
			const contextFields = ['sourceSection', 'originalText', 'complexity', 'type'];
			for (const field of contextFields) {
				if (!task.prdContext[field]) {
					logger.report(`Task ${index + 1}: PRD context missing field '${field}'`, 'warn');
				}
			}
		}

		if (task.expansionMetadata) {
			const metadataFields = ['analysisComplexity', 'autoExpandable'];
			for (const field of metadataFields) {
				if (task.expansionMetadata[field] === undefined) {
					logger.report(`Task ${index + 1}: Expansion metadata missing field '${field}'`, 'warn');
				}
			}
		}
	});

	return isValid;
}

// Export compatibility functions for existing code
export {
	readPrdContent as readPrdContentLegacy,
	processTasks as processTasksLegacy
} from './parse-prd-helpers.js';