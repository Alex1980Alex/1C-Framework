#!/usr/bin/env node

/**
 * Test Runner for Task Master MCP Server E2E Tests
 * Orchestrates all test suites and provides unified reporting
 */

import { runAllTests } from './example-server-tests.js';
import { runIntegrationTests } from './integration-tests.js';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * Configuration for test execution
 */
const TEST_CONFIG = {
  // Test execution order
  suites: [
    {
      name: 'Basic Server Tests',
      runner: runAllTests,
      description: 'Fundamental server functionality and API tests',
      required: true
    },
    {
      name: 'Integration Tests',
      runner: runIntegrationTests,
      description: 'Advanced integration and performance tests',
      required: false
    }
  ],

  // Global settings
  settings: {
    continueOnFailure: false,
    generateReport: true,
    verbose: true
  }
};

/**
 * Test Result Aggregator
 */
class TestResultAggregator {
  constructor() {
    this.results = [];
    this.startTime = Date.now();
  }

  addResult(suiteName, success, duration, details = null) {
    this.results.push({
      suiteName,
      success,
      duration,
      details,
      timestamp: Date.now()
    });
  }

  getOverallResults() {
    const totalDuration = Date.now() - this.startTime;
    const totalSuites = this.results.length;
    const passedSuites = this.results.filter(r => r.success).length;
    const failedSuites = totalSuites - passedSuites;

    return {
      totalDuration,
      totalSuites,
      passedSuites,
      failedSuites,
      overallSuccess: failedSuites === 0,
      results: this.results
    };
  }

  generateReport() {
    const overall = this.getOverallResults();

    console.log('\n' + '═'.repeat(100));
    console.log('📋 COMPREHENSIVE TEST EXECUTION REPORT');
    console.log('═'.repeat(100));

    console.log(`\n🕐 Execution Summary:`);
    console.log(`   Total Duration: ${Math.round(overall.totalDuration / 1000)}s`);
    console.log(`   Test Suites: ${overall.totalSuites}`);
    console.log(`   ✅ Passed: ${overall.passedSuites}`);
    console.log(`   ❌ Failed: ${overall.failedSuites}`);
    console.log(`   📊 Success Rate: ${Math.round((overall.passedSuites / overall.totalSuites) * 100)}%`);

    console.log(`\n📝 Suite Details:`);
    this.results.forEach((result, index) => {
      const status = result.success ? '✅' : '❌';
      const duration = Math.round(result.duration / 1000);
      console.log(`   ${index + 1}. ${status} ${result.suiteName} (${duration}s)`);

      if (result.details && !result.success) {
        console.log(`      ⚠️  ${result.details}`);
      }
    });

    if (overall.overallSuccess) {
      console.log('\n🎉 ALL TEST SUITES PASSED SUCCESSFULLY!');
      console.log('\n✨ The Task Master MCP Server E2E Test Framework is fully validated and ready for use.');
    } else {
      console.log('\n💥 SOME TEST SUITES FAILED');
      console.log('\n🔍 Please review the failed test suites above and address any issues.');
    }

    console.log('\n' + '═'.repeat(100));

    return overall;
  }
}

/**
 * Enhanced test runner with error handling and reporting
 */
async function runTestSuite(suite, aggregator) {
  console.log(`\n🚀 Starting: ${suite.name}`);
  console.log(`   ${suite.description}`);
  console.log(`   Required: ${suite.required ? 'Yes' : 'No'}`);
  console.log('   ' + '─'.repeat(80));

  const startTime = Date.now();

  try {
    await suite.runner();
    const duration = Date.now() - startTime;

    aggregator.addResult(suite.name, true, duration);
    console.log(`\n✅ ${suite.name} completed successfully in ${Math.round(duration / 1000)}s`);

    return true;

  } catch (error) {
    const duration = Date.now() - startTime;
    const errorMessage = error.message || 'Unknown error';

    aggregator.addResult(suite.name, false, duration, errorMessage);
    console.error(`\n❌ ${suite.name} failed after ${Math.round(duration / 1000)}s:`);
    console.error(`   Error: ${errorMessage}`);

    if (suite.required) {
      console.error(`   ⚠️  This is a required test suite - execution may be halted`);
    }

    return false;
  }
}

/**
 * Pre-execution environment check
 */
async function checkTestEnvironment() {
  console.log('🔍 Checking test environment...');

  const checks = [
    {
      name: 'Node.js version',
      check: () => {
        const version = process.version;
        const majorVersion = parseInt(version.slice(1).split('.')[0]);
        return majorVersion >= 16;
      },
      message: 'Node.js 16+ required'
    },
    {
      name: 'MCP server file exists',
      check: () => {
        try {
          const fs = await import('fs');
          const serverPath = path.join(__dirname, '../../bin/task-master-mcp.js');
          return fs.existsSync(serverPath);
        } catch {
          return false;
        }
      },
      message: 'MCP server file should exist at bin/task-master-mcp.js'
    }
  ];

  let allPassed = true;

  for (const check of checks) {
    try {
      const result = await check.check();
      if (result) {
        console.log(`   ✅ ${check.name}`);
      } else {
        console.log(`   ❌ ${check.name} - ${check.message}`);
        allPassed = false;
      }
    } catch (error) {
      console.log(`   ❌ ${check.name} - Error: ${error.message}`);
      allPassed = false;
    }
  }

  if (!allPassed) {
    console.log('\n⚠️  Environment checks failed. Some tests may not work correctly.');
    console.log('   Consider fixing the issues above before proceeding.');
  } else {
    console.log('\n✅ Environment checks passed');
  }

  return allPassed;
}

/**
 * Main test orchestrator
 */
async function main() {
  console.log('🧪 Task Master MCP Server - E2E Test Framework');
  console.log('═'.repeat(80));
  console.log('🎯 Purpose: Comprehensive validation of MCP server functionality');
  console.log('🔧 Framework: Custom E2E testing framework with JSON-RPC support');
  console.log('📊 Coverage: Basic functionality, integration, and performance testing');

  // Environment check
  const envOk = await checkTestEnvironment();

  const aggregator = new TestResultAggregator();
  let overallSuccess = true;

  // Execute test suites in order
  for (const suite of TEST_CONFIG.suites) {
    const suiteSuccess = await runTestSuite(suite, aggregator);

    if (!suiteSuccess) {
      overallSuccess = false;

      // Stop execution if required suite fails and continueOnFailure is false
      if (suite.required && !TEST_CONFIG.settings.continueOnFailure) {
        console.log('\n🛑 Required test suite failed - stopping execution');
        break;
      }
    }
  }

  // Generate comprehensive report
  if (TEST_CONFIG.settings.generateReport) {
    const finalResults = aggregator.generateReport();
    overallSuccess = finalResults.overallSuccess;
  }

  // Exit with appropriate code
  if (overallSuccess) {
    console.log('\n🎉 All tests completed successfully!');
    process.exit(0);
  } else {
    console.log('\n💥 Test execution failed');
    process.exit(1);
  }
}

// Handle unhandled errors
process.on('unhandledRejection', (reason, promise) => {
  console.error('💥 Unhandled Rejection at:', promise, 'reason:', reason);
  process.exit(1);
});

process.on('uncaughtException', (error) => {
  console.error('💥 Uncaught Exception:', error);
  process.exit(1);
});

// Execute if run directly
if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch(error => {
    console.error('💥 Test execution failed:', error);
    process.exit(1);
  });
}

export { main as runAllE2ETests, TestResultAggregator };