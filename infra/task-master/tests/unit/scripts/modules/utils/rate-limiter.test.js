/**
 * rate-limiter.test.js
 * Unit tests for Rate Limiter utility
 * Part of Task #101.1 - Implement GitHub API Export Service
 */

import { jest } from '@jest/globals';
import { RateLimiter } from '../../../../../scripts/modules/utils/rate-limiter.js';

// Mock setTimeout for testing
jest.useFakeTimers();

describe('RateLimiter', () => {
	beforeEach(() => {
		jest.clearAllTimers();
		jest.clearAllMocks();
	});

	afterEach(() => {
		jest.runOnlyPendingTimers();
	});

	describe('Constructor', () => {
		test('should create with default values', () => {
			const limiter = new RateLimiter();

			expect(limiter.capacity).toBe(5000);
			expect(limiter.tokens).toBe(5000);
			expect(limiter.interval).toBe(60 * 60 * 1000); // 1 hour in ms
		});

		test('should accept custom configuration', () => {
			const limiter = new RateLimiter({
				tokensPerInterval: 100,
				interval: 'minute'
			});

			expect(limiter.capacity).toBe(100);
			expect(limiter.tokens).toBe(100);
			expect(limiter.interval).toBe(60 * 1000); // 1 minute in ms
		});

		test('should parse interval strings correctly', () => {
			const limiter = new RateLimiter();

			expect(limiter.parseInterval('second')).toBe(1000);
			expect(limiter.parseInterval('minute')).toBe(60 * 1000);
			expect(limiter.parseInterval('hour')).toBe(60 * 60 * 1000);
			expect(limiter.parseInterval('day')).toBe(24 * 60 * 60 * 1000);
		});

		test('should handle numeric intervals', () => {
			const limiter = new RateLimiter({
				tokensPerInterval: 100,
				interval: 5000 // 5 seconds
			});

			expect(limiter.interval).toBe(5000);
		});
	});

	describe('Token Management', () => {
		test('should have tokens available initially', () => {
			const limiter = new RateLimiter({ tokensPerInterval: 10, interval: 'minute' });

			expect(limiter.hasTokens(1)).toBe(true);
			expect(limiter.hasTokens(5)).toBe(true);
			expect(limiter.hasTokens(10)).toBe(true);
			expect(limiter.hasTokens(11)).toBe(false);
		});

		test('should consume tokens successfully', () => {
			const limiter = new RateLimiter({ tokensPerInterval: 10, interval: 'minute' });

			expect(limiter.tryRemoveTokens(3)).toBe(true);
			expect(limiter.tokens).toBe(7);

			expect(limiter.tryRemoveTokens(7)).toBe(true);
			expect(limiter.tokens).toBe(0);

			expect(limiter.tryRemoveTokens(1)).toBe(false);
			expect(limiter.tokens).toBe(0);
		});

		test('should track statistics', () => {
			const limiter = new RateLimiter({ tokensPerInterval: 10, interval: 'minute' });

			limiter.tryRemoveTokens(5);
			limiter.tryRemoveTokens(3);
			limiter.tryRemoveTokens(5); // Should fail

			const status = limiter.getStatus();
			expect(status.stats.requestsAllowed).toBe(2);
			expect(status.stats.requestsBlocked).toBe(1);
		});
	});

	describe('Token Refill', () => {
		test('should refill tokens over time', () => {
			const limiter = new RateLimiter({ tokensPerInterval: 60, interval: 'minute' });

			// Consume all tokens
			limiter.tryRemoveTokens(60);
			expect(limiter.tokens).toBe(0);

			// Advance time by 30 seconds (should refill 30 tokens)
			jest.advanceTimersByTime(30 * 1000);
			limiter.refillTokens();
			expect(limiter.tokens).toBe(30);

			// Advance another 30 seconds (should be back to full capacity)
			jest.advanceTimersByTime(30 * 1000);
			limiter.refillTokens();
			expect(limiter.tokens).toBe(60);
		});

		test('should not exceed capacity when refilling', () => {
			const limiter = new RateLimiter({ tokensPerInterval: 10, interval: 'minute' });

			// Don't consume any tokens, advance time
			jest.advanceTimersByTime(2 * 60 * 1000); // 2 minutes
			limiter.refillTokens();

			expect(limiter.tokens).toBe(10); // Should not exceed capacity
		});
	});

	describe('Async Token Removal', () => {
		test('should wait for tokens to become available', async () => {
			const limiter = new RateLimiter({ tokensPerInterval: 60, interval: 'minute' });

			// Consume all tokens
			limiter.tryRemoveTokens(60);
			expect(limiter.tokens).toBe(0);

			// Start async removal
			const removalPromise = limiter.removeTokens(1);

			// Should not resolve immediately
			let resolved = false;
			removalPromise.then(() => { resolved = true; });

			// Advance timers but not enough
			jest.advanceTimersByTime(500);
			await Promise.resolve(); // Allow Promise to process
			expect(resolved).toBe(false);

			// Advance enough time for one token to be available
			jest.advanceTimersByTime(1500);
			await removalPromise;

			expect(resolved).toBe(true);
		});

		test('should handle multiple concurrent requests', async () => {
			const limiter = new RateLimiter({ tokensPerInterval: 60, interval: 'minute' });

			// Consume most tokens, leaving only 2
			limiter.tryRemoveTokens(58);
			expect(limiter.tokens).toBe(2);

			// Start three concurrent requests for 1 token each
			const promises = [
				limiter.removeTokens(1),
				limiter.removeTokens(1),
				limiter.removeTokens(1)
			];

			// First two should resolve quickly
			jest.advanceTimersByTime(100);
			await Promise.all(promises.slice(0, 2));

			expect(limiter.tokens).toBe(0);

			// Third one should wait
			jest.advanceTimersByTime(1000);
			await promises[2];

			expect(limiter.tokens).toBe(0);
		});
	});

	describe('Status and Statistics', () => {
		test('should provide accurate status', () => {
			const limiter = new RateLimiter({ tokensPerInterval: 100, interval: 'hour' });

			limiter.tryRemoveTokens(25);

			const status = limiter.getStatus();
			expect(status.tokensAvailable).toBe(75);
			expect(status.capacity).toBe(100);
			expect(status.utilizationRate).toBe(25);
		});

		test('should calculate time to next refill', () => {
			const limiter = new RateLimiter({ tokensPerInterval: 60, interval: 'minute' });

			limiter.tryRemoveTokens(60); // Consume all tokens

			const timeToRefill = limiter.getTimeToNextRefill();
			expect(timeToRefill).toBeGreaterThan(0);
			expect(timeToRefill).toBeLessThanOrEqual(1000);
		});

		test('should reset statistics and tokens', () => {
			const limiter = new RateLimiter({ tokensPerInterval: 10, interval: 'minute' });

			limiter.tryRemoveTokens(5);
			limiter.tryRemoveTokens(10); // Should fail

			limiter.reset();

			const status = limiter.getStatus();
			expect(status.tokensAvailable).toBe(10);
			expect(status.stats.requestsAllowed).toBe(0);
			expect(status.stats.requestsBlocked).toBe(0);
		});
	});

	describe('GitHub API Presets', () => {
		test('should create GitHub API rate limiter', () => {
			const limiter = RateLimiter.forGitHubAPI();

			expect(limiter.capacity).toBe(5000);
			expect(limiter.interval).toBe(60 * 60 * 1000); // 1 hour
		});

		test('should create GitHub Search API rate limiter', () => {
			const limiter = RateLimiter.forGitHubSearchAPI();

			expect(limiter.capacity).toBe(30);
			expect(limiter.interval).toBe(60 * 1000); // 1 minute
		});

		test('should allow overriding preset options', () => {
			const limiter = RateLimiter.forGitHubAPI({ tokensPerInterval: 3000 });

			expect(limiter.capacity).toBe(3000);
			expect(limiter.interval).toBe(60 * 60 * 1000);
		});
	});

	describe('Edge Cases', () => {
		test('should handle zero tokens request', () => {
			const limiter = new RateLimiter({ tokensPerInterval: 10, interval: 'minute' });

			expect(limiter.tryRemoveTokens(0)).toBe(true);
			expect(limiter.tokens).toBe(10);
		});

		test('should handle negative tokens request', () => {
			const limiter = new RateLimiter({ tokensPerInterval: 10, interval: 'minute' });

			expect(limiter.tryRemoveTokens(-1)).toBe(true);
			expect(limiter.tokens).toBe(10);
		});

		test('should handle very large intervals', () => {
			const limiter = new RateLimiter({
				tokensPerInterval: 1000000,
				interval: 'day'
			});

			expect(limiter.capacity).toBe(1000000);
			expect(limiter.interval).toBe(24 * 60 * 60 * 1000);
		});
	});
});