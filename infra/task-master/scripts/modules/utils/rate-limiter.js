/**
 * rate-limiter.js
 * Rate limiting utility for API requests
 * Part of Task #101.1 - Implement GitHub API Export Service
 */

/**
 * Token bucket rate limiter implementation
 */
export class RateLimiter {
	constructor(options = {}) {
		// Default to GitHub API limits if not specified
		this.capacity = options.tokensPerInterval || 5000;
		this.interval = this.parseInterval(options.interval || 'hour');
		this.tokens = this.capacity;
		this.lastRefill = Date.now();

		// Configuration
		this.refillRate = this.capacity / this.interval;

		// Statistics
		this.stats = {
			requestsAllowed: 0,
			requestsBlocked: 0,
			totalWaitTime: 0
		};
	}

	/**
	 * Parse interval string to milliseconds
	 * @param {string|number} interval - Interval specification
	 * @returns {number} Interval in milliseconds
	 */
	parseInterval(interval) {
		if (typeof interval === 'number') {
			return interval;
		}

		const intervals = {
			'second': 1000,
			'minute': 60 * 1000,
			'hour': 60 * 60 * 1000,
			'day': 24 * 60 * 60 * 1000
		};

		return intervals[interval] || intervals['hour'];
	}

	/**
	 * Refill tokens based on elapsed time
	 */
	refillTokens() {
		const now = Date.now();
		const elapsed = now - this.lastRefill;

		if (elapsed > 0) {
			const tokensToAdd = Math.floor((elapsed / 1000) * (this.refillRate / 1000));
			this.tokens = Math.min(this.capacity, this.tokens + tokensToAdd);
			this.lastRefill = now;
		}
	}

	/**
	 * Check if tokens are available without consuming them
	 * @param {number} count - Number of tokens needed
	 * @returns {boolean} Whether tokens are available
	 */
	hasTokens(count = 1) {
		this.refillTokens();
		return this.tokens >= count;
	}

	/**
	 * Try to consume tokens immediately
	 * @param {number} count - Number of tokens to consume
	 * @returns {boolean} Whether tokens were successfully consumed
	 */
	tryRemoveTokens(count = 1) {
		this.refillTokens();

		if (this.tokens >= count) {
			this.tokens -= count;
			this.stats.requestsAllowed++;
			return true;
		}

		this.stats.requestsBlocked++;
		return false;
	}

	/**
	 * Remove tokens, waiting if necessary
	 * @param {number} count - Number of tokens to consume
	 * @returns {Promise<void>} Resolves when tokens are available
	 */
	async removeTokens(count = 1) {
		this.refillTokens();

		if (this.tokens >= count) {
			this.tokens -= count;
			this.stats.requestsAllowed++;
			return;
		}

		// Calculate wait time
		const tokensNeeded = count - this.tokens;
		const waitTime = Math.ceil((tokensNeeded / this.refillRate) * 1000);

		this.stats.requestsBlocked++;
		this.stats.totalWaitTime += waitTime;

		// Wait for tokens to become available
		await this.wait(waitTime);

		// Recursively try again
		return this.removeTokens(count);
	}

	/**
	 * Get current status of the rate limiter
	 * @returns {Object} Status information
	 */
	getStatus() {
		this.refillTokens();

		return {
			tokensAvailable: this.tokens,
			capacity: this.capacity,
			interval: this.interval,
			utilizationRate: ((this.capacity - this.tokens) / this.capacity) * 100,
			nextRefillIn: this.getTimeToNextRefill(),
			stats: { ...this.stats }
		};
	}

	/**
	 * Calculate time until next token refill
	 * @returns {number} Time in milliseconds
	 */
	getTimeToNextRefill() {
		if (this.tokens >= this.capacity) {
			return 0;
		}

		const timeBetweenTokens = 1000 / (this.refillRate / 1000);
		return Math.ceil(timeBetweenTokens);
	}

	/**
	 * Reset the rate limiter
	 */
	reset() {
		this.tokens = this.capacity;
		this.lastRefill = Date.now();
		this.stats = {
			requestsAllowed: 0,
			requestsBlocked: 0,
			totalWaitTime: 0
		};
	}

	/**
	 * Utility method to wait for a specified duration
	 * @param {number} ms - Milliseconds to wait
	 * @returns {Promise<void>} Promise that resolves after the wait
	 */
	wait(ms) {
		return new Promise(resolve => setTimeout(resolve, ms));
	}

	/**
	 * Create a rate limiter specifically configured for GitHub API
	 * @param {Object} options - Optional configuration overrides
	 * @returns {RateLimiter} Configured rate limiter
	 */
	static forGitHubAPI(options = {}) {
		return new RateLimiter({
			tokensPerInterval: 5000,  // GitHub allows 5000 requests per hour
			interval: 'hour',
			...options
		});
	}

	/**
	 * Create a rate limiter for GitHub Search API (stricter limits)
	 * @param {Object} options - Optional configuration overrides
	 * @returns {RateLimiter} Configured rate limiter
	 */
	static forGitHubSearchAPI(options = {}) {
		return new RateLimiter({
			tokensPerInterval: 30,    // GitHub Search API allows 30 requests per minute
			interval: 'minute',
			...options
		});
	}
}

export default RateLimiter;