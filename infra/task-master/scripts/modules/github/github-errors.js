/**
 * github-errors.js
 * Custom error classes for GitHub API operations
 * Part of Task #101.1 - Implement GitHub API Export Service
 */

/**
 * Base class for GitHub-related errors
 */
export class GitHubError extends Error {
	constructor(message, code = null) {
		super(message);
		this.name = this.constructor.name;
		this.code = code;
		Error.captureStackTrace(this, this.constructor);
	}
}

/**
 * Error for GitHub API-specific issues
 */
export class GitHubAPIError extends GitHubError {
	constructor(message, statusCode = null, response = null) {
		super(message, 'GITHUB_API_ERROR');
		this.statusCode = statusCode;
		this.response = response;
	}
}

/**
 * Error for authentication and authorization issues
 */
export class AuthenticationError extends GitHubError {
	constructor(message) {
		super(message, 'AUTHENTICATION_ERROR');
	}
}

/**
 * Error for validation and input issues
 */
export class ValidationError extends GitHubError {
	constructor(message) {
		super(message, 'VALIDATION_ERROR');
	}
}

/**
 * Error for rate limiting issues
 */
export class RateLimitError extends GitHubError {
	constructor(message, resetTime = null) {
		super(message, 'RATE_LIMIT_ERROR');
		this.resetTime = resetTime;
	}
}

/**
 * Error for network and connectivity issues
 */
export class NetworkError extends GitHubError {
	constructor(message) {
		super(message, 'NETWORK_ERROR');
	}
}

/**
 * Error for repository access issues
 */
export class RepositoryError extends GitHubError {
	constructor(message, repository = null) {
		super(message, 'REPOSITORY_ERROR');
		this.repository = repository;
	}
}

/**
 * Error factory for creating appropriate error types based on HTTP status codes
 * @param {number} statusCode - HTTP status code
 * @param {string} message - Error message
 * @param {Object} response - Optional response object
 * @returns {GitHubError} Appropriate error instance
 */
export function createGitHubError(statusCode, message, response = null) {
	switch (statusCode) {
		case 401:
			return new AuthenticationError(`Authentication failed: ${message}`);
		case 403:
			if (message.includes('rate limit')) {
				const resetTime = response?.headers?.get('x-ratelimit-reset');
				return new RateLimitError(message, resetTime);
			}
			return new AuthenticationError(`Forbidden: ${message}`);
		case 404:
			return new RepositoryError(`Resource not found: ${message}`);
		case 422:
			return new ValidationError(`Validation failed: ${message}`);
		case 429:
			const resetTime = response?.headers?.get('x-ratelimit-reset');
			return new RateLimitError(`Rate limit exceeded: ${message}`, resetTime);
		default:
			return new GitHubAPIError(message, statusCode, response);
	}
}

/**
 * Check if an error is retryable
 * @param {Error} error - Error to check
 * @returns {boolean} Whether the error is retryable
 */
export function isRetryableError(error) {
	if (error instanceof RateLimitError) {
		return true;
	}

	if (error instanceof GitHubAPIError) {
		// Retry on server errors (5xx)
		return error.statusCode >= 500 && error.statusCode < 600;
	}

	if (error instanceof NetworkError) {
		return true;
	}

	return false;
}

/**
 * Get retry delay for retryable errors
 * @param {Error} error - Error to get delay for
 * @param {number} attempt - Current attempt number
 * @returns {number} Delay in milliseconds
 */
export function getRetryDelay(error, attempt = 1) {
	if (error instanceof RateLimitError && error.resetTime) {
		// Wait until rate limit resets
		const resetTime = parseInt(error.resetTime) * 1000;
		const now = Date.now();
		return Math.max(0, resetTime - now);
	}

	// Exponential backoff for other retryable errors
	return Math.min(1000 * Math.pow(2, attempt - 1), 30000);
}

export default {
	GitHubError,
	GitHubAPIError,
	AuthenticationError,
	ValidationError,
	RateLimitError,
	NetworkError,
	RepositoryError,
	createGitHubError,
	isRetryableError,
	getRetryDelay
};