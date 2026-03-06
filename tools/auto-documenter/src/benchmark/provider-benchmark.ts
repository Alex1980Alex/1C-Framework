/**
 * Provider Benchmark - Measure AI provider performance
 * @module benchmark/provider-benchmark
 */

import { BenchmarkRunner, BenchmarkConfig, BenchmarkResult, BenchmarkSuite } from './runner.js';

/**
 * Provider types
 */
export type Provider = 'gemini' | 'groq' | 'ollama' | 'grok' | 'openrouter';

/**
 * Provider benchmark configuration
 */
export interface ProviderBenchmarkConfig {
  /** Provider to benchmark */
  provider: Provider;
  /** Model to use */
  model?: string;
  /** API key (if required) */
  apiKey?: string;
  /** Number of iterations */
  iterations?: number;
  /** Prompt to use */
  prompt?: string;
  /** Maximum tokens in response */
  maxTokens?: number;
}

/**
 * Provider benchmark result with additional metrics
 */
export type ProviderBenchmarkResult = BenchmarkResult;

/**
 * Default models for each provider
 */
const DEFAULT_MODELS: Record<Provider, string> = {
  gemini: 'gemini-2.5-flash-lite',  // Fast and free
  groq: 'llama-3.3-70b-versatile',
  ollama: 'gpt-oss:120b-cloud',  // Available locally
  grok: 'grok-2-1212',
  openrouter: 'google/gemini-2.5-flash-lite'  // Cheap via OpenRouter
};

/**
 * Test prompts of varying complexity
 */
const TEST_PROMPTS = {
  simple: 'Explain what a function is in one sentence.',
  medium: 'Document this code: function add(a, b) { return a + b; }',
  complex: `Analyze this code and provide documentation:
    class UserService {
      constructor(db) { this.db = db; }
      async getUser(id) { return await this.db.users.findOne({ id }); }
      async createUser(data) { return await this.db.users.insert(data); }
    }`
};

/**
 * Provider Benchmark class
 */
export class ProviderBenchmark {
  private runner: BenchmarkRunner;

  constructor() {
    this.runner = new BenchmarkRunner();
  }

  /**
   * Make API call to provider
   */
  private async callProvider(
    provider: Provider,
    model: string,
    prompt: string,
    apiKey?: string,
    maxTokens: number = 500
  ): Promise<{ response: string; tokens: number; latency: number }> {
    const startTime = performance.now();

    try {
      let response: string;
      let tokens: number = 0;

      switch (provider) {
        case 'gemini':
          const geminiResult = await this.callGemini(prompt, model, apiKey, maxTokens);
          response = geminiResult.response;
          tokens = geminiResult.tokens;
          break;

        case 'groq':
          const groqResult = await this.callGroq(prompt, model, apiKey, maxTokens);
          response = groqResult.response;
          tokens = groqResult.tokens;
          break;

        case 'ollama':
          const ollamaResult = await this.callOllama(prompt, model, maxTokens);
          response = ollamaResult.response;
          tokens = ollamaResult.tokens;
          break;

        case 'grok':
          const grokResult = await this.callGrok(prompt, model, apiKey, maxTokens);
          response = grokResult.response;
          tokens = grokResult.tokens;
          break;

        case 'openrouter':
          const orResult = await this.callOpenRouter(prompt, model, apiKey, maxTokens);
          response = orResult.response;
          tokens = orResult.tokens;
          break;

        default:
          throw new Error(`Unknown provider: ${provider}`);
      }

      const latency = performance.now() - startTime;
      return { response, tokens, latency };
    } catch (error: any) {
      const latency = performance.now() - startTime;
      throw new Error(`Provider ${provider} failed after ${latency.toFixed(0)}ms: ${error.message}`);
    }
  }

  /**
   * Call Gemini API
   */
  private async callGemini(
    prompt: string,
    model: string,
    apiKey?: string,
    maxTokens: number = 500
  ): Promise<{ response: string; tokens: number }> {
    const key = apiKey || process.env.GEMINI_API_KEY;
    if (!key) throw new Error('GEMINI_API_KEY not set');

    const response = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${key}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contents: [{ parts: [{ text: prompt }] }],
          generationConfig: { maxOutputTokens: maxTokens }
        })
      }
    );

    if (!response.ok) {
      throw new Error(`Gemini API error: ${response.status}`);
    }

    const data = await response.json();
    const text = data.candidates?.[0]?.content?.parts?.[0]?.text || '';
    const tokens = data.usageMetadata?.totalTokenCount || text.length / 4;

    return { response: text, tokens };
  }

  /**
   * Call Groq API
   */
  private async callGroq(
    prompt: string,
    model: string,
    apiKey?: string,
    maxTokens: number = 500
  ): Promise<{ response: string; tokens: number }> {
    const key = apiKey || process.env.GROQ_API_KEY;
    if (!key) throw new Error('GROQ_API_KEY not set');

    const response = await fetch('https://api.groq.com/openai/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${key}`
      },
      body: JSON.stringify({
        model,
        messages: [{ role: 'user', content: prompt }],
        max_tokens: maxTokens
      })
    });

    if (!response.ok) {
      throw new Error(`Groq API error: ${response.status}`);
    }

    const data = await response.json();
    const text = data.choices?.[0]?.message?.content || '';
    const tokens = data.usage?.total_tokens || text.length / 4;

    return { response: text, tokens };
  }

  /**
   * Call Ollama API
   */
  private async callOllama(
    prompt: string,
    model: string,
    maxTokens: number = 500
  ): Promise<{ response: string; tokens: number }> {
    const baseUrl = process.env.OLLAMA_BASE_URL || 'http://localhost:11434';

    const response = await fetch(`${baseUrl}/api/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model,
        prompt,
        stream: false,
        options: { num_predict: maxTokens }
      })
    });

    if (!response.ok) {
      throw new Error(`Ollama API error: ${response.status}`);
    }

    const data = await response.json();
    const text = data.response || '';
    const tokens = data.eval_count || text.length / 4;

    return { response: text, tokens };
  }

  /**
   * Call Grok API
   */
  private async callGrok(
    prompt: string,
    model: string,
    apiKey?: string,
    maxTokens: number = 500
  ): Promise<{ response: string; tokens: number }> {
    const key = apiKey || process.env.XAI_API_KEY;
    if (!key) throw new Error('XAI_API_KEY not set');

    const response = await fetch('https://api.x.ai/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${key}`
      },
      body: JSON.stringify({
        model,
        messages: [{ role: 'user', content: prompt }],
        max_tokens: maxTokens
      })
    });

    if (!response.ok) {
      throw new Error(`Grok API error: ${response.status}`);
    }

    const data = await response.json();
    const text = data.choices?.[0]?.message?.content || '';
    const tokens = data.usage?.total_tokens || text.length / 4;

    return { response: text, tokens };
  }

  /**
   * Call OpenRouter API
   */
  private async callOpenRouter(
    prompt: string,
    model: string,
    apiKey?: string,
    maxTokens: number = 500
  ): Promise<{ response: string; tokens: number }> {
    const key = apiKey || process.env.OPENROUTER_API_KEY;
    if (!key) throw new Error('OPENROUTER_API_KEY not set');

    const response = await fetch('https://openrouter.ai/api/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${key}`
      },
      body: JSON.stringify({
        model,
        messages: [{ role: 'user', content: prompt }],
        max_tokens: maxTokens
      })
    });

    if (!response.ok) {
      throw new Error(`OpenRouter API error: ${response.status}`);
    }

    const data = await response.json();
    const text = data.choices?.[0]?.message?.content || '';
    const tokens = data.usage?.total_tokens || text.length / 4;

    return { response: text, tokens };
  }

  /**
   * Run provider benchmark
   */
  async runProviderBenchmark(config: ProviderBenchmarkConfig): Promise<ProviderBenchmarkResult> {
    const {
      provider,
      model = DEFAULT_MODELS[provider],
      apiKey,
      iterations = 3,
      prompt = TEST_PROMPTS.medium,
      maxTokens = 500
    } = config;

    const responseTimes: number[] = [];
    const tokenCounts: number[] = [];
    const errors: string[] = [];
    let successCount = 0;

    const benchmarkConfig: BenchmarkConfig = {
      name: `Provider: ${provider} (${model})`,
      fn: async () => {
        try {
          const result = await this.callProvider(provider, model, prompt, apiKey, maxTokens);
          responseTimes.push(result.latency);
          tokenCounts.push(result.tokens);
          successCount++;
        } catch (error: any) {
          errors.push(error.message);
        }
      },
      iterations,
      warmupIterations: 0 // No warmup for API calls (costs money)
    };

    const result = await this.runner.run(benchmarkConfig);

    const avgResponseTime = responseTimes.length > 0
      ? responseTimes.reduce((a, b) => a + b, 0) / responseTimes.length
      : 0;

    const avgTokens = tokenCounts.length > 0
      ? tokenCounts.reduce((a, b) => a + b, 0) / tokenCounts.length
      : 0;

    const enhancedResult: ProviderBenchmarkResult = {
      ...result,
      success: successCount > 0,
      metrics: {
        ...result.metrics,
        provider,
        model,
        avgResponseTime,
        tokensPerSecond: avgTokens / (avgResponseTime / 1000) || 0,
        successRate: (successCount / iterations) * 100,
        errors
      }
    };

    return enhancedResult;
  }

  /**
   * Run comparison benchmark across all available providers
   */
  async runComparisonBenchmark(
    prompt: string = TEST_PROMPTS.medium,
    iterations: number = 3
  ): Promise<BenchmarkSuite> {
    const suite: BenchmarkSuite = {
      name: 'Provider Comparison',
      description: 'Compare response times across providers',
      benchmarks: []
    };

    const results: BenchmarkResult[] = [];
    const providers: Provider[] = ['gemini', 'groq', 'ollama', 'grok', 'openrouter'];

    for (const provider of providers) {
      try {
        const result = await this.runProviderBenchmark({
          provider,
          iterations,
          prompt
        });
        results.push(result);
      } catch (error: any) {
        // Provider not configured, skip
        results.push({
          name: `Provider: ${provider}`,
          duration: 0,
          memoryUsed: 0,
          operations: 0,
          opsPerSecond: 0,
          metrics: { error: error.message },
          timestamp: new Date(),
          success: false,
          error: error.message
        });
      }
    }

    suite.results = results;
    return suite;
  }

  /**
   * Run latency benchmark with different prompt sizes
   */
  async runLatencyBenchmark(provider: Provider): Promise<BenchmarkSuite> {
    const suite: BenchmarkSuite = {
      name: `Latency Benchmark: ${provider}`,
      description: 'Measure latency with different prompt sizes',
      benchmarks: []
    };

    const results: BenchmarkResult[] = [];

    for (const [name, prompt] of Object.entries(TEST_PROMPTS)) {
      try {
        const result = await this.runProviderBenchmark({
          provider,
          prompt,
          iterations: 3
        });
        result.name = `${provider} - ${name}`;
        results.push(result);
      } catch (error: any) {
        results.push({
          name: `${provider} - ${name}`,
          duration: 0,
          memoryUsed: 0,
          operations: 0,
          opsPerSecond: 0,
          metrics: {},
          timestamp: new Date(),
          success: false,
          error: error.message
        });
      }
    }

    suite.results = results;
    return suite;
  }

  /**
   * Get benchmark results
   */
  getResults(): BenchmarkResult[] {
    return this.runner.getResults();
  }
}
