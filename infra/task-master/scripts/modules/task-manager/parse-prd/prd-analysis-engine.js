/**
 * prd-analysis-engine.js
 * Intelligent PRD Analysis and Segmentation Engine for enhanced task generation
 * Part of Task #99 - Enhance Parse-PRD with Intelligent Task Expansion
 */

import chalk from 'chalk';

/**
 * PRD Complexity Metrics for determining appropriate task count
 */
export class PRDComplexityMetrics {
	constructor() {
		this.wordCount = 0;
		this.sectionCount = 0;
		this.featureCount = 0;
		this.technicalDepth = 0;
		this.dependencies = 0;
		this.requirements = 0;
		this.complexity = 0;
	}

	/**
	 * Calculate overall complexity score
	 * @returns {number} Complexity score from 1-10
	 */
	calculateComplexity() {
		const wordWeight = Math.min(this.wordCount / 500, 5); // 0-5 based on word count
		const sectionWeight = Math.min(this.sectionCount / 10, 2); // 0-2 based on sections
		const featureWeight = Math.min(this.featureCount / 5, 3); // 0-3 based on features
		const techWeight = this.technicalDepth; // 0-2 based on technical complexity
		const depsWeight = Math.min(this.dependencies / 3, 1); // 0-1 based on dependencies

		this.complexity = Math.min(wordWeight + sectionWeight + featureWeight + techWeight + depsWeight, 10);
		return this.complexity;
	}
}

/**
 * PRD Section Mapping for context preservation
 */
export class PRDSectionMapping {
	constructor() {
		this.sections = new Map();
		this.boundaries = [];
		this.contextWindows = new Map();
	}

	/**
	 * Add a section with its boundaries and content
	 * @param {string} title - Section title
	 * @param {number} startLine - Starting line number
	 * @param {number} endLine - Ending line number
	 * @param {string} content - Section content
	 * @param {string} type - Section type (header, feature, requirement, etc.)
	 */
	addSection(title, startLine, endLine, content, type = 'general') {
		const section = {
			title,
			startLine,
			endLine,
			content,
			type,
			wordCount: content.split(/\s+/).length,
			hasCode: /```|`[^`]+`/.test(content),
			hasDependencies: /depend|require|need|integrate/.test(content.toLowerCase()),
			complexity: this.assessSectionComplexity(content, type)
		};

		this.sections.set(title, section);
		this.boundaries.push({ title, startLine, endLine });

		// Sort boundaries by start line
		this.boundaries.sort((a, b) => a.startLine - b.startLine);

		return section;
	}

	/**
	 * Assess complexity of a section
	 * @param {string} content - Section content
	 * @param {string} type - Section type
	 * @returns {number} Complexity score 1-5
	 */
	assessSectionComplexity(content, type) {
		let complexity = 1;

		// Technical indicators
		if (/API|REST|GraphQL|database|SQL|authentication|security|encryption/.test(content)) {
			complexity += 2;
		}

		// Integration complexity
		if (/integrate|webhook|third.party|external|service/.test(content)) {
			complexity += 1;
		}

		// UI/UX complexity
		if (/responsive|mobile|design|interface|user experience/.test(content)) {
			complexity += 1;
		}

		// Performance requirements
		if (/performance|optimization|scalability|load|concurrent/.test(content)) {
			complexity += 1;
		}

		return Math.min(complexity, 5);
	}

	/**
	 * Create context window for a specific section
	 * @param {string} sectionTitle - Title of the section
	 * @param {number} windowSize - Size of context window in lines
	 * @returns {string} Context window content
	 */
	createContextWindow(sectionTitle, windowSize = 10) {
		const section = this.sections.get(sectionTitle);
		if (!section) return '';

		const relatedSections = this.findRelatedSections(sectionTitle);
		let contextContent = section.content;

		// Add related sections content
		relatedSections.forEach(relatedTitle => {
			const relatedSection = this.sections.get(relatedTitle);
			if (relatedSection) {
				contextContent += `\n\n--- Related: ${relatedTitle} ---\n${relatedSection.content}`;
			}
		});

		this.contextWindows.set(sectionTitle, contextContent);
		return contextContent;
	}

	/**
	 * Find sections related to the given section
	 * @param {string} sectionTitle - Title of the section
	 * @returns {Array<string>} Array of related section titles
	 */
	findRelatedSections(sectionTitle) {
		const section = this.sections.get(sectionTitle);
		if (!section) return [];

		const related = [];
		const keywords = this.extractKeywords(section.content);

		this.sections.forEach((otherSection, otherTitle) => {
			if (otherTitle === sectionTitle) return;

			const otherKeywords = this.extractKeywords(otherSection.content);
			const commonKeywords = keywords.filter(keyword =>
				otherKeywords.includes(keyword)
			);

			// If sections share significant keywords, they're related
			if (commonKeywords.length >= 2) {
				related.push(otherTitle);
			}
		});

		return related;
	}

	/**
	 * Extract keywords from content
	 * @param {string} content - Content to extract keywords from
	 * @returns {Array<string>} Array of keywords
	 */
	extractKeywords(content) {
		const stopWords = new Set(['the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should']);

		return content
			.toLowerCase()
			.match(/\b[a-z]{3,}\b/g) // Words 3+ characters
			?.filter(word => !stopWords.has(word))
			?.filter((word, index, arr) => arr.indexOf(word) === index) // Remove duplicates
			|| [];
	}
}

/**
 * Main PRD Analysis Engine
 */
export class PRDAnalysisEngine {
	constructor(options = {}) {
		this.options = {
			minSectionWords: 50,
			maxSections: 20,
			technicalIndicators: [
				'API', 'REST', 'GraphQL', 'database', 'SQL', 'authentication',
				'security', 'encryption', 'OAuth', 'JWT', 'microservice'
			],
			featureIndicators: [
				'feature', 'functionality', 'capability', 'requirement',
				'specification', 'behavior', 'action', 'workflow'
			],
			...options
		};

		this.metrics = new PRDComplexityMetrics();
		this.sectionMapping = new PRDSectionMapping();
	}

	/**
	 * Analyze PRD content and extract structure
	 * @param {string} prdContent - Raw PRD content
	 * @returns {Object} Analysis results
	 */
	analyzePRD(prdContent) {
		const lines = prdContent.split('\n');

		// Basic metrics
		this.metrics.wordCount = prdContent.split(/\s+/).length;

		// Identify sections
		const sections = this.identifySections(lines);
		this.metrics.sectionCount = sections.length;

		// Process each section
		sections.forEach(section => {
			this.sectionMapping.addSection(
				section.title,
				section.startLine,
				section.endLine,
				section.content,
				section.type
			);
		});

		// Analyze features and requirements
		this.metrics.featureCount = this.countFeatures(prdContent);
		this.metrics.requirements = this.countRequirements(prdContent);
		this.metrics.technicalDepth = this.assessTechnicalDepth(prdContent);
		this.metrics.dependencies = this.countDependencies(prdContent);

		// Calculate complexity
		const complexityScore = this.metrics.calculateComplexity();

		// Determine optimal task count
		const recommendedTaskCount = this.calculateRecommendedTaskCount(complexityScore);

		// Identify natural task boundaries
		const taskBoundaries = this.identifyTaskBoundaries();

		return {
			metrics: this.metrics,
			sectionMapping: this.sectionMapping,
			complexityScore,
			recommendedTaskCount,
			taskBoundaries,
			analysis: this.generateAnalysisSummary(prdContent)
		};
	}

	/**
	 * Identify sections in the PRD
	 * @param {Array<string>} lines - PRD lines
	 * @returns {Array<Object>} Array of section objects
	 */
	identifySections(lines) {
		const sections = [];
		let currentSection = null;

		lines.forEach((line, index) => {
			const trimmedLine = line.trim();

			// Check for headers (markdown style)
			const headerMatch = trimmedLine.match(/^(#{1,6})\s+(.+)$/);
			if (headerMatch) {
				// Close previous section
				if (currentSection) {
					currentSection.endLine = index - 1;
					currentSection.content = lines
						.slice(currentSection.startLine, currentSection.endLine + 1)
						.join('\n');
					sections.push(currentSection);
				}

				// Start new section
				currentSection = {
					title: headerMatch[2],
					startLine: index,
					endLine: index,
					level: headerMatch[1].length,
					type: this.categorizeSection(headerMatch[2]),
					content: ''
				};
			}

			// Check for other section indicators
			if (!headerMatch && this.isSection(trimmedLine)) {
				// Close previous section
				if (currentSection) {
					currentSection.endLine = index - 1;
					currentSection.content = lines
						.slice(currentSection.startLine, currentSection.endLine + 1)
						.join('\n');
					sections.push(currentSection);
				}

				// Start new section
				currentSection = {
					title: trimmedLine,
					startLine: index,
					endLine: index,
					level: 1,
					type: this.categorizeSection(trimmedLine),
					content: ''
				};
			}
		});

		// Close final section
		if (currentSection) {
			currentSection.endLine = lines.length - 1;
			currentSection.content = lines
				.slice(currentSection.startLine, currentSection.endLine + 1)
				.join('\n');
			sections.push(currentSection);
		}

		return sections.filter(section =>
			section.content.split(/\s+/).length >= this.options.minSectionWords
		);
	}

	/**
	 * Check if a line indicates a section
	 * @param {string} line - Line to check
	 * @returns {boolean} True if line is a section indicator
	 */
	isSection(line) {
		// All caps lines that aren't too long
		if (/^[A-Z\s]{3,30}$/.test(line) && line.length > 5) {
			return true;
		}

		// Lines ending with colon
		if (/^[A-Z][^:]*:$/.test(line)) {
			return true;
		}

		// Numbered sections
		if (/^\d+\.\s+[A-Z]/.test(line)) {
			return true;
		}

		return false;
	}

	/**
	 * Categorize a section based on its title
	 * @param {string} title - Section title
	 * @returns {string} Section category
	 */
	categorizeSection(title) {
		const lowerTitle = title.toLowerCase();

		if (/overview|introduction|summary|executive/.test(lowerTitle)) {
			return 'overview';
		}

		if (/requirement|spec|specification/.test(lowerTitle)) {
			return 'requirement';
		}

		if (/feature|functionality|capability/.test(lowerTitle)) {
			return 'feature';
		}

		if (/technical|architecture|design|implementation/.test(lowerTitle)) {
			return 'technical';
		}

		if (/api|interface|endpoint/.test(lowerTitle)) {
			return 'api';
		}

		if (/ui|user interface|frontend|design/.test(lowerTitle)) {
			return 'ui';
		}

		if (/test|testing|qa|quality/.test(lowerTitle)) {
			return 'testing';
		}

		if (/deploy|deployment|infrastructure|devops/.test(lowerTitle)) {
			return 'deployment';
		}

		return 'general';
	}

	/**
	 * Count features in PRD content
	 * @param {string} content - PRD content
	 * @returns {number} Feature count
	 */
	countFeatures(content) {
		const featurePatterns = [
			/(?:^|\n)\s*[-*]\s+.*(?:feature|functionality|capability)/gmi,
			/(?:^|\n)\s*\d+\.\s+.*(?:feature|functionality|capability)/gmi,
			/(?:the|a|an)\s+(?:system|application|user)\s+(?:shall|should|must|will)/gmi
		];

		let totalFeatures = 0;
		featurePatterns.forEach(pattern => {
			const matches = content.match(pattern);
			if (matches) totalFeatures += matches.length;
		});

		return Math.max(totalFeatures, 1);
	}

	/**
	 * Count requirements in PRD content
	 * @param {string} content - PRD content
	 * @returns {number} Requirements count
	 */
	countRequirements(content) {
		const reqPatterns = [
			/(?:must|shall|should|will|required to)/gmi,
			/(?:requirement|spec|specification):\s*/gmi
		];

		let totalReqs = 0;
		reqPatterns.forEach(pattern => {
			const matches = content.match(pattern);
			if (matches) totalReqs += matches.length;
		});

		return totalReqs;
	}

	/**
	 * Assess technical depth of the PRD
	 * @param {string} content - PRD content
	 * @returns {number} Technical depth score (0-2)
	 */
	assessTechnicalDepth(content) {
		let depth = 0;

		// Check for technical indicators
		this.options.technicalIndicators.forEach(indicator => {
			if (content.toLowerCase().includes(indicator.toLowerCase())) {
				depth += 0.2;
			}
		});

		// Check for code blocks
		if (/```[\s\S]*?```|`[^`]+`/.test(content)) {
			depth += 0.5;
		}

		// Check for technical diagrams/schemas
		if (/schema|diagram|architecture|flow|endpoint|payload/.test(content.toLowerCase())) {
			depth += 0.3;
		}

		return Math.min(depth, 2);
	}

	/**
	 * Count dependencies in PRD content
	 * @param {string} content - PRD content
	 * @returns {number} Dependencies count
	 */
	countDependencies(content) {
		const depPatterns = [
			/depend\s+on|depends\s+on|dependency/gmi,
			/integrate\s+with|integration\s+with/gmi,
			/require\s+.*(?:service|system|component)/gmi,
			/third.party|external\s+(?:service|api|system)/gmi
		];

		let totalDeps = 0;
		depPatterns.forEach(pattern => {
			const matches = content.match(pattern);
			if (matches) totalDeps += matches.length;
		});

		return totalDeps;
	}

	/**
	 * Calculate recommended task count based on complexity
	 * @param {number} complexityScore - Complexity score (1-10)
	 * @returns {number} Recommended task count
	 */
	calculateRecommendedTaskCount(complexityScore) {
		const baseTaskCount = Math.max(this.metrics.sectionCount, 5);
		const complexityMultiplier = 1 + (complexityScore / 10);
		const featureMultiplier = 1 + (this.metrics.featureCount / 10);

		let recommended = Math.round(baseTaskCount * complexityMultiplier * featureMultiplier);

		// Bound between reasonable limits
		recommended = Math.max(recommended, 5);
		recommended = Math.min(recommended, 50);

		return recommended;
	}

	/**
	 * Identify natural task boundaries in the PRD
	 * @returns {Array<Object>} Array of task boundary objects
	 */
	identifyTaskBoundaries() {
		const boundaries = [];

		this.sectionMapping.sections.forEach((section, title) => {
			// Sections that naturally map to tasks
			if (['feature', 'requirement', 'technical', 'api', 'ui'].includes(section.type)) {
				boundaries.push({
					title,
					type: section.type,
					complexity: section.complexity,
					startLine: section.startLine,
					endLine: section.endLine,
					suggestedSubtasks: this.suggestSubtasksForSection(section)
				});
			}
		});

		return boundaries.sort((a, b) => a.complexity - b.complexity);
	}

	/**
	 * Suggest subtasks for a section
	 * @param {Object} section - Section object
	 * @returns {Array<string>} Array of suggested subtask titles
	 */
	suggestSubtasksForSection(section) {
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
	 * Generate analysis summary
	 * @param {string} prdContent - PRD content
	 * @returns {Object} Analysis summary
	 */
	generateAnalysisSummary(prdContent) {
		const summary = {
			overview: {
				totalWords: this.metrics.wordCount,
				sections: this.metrics.sectionCount,
				estimatedReadingTime: Math.ceil(this.metrics.wordCount / 200), // minutes
				complexity: this.metrics.complexity
			},
			breakdown: {
				features: this.metrics.featureCount,
				requirements: this.metrics.requirements,
				technicalSections: Array.from(this.sectionMapping.sections.values())
					.filter(s => s.type === 'technical').length,
				apiSections: Array.from(this.sectionMapping.sections.values())
					.filter(s => s.type === 'api').length
			},
			recommendations: {
				taskCount: this.calculateRecommendedTaskCount(this.metrics.complexity),
				expansionNeeded: this.metrics.complexity > 6,
				researchRequired: this.metrics.technicalDepth > 1.5
			}
		};

		return summary;
	}

	/**
	 * Generate PRD context for task generation
	 * @param {string} sectionTitle - Section title to generate context for
	 * @returns {Object} Context object for task generation
	 */
	generateTaskContext(sectionTitle) {
		const section = this.sectionMapping.sections.get(sectionTitle);
		if (!section) return null;

		const contextWindow = this.sectionMapping.createContextWindow(sectionTitle);
		const relatedSections = this.sectionMapping.findRelatedSections(sectionTitle);

		return {
			sourceSection: `${sectionTitle} (Lines ${section.startLine}-${section.endLine})`,
			originalText: section.content,
			relatedSections,
			contextWindow,
			complexity: section.complexity,
			type: section.type,
			keywords: this.sectionMapping.extractKeywords(section.content),
			suggestedSubtasks: this.suggestSubtasksForSection(section)
		};
	}
}

/**
 * Factory function to create and run PRD analysis
 * @param {string} prdContent - PRD content to analyze
 * @param {Object} options - Analysis options
 * @returns {Object} Complete analysis results
 */
export function analyzePRDContent(prdContent, options = {}) {
	const engine = new PRDAnalysisEngine(options);
	return engine.analyzePRD(prdContent);
}

/**
 * Utility function to determine if PRD needs intelligent expansion
 * @param {Object} analysisResults - Results from analyzePRDContent
 * @returns {boolean} True if expansion is recommended
 */
export function shouldExpandTasks(analysisResults) {
	return analysisResults.complexityScore > 6 ||
		   analysisResults.metrics.featureCount > 8 ||
		   analysisResults.metrics.sectionCount > 12;
}

/**
 * Export PRD context for task expansion
 * @param {Object} analysisResults - Results from analyzePRDContent
 * @param {string} taskTitle - Title of the task to expand
 * @returns {Object|null} Context for expansion or null if not found
 */
export function getPRDContextForTask(analysisResults, taskTitle) {
	const engine = new PRDAnalysisEngine();
	engine.sectionMapping = analysisResults.sectionMapping;

	// Try to find matching section by title similarity
	for (const [sectionTitle] of analysisResults.sectionMapping.sections) {
		if (sectionTitle.toLowerCase().includes(taskTitle.toLowerCase()) ||
			taskTitle.toLowerCase().includes(sectionTitle.toLowerCase())) {
			return engine.generateTaskContext(sectionTitle);
		}
	}

	return null;
}