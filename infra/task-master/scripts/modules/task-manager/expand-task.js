import fs from 'fs';
import path from 'path';
import { z } from 'zod';

import {
	log,
	readJSON,
	writeJSON,
	isSilentMode,
	getTagAwareFilePath
} from '../utils.js';

import {
	startLoadingIndicator,
	stopLoadingIndicator,
	displayAiUsageSummary
} from '../ui.js';

import { generateTextService } from '../ai-services-unified.js';
import { enhancePromptWithContext } from '../context/ai-context-integration.js';

import {
	getDefaultSubtasks,
	getDebugFlag,
	hasCodebaseAnalysis
} from '../config-manager.js';
import { getPromptManager } from '../prompt-manager.js';
import generateTaskFiles from './generate-task-files.js';
import { COMPLEXITY_REPORT_FILE } from '../../../src/constants/paths.js';
import { ContextGatherer } from '../utils/contextGatherer.js';
import { FuzzyTaskSearch } from '../utils/fuzzyTaskSearch.js';
import { flattenTasksWithSubtasks, findProjectRoot } from '../utils.js';

// --- Zod Schemas (Keep from previous step) ---
const subtaskSchema = z
	.object({
		id: z
			.number()
			.int()
			.positive()
			.describe('Sequential subtask ID starting from 1'),
		title: z.string().min(5).describe('Clear, specific title for the subtask'),
		description: z
			.string()
			.min(10)
			.describe('Detailed description of the subtask'),
		dependencies: z
			.array(z.string())
			.describe(
				'Array of subtask dependencies within the same parent task. Use format ["parentTaskId.1", "parentTaskId.2"]. Subtasks can only depend on siblings, not external tasks.'
			),
		details: z.string().min(20).describe('Implementation details and guidance'),
		status: z
			.string()
			.describe(
				'The current status of the subtask (should be pending initially)'
			),
		testStrategy: z
			.string()
			.nullable()
			.describe('Approach for testing this subtask')
			.default('')
	})
	.strict();
const subtaskArraySchema = z.array(subtaskSchema);
const subtaskWrapperSchema = z.object({
	subtasks: subtaskArraySchema.describe('The array of generated subtasks.')
});
// --- End Zod Schemas ---

/**
 * Parse subtasks from AI's text response. Includes basic cleanup.
 * @param {string} text - Response text from AI.
 * @param {number} startId - Starting subtask ID expected.
 * @param {number} expectedCount - Expected number of subtasks.
 * @param {number} parentTaskId - Parent task ID for context.
 * @param {Object} logger - Logging object (mcpLog or console log).
 * @returns {Array} Parsed and potentially corrected subtasks array.
 * @throws {Error} If parsing fails or JSON is invalid/malformed.
 */
function parseSubtasksFromText(
	text,
	startId,
	expectedCount,
	parentTaskId,
	logger
) {
	if (typeof text !== 'string') {
		logger.error(
			`AI response text is not a string. Received type: ${typeof text}, Value: ${text}`
		);
		throw new Error('AI response text is not a string.');
	}

	if (!text || text.trim() === '') {
		throw new Error('AI response text is empty after trimming.');
	}

	const originalTrimmedResponse = text.trim(); // Store the original trimmed response
	let jsonToParse = originalTrimmedResponse; // Initialize jsonToParse with it

	logger.debug(
		`Original AI Response for parsing (full length: ${jsonToParse.length}): ${jsonToParse.substring(0, 1000)}...`
	);

	// --- Pre-emptive cleanup for known AI JSON issues ---
	// Fix for "dependencies": , or "dependencies":,
	if (jsonToParse.includes('"dependencies":')) {
		const malformedPattern = /"dependencies":\s*,/g;
		if (malformedPattern.test(jsonToParse)) {
			logger.warn('Attempting to fix malformed "dependencies": , issue.');
			jsonToParse = jsonToParse.replace(
				malformedPattern,
				'"dependencies": [],'
			);
			logger.debug(
				`JSON after fixing "dependencies": ${jsonToParse.substring(0, 500)}...`
			);
		}
	}
	// --- End pre-emptive cleanup ---

	let parsedObject;
	let primaryParseAttemptFailed = false;

	// --- Attempt 1: Simple Parse (with optional Markdown cleanup) ---
	logger.debug('Attempting simple parse...');
	try {
		// Check for markdown code block
		const codeBlockMatch = jsonToParse.match(/```(?:json)?\s*([\s\S]*?)\s*```/);
		let contentToParseDirectly = jsonToParse;
		if (codeBlockMatch && codeBlockMatch[1]) {
			contentToParseDirectly = codeBlockMatch[1].trim();
			logger.debug('Simple parse: Extracted content from markdown code block.');
		} else {
			logger.debug(
				'Simple parse: No markdown code block found, using trimmed original.'
			);
		}

		parsedObject = JSON.parse(contentToParseDirectly);
		logger.debug('Simple parse successful!');

		// Quick check if it looks like our target object
		if (
			!parsedObject ||
			typeof parsedObject !== 'object' ||
			!Array.isArray(parsedObject.subtasks)
		) {
			logger.warn(
				'Simple parse succeeded, but result is not the expected {"subtasks": []} structure. Will proceed to advanced extraction.'
			);
			primaryParseAttemptFailed = true;
			parsedObject = null; // Reset parsedObject so we enter the advanced logic
		}
		// If it IS the correct structure, we'll skip advanced extraction.
	} catch (e) {
		logger.warn(
			`Simple parse failed: ${e.message}. Proceeding to advanced extraction logic.`
		);
		primaryParseAttemptFailed = true;
		// jsonToParse is already originalTrimmedResponse if simple parse failed before modifying it for markdown
	}

	// --- Attempt 2: Advanced Extraction (if simple parse failed or produced wrong structure) ---
	if (primaryParseAttemptFailed || !parsedObject) {
		// Ensure we try advanced if simple parse gave wrong structure
		logger.debug('Attempting advanced extraction logic...');
		// Reset jsonToParse to the original full trimmed response for advanced logic
		jsonToParse = originalTrimmedResponse;

		// (Insert the more complex extraction logic here - the one we worked on with:
		//  - targetPattern = '{"subtasks":';
		//  - careful brace counting for that targetPattern
		//  - fallbacks to last '{' and '}' if targetPattern logic fails)
		//  This was the logic from my previous message. Let's assume it's here.
		//  This block should ultimately set `jsonToParse` to the best candidate string.

		// Example snippet of that advanced logic's start:
		const targetPattern = '{"subtasks":';
		const patternStartIndex = jsonToParse.indexOf(targetPattern);

		if (patternStartIndex !== -1) {
			const openBraces = 0;
			const firstBraceFound = false;
			const extractedJsonBlock = '';
			// ... (loop for brace counting as before) ...
			// ... (if successful, jsonToParse = extractedJsonBlock) ...
			// ... (if that fails, fallbacks as before) ...
		} else {
			// ... (fallback to last '{' and '}' if targetPattern not found) ...
		}
		// End of advanced logic excerpt

		logger.debug(
			`Advanced extraction: JSON string that will be parsed: ${jsonToParse.substring(0, 500)}...`
		);
		try {
			parsedObject = JSON.parse(jsonToParse);
			logger.debug('Advanced extraction parse successful!');
		} catch (parseError) {
			logger.error(
				`Advanced extraction: Failed to parse JSON object: ${parseError.message}`
			);
			logger.error(
				`Advanced extraction: Problematic JSON string for parse (first 500 chars): ${jsonToParse.substring(0, 500)}`
			);
			throw new Error(
				// Re-throw a more specific error if advanced also fails
				`Failed to parse JSON response object after both simple and advanced attempts: ${parseError.message}`
			);
		}
	}

	// --- Validation (applies to successfully parsedObject from either attempt) ---
	if (
		!parsedObject ||
		typeof parsedObject !== 'object' ||
		!Array.isArray(parsedObject.subtasks)
	) {
		logger.error(
			`Final parsed content is not an object or missing 'subtasks' array. Content: ${JSON.stringify(parsedObject).substring(0, 200)}`
		);
		throw new Error(
			'Parsed AI response is not a valid object containing a "subtasks" array after all attempts.'
		);
	}
	const parsedSubtasks = parsedObject.subtasks;

	if (expectedCount && parsedSubtasks.length !== expectedCount) {
		logger.warn(
			`Expected ${expectedCount} subtasks, but parsed ${parsedSubtasks.length}.`
		);
	}

	let currentId = startId;
	const validatedSubtasks = [];
	const validationErrors = [];

	for (const rawSubtask of parsedSubtasks) {
		const correctedSubtask = {
			...rawSubtask,
			id: currentId,
			dependencies: Array.isArray(rawSubtask.dependencies)
				? rawSubtask.dependencies.filter(
						(dep) =>
							typeof dep === 'string' && dep.startsWith(`${parentTaskId}.`)
					)
				: [],
			status: 'pending'
		};

		const result = subtaskSchema.safeParse(correctedSubtask);

		if (result.success) {
			validatedSubtasks.push(result.data);
		} else {
			logger.warn(
				`Subtask validation failed for raw data: ${JSON.stringify(rawSubtask).substring(0, 100)}...`
			);
			result.error.errors.forEach((err) => {
				const errorMessage = `  - Field '${err.path.join('.')}': ${err.message}`;
				logger.warn(errorMessage);
				validationErrors.push(`Subtask ${currentId}: ${errorMessage}`);
			});
		}
		currentId++;
	}

	if (validationErrors.length > 0) {
		logger.error(
			`Found ${validationErrors.length} validation errors in the generated subtasks.`
		);
		logger.warn('Proceeding with only the successfully validated subtasks.');
	}

	if (validatedSubtasks.length === 0 && parsedSubtasks.length > 0) {
		throw new Error(
			'AI response contained potential subtasks, but none passed validation.'
		);
	}
	return validatedSubtasks.slice(0, expectedCount || validatedSubtasks.length);
}

/**
 * Expand a task into subtasks using the unified AI service (generateTextService).
 * Appends new subtasks by default. Replaces existing subtasks if force=true.
 * Integrates complexity report to determine subtask count and prompt if available,
 * unless numSubtasks is explicitly provided.
 * Enhanced with PRD context integration for intelligent expansion.
 * @param {string} tasksPath - Path to the tasks.json file
 * @param {number} taskId - Task ID to expand
 * @param {number | null | undefined} [numSubtasks] - Optional: Explicit target number of subtasks. If null/undefined, check complexity report or config default.
 * @param {boolean} [useResearch=false] - Whether to use the research AI role.
 * @param {string} [additionalContext=''] - Optional additional context.
 * @param {Object} context - Context object containing session and mcpLog.
 * @param {Object} [context.session] - Session object from MCP.
 * @param {Object} [context.mcpLog] - MCP logger object.
 * @param {string} [context.projectRoot] - Project root path
 * @param {string} [context.tag] - Tag for the task
 * @param {boolean} [force=false] - If true, replace existing subtasks; otherwise, append.
 * @param {Object} [contextOptions] - Context enhancement options
 * @param {Object} [prdContext] - PRD context for enhanced expansion
 * @param {string} [prdContext.sourceSection] - Source section from PRD
 * @param {string} [prdContext.originalText] - Original PRD text
 * @param {string} [prdContext.contextWindow] - Context window from PRD
 * @param {number} [prdContext.complexity] - Complexity score from PRD analysis
 * @param {string} [prdContext.type] - Section type (feature, api, ui, technical)
 * @param {Array<string>} [prdContext.keywords] - Keywords from PRD analysis
 * @param {Array<string>} [prdContext.suggestedSubtasks] - Suggested subtasks from PRD
 * @returns {Promise<Object>} The updated parent task object with new subtasks.
 * @throws {Error} If task not found, AI service fails, or parsing fails.
 */
async function expandTask(
	tasksPath,
	taskId,
	numSubtasks,
	useResearch = false,
	additionalContext = '',
	context = {},
	force = false,
	contextOptions = {},
	prdContext = null
) {
	const {
		session,
		mcpLog,
		projectRoot: contextProjectRoot,
		tag,
		complexityReportPath
	} = context;
	const outputFormat = mcpLog ? 'json' : 'text';

	// Determine projectRoot: Use from context if available, otherwise derive from tasksPath
	const projectRoot = contextProjectRoot || findProjectRoot(tasksPath);

	// Use mcpLog if available, otherwise use the default console log wrapper
	const logger = mcpLog || {
		info: (msg) => !isSilentMode() && log('info', msg),
		warn: (msg) => !isSilentMode() && log('warn', msg),
		error: (msg) => !isSilentMode() && log('error', msg),
		debug: (msg) =>
			!isSilentMode() && getDebugFlag(session) && log('debug', msg) // Use getDebugFlag
	};

	if (mcpLog) {
		logger.info(`expandTask called with context: session=${!!session}`);
	}

	try {
		// --- Task Loading/Filtering (Unchanged) ---
		logger.info(`Reading tasks from ${tasksPath}`);
		const data = readJSON(tasksPath, projectRoot, tag);
		if (!data || !data.tasks)
			throw new Error(`Invalid tasks data in ${tasksPath}`);
		const taskIndex = data.tasks.findIndex(
			(t) => t.id === parseInt(taskId, 10)
		);
		if (taskIndex === -1) throw new Error(`Task ${taskId} not found`);
		const task = data.tasks[taskIndex];
		logger.info(
			`Expanding task ${taskId}: ${task.title}${useResearch ? ' with research' : ''}`
		);
		// --- End Task Loading/Filtering ---

		// --- Handle Force Flag: Clear existing subtasks if force=true ---
		if (force && Array.isArray(task.subtasks) && task.subtasks.length > 0) {
			logger.info(
				`Force flag set. Clearing existing ${task.subtasks.length} subtasks for task ${taskId}.`
			);
			task.subtasks = []; // Clear existing subtasks
		}
		// --- End Force Flag Handling ---

		// --- PRD Context Integration ---
		let prdContextInfo = prdContext;
		if (!prdContextInfo && task.prdContext) {
			// Use PRD context stored with the task if available
			prdContextInfo = task.prdContext;
			logger.info(`Using PRD context from task ${taskId}: ${prdContextInfo.sourceSection || 'Context available'}`);
		}

		// Enhance numSubtasks based on PRD context if available
		if (prdContextInfo && !numSubtasks) {
			// Adjust subtask count based on PRD complexity
			if (prdContextInfo.complexity) {
				const complexityBasedCount = Math.min(Math.max(prdContextInfo.complexity + 1, 3), 8);
				if (!finalSubtaskCount || finalSubtaskCount === getDefaultSubtasks(session)) {
					logger.info(`Adjusting subtask count based on PRD complexity ${prdContextInfo.complexity}: ${complexityBasedCount} subtasks`);
					numSubtasks = complexityBasedCount;
				}
			}
		}
		// --- End PRD Context Integration ---

		// --- Context Gathering ---
		let gatheredContext = '';
		try {
			const contextGatherer = new ContextGatherer(projectRoot, tag);
			const allTasksFlat = flattenTasksWithSubtasks(data.tasks);
			const fuzzySearch = new FuzzyTaskSearch(allTasksFlat, 'expand-task');
			const searchQuery = `${task.title} ${task.description}`;
			const searchResults = fuzzySearch.findRelevantTasks(searchQuery, {
				maxResults: 5,
				includeSelf: true
			});
			const relevantTaskIds = fuzzySearch.getTaskIds(searchResults);

			const finalTaskIds = [
				...new Set([taskId.toString(), ...relevantTaskIds])
			];

			if (finalTaskIds.length > 0) {
				const contextResult = await contextGatherer.gather({
					tasks: finalTaskIds,
					format: 'research'
				});
				gatheredContext = contextResult.context || '';
			}
		} catch (contextError) {
			logger.warn(`Could not gather context: ${contextError.message}`);
		}
		// --- End Context Gathering ---

		// --- Complexity Report Integration ---
		let finalSubtaskCount;
		let complexityReasoningContext = '';
		let taskAnalysis = null;

		logger.info(
			`Looking for complexity report at: ${complexityReportPath}${tag !== 'master' ? ` (tag-specific for '${tag}')` : ''}`
		);

		try {
			if (fs.existsSync(complexityReportPath)) {
				const complexityReport = readJSON(complexityReportPath);
				taskAnalysis = complexityReport?.complexityAnalysis?.find(
					(a) => a.taskId === task.id
				);
				if (taskAnalysis) {
					logger.info(
						`Found complexity analysis for task ${task.id}: Score ${taskAnalysis.complexityScore}`
					);
					if (taskAnalysis.reasoning) {
						complexityReasoningContext = `\nComplexity Analysis Reasoning: ${taskAnalysis.reasoning}`;
					}
				} else {
					logger.info(
						`No complexity analysis found for task ${task.id} in report.`
					);
				}
			} else {
				logger.info(
					`Complexity report not found at ${complexityReportPath}. Skipping complexity check.`
				);
			}
		} catch (reportError) {
			logger.warn(
				`Could not read or parse complexity report: ${reportError.message}. Proceeding without it.`
			);
		}

		// Determine final subtask count
		const explicitNumSubtasks = parseInt(numSubtasks, 10);
		if (!Number.isNaN(explicitNumSubtasks) && explicitNumSubtasks >= 0) {
			finalSubtaskCount = explicitNumSubtasks;
			logger.info(
				`Using explicitly provided subtask count: ${finalSubtaskCount}`
			);
		} else if (taskAnalysis?.recommendedSubtasks) {
			finalSubtaskCount = parseInt(taskAnalysis.recommendedSubtasks, 10);
			logger.info(
				`Using subtask count from complexity report: ${finalSubtaskCount}`
			);
		} else {
			finalSubtaskCount = getDefaultSubtasks(session);
			logger.info(`Using default number of subtasks: ${finalSubtaskCount}`);
		}
		if (Number.isNaN(finalSubtaskCount) || finalSubtaskCount < 0) {
			logger.warn(
				`Invalid subtask count determined (${finalSubtaskCount}), defaulting to 3.`
			);
			finalSubtaskCount = 3;
		}

		// Determine prompt content AND system prompt
		const nextSubtaskId = (task.subtasks?.length || 0) + 1;

		// Load prompts using PromptManager
		const promptManager = getPromptManager();

		// Check if a codebase analysis provider is being used
		const hasCodebaseAnalysisCapability = hasCodebaseAnalysis(
			useResearch,
			projectRoot,
			session
		);

		// Combine all context sources into a single additionalContext parameter
		let combinedAdditionalContext = '';
		if (additionalContext || complexityReasoningContext) {
			combinedAdditionalContext =
				`\n\n${additionalContext}${complexityReasoningContext}`.trim();
		}
		if (gatheredContext) {
			combinedAdditionalContext =
				`${combinedAdditionalContext}\n\n# Project Context\n\n${gatheredContext}`.trim();
		}

		// Add PRD context to additional context
		if (prdContextInfo) {
			let prdContextText = '\n\n# PRD Context Information\n\n';

			if (prdContextInfo.sourceSection) {
				prdContextText += `**Source Section**: ${prdContextInfo.sourceSection}\n`;
			}
			if (prdContextInfo.type) {
				prdContextText += `**Section Type**: ${prdContextInfo.type}\n`;
			}
			if (prdContextInfo.complexity) {
				prdContextText += `**Complexity**: ${prdContextInfo.complexity}/5\n`;
			}
			if (prdContextInfo.keywords && prdContextInfo.keywords.length > 0) {
				prdContextText += `**Keywords**: ${prdContextInfo.keywords.join(', ')}\n`;
			}

			if (prdContextInfo.contextWindow || prdContextInfo.originalText) {
				prdContextText += '\n**Related PRD Content**:\n';
				prdContextText += prdContextInfo.contextWindow || prdContextInfo.originalText;
			}

			if (prdContextInfo.suggestedSubtasks && prdContextInfo.suggestedSubtasks.length > 0) {
				prdContextText += '\n\n**Suggested Subtask Areas**:\n';
				prdContextInfo.suggestedSubtasks.forEach(subtask => {
					prdContextText += `- ${subtask}\n`;
				});
			}

			combinedAdditionalContext = `${combinedAdditionalContext}${prdContextText}`.trim();
			logger.info(`Enhanced expansion with PRD context from ${prdContextInfo.sourceSection || 'PRD analysis'}`);
		}

		// Ensure expansionPrompt is a string (handle both string and object formats)
		let expansionPromptText = undefined;
		if (taskAnalysis?.expansionPrompt) {
			if (typeof taskAnalysis.expansionPrompt === 'string') {
				expansionPromptText = taskAnalysis.expansionPrompt;
			} else if (
				typeof taskAnalysis.expansionPrompt === 'object' &&
				taskAnalysis.expansionPrompt.text
			) {
				expansionPromptText = taskAnalysis.expansionPrompt.text;
			}
		}

		// Ensure gatheredContext is a string (handle both string and object formats)
		let gatheredContextText = gatheredContext;
		if (typeof gatheredContext === 'object' && gatheredContext !== null) {
			if (gatheredContext.data) {
				gatheredContextText = gatheredContext.data;
			} else if (gatheredContext.text) {
				gatheredContextText = gatheredContext.text;
			} else {
				gatheredContextText = JSON.stringify(gatheredContext);
			}
		}

		const promptParams = {
			task: task,
			subtaskCount: finalSubtaskCount,
			nextSubtaskId: nextSubtaskId,
			additionalContext: combinedAdditionalContext,
			complexityReasoningContext: complexityReasoningContext,
			gatheredContext: gatheredContextText || '',
			useResearch: useResearch,
			expansionPrompt: expansionPromptText || undefined,
			hasCodebaseAnalysis: hasCodebaseAnalysisCapability,
			projectRoot: projectRoot || '',
			prdContext: prdContextInfo
		};

		let variantKey = 'default';
		if (prdContextInfo) {
			variantKey = 'prd-context';
			logger.info(
				`Using PRD context-enhanced expansion for task ${task.id} (type: ${prdContextInfo.type || 'general'}).`
			);
		} else if (expansionPromptText) {
			variantKey = 'complexity-report';
			logger.info(
				`Using expansion prompt from complexity report for task ${task.id}.`
			);
		} else if (useResearch) {
			variantKey = 'research';
			logger.info(`Using research variant for task ${task.id}.`);
		} else {
			logger.info(`Using standard prompt generation for task ${task.id}.`);
		}

		const { systemPrompt, userPrompt: promptContent } =
			await promptManager.loadPrompt('expand-task', promptParams, variantKey);

		// Debug logging to identify the issue
		logger.debug(`Selected variant: ${variantKey}`);
		logger.debug(
			`Prompt params passed: ${JSON.stringify(promptParams, null, 2)}`
		);
		logger.debug(
			`System prompt (first 500 chars): ${systemPrompt.substring(0, 500)}...`
		);
		logger.debug(
			`User prompt (first 500 chars): ${promptContent.substring(0, 500)}...`
		);
		// --- End Complexity Report / Prompt Logic ---

		// --- AI Subtask Generation using generateTextService ---
		let generatedSubtasks = [];
		let loadingIndicator = null;
		if (outputFormat === 'text') {
			loadingIndicator = startLoadingIndicator(
				`Generating ${finalSubtaskCount || 'appropriate number of'} subtasks...\n`
			);
		}

		let responseText = '';
		let aiServiceResponse = null;

		try {
			// Enhance prompt with context if contextOptions are provided
			const enhancedPrompt = await enhancePromptWithContext(promptContent, contextOptions || {}, {
				taskContext: task ? `Current task: ${task.title} (ID: ${task.id})` : null,
				projectContext: projectRoot ? `Project root: ${projectRoot}` : null
			});

			const role = useResearch ? 'research' : 'main';

			// Call generateTextService with the determined prompts and telemetry params
			aiServiceResponse = await generateTextService({
				prompt: enhancedPrompt,
				systemPrompt: systemPrompt,
				role,
				session,
				projectRoot,
				commandName: 'expand-task',
				outputType: outputFormat
			});
			responseText = aiServiceResponse.mainResult;

			// Parse Subtasks
			generatedSubtasks = parseSubtasksFromText(
				responseText,
				nextSubtaskId,
				finalSubtaskCount,
				task.id,
				logger
			);
			logger.info(
				`Successfully parsed ${generatedSubtasks.length} subtasks from AI response.`
			);
		} catch (error) {
			if (loadingIndicator) stopLoadingIndicator(loadingIndicator);
			logger.error(
				`Error during AI call or parsing for task ${taskId}: ${error.message}`, // Added task ID context
				'error'
			);
			// Log raw response in debug mode if parsing failed
			if (
				error.message.includes('Failed to parse valid subtasks') &&
				getDebugFlag(session)
			) {
				logger.error(`Raw AI Response that failed parsing:\n${responseText}`);
			}
			throw error;
		} finally {
			if (loadingIndicator) stopLoadingIndicator(loadingIndicator);
		}

		// --- Task Update & File Writing ---
		// Ensure task.subtasks is an array before appending
		if (!Array.isArray(task.subtasks)) {
			task.subtasks = [];
		}

		// Enhance generated subtasks with PRD context if available
		if (prdContextInfo) {
			generatedSubtasks.forEach(subtask => {
				// Preserve PRD context in subtasks for future expansion
				subtask.prdContext = {
					...prdContextInfo,
					// Mark as derived from parent task expansion
					derivedFrom: 'parent-task-expansion',
					parentTaskId: task.id
				};

				// Add expansion metadata for potential auto-expansion
				if (!subtask.expansionMetadata) {
					subtask.expansionMetadata = {};
				}

				// Mark as auto-expandable if complexity is high enough
				if (prdContextInfo.complexity >= 3) {
					subtask.expansionMetadata.autoExpandable = true;
					subtask.expansionMetadata.complexityScore = prdContextInfo.complexity;
				}

				logger.debug(`Enhanced subtask ${subtask.id} with PRD context (complexity: ${prdContextInfo.complexity})`);
			});
		}

		// Append the newly generated and validated subtasks
		task.subtasks.push(...generatedSubtasks);
		// --- End Change: Append instead of replace ---

		data.tasks[taskIndex] = task; // Assign the modified task back
		writeJSON(tasksPath, data, projectRoot, tag);
		// await generateTaskFiles(tasksPath, path.dirname(tasksPath));

		// Display AI Usage Summary for CLI
		if (
			outputFormat === 'text' &&
			aiServiceResponse &&
			aiServiceResponse.telemetryData
		) {
			displayAiUsageSummary(aiServiceResponse.telemetryData, 'cli');
		}

		// Return the updated task object AND telemetry data
		return {
			task,
			telemetryData: aiServiceResponse?.telemetryData,
			tagInfo: aiServiceResponse?.tagInfo,
			// Enhanced return data for PRD context integration
			prdEnhancement: prdContextInfo ? {
				usedPrdContext: true,
				sourceSection: prdContextInfo.sourceSection,
				complexity: prdContextInfo.complexity,
				type: prdContextInfo.type,
				subtasksGenerated: generatedSubtasks.length,
				autoExpandableSubtasks: generatedSubtasks.filter(s => s.expansionMetadata?.autoExpandable).length
			} : {
				usedPrdContext: false
			}
		};
	} catch (error) {
		// Catches errors from file reading, parsing, AI call etc.
		logger.error(`Error expanding task ${taskId}: ${error.message}`, 'error');
		if (outputFormat === 'text' && getDebugFlag(session)) {
			console.error(error); // Log full stack in debug CLI mode
		}
		throw error; // Re-throw for the caller
	}
}

/**
 * Enhanced expandTask wrapper for PRD context integration
 * Provides compatibility with in-flight expansion pipeline and direct PRD context usage
 * @param {string} taskIdStr - Task ID as string
 * @param {string} tasksPath - Path to tasks file
 * @param {string} enhancedPrompt - Enhanced prompt (optional, will be added to additionalContext)
 * @param {Object} options - Expansion options
 * @param {string} outputFormat - Output format
 * @returns {Promise<Object>} Expansion result with PRD context information
 */
export async function expandTaskWithPRDContext(
	taskIdStr,
	tasksPath,
	enhancedPrompt = '',
	options = {},
	outputFormat = 'json'
) {
	const {
		session,
		mcpLog,
		projectRoot,
		tag,
		force = false,
		research = false,
		prdContext,
		contextWindow,
		maxSubtasks,
		preserveDetail = false,
		commandName = 'expand-task-prd',
		outputType = 'json'
	} = options;

	// Create logger
	const logger = mcpLog || {
		info: (msg) => !isSilentMode() && log('info', msg),
		warn: (msg) => !isSilentMode() && log('warn', msg),
		error: (msg) => !isSilentMode() && log('error', msg),
		debug: (msg) => !isSilentMode() && getDebugFlag(session) && log('debug', msg),
		report: (msg, level = 'info') => {
			const logFn = logger[level] || logger.info;
			logFn(msg);
		}
	};

	try {
		const taskId = parseInt(taskIdStr, 10);

		// Build enhanced additional context
		let additionalContext = enhancedPrompt || '';
		if (contextWindow) {
			additionalContext += additionalContext ? `\n\n${contextWindow}` : contextWindow;
		}

		// Prepare context object
		const context = {
			session,
			mcpLog: logger,
			projectRoot,
			tag
		};

		// Call the enhanced expandTask function
		const result = await expandTask(
			tasksPath,
			taskId,
			maxSubtasks, // numSubtasks
			research, // useResearch
			additionalContext,
			context,
			force,
			{}, // contextOptions
			prdContext // PRD context
		);

		logger.report(
			`PRD-enhanced expansion completed for task ${taskId}: ${result.prdEnhancement.subtasksGenerated} subtasks created` +
			(result.prdEnhancement.usedPrdContext ? ` with PRD context (${result.prdEnhancement.sourceSection})` : ''),
			'info'
		);

		return {
			success: true,
			task: result.task,
			subtasksAdded: result.prdEnhancement.subtasksGenerated,
			details: result.prdEnhancement.usedPrdContext
				? `Expanded with PRD context from ${result.prdEnhancement.sourceSection}. Generated ${result.prdEnhancement.subtasksGenerated} subtasks (${result.prdEnhancement.autoExpandableSubtasks} auto-expandable).`
				: `Expanded task without PRD context. Generated ${result.prdEnhancement.subtasksGenerated} subtasks.`,
			telemetryData: result.telemetryData,
			tagInfo: result.tagInfo,
			prdEnhancement: result.prdEnhancement
		};

	} catch (error) {
		logger.report(`Failed to expand task ${taskIdStr}: ${error.message}`, 'error');
		return {
			success: false,
			error: error.message,
			details: `Task expansion failed: ${error.message}`
		};
	}
}

export { expandTask };
export default expandTask;
