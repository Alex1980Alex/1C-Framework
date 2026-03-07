/**
 * mcp-e2e-framework.js
 * End-to-End Test Framework for Task Master MCP Server over stdio
 * 
 * This framework enables programmatic interaction with the FastMCP server
 * by launching it as a subprocess and communicating via JSON messages over stdio.
 */

import { spawn } from 'child_process';
import { EventEmitter } from 'events';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * MCP Server E2E Test Framework
 * Handles launching FastMCP server, message protocol, and test assertions
 */
export class MCPTestFramework extends EventEmitter {
	constructor(options = {}) {
		super();
		
		this.options = {
			serverPath: path.join(__dirname, '../../mcp-server/server.js'),
			timeout: 30000, // 30 seconds default timeout
			debug: false,
			...options
		};
		
		this.server = null;
		this.isRunning = false;
		this.messageId = 0;
		this.pendingRequests = new Map();
		this.responseBuffer = '';
		this.buffer = '';

		// Request/Response correlation tracking
		this.messageHistory = [];
		this.responseTimes = new Map();
		this.errorCounts = { total: 0, network: 0, protocol: 0, timeout: 0 };

		// Bind methods
		this.start = this.start.bind(this);
		this.stop = this.stop.bind(this);
		this.sendRequest = this.sendRequest.bind(this);
		this.handleServerOutput = this.handleServerOutput.bind(this);
		this.handleServerError = this.handleServerError.bind(this);
	}
	
	/**
	 * Launch the FastMCP server as subprocess
	 */
	async start() {
		if (this.isRunning) {
			throw new Error('MCP server is already running');
		}
		
		return new Promise((resolve, reject) => {
			try {
				// Launch server with Node.js
				this.server = spawn('node', [this.options.serverPath], {
					stdio: ['pipe', 'pipe', 'pipe'],
					env: {
						...process.env,
						NODE_ENV: 'test'
					}
				});
				
				if (this.options.debug) {
					console.log(`[DEBUG] Launched MCP server with PID: ${this.server.pid}`);
				}
				
				// Setup event handlers
				this.server.stdout.on('data', this.handleServerOutput);
				this.server.stderr.on('data', this.handleServerError);
				
				this.server.on('close', (code) => {
					this.isRunning = false;
					if (this.options.debug) {
						console.log(`[DEBUG] MCP server closed with code: ${code}`);
					}
					this.emit('close', code);
				});
				
				this.server.on('error', (error) => {
					if (this.options.debug) {
						console.error(`[DEBUG] MCP server error:`, error);
					}
					this.emit('error', error);
					reject(error);
				});
				
				// Wait for server to be ready
				// FastMCP should output initialization messages
				const initTimeout = setTimeout(() => {
					reject(new Error('Server initialization timeout'));
				}, 10000);
				
				const onReady = () => {
					clearTimeout(initTimeout);
					this.isRunning = true;
					resolve();
				};
				
				// Listen for ready signal or first successful response
				this.once('server-ready', onReady);
				
				// Send initialization message to check if server is ready
				setTimeout(() => {
					this.sendInitializationRequest()
						.then(() => onReady())
						.catch(reject);
				}, 1000);
				
			} catch (error) {
				reject(error);
			}
		});
	}
	
	/**
	 * Stop the MCP server
	 */
	async stop() {
		if (!this.isRunning || !this.server) {
			return;
		}
		
		return new Promise((resolve) => {
			const cleanup = () => {
				this.isRunning = false;
				this.server = null;
				this.pendingRequests.clear();
				this.responseBuffer = '';
				resolve();
			};
			
			// Try graceful shutdown first
			this.server.on('close', cleanup);
			this.server.kill('SIGTERM');
			
			// Force kill after timeout
			setTimeout(() => {
				if (this.server && !this.server.killed) {
					this.server.kill('SIGKILL');
					cleanup();
				}
			}, 5000);
		});
	}
	
	/**
	 * Send initialization request to check server readiness
	 */
	async sendInitializationRequest() {
		const request = {
			jsonrpc: '2.0',
			id: this.getNextMessageId(),
			method: 'initialize',
			params: {
				capabilities: {},
				clientInfo: {
					name: 'MCP E2E Test Framework',
					version: '1.0.0'
				}
			}
		};
		
		return this.sendRequest(request);
	}
	
	/**
	 * Send JSON-RPC request to MCP server
	 * Enhanced with correlation tracking and performance monitoring
	 */
	async sendRequest(request, timeoutMs = null) {
		if (!this.isRunning) {
			throw new Error('MCP server is not running');
		}

		const timeout = timeoutMs || this.options.timeout;
		const messageId = request.id || this.getNextMessageId();
		const startTime = Date.now();

		// Ensure request has proper structure
		const fullRequest = {
			jsonrpc: '2.0',
			...request,
			id: messageId
		};

		// Record request in history
		this.messageHistory.push({
			id: messageId,
			type: 'request',
			method: request.method,
			timestamp: startTime,
			status: 'sent'
		});

		return new Promise((resolve, reject) => {
			// Setup timeout with enhanced error tracking
			const timeoutHandle = setTimeout(() => {
				this.pendingRequests.delete(messageId);
				this.errorCounts.total++;
				this.errorCounts.timeout++;

				// Update history
				const historyItem = this.messageHistory.find(item => item.id === messageId);
				if (historyItem) {
					historyItem.status = 'timeout';
					historyItem.duration = Date.now() - startTime;
				}

				reject(new Error(`Request timeout after ${timeout}ms for method: ${request.method}`));
			}, timeout);

			// Store request promise with enhanced metadata
			this.pendingRequests.set(messageId, {
				resolve: (response) => {
					clearTimeout(timeoutHandle);

					// Record response time
					const duration = Date.now() - startTime;
					this.responseTimes.set(messageId, duration);

					// Update history
					const historyItem = this.messageHistory.find(item => item.id === messageId);
					if (historyItem) {
						historyItem.status = 'completed';
						historyItem.duration = duration;
						historyItem.hasError = !!response.error;
					}

					resolve(response);
				},
				reject: (error) => {
					clearTimeout(timeoutHandle);
					this.errorCounts.total++;
					this.errorCounts.protocol++;

					// Update history
					const historyItem = this.messageHistory.find(item => item.id === messageId);
					if (historyItem) {
						historyItem.status = 'error';
						historyItem.duration = Date.now() - startTime;
						historyItem.error = error.message;
					}

					reject(error);
				},
				timeout: timeoutHandle,
				startTime,
				method: request.method
			});

			// Send request
			const message = JSON.stringify(fullRequest) + '\n';

			if (this.options.debug) {
				console.log(`[DEBUG] Sending request (ID: ${messageId}):`, fullRequest);
			}

			try {
				this.server.stdin.write(message);
			} catch (error) {
				// Handle network errors
				this.errorCounts.total++;
				this.errorCounts.network++;
				clearTimeout(timeoutHandle);
				this.pendingRequests.delete(messageId);
				reject(new Error(`Failed to send request: ${error.message}`));
			}
		});
	}
	
	/**
	 * Handle stdout data from MCP server
	 * Enhanced message protocol handler with better streaming support
	 */
	handleServerOutput(data) {
		const chunk = data.toString();
		this.buffer = (this.buffer || '') + chunk;

		if (this.options.verbose) {
			console.log(`[VERBOSE] Received chunk (${chunk.length} bytes):`, chunk);
		}

		// Parse all complete messages from buffer
		const messages = this.parseMessages(data);

		// Process each parsed message
		for (const message of messages) {
			this.handleJSONResponse(message);
		}
	}

	/**
	 * Parse incoming JSON-RPC messages from buffer
	 * Enhanced with better error handling and streaming support
	 */
	parseMessages(data) {
		this.buffer = (this.buffer || '') + data.toString();

		const messages = [];
		let processedLength = 0;

		// Handle both single messages and streams
		const lines = this.buffer.split('\n');

		for (let i = 0; i < lines.length - 1; i++) { // -1 because last line might be incomplete
			const line = lines[i].trim();
			if (!line) continue;

			try {
				// Try to parse each line as a separate JSON message
				const message = JSON.parse(line);

				// Validate JSON-RPC structure
				if (this.isValidJsonRpcMessage(message)) {
					messages.push(message);
					processedLength += lines[i].length + 1; // +1 for newline
				} else if (this.options.verbose) {
					console.warn('Invalid JSON-RPC message structure:', message);
				}
			} catch (error) {
				// If line parsing fails, try brace-counting approach for complex messages
				const complexMessage = this.tryComplexParsing(line);
				if (complexMessage) {
					messages.push(complexMessage);
					processedLength += lines[i].length + 1;
				} else if (this.options.verbose) {
					console.warn('Failed to parse message line:', line, 'Error:', error.message);
				}
			}
		}

		// Keep the unprocessed part of buffer (last incomplete line)
		if (processedLength > 0) {
			this.buffer = this.buffer.slice(processedLength);
		}

		return messages;
	}

	/**
	 * Validate JSON-RPC message structure
	 */
	isValidJsonRpcMessage(message) {
		if (!message || typeof message !== 'object') return false;

		// Check for required fields based on message type
		if (message.method) {
			// Request or notification
			return typeof message.method === 'string' &&
				   (message.id !== undefined || message.id === null);
		} else if (message.result !== undefined || message.error !== undefined) {
			// Response
			return message.id !== undefined;
		}

		return false;
	}

	/**
	 * Try complex parsing for malformed or multi-line JSON
	 */
	tryComplexParsing(text) {
		let braceCount = 0;
		let inString = false;
		let escapeNext = false;
		let messageEnd = -1;

		for (let i = 0; i < text.length; i++) {
			const char = text[i];

			if (escapeNext) {
				escapeNext = false;
				continue;
			}

			if (char === '\\') {
				escapeNext = true;
				continue;
			}

			if (char === '"') {
				inString = !inString;
				continue;
			}

			if (!inString) {
				if (char === '{') braceCount++;
				if (char === '}') braceCount--;

				if (braceCount === 0 && i > 0) {
					messageEnd = i + 1;
					break;
				}
			}
		}

		if (messageEnd > 0) {
			try {
				return JSON.parse(text.slice(0, messageEnd));
			} catch (error) {
				return null;
			}
		}

		return null;
	}
	
	/**
	 * Handle stderr data from MCP server
	 */
	handleServerError(data) {
		const error = data.toString();
		if (this.options.debug) {
			console.error(`[DEBUG] Server stderr:`, error);
		}
		this.emit('server-error', error);
	}
	
	/**
	 * Handle parsed JSON response from server
	 */
	handleJSONResponse(response) {
		if (this.options.debug) {
			console.log(`[DEBUG] Received response:`, response);
		}
		
		// Handle responses with IDs (request/response pairs)
		if (response.id && this.pendingRequests.has(response.id)) {
			const { resolve, reject } = this.pendingRequests.get(response.id);
			this.pendingRequests.delete(response.id);
			
			if (response.error) {
				reject(new Error(response.error.message || 'Server error'));
			} else {
				resolve(response);
			}
		}
		
		// Handle notifications (no ID)
		if (!response.id) {
			this.emit('notification', response);
		}
		
		// Emit all responses for general handling
		this.emit('response', response);
	}
	
	/**
	 * Get next unique message ID
	 */
	getNextMessageId() {
		return ++this.messageId;
	}
	
	/**
	 * Send tool call request
	 */
	async callTool(toolName, parameters = {}) {
		const request = {
			method: 'tools/call',
			params: {
				name: toolName,
				arguments: parameters
			}
		};
		
		return this.sendRequest(request);
	}
	
	/**
	 * List available tools
	 */
	async listTools() {
		const request = {
			method: 'tools/list',
			params: {}
		};
		
		return this.sendRequest(request);
	}
	
	/**
	 * Get tool description
	 */
	async describeTool(toolName) {
		const tools = await this.listTools();
		return tools.result?.tools?.find(tool => tool.name === toolName);
	}

	/**
	 * Initialize server with client capabilities
	 */
	async initialize(params = {}) {
		const request = {
			method: 'initialize',
			params: {
				protocolVersion: '2024-11-05',
				capabilities: { tools: {} },
				clientInfo: { name: 'MCP E2E Framework', version: '1.0.0' },
				...params
			}
		};

		return this.sendRequest(request);
	}

	/**
	 * Get performance statistics
	 */
	getPerformanceStats() {
		const responseTimes = Array.from(this.responseTimes.values());
		const completedRequests = this.messageHistory.filter(msg => msg.status === 'completed');

		return {
			totalRequests: this.messageHistory.length,
			completedRequests: completedRequests.length,
			errorCounts: this.errorCounts,
			responseTimes: {
				min: responseTimes.length > 0 ? Math.min(...responseTimes) : 0,
				max: responseTimes.length > 0 ? Math.max(...responseTimes) : 0,
				avg: responseTimes.length > 0 ? responseTimes.reduce((a, b) => a + b, 0) / responseTimes.length : 0,
				p95: responseTimes.length > 0 ? this.calculatePercentile(responseTimes, 95) : 0
			},
			messageHistory: this.messageHistory.slice(-20) // Last 20 messages
		};
	}

	/**
	 * Calculate percentile from array of numbers
	 */
	calculatePercentile(arr, percentile) {
		const sorted = arr.slice().sort((a, b) => a - b);
		const index = Math.ceil((percentile / 100) * sorted.length) - 1;
		return sorted[index] || 0;
	}

	/**
	 * Clear performance tracking data
	 */
	clearStats() {
		this.messageHistory = [];
		this.responseTimes.clear();
		this.errorCounts = { total: 0, network: 0, protocol: 0, timeout: 0 };
	}

	// ============================================================================
	// TEST ASSERTION FRAMEWORK
	// ============================================================================

	/**
	 * Assert server is running
	 */
	assertServerRunning() {
		if (!this.isRunning) {
			throw new Error('MCP server is not running');
		}
	}

	/**
	 * Assert response structure and success
	 */
	assertResponse(response, context = '') {
		const prefix = context ? `${context}: ` : '';

		if (!response) {
			throw new Error(`${prefix}Response is null or undefined`);
		}

		if (typeof response !== 'object') {
			throw new Error(`${prefix}Response is not an object: ${typeof response}`);
		}

		if (response.error) {
			throw new Error(`${prefix}Response contains error: ${response.error.message || JSON.stringify(response.error)}`);
		}
	}

	/**
	 * Assert tool response structure
	 */
	assertToolResponse(response, context = '') {
		this.assertResponse(response, context);

		if (!response.result) {
			throw new Error(`${context ? context + ': ' : ''}Tool response missing result field`);
		}

		if (!response.result.content) {
			throw new Error(`${context ? context + ': ' : ''}Tool response missing content field`);
		}

		if (!Array.isArray(response.result.content)) {
			throw new Error(`${context ? context + ': ' : ''}Tool response content is not an array`);
		}
	}

	/**
	 * Assert object has specific property
	 */
	assertProperty(obj, property, context = '') {
		const prefix = context ? `${context}: ` : '';

		if (!obj || typeof obj !== 'object') {
			throw new Error(`${prefix}Object is null, undefined, or not an object`);
		}

		if (!(property in obj)) {
			throw new Error(`${prefix}Object missing required property: ${property}`);
		}
	}

	/**
	 * Assert array is not empty
	 */
	assertArrayNotEmpty(arr, context = '') {
		const prefix = context ? `${context}: ` : '';

		if (!Array.isArray(arr)) {
			throw new Error(`${prefix}Value is not an array: ${typeof arr}`);
		}

		if (arr.length === 0) {
			throw new Error(`${prefix}Array is empty`);
		}
	}

	/**
	 * Assert array structure
	 */
	assertArray(arr, context = '') {
		const prefix = context ? `${context}: ` : '';

		if (!Array.isArray(arr)) {
			throw new Error(`${prefix}Value is not an array: ${typeof arr}`);
		}
	}

	/**
	 * Assert tool exists in tools array
	 */
	assertToolExists(tools, toolName) {
		if (!Array.isArray(tools)) {
			throw new Error('Tools is not an array');
		}

		const tool = tools.find(t => t.name === toolName);
		if (!tool) {
			const availableTools = tools.map(t => t.name).join(', ');
			throw new Error(`Tool "${toolName}" not found. Available tools: ${availableTools}`);
		}
	}

	/**
	 * Assert values are equal
	 */
	assertEqual(actual, expected, message = '') {
		if (actual !== expected) {
			const prefix = message ? `${message}: ` : '';
			throw new Error(`${prefix}Expected "${expected}", but got "${actual}"`);
		}
	}

	/**
	 * Assert condition is true
	 */
	assertTrue(condition, message = 'Assertion failed') {
		if (!condition) {
			throw new Error(message);
		}
	}

	/**
	 * Assert condition is false
	 */
	assertFalse(condition, message = 'Assertion failed') {
		if (condition) {
			throw new Error(message);
		}
	}

	/**
	 * Assert error type for JSON-RPC errors
	 */
	assertErrorType(error, expectedType) {
		if (!error) {
			throw new Error('Expected error but none was thrown');
		}

		// For JSON-RPC errors, check if message contains the error type
		const errorMessage = error.message || error.toString();
		if (!errorMessage.includes(expectedType)) {
			throw new Error(`Expected error type "${expectedType}", but got: ${errorMessage}`);
		}
	}

	/**
	 * Assert response time is within acceptable range
	 */
	assertResponseTime(messageId, maxMs, message = '') {
		const responseTime = this.responseTimes.get(messageId);
		if (responseTime === undefined) {
			throw new Error(`No response time recorded for message ID: ${messageId}`);
		}

		if (responseTime > maxMs) {
			const prefix = message ? `${message}: ` : '';
			throw new Error(`${prefix}Response time ${responseTime}ms exceeds maximum ${maxMs}ms`);
		}
	}

	/**
	 * Assert number of items matches expected count
	 */
	assertCount(items, expectedCount, message = '') {
		const actualCount = Array.isArray(items) ? items.length : (items ? 1 : 0);
		const prefix = message ? `${message}: ` : '';

		if (actualCount !== expectedCount) {
			throw new Error(`${prefix}Expected ${expectedCount} items, but got ${actualCount}`);
		}
	}

	/**
	 * Assert string contains substring
	 */
	assertContains(haystack, needle, message = '') {
		const prefix = message ? `${message}: ` : '';

		if (typeof haystack !== 'string') {
			throw new Error(`${prefix}Haystack is not a string: ${typeof haystack}`);
		}

		if (!haystack.includes(needle)) {
			throw new Error(`${prefix}String "${haystack}" does not contain "${needle}"`);
		}
	}

	/**
	 * Assert value matches regular expression
	 */
	assertMatches(value, regex, message = '') {
		const prefix = message ? `${message}: ` : '';

		if (typeof value !== 'string') {
			throw new Error(`${prefix}Value is not a string: ${typeof value}`);
		}

		if (!regex.test(value)) {
			throw new Error(`${prefix}String "${value}" does not match pattern ${regex}`);
		}
	}
}

/**
 * Test Case Builder - Fluent API for creating test scenarios
 */
export class MCPTestCase {
	constructor(name, description, testFn = null) {
		this.name = name;
		this.description = description;
		this.testFn = testFn;
		this.timeout = 30000; // 30 seconds default
		this.retryCount = 0;
		this.setup = null;
		this.teardown = null;
		this.tags = [];
	}

	/**
	 * Set test timeout
	 */
	setTimeout(ms) {
		this.timeout = ms;
		return this;
	}

	/**
	 * Set retry count for flaky tests
	 */
	setRetries(count) {
		this.retryCount = count;
		return this;
	}

	/**
	 * Add tags for test categorization
	 */
	addTags(...tags) {
		this.tags.push(...tags);
		return this;
	}

	/**
	 * Set setup function
	 */
	setSetup(fn) {
		this.setup = fn;
		return this;
	}

	/**
	 * Set teardown function
	 */
	setTeardown(fn) {
		this.teardown = fn;
		return this;
	}

	/**
	 * Execute the test case
	 */
	async run() {
		const result = {
			name: this.name,
			description: this.description,
			success: false,
			duration: 0,
			attempts: 0,
			error: null,
			tags: this.tags
		};

		const startTime = Date.now();

		try {
			// Run setup if defined
			if (this.setup) {
				await this.setup();
			}

			// Execute test with retries
			let lastError = null;
			for (let attempt = 0; attempt <= this.retryCount; attempt++) {
				result.attempts = attempt + 1;

				try {
					// Run test function with timeout
					if (this.testFn) {
						await this.executeWithTimeout(this.testFn, this.timeout);
					}

					result.success = true;
					break; // Success, no need to retry
				} catch (error) {
					lastError = error;
					if (attempt < this.retryCount) {
						// Wait before retry (exponential backoff)
						await this.delay(Math.pow(2, attempt) * 1000);
					}
				}
			}

			if (!result.success && lastError) {
				result.error = lastError.message;
			}

		} catch (setupError) {
			result.error = `Setup failed: ${setupError.message}`;
		} finally {
			// Always run teardown
			if (this.teardown) {
				try {
					await this.teardown();
				} catch (teardownError) {
					console.warn(`Teardown failed for test "${this.name}":`, teardownError);
				}
			}

			result.duration = Date.now() - startTime;
		}

		return result;
	}

	/**
	 * Execute function with timeout
	 */
	async executeWithTimeout(fn, timeoutMs) {
		return new Promise(async (resolve, reject) => {
			const timeoutHandle = setTimeout(() => {
				reject(new Error(`Test timed out after ${timeoutMs}ms`));
			}, timeoutMs);

			try {
				const result = await fn();
				clearTimeout(timeoutHandle);
				resolve(result);
			} catch (error) {
				clearTimeout(timeoutHandle);
				reject(error);
			}
		});
	}

	/**
	 * Simple delay utility
	 */
	async delay(ms) {
		return new Promise(resolve => setTimeout(resolve, ms));
	}
	
	/**
	 * Add a setup step
	 */
	setup(fn) {
		this.steps.unshift({ type: 'setup', fn });
		return this;
	}
	
	/**
	 * Add a test step
	 */
	step(description, fn) {
		this.steps.push({ type: 'step', description, fn });
		return this;
	}
	
	/**
	 * Add a tool call step
	 */
	callTool(toolName, parameters = {}, description = null) {
		const desc = description || `Call tool: ${toolName}`;
		this.steps.push({
			type: 'tool-call',
			description: desc,
			toolName,
			parameters
		});
		return this;
	}
	
	/**
	 * Add assertion
	 */
	expect(description, assertionFn) {
		this.assertions.push({ description, fn: assertionFn });
		return this;
	}
	
	/**
	 * Add cleanup step
	 */
	teardown(fn) {
		this.cleanup.push(fn);
		return this;
	}
	
	/**
	 * Execute the test case
	 */
	async run() {
		const results = {
			name: this.name,
			success: true,
			steps: [],
			errors: []
		};
		
		try {
			// Execute setup and steps
			for (const step of this.steps) {
				const stepResult = await this.executeStep(step);
				results.steps.push(stepResult);
				
				if (!stepResult.success) {
					results.success = false;
				}
			}
			
			// Run assertions
			for (const assertion of this.assertions) {
				try {
					await assertion.fn();
					results.steps.push({
						type: 'assertion',
						description: assertion.description,
						success: true
					});
				} catch (error) {
					results.success = false;
					results.errors.push(error);
					results.steps.push({
						type: 'assertion',
						description: assertion.description,
						success: false,
						error: error.message
					});
				}
			}
			
		} catch (error) {
			results.success = false;
			results.errors.push(error);
		} finally {
			// Execute cleanup
			for (const cleanupFn of this.cleanup) {
				try {
					await cleanupFn();
				} catch (error) {
					// Log cleanup errors but don't fail the test
					console.warn('Cleanup error:', error);
				}
			}
		}
		
		return results;
	}
	
	/**
	 * Execute individual step
	 */
	async executeStep(step) {
		try {
			let result;
			
			switch (step.type) {
				case 'setup':
				case 'step':
					result = await step.fn();
					break;
					
				case 'tool-call':
					result = await this.framework.callTool(step.toolName, step.parameters);
					break;
					
				default:
					throw new Error(`Unknown step type: ${step.type}`);
			}
			
			return {
				type: step.type,
				description: step.description || step.type,
				success: true,
				result
			};
			
		} catch (error) {
			return {
				type: step.type,
				description: step.description || step.type,
				success: false,
				error: error.message
			};
		}
	}
}

/**
 * Test Suite - Collection of test cases
 */
export class MCPTestSuite {
	constructor(name, description = '', options = {}) {
		this.name = name;
		this.description = description;
		this.options = {
			parallel: false,
			stopOnFailure: false,
			timeout: 60000, // 60 seconds for entire suite
			verbose: false,
			...options
		};
		this.testCases = [];
		this.framework = null;
		this.setupSuite = null;
		this.teardownSuite = null;
	}

	/**
	 * Set suite-wide setup
	 */
	async setupSuite() {
		// Override in subclasses
	}

	/**
	 * Set suite-wide teardown
	 */
	async teardownSuite() {
		// Override in subclasses
	}

	/**
	 * Create test cases - override in subclasses
	 */
	createTests() {
		return [];
	}
	
	/**
	 * Add test case
	 */
	test(name, builderFn) {
		const testCase = new MCPTestCase(name, this.framework);
		builderFn(testCase);
		this.testCases.push(testCase);
		return this;
	}
	
	/**
	 * Run all test cases
	 */
	async run() {
		const startTime = Date.now();

		console.log(`\n🧪 Running Test Suite: ${this.name}`);
		if (this.description) {
			console.log(`   ${this.description}`);
		}
		console.log('   ' + '─'.repeat(60));

		// Get test cases from createTests method
		this.testCases = this.createTests();

		const suiteResults = {
			name: this.name,
			description: this.description,
			success: true,
			duration: 0,
			testResults: [],
			summary: {
				total: this.testCases.length,
				passed: 0,
				failed: 0,
				skipped: 0
			},
			performance: null
		};

		try {
			// Run suite setup
			if (this.setupSuite) {
				await this.setupSuite();
			}

			// Run test cases (parallel or sequential)
			if (this.options.parallel && this.testCases.length > 1) {
				suiteResults.testResults = await this.runTestsParallel();
			} else {
				suiteResults.testResults = await this.runTestsSequential();
			}

			// Calculate summary
			for (const result of suiteResults.testResults) {
				if (result.success) {
					suiteResults.summary.passed++;
				} else {
					suiteResults.summary.failed++;
					suiteResults.success = false;
				}
			}

			// Get performance stats if framework is available
			if (this.framework) {
				suiteResults.performance = this.framework.getPerformanceStats();
			}

		} catch (suiteError) {
			suiteResults.success = false;
			suiteResults.error = suiteError.message;
			console.error(`   💥 Suite setup/teardown failed: ${suiteError.message}`);

		} finally {
			// Run suite teardown
			if (this.teardownSuite) {
				try {
					await this.teardownSuite();
				} catch (teardownError) {
					console.warn(`   ⚠️  Suite teardown failed: ${teardownError.message}`);
				}
			}

			suiteResults.duration = Date.now() - startTime;
		}

		// Print summary
		this.printSummary(suiteResults);

		return suiteResults;
	}

	/**
	 * Run tests sequentially
	 */
	async runTestsSequential() {
		const results = [];

		for (const testCase of this.testCases) {
			if (this.options.verbose) {
				console.log(`   📋 Running: ${testCase.name}`);
			}

			const result = await testCase.run();
			results.push(result);

			if (result.success) {
				console.log(`   ✅ ${testCase.name} (${result.duration}ms)`);
			} else {
				console.log(`   ❌ ${testCase.name} - ${result.error}`);

				// Stop on failure if configured
				if (this.options.stopOnFailure) {
					break;
				}
			}
		}

		return results;
	}

	/**
	 * Run tests in parallel
	 */
	async runTestsParallel() {
		console.log(`   🚀 Running ${this.testCases.length} tests in parallel...`);

		const promises = this.testCases.map(async (testCase) => {
			const result = await testCase.run();

			if (result.success) {
				console.log(`   ✅ ${testCase.name} (${result.duration}ms)`);
			} else {
				console.log(`   ❌ ${testCase.name} - ${result.error}`);
			}

			return result;
		});

		return Promise.all(promises);
	}

	/**
	 * Print test suite summary
	 */
	printSummary(results) {
		console.log('\n' + '═'.repeat(60));
		console.log(`📊 ${results.name} - SUMMARY`);
		console.log('═'.repeat(60));
		console.log(`Duration: ${results.duration}ms`);
		console.log(`Total Tests: ${results.summary.total}`);
		console.log(`✅ Passed: ${results.summary.passed}`);
		console.log(`❌ Failed: ${results.summary.failed}`);

		if (results.summary.skipped > 0) {
			console.log(`⏭️  Skipped: ${results.summary.skipped}`);
		}

		const successRate = results.summary.total > 0
			? Math.round((results.summary.passed / results.summary.total) * 100)
			: 0;
		console.log(`Success Rate: ${successRate}%`);

		// Performance summary
		if (results.performance) {
			const perf = results.performance;
			console.log(`\n📈 Performance:`);
			console.log(`   Requests: ${perf.totalRequests} (${perf.completedRequests} completed)`);
			console.log(`   Avg Response Time: ${Math.round(perf.responseTimes.avg)}ms`);
			console.log(`   95th Percentile: ${Math.round(perf.responseTimes.p95)}ms`);
			console.log(`   Errors: ${perf.errorCounts.total}`);
		}

		console.log(`\n${results.success ? '🎉 ALL TESTS PASSED' : '💥 SOME TESTS FAILED'}`);
	}
}

/**
 * Helper functions for common test patterns
 */
export const TestHelpers = {
	/**
	 * Assert response structure
	 */
	assertResponseStructure(response, expectedStructure) {
		if (!response || typeof response !== 'object') {
			throw new Error('Response is not an object');
		}
		
		for (const [key, type] of Object.entries(expectedStructure)) {
			if (!(key in response)) {
				throw new Error(`Missing required field: ${key}`);
			}
			
			if (typeof response[key] !== type) {
				throw new Error(`Field ${key} should be ${type}, got ${typeof response[key]}`);
			}
		}
	},
	
	/**
	 * Assert tool response success
	 */
	assertToolSuccess(response) {
		if (!response.result) {
			throw new Error('Tool call failed: missing result');
		}
		
		if (response.error) {
			throw new Error(`Tool call failed: ${response.error.message}`);
		}
	},
	
	/**
	 * Assert task data structure
	 */
	assertTaskStructure(task) {
		const required = {
			id: 'number',
			title: 'string',
			status: 'string'
		};
		
		TestHelpers.assertResponseStructure(task, required);
	}
};

export default MCPTestFramework;