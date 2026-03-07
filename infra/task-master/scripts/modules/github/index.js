/**
 * github/index.js
 * Main entry point for GitHub integration modules
 * Part of Task #101.1 - Implement GitHub API Export Service
 */

export { GitHubExportService } from './github-export-service.js';
export { TaskGitHubFormatter } from './task-github-formatter.js';
export { GitHubLinkManager } from './link-manager.js';
export {
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
} from './github-errors.js';

// Re-export rate limiter from utils
export { RateLimiter } from '../utils/rate-limiter.js';

// Default export with imported modules
import { GitHubExportService as _GitHubExportService } from './github-export-service.js';
import { TaskGitHubFormatter as _TaskGitHubFormatter } from './task-github-formatter.js';
import { GitHubLinkManager as _GitHubLinkManager } from './link-manager.js';
import {
	GitHubError as _GitHubError,
	GitHubAPIError as _GitHubAPIError,
	AuthenticationError as _AuthenticationError,
	ValidationError as _ValidationError,
	RateLimitError as _RateLimitError,
	NetworkError as _NetworkError,
	RepositoryError as _RepositoryError,
	createGitHubError as _createGitHubError,
	isRetryableError as _isRetryableError,
	getRetryDelay as _getRetryDelay
} from './github-errors.js';
import { RateLimiter as _RateLimiter } from '../utils/rate-limiter.js';

export default {
	GitHubExportService: _GitHubExportService,
	TaskGitHubFormatter: _TaskGitHubFormatter,
	GitHubLinkManager: _GitHubLinkManager,
	GitHubError: _GitHubError,
	GitHubAPIError: _GitHubAPIError,
	AuthenticationError: _AuthenticationError,
	ValidationError: _ValidationError,
	RateLimitError: _RateLimitError,
	NetworkError: _NetworkError,
	RepositoryError: _RepositoryError,
	createGitHubError: _createGitHubError,
	isRetryableError: _isRetryableError,
	getRetryDelay: _getRetryDelay,
	RateLimiter: _RateLimiter
};