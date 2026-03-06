import axios, { AxiosError } from 'axios';
import { spawn, execSync } from 'child_process';
import { platform } from 'os';
import { DEFAULT_OLLAMA_CONFIG, getAvailableOllamaModels, getModelInfo } from './local-llm-config.js';

/**
 * Ollama server status
 */
export interface OllamaStatus {
  available: boolean;
  version?: string;
  models: string[];
  error?: string;
}

/**
 * Model pull progress
 */
export interface PullProgress {
  status: string;
  digest?: string;
  total?: number;
  completed?: number;
}

/**
 * Check if Ollama server is running
 * @param baseURL Ollama server URL (default: http://localhost:11434)
 * @returns Ollama status
 */
export async function checkOllamaAvailability(
  baseURL: string = DEFAULT_OLLAMA_CONFIG.baseURL
): Promise<OllamaStatus> {
  try {
    // Try to get Ollama version
    const versionResponse = await axios.get(`${baseURL}/api/version`, {
      timeout: 5000,
    });

    // List available models
    const modelsResponse = await axios.get(`${baseURL}/api/tags`, {
      timeout: 5000,
    });

    const models = modelsResponse.data.models?.map((m: any) => m.name) || [];

    return {
      available: true,
      version: versionResponse.data.version,
      models,
    };
  } catch (error: any) {
    const axiosError = error as AxiosError;

    if (axiosError.code === 'ECONNREFUSED') {
      return {
        available: false,
        models: [],
        error: 'Ollama server is not running. Start with: ollama serve',
      };
    }

    return {
      available: false,
      models: [],
      error: `Failed to connect to Ollama: ${error.message}`,
    };
  }
}

/**
 * Check if a specific model is available locally
 * @param modelName Model name to check
 * @param baseURL Ollama server URL
 * @returns True if model is available
 */
export async function isModelAvailable(
  modelName: string,
  baseURL: string = DEFAULT_OLLAMA_CONFIG.baseURL
): Promise<boolean> {
  const status = await checkOllamaAvailability(baseURL);
  return status.available && status.models.includes(modelName);
}

/**
 * Pull a model from Ollama registry
 * @param modelName Model name to pull
 * @param baseURL Ollama server URL
 * @param onProgress Progress callback
 */
export async function pullModel(
  modelName: string,
  baseURL: string = DEFAULT_OLLAMA_CONFIG.baseURL,
  onProgress?: (progress: PullProgress) => void
): Promise<void> {
  try {
    const response = await axios.post(
      `${baseURL}/api/pull`,
      { name: modelName },
      {
        timeout: 3600000, // 1 hour for large models
        responseType: 'stream',
      }
    );

    // Parse streaming response
    return new Promise((resolve, reject) => {
      let buffer = '';

      response.data.on('data', (chunk: Buffer) => {
        buffer += chunk.toString();
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.trim()) {
            try {
              const progress = JSON.parse(line);
              if (onProgress) {
                onProgress(progress);
              }

              if (progress.status === 'success') {
                resolve();
              }
            } catch (parseError) {
              // Ignore JSON parse errors
            }
          }
        }
      });

      response.data.on('end', () => {
        resolve();
      });

      response.data.on('error', (error: Error) => {
        reject(error);
      });
    });
  } catch (error: any) {
    throw new Error(`Failed to pull model ${modelName}: ${error.message}`);
  }
}

/**
 * Ensure a model is available, pull if needed
 * @param modelName Model name
 * @param baseURL Ollama server URL
 * @param autoPull Automatically pull if not available (default: true)
 * @returns True if model is ready
 */
export async function ensureModelAvailable(
  modelName: string,
  baseURL: string = DEFAULT_OLLAMA_CONFIG.baseURL,
  autoPull: boolean = true
): Promise<boolean> {
  // Check if model is already available
  const available = await isModelAvailable(modelName, baseURL);
  if (available) {
    console.error(`✅ Model ${modelName} is already available`);
    return true;
  }

  if (!autoPull) {
    console.error(`❌ Model ${modelName} is not available`);
    console.error(`   Run: ollama pull ${modelName}`);
    return false;
  }

  // Pull model
  console.error(`📥 Pulling model ${modelName}...`);
  console.error(`   This may take several minutes depending on model size`);

  await pullModel(modelName, baseURL, (progress) => {
    if (progress.status === 'downloading') {
      const percent = progress.completed && progress.total
        ? Math.round((progress.completed / progress.total) * 100)
        : 0;
      process.stderr.write(`\r   Progress: ${percent}%`);
    } else if (progress.status === 'verifying') {
      process.stderr.write('\r   Verifying...         ');
    } else if (progress.status === 'success') {
      process.stderr.write('\r✅ Model pulled successfully!\n');
    }
  });

  return true;
}

/**
 * Get recommended setup instructions
 * @param includeInstall Include Ollama installation instructions
 */
export function getSetupInstructions(includeInstall: boolean = true): string {
  let instructions = '\n🚀 Ollama Local LLM Setup Guide\n\n';

  if (includeInstall) {
    instructions += '1. Install Ollama:\n';
    instructions += '   • Windows/Mac: Download from https://ollama.com/download\n';
    instructions += '   • Linux: curl -fsSL https://ollama.com/install.sh | sh\n\n';
  }

  instructions += '2. Start Ollama server:\n';
  instructions += '   ollama serve\n\n';

  instructions += '3. Pull recommended model:\n';
  instructions += '   ollama pull qwen2.5-coder:14b  # Balanced (recommended)\n';
  instructions += '   # OR\n';
  instructions += '   ollama pull qwen2.5-coder:7b   # Fast alternative\n\n';

  instructions += '4. Configure Auto-Documenter:\n';
  instructions += '   export ENABLE_ROTATION=true\n';
  instructions += '   export PRIMARY_PROVIDER=ollama\n';
  instructions += '   export OLLAMA_MODEL=qwen2.5-coder:14b\n\n';

  instructions += '5. Test the setup:\n';
  instructions += '   node build/test-ollama.js\n\n';

  instructions += '💡 Benefits of Local LLM:\n';
  instructions += '   • Free unlimited usage\n';
  instructions += '   • Full privacy (no data sent to cloud)\n';
  instructions += '   • Faster for small models\n';
  instructions += '   • Works offline\n\n';

  return instructions;
}

/**
 * Print diagnostic information about Ollama setup
 */
export async function printDiagnostics(
  baseURL: string = DEFAULT_OLLAMA_CONFIG.baseURL
): Promise<void> {
  console.error('\n🔍 Ollama Diagnostics\n');
  console.error(`Server URL: ${baseURL}`);

  const status = await checkOllamaAvailability(baseURL);

  if (!status.available) {
    console.error(`\n❌ Status: NOT AVAILABLE`);
    console.error(`Error: ${status.error}\n`);
    console.error(getSetupInstructions());
    return;
  }

  console.error(`\n✅ Status: AVAILABLE`);
  console.error(`Version: ${status.version}`);
  console.error(`\nInstalled models (${status.models.length}):`);

  if (status.models.length === 0) {
    console.error('   (none)\n');
    console.error('💡 Install a recommended model:');
    console.error('   ollama pull qwen2.5-coder:14b\n');
  } else {
    for (const modelName of status.models) {
      const info = getModelInfo(modelName);
      if (info) {
        console.error(`   ✅ ${modelName} - ${info.description}`);
      } else {
        console.error(`   • ${modelName}`);
      }
    }
    console.error('');
  }

  // Check for recommended models
  const recommendedModels = [
    'qwen2.5-coder:14b',
    'qwen2.5-coder:7b',
    'codellama:13b',
  ];

  const missing = recommendedModels.filter(
    (m) => !status.models.includes(m)
  );

  if (missing.length > 0) {
    console.error('📋 Recommended models not yet installed:');
    for (const modelName of missing) {
      const info = getModelInfo(modelName);
      console.error(`   • ${modelName}`);
      if (info) {
        console.error(`     ${info.description}`);
        console.error(`     Install: ollama pull ${modelName}`);
      }
    }
    console.error('');
  }
}

/**
 * Test Ollama inference with a simple prompt
 * @param modelName Model to test
 * @param baseURL Ollama server URL
 */
export async function testInference(
  modelName: string,
  baseURL: string = DEFAULT_OLLAMA_CONFIG.baseURL
): Promise<{ success: boolean; response?: string; error?: string; timeMs?: number }> {
  try {
    const startTime = Date.now();

    const response = await axios.post(
      `${baseURL}/api/generate`,
      {
        model: modelName,
        prompt: 'Write a one-sentence description of what documentation is.',
        stream: false,
      },
      {
        timeout: 60000,
      }
    );

    const timeMs = Date.now() - startTime;

    return {
      success: true,
      response: response.data.response,
      timeMs,
    };
  } catch (error: any) {
    return {
      success: false,
      error: error.message,
    };
  }
}

/**
 * Start Ollama server if not running
 * @param baseURL Ollama server URL
 * @returns True if server started or already running
 */
export async function startOllama(
  baseURL: string = DEFAULT_OLLAMA_CONFIG.baseURL
): Promise<boolean> {
  // Check if already running
  const status = await checkOllamaAvailability(baseURL);
  if (status.available) {
    console.error('✅ Ollama server is already running');
    return true;
  }

  console.error('⚠️ Ollama server not running, attempting to start...');

  try {
    const currentPlatform = platform();

    if (currentPlatform === 'win32') {
      // Windows: check if ollama is installed
      try {
        execSync('where ollama', { stdio: 'pipe' });
      } catch {
        console.error('❌ Ollama not installed. Download from https://ollama.ai');
        return false;
      }

      // Start ollama serve in background (Windows)
      spawn('ollama', ['serve'], {
        detached: true,
        stdio: 'ignore',
        windowsHide: true,
      }).unref();

      console.error('🚀 Started ollama serve (Windows)');

    } else if (currentPlatform === 'linux') {
      // Linux: try systemctl first, then direct
      try {
        execSync('systemctl start ollama', { stdio: 'pipe' });
        console.error('🚀 Started Ollama via systemctl');
      } catch {
        // Fallback to direct start
        spawn('ollama', ['serve'], {
          detached: true,
          stdio: 'ignore',
        }).unref();
        console.error('🚀 Started ollama serve (Linux)');
      }

    } else if (currentPlatform === 'darwin') {
      // macOS: direct start
      spawn('ollama', ['serve'], {
        detached: true,
        stdio: 'ignore',
      }).unref();
      console.error('🚀 Started ollama serve (macOS)');

    } else {
      console.error(`❌ Unsupported platform: ${currentPlatform}`);
      return false;
    }

    // Wait for server to start (up to 10 seconds)
    for (let i = 0; i < 5; i++) {
      await new Promise(resolve => setTimeout(resolve, 2000));
      const checkStatus = await checkOllamaAvailability(baseURL);
      if (checkStatus.available) {
        console.error('✅ Ollama server started successfully');
        return true;
      }
      console.error(`   Waiting for Ollama to start... (${i + 1}/5)`);
    }

    console.error('❌ Ollama server did not start in time');
    return false;

  } catch (error: any) {
    console.error(`❌ Failed to start Ollama: ${error.message}`);
    return false;
  }
}

/**
 * Check LLM Rotation HTTP server availability
 * @param rotationURL LLM Rotation server URL (default: http://localhost:8000)
 * @returns Status object
 */
export async function checkRotationAvailability(
  rotationURL: string = 'http://localhost:8000'
): Promise<{ available: boolean; providers?: number; error?: string }> {
  try {
    const response = await axios.get(`${rotationURL}/health`, {
      timeout: 5000,
    });

    if (response.status === 200) {
      const providers = response.data?.providers?.available || 0;
      return {
        available: true,
        providers,
      };
    }

    return {
      available: false,
      error: `HTTP ${response.status}`,
    };
  } catch (error: any) {
    return {
      available: false,
      error: error.message,
    };
  }
}

/**
 * Ensure either LLM Rotation or Ollama is available
 * @param rotationURL LLM Rotation server URL
 * @param ollamaURL Ollama server URL
 * @returns Object with available provider info
 */
export async function ensureProviderAvailable(
  rotationURL: string = 'http://localhost:8000',
  ollamaURL: string = DEFAULT_OLLAMA_CONFIG.baseURL
): Promise<{ provider: 'rotation' | 'ollama' | null; url: string | null; error?: string }> {
  // Try LLM Rotation first (primary)
  const rotationStatus = await checkRotationAvailability(rotationURL);
  if (rotationStatus.available) {
    console.error(`✅ LLM Rotation HTTP available (${rotationStatus.providers} providers)`);
    return { provider: 'rotation', url: rotationURL };
  }

  console.error('⚠️ LLM Rotation HTTP not available, trying Ollama fallback...');

  // Try Ollama (fallback)
  const ollamaStatus = await checkOllamaAvailability(ollamaURL);
  if (ollamaStatus.available) {
    console.error(`✅ Ollama available (${ollamaStatus.models.length} models)`);
    return { provider: 'ollama', url: ollamaURL };
  }

  // Try to start Ollama
  const started = await startOllama(ollamaURL);
  if (started) {
    return { provider: 'ollama', url: ollamaURL };
  }

  return {
    provider: null,
    url: null,
    error: 'No LLM provider available. Start LLM Rotation HTTP or Ollama.',
  };
}
