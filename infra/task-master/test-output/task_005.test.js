/**
 * @fileoverview This file contains the Jest test suite for the ClaudeApiService.
 *
 * The ClaudeApiService is responsible for integrating with the Anthropic Claude API.
 * These tests cover:
 * - API client initialization and authentication.
 * - Successful text generation and response parsing.
 * - Configuration of model parameters.
 * - Error handling, including retry logic with exponential backoff.
 * - Token usage tracking integration.
 *
 * Mocks are used for the Anthropic SDK and a TokenTracker to isolate the service
 * and prevent actual API calls during testing.
 */

// Import Jest functions and types
import { describe, it, expect, jest, beforeEach, afterEach, afterAll } from '@jest/globals';

// Mock external dependencies before importing the service
const mockApiCreate = jest.fn();
const mockTokenTrack = jest.fn();

// Mock the entire '@anthropic-ai/sdk' module
jest.mock('@anthropic-ai/sdk', () => {
  // We need to be able to instantiate the mocked error class for testing
  const originalModule = jest.requireActual('@anthropic-ai/sdk');
  return {
    ...originalModule, // Keep original exports like types
    Anthropic: jest.fn().mockImplementation(() => ({
      messages: {
        create: mockApiCreate,
      },
    })),
    // Mock the APIError class to simulate specific API failures
    APIError: class MockAPIError extends Error {
      status: number;
      constructor(status: number, message: string) {
        super(message);
        this.name = 'APIError';
        this.status = status;
      }
    },
  };
});

// This is a hypothetical TokenTracker class that the service depends on.
// We mock it to verify interactions.
class TokenTracker {
  public track(inputTokens: number, outputTokens: number): void {
    // This implementation is mocked below
  }
}

// Mock the TokenTracker implementation
jest.mock('../services/TokenTracker', () => { // Assuming a path for the tracker
  return {
    TokenTracker: jest.fn().mockImplementation(() => ({
      track: mockTokenTrack,
    })),
  };
});


// Import the System Under Test (SUT) and its dependencies
// NOTE: The actual implementation of ClaudeApiService is assumed to exist at this path.
import { ClaudeApiService, ClaudeConfig, GenerateParams } from '../services/claudeApiService';
import { Anthropic, APIError } from '@anthropic-ai/sdk';
import { Message } from '@anthropic-ai/sdk/resources/messages';

// Type-safe mock for the Anthropic class constructor
const MockedAnthropic = Anthropic as jest.MockedClass<typeof Anthropic>;

// Use fake timers for testing retry logic with exponential backoff
jest.useFakeTimers();

describe('ClaudeApiService', () => {
  const originalEnv = process.env;

  // --- Test Data and Mocks ---
  const mockApiKey = 'test-api-key-12345';
  const mockSuccessResponse: Message = {
    id: 'msg_123',
    type: 'message',
    role: 'assistant',
    model: 'claude-3-opus-20240229',
    content: [{ type: 'text', text: 'This is a generated task.' }],
    stop_reason: 'end_turn',
    stop_sequence: null,
    usage: { input_tokens: 10, output_tokens: 25 },
  };

  beforeEach(() => {
    // Reset mocks and environment variables before each test
    jest.clearAllMocks();
    process.env = { ...originalEnv };
  });

  afterAll(() => {
    // Restore original environment variables after all tests
    process.env = originalEnv;
  });

  // --- Test Suite for Initialization and Authentication ---
  describe('Initialization and Authentication', () => {
    it('should throw an error if ANTHROPIC_API_KEY environment variable is not set and no key is provided in config', () => {
      delete process.env.ANTHROPIC_API_KEY;
      const tokenTracker = new TokenTracker();
      expect(() => new ClaudeApiService(tokenTracker)).toThrow(
        'Anthropic API key is not provided. Please set the ANTHROPIC_API_KEY environment variable.'
      );
    });

    it('should initialize successfully using the ANTHROPIC_API_KEY environment variable', () => {
      process.env.ANTHROPIC_API_KEY = mockApiKey;
      const tokenTracker = new TokenTracker();
      expect(() => new ClaudeApiService(tokenTracker)).not.toThrow();
      expect(MockedAnthropic).toHaveBeenCalledWith({ apiKey: mockApiKey });
    });

    it('should initialize successfully using an API key provided in the constructor config', () => {
      delete process.env.ANTHROPIC_API_KEY;
      const tokenTracker = new TokenTracker();
      const config: ClaudeConfig = { apiKey: 'config-key' };
      expect(() => new ClaudeApiService(tokenTracker, config)).not.toThrow();
      expect(MockedAnthropic).toHaveBeenCalledWith({ apiKey: 'config-key' });
    });

    it('should prioritize the API key from config over the environment variable', () => {
      process.env.ANTHROPIC_API_KEY = 'env-key';
      const tokenTracker = new TokenTracker();
      const config: ClaudeConfig = { apiKey: 'config-key-priority' };
      new ClaudeApiService(tokenTracker, config);
      expect(MockedAnthropic).toHaveBeenCalledWith({ apiKey: 'config-key-priority' });
    });
  });

  // --- Test Suite for Core Functionality ---
  describe('Text Generation', () => {
    let service: ClaudeApiService;
    let tokenTracker: TokenTracker;

    beforeEach(() => {
      process.env.ANTHROPIC_API_KEY = mockApiKey;
      tokenTracker = new TokenTracker();
      service = new ClaudeApiService(tokenTracker);
    });

    it('should call the Anthropic API with correct default parameters', async () => {
      mockApiCreate.mockResolvedValue(mockSuccessResponse);
      const prompt = 'Generate a simple task.';
      await service.generate(prompt);

      expect(mockApiCreate).toHaveBeenCalledTimes(1);
      expect(mockApiCreate).toHaveBeenCalledWith({
        model: 'claude-3-opus-20240229', // Default model
        max_tokens: 1024, // Default max_tokens
        temperature: 0.7, // Default temperature
        messages: [{ role: 'user', content: prompt }],
        system: undefined,
      });
    });

    it('should return the parsed response content on a successful API call', async () => {
      mockApiCreate.mockResolvedValue(mockSuccessResponse);
      const result = await service.generate('test prompt');
      expect(result.content).toBe('This is a generated task.');
    });

    it('should handle an empty or malformed response from the API', async () => {
      const malformedResponse: Message = {
        ...mockSuccessResponse,
        content: [], // Empty content
      };
      mockApiCreate.mockResolvedValue(malformedResponse);
      await expect(service.generate('test prompt')).rejects.toThrow(
        'Invalid or empty response from Claude API'
      );
    });
  });

  // --- Test Suite for Model Parameter Configuration ---
  describe('Model Parameter Configuration', () => {
    let service: ClaudeApiService;

    beforeEach(() => {
      process.env.ANTHROPIC_API_KEY = mockApiKey;
      const tokenTracker = new TokenTracker();
      service = new ClaudeApiService(tokenTracker, { model: 'default-model' });
      mockApiCreate.mockResolvedValue(mockSuccessResponse);
    });

    it('should use default model parameters if none are provided at call time', async () => {
      await service.generate('test');
      expect(mockApiCreate).toHaveBeenCalledWith(expect.objectContaining({
        model: 'default-model',
      }));
    });

    it('should override default parameters with those provided in GenerateParams', async () => {
      const params: GenerateParams = {
        model: 'claude-3-sonnet-20240229',
        max_tokens: 500,
        temperature: 0.2,
        system: 'You are a helpful assistant.',
      };
      await service.generate('test', params);

      expect(mockApiCreate).toHaveBeenCalledWith(expect.objectContaining({
        model: params.model,
        max_tokens: params.max_tokens,
        temperature: params.temperature,
        system: params.system,
      }));
    });

    it('should merge provided parameters with defaults', async () => {
      const params: GenerateParams = { temperature: 0.9 };
      await service.generate('test', params);

      expect(mockApiCreate).toHaveBeenCalledWith(expect.objectContaining({
        model: 'default-model', // From constructor config
        max_tokens: 1024, // Default from implementation
        temperature: 0.9, // Overridden at call time
      }));
    });
  });

  // --- Test Suite for Error Management and Retries ---
  describe('Error Management and Retries', () => {
    let service: ClaudeApiService;

    beforeEach(() => {
      process.env.ANTHROPIC_API_KEY = mockApiKey;
      const tokenTracker = new TokenTracker();
      // Configure for faster tests: 3 retries, 100ms initial delay
      service = new ClaudeApiService(tokenTracker, { maxRetries: 3, initialDelay: 100 });
    });

    it('should not retry on non-retriable errors (e.g., 400 Bad Request)', async () => {
      const badRequestError = new APIError(400, 'Bad Request');
      mockApiCreate.mockRejectedValueOnce(badRequestError);

      await expect(service.generate('test')).rejects.toThrow(badRequestError);
      expect(mockApiCreate).toHaveBeenCalledTimes(1);
    });

    it('should not retry on authentication errors (e.g., 401 Unauthorized)', async () => {
      const authError = new APIError(401, 'Invalid API Key');
      mockApiCreate.mockRejectedValueOnce(authError);

      await expect(service.generate('test')).rejects.toThrow(authError);
      expect(mockApiCreate).toHaveBeenCalledTimes(1);
    });

    it('should retry on rate limit errors (429) and then succeed', async () => {
      const rateLimitError = new APIError(429, 'Rate limit exceeded');
      mockApiCreate
        .mockRejectedValueOnce(rateLimitError)
        .mockResolvedValueOnce(mockSuccessResponse);

      const promise = service.generate('test');
      
      // First attempt fails, should wait for 100ms (initialDelay)
      await jest.advanceTimersByTimeAsync(100);

      const result = await promise;
      expect(result.content).toBe('This is a generated task.');
      expect(mockApiCreate).toHaveBeenCalledTimes(2);
    });

    it('should retry on server errors (5xx) and then succeed', async () => {
      const serverError = new APIError(500, 'Internal Server Error');
      mockApiCreate
        .mockRejectedValueOnce(serverError)
        .mockResolvedValueOnce(mockSuccessResponse);

      const promise = service.generate('test');
      await jest.advanceTimersByTimeAsync(100); // Wait for retry delay

      await expect(promise).resolves.toBeDefined();
      expect(mockApiCreate).toHaveBeenCalledTimes(2);
    });

    it('should use exponential backoff for retries', async () => {
      const rateLimitError = new APIError(429, 'Rate limit exceeded');
      mockApiCreate
        .mockRejectedValueOnce(rateLimitError) // Fails 1st time
        .mockRejectedValueOnce(rateLimitError) // Fails 2nd time
        .mockResolvedValueOnce(mockSuccessResponse); // Succeeds 3rd time

      const promise = service.generate('test');

      // 1st retry delay: 100ms
      await jest.advanceTimersByTimeAsync(100);
      // 2nd retry delay: 100ms * 2^1 = 200ms
      await jest.advanceTimersByTimeAsync(200);

      await expect(promise).resolves.toBeDefined();
      expect(mockApiCreate).toHaveBeenCalledTimes(3);
    });

    it('should fail after exceeding the maximum number of retries', async () => {
      const persistentError = new APIError(503, 'Service Unavailable');
      mockApiCreate.mockRejectedValue(persistentError);

      const promise = service.generate('test');

      // Total attempts = 1 (initial) + 3 (retries) = 4
      // Delays: 100ms, 200ms, 400ms
      await jest.advanceTimersByTimeAsync(100 + 200 + 400);

      await expect(promise).rejects.toThrow(persistentError);
      expect(mockApiCreate).toHaveBeenCalledTimes(4);
    });
  });

  // --- Test Suite for Token Usage Tracking ---
  describe('Token Usage Tracking', () => {
    let service: ClaudeApiService;

    beforeEach(() => {
      process.env.ANTHROPIC_API_KEY = mockApiKey;
      const tokenTracker = new TokenTracker();
      service = new ClaudeApiService(tokenTracker);
    });

    it('should call the token tracker with correct usage data on success', async () => {
      mockApiCreate.mockResolvedValue(mockSuccessResponse);
      await service.generate('test');

      expect(mockTokenTrack).toHaveBeenCalledTimes(1);
      expect(mockTokenTrack).toHaveBeenCalledWith(
        mockSuccessResponse.usage.input_tokens,
        mockSuccessResponse.usage.output_tokens
      );
    });

    it('should not call the token tracker if the API call fails completely', async () => {
      const error = new APIError(400, 'Bad Request');
      mockApiCreate.mockRejectedValue(error);

      await expect(service.generate('test')).rejects.toThrow(error);
      expect(mockTokenTrack).not.toHaveBeenCalled();
    });

    it('should not call the token tracker during failed retry attempts', async () => {
      const rateLimitError = new APIError(429, 'Rate limit exceeded');
      mockApiCreate
        .mockRejectedValueOnce(rateLimitError)
        .mockResolvedValueOnce(mockSuccessResponse);

      const promise = service.generate('test');
      await jest.advanceTimersByTimeAsync(100);
      await promise;

      // Should only be called once for the final successful call
      expect(mockTokenTrack).toHaveBeenCalledTimes(1);
    });
  });
});