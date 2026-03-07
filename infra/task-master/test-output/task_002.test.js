/**
 * @file Jest test suite for the CLI Foundation (Task 2).
 * @description This file contains comprehensive tests for the basic CLI structure,
 * including command parsing, global options, help documentation, and the logging system.
 * It uses Jest's mocking capabilities to isolate the CLI logic from external
 * dependencies like the file system and to capture console output.
 */

import { run } from '../src/cli'; // Assuming the main CLI entry point is in 'src/cli.ts'
import { getLogger } from '../src/logger'; // Assuming a logger module
import * as packageJson from '../package.json'; // To get the version for testing

// Mock the logger module to control its behavior and spy on its methods
jest.mock('../src/logger', () => {
  const originalLogger = jest.requireActual('../src/logger');
  // We create a single, mutable logger instance that tests can configure.
  const mockLogger = originalLogger.createLogger({ level: 'info' });
  return {
    __esModule: true,
    // Allow tests to reconfigure the logger on the fly
    getLogger: jest.fn(() => mockLogger),
    // Expose the mock logger instance for direct manipulation in tests
    mockLoggerInstance: mockLogger,
  };
});

// Mock the 'fs' module to simulate file system operations without touching the actual disk.
jest.mock('fs');

// Type assertion for the mocked logger to access the mock instance
const { mockLoggerInstance } = jest.requireActual('../src/logger');

describe('CLI Foundation (Task 2)', () => {
  // Spies to capture console output and process exit calls
  let consoleLogSpy: jest.SpyInstance;
  let consoleErrorSpy: jest.SpyInstance;
  let processExitSpy: jest.SpyInstance;

  /**
   * A helper function to execute the CLI command with specified arguments.
   * It simulates `process.argv` and wraps the execution to catch `process.exit`.
   * @param {string[]} args - The arguments to pass to the CLI, e.g., ['--help'].
   * @returns {Promise<void>} A promise that resolves after the command has been executed.
   */
  const executeCli = async (args: string[]): Promise<void> => {
    // Prepend standard argv elements
    const argv = ['node', 'cli.js', ...args];
    try {
      await run(argv);
    } catch (error) {
      // Commander's exit behavior is mocked to throw an error.
      // We can safely ignore it as it's expected.
      const e = error as Error;
      if (e.message !== 'process.exit called') {
        throw error; // Re-throw unexpected errors
      }
    }
  };

  beforeEach(() => {
    // Reset mocks before each test to ensure isolation
    jest.clearAllMocks();

    // Spy on console methods to capture output
    consoleLogSpy = jest.spyOn(console, 'log').mockImplementation(() => {});
    consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

    // Mock process.exit to prevent tests from terminating prematurely.
    // Commander.js calls process.exit for --help, --version, and errors.
    processExitSpy = jest.spyOn(process, 'exit').mockImplementation((code?: number) => {
      throw new Error('process.exit called');
    });

    // Spy on logger methods to verify logging behavior
    jest.spyOn(mockLoggerInstance, 'info').mockImplementation(() => {});
    jest.spyOn(mockLoggerInstance, 'debug').mockImplementation(() => {});
    jest.spyOn(mockLoggerInstance, 'warn').mockImplementation(() => {});
    jest.spyOn(mockLoggerInstance, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    // Restore all mocked functions to their original implementations
    jest.restoreAllMocks();
  });

  describe('Global Options', () => {
    it('should display the version number and exit when --version is used', async () => {
      await executeCli(['--version']);
      expect(consoleLogSpy).toHaveBeenCalledWith(packageJson.version);
      expect(processExitSpy).toHaveBeenCalledWith(0);
    });

    it('should display help documentation and exit when --help is used', async () => {
      await executeCli(['--help']);
      const output = consoleLogSpy.mock.calls[0][0];

      // Check for key sections in the help output
      expect(output).toMatch(/Usage: cli\.js \[command\] \[options\]/);
      expect(output).toMatch(/Options:/);
      expect(output).toMatch(/Commands:/);

      // Check for presence of all global options
      expect(output).toMatch(/--version/);
      expect(output).toMatch(/--help/);
      expect(output).toMatch(/--file <path>/);
      expect(output).toMatch(/--quiet/);
      expect(output).toMatch(/--debug/);
      expect(output).toMatch(/--json/);

      expect(processExitSpy).toHaveBeenCalledWith(0);
    });

    it('should correctly parse the --file option', async () => {
      // This test assumes a command 'check' exists that uses the file option.
      // The CLI implementation should pass this option to the command's action.
      const filePath = 'config/test.json';
      await executeCli(['check', '--file', filePath]);

      // We can't directly check Commander's internal state, so we verify
      // the side effect. Here, we assume the logger would log the file being used.
      // This is a stand-in for a real action.
      expect(mockLoggerInstance.info).toHaveBeenCalledWith(
        expect.stringContaining(`Using file: ${filePath}`),
      );
    });

    it('should handle unknown commands gracefully', async () => {
      await executeCli(['non-existent-command']);
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        expect.stringContaining("error: unknown command 'non-existent-command'"),
      );
      expect(processExitSpy).toHaveBeenCalledWith(1);
    });
  });

  describe('Logging System', () => {
    beforeEach(() => {
      // Reset logger level before each logging test
      mockLoggerInstance.level = 'info';
    });

    it('should default to the "info" logging level', async () => {
      await executeCli(['check']); // A dummy command that logs at all levels

      expect(mockLoggerInstance.debug).not.toHaveBeenCalled();
      expect(mockLoggerInstance.info).toHaveBeenCalled();
      expect(mockLoggerInstance.warn).toHaveBeenCalled();
      expect(mockLoggerInstance.error).toHaveBeenCalled();
    });

    it('should set logging level to "debug" when --debug is used', async () => {
      await executeCli(['--debug', 'check']);

      // The CLI setup should reconfigure the logger based on the option
      expect(getLogger().level).toBe('debug');

      // With debug level, all logs should be visible
      expect(mockLoggerInstance.debug).toHaveBeenCalled();
      expect(mockLoggerInstance.info).toHaveBeenCalled();
      expect(mockLoggerInstance.warn).toHaveBeenCalled();
      expect(mockLoggerInstance.error).toHaveBeenCalled();
    });

    it('should set logging level to "silent" when --quiet is used', async () => {
      await executeCli(['--quiet', 'check']);

      expect(getLogger().level).toBe('silent');

      // With quiet/silent, no logs should be visible (often errors are still shown on stderr, but the logger itself is silenced)
      expect(mockLoggerInstance.debug).not.toHaveBeenCalled();
      expect(mockLoggerInstance.info).not.toHaveBeenCalled();
      expect(mockLoggerInstance.warn).not.toHaveBeenCalled();
      // Errors might still be logged depending on implementation, but a "silent" logger typically silences all.
      expect(mockLoggerInstance.error).not.toHaveBeenCalled();
    });

    it('should prioritize --debug over --quiet if both are provided', async () => {
      await executeCli(['--debug', '--quiet', 'check']);
      expect(getLogger().level).toBe('debug');
      expect(mockLoggerInstance.debug).toHaveBeenCalled();
    });
  });

  describe('Command Parsing and Execution', () => {
    // Assuming a simple 'check' command exists for demonstration
    it('should execute a known command with its action', async () => {
      await executeCli(['check']);
      expect(mockLoggerInstance.info).toHaveBeenCalledWith(
        'Executing check command...',
      );
      expect(mockLoggerInstance.info).toHaveBeenCalledWith(
        'Check command finished.',
      );
    });

    it('should parse command-specific options correctly', async () => {
      await executeCli(['check', '--mode', 'strict']);
      expect(mockLoggerInstance.info).toHaveBeenCalledWith(
        'Check command running in strict mode.',
      );
    });

    it('should show an error for missing required arguments for a command', async () => {
      // Assuming a command `greet <name>` exists
      await executeCli(['greet']);
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        expect.stringContaining("error: missing required argument 'name'"),
      );
      expect(processExitSpy).toHaveBeenCalledWith(1);
    });

    it('should correctly parse required arguments for a command', async () => {
      await executeCli(['greet', 'World']);
      expect(mockLoggerInstance.info).toHaveBeenCalledWith('Hello, World');
    });
  });

  describe('JSON Output Mode', () => {
    it('should produce valid JSON output when --json is used', async () => {
      await executeCli(['check', '--json']);

      // The action for the 'check' command should call console.log with a JSON string
      expect(consoleLogSpy).toHaveBeenCalledTimes(1);
      const output = consoleLogSpy.mock.calls[0][0];

      let parsedOutput;
      expect(() => {
        parsedOutput = JSON.parse(output);
      }).not.toThrow();

      expect(parsedOutput).toEqual({
        status: 'success',
        command: 'check',
        details: 'Check command finished.',
      });
    });

    it('should not produce regular log messages when --json is active', async () => {
      await executeCli(['check', '--json']);

      // Logger methods should not be called directly for output,
      // as all output is channeled into the final JSON object.
      expect(mockLoggerInstance.info).not.toHaveBeenCalled();
      expect(mockLoggerInstance.warn).not.toHaveBeenCalled();
      expect(mockLoggerInstance.debug).not.toHaveBeenCalled();
    });

    it('should produce a JSON error object on failure', async () => {
      // Assuming the 'greet' command fails if no name is provided
      await executeCli(['greet', '--json']);

      expect(consoleErrorSpy).toHaveBeenCalledTimes(1);
      const output = consoleErrorSpy.mock.calls[0][0];

      let parsedOutput;
      expect(() => {
        parsedOutput = JSON.parse(output);
      }).not.toThrow();

      expect(parsedOutput).toEqual({
        status: 'error',
        message: "Missing required argument 'name'",
      });
      expect(processExitSpy).toHaveBeenCalledWith(1);
    });
  });
});