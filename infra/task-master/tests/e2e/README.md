# Task Master MCP Server - E2E Test Framework

A comprehensive End-to-End testing framework specifically designed for testing Task Master MCP (Model Context Protocol) servers over stdio communication.

## 🎯 Overview

This framework enables programmatic testing of FastMCP servers by launching them as subprocesses and communicating via JSON-RPC messages over stdio. It provides:

- **Server Lifecycle Management**: Automatic startup, initialization, and shutdown
- **JSON-RPC Protocol Handling**: Robust message parsing and correlation
- **Request/Response Correlation**: Track requests across concurrent operations
- **Performance Monitoring**: Built-in performance metrics and statistics
- **Comprehensive Assertions**: Rich set of test assertion methods
- **Test Organization**: Test cases and test suites with setup/teardown support
- **Parallel Execution**: Support for concurrent test execution
- **CI/CD Integration**: Ready for continuous integration pipelines

## 🏗️ Architecture

### Core Components

1. **MCPTestFramework** - Main framework for server interaction
2. **MCPTestCase** - Individual test case with timeout and retry support
3. **MCPTestSuite** - Collection of test cases with suite-level setup/teardown
4. **TestHelpers** - Utility functions for common test patterns

### Framework Features

- ✅ **Protocol Validation**: Validates JSON-RPC message structure
- ✅ **Error Handling**: Graceful handling of malformed messages
- ✅ **Performance Tracking**: Response times, error rates, correlation
- ✅ **Concurrent Testing**: Multiple parallel requests with correlation
- ✅ **Test Organization**: Hierarchical test structure with clear reporting
- ✅ **CI Integration**: Exit codes and structured output for automation

## 🚀 Quick Start

### Basic Usage

```javascript
import { MCPTestFramework, MCPTestCase, MCPTestSuite } from './mcp-e2e-framework.js';

// 1. Create and start framework
const framework = new MCPTestFramework({
  serverPath: 'path/to/mcp-server.js',
  timeout: 30000,
  verbose: true
});

await framework.start();
await framework.initialize();

// 2. Make tool calls
const response = await framework.callTool('get-tasks', { tag: 'master' });
framework.assertToolResponse(response);

// 3. Clean up
await framework.stop();
```

### Test Suite Example

```javascript
class MyTestSuite extends MCPTestSuite {
  constructor() {
    super('My Tests', 'Testing basic functionality');
  }

  async setupSuite() {
    this.framework = new MCPTestFramework({ /* config */ });
    await this.framework.start();
    await this.framework.initialize();
  }

  async teardownSuite() {
    if (this.framework) {
      await this.framework.stop();
    }
  }

  createTests() {
    return [
      new MCPTestCase(
        'test-basic-functionality',
        'Should handle basic operations',
        async () => {
          const response = await this.framework.callTool('list-tags');
          this.framework.assertToolResponse(response);
        }
      )
    ];
  }
}

// Run the suite
const suite = new MyTestSuite();
const results = await suite.run();
```

## 📋 Available Test Commands

### Running Tests

```bash
# Run all test suites
node tests/e2e/run-all-tests.js

# Run basic server tests only
node tests/e2e/example-server-tests.js

# Run integration tests only
node tests/e2e/integration-tests.js
```

### Test Configuration

```javascript
const config = {
  serverPath: './bin/task-master-mcp.js',  // Path to MCP server
  timeout: 30000,                          // Request timeout (ms)
  debug: false,                            // Enable debug logging
  verbose: true                            // Enable verbose output
};
```

## 🧪 Test Suites

### 1. Basic Server Tests (`example-server-tests.js`)

**Purpose**: Validate fundamental server functionality

**Test Categories**:
- **Server Connection**: Startup, initialization, tool listing
- **Task Management**: CRUD operations on tasks
- **Error Handling**: Invalid requests, malformed data
- **Performance**: Concurrent requests, response times

**Key Tests**:
- Server startup and initialization
- Tool availability verification
- Task retrieval and status updates
- Error condition handling
- Concurrent request processing

### 2. Integration Tests (`integration-tests.js`)

**Purpose**: Advanced integration and business logic validation

**Test Categories**:
- **Advanced Protocol**: Complex JSON-RPC scenarios
- **Business Logic**: End-to-end workflows
- **Performance**: Stress testing and benchmarks

**Key Tests**:
- Malformed request handling
- Request timeout management
- Concurrent request correlation
- Complete task workflows
- Tag and status filtering accuracy
- Performance benchmarking
- Memory efficiency testing

### 3. Test Result Aggregation (`run-all-tests.js`)

**Purpose**: Orchestrate all test suites with unified reporting

**Features**:
- Environment validation
- Sequential test suite execution
- Comprehensive result aggregation
- Detailed execution reporting
- CI/CD integration support

## 🔧 Framework API Reference

### MCPTestFramework

#### Constructor Options
```javascript
{
  serverPath: string,      // Path to MCP server executable
  timeout: number,         // Default request timeout (ms)
  debug: boolean,          // Enable debug logging
  verbose: boolean         // Enable verbose output
}
```

#### Core Methods
- `start()` - Launch and initialize the MCP server
- `stop()` - Gracefully shut down the server
- `initialize(params)` - Send initialization request
- `callTool(name, params)` - Call a specific tool
- `listTools()` - Get available tools
- `sendRequest(request, timeout)` - Send raw JSON-RPC request

#### Performance Methods
- `getPerformanceStats()` - Get performance metrics
- `clearStats()` - Reset performance tracking
- `calculatePercentile(arr, percentile)` - Calculate response time percentiles

#### Assertion Methods
- `assertResponse(response, context)` - Validate basic response structure
- `assertToolResponse(response, context)` - Validate tool response structure
- `assertProperty(obj, property, context)` - Check object has property
- `assertArrayNotEmpty(arr, context)` - Validate non-empty array
- `assertEqual(actual, expected, message)` - Compare values
- `assertTrue(condition, message)` - Assert condition is true
- `assertContains(string, substring, message)` - Check string contains text
- `assertMatches(string, regex, message)` - Validate regex match
- `assertErrorType(error, expectedType)` - Validate error type
- `assertResponseTime(messageId, maxMs, message)` - Check response time

### MCPTestCase

#### Constructor
```javascript
new MCPTestCase(name, description, testFunction)
```

#### Configuration Methods
- `setTimeout(ms)` - Set test timeout
- `setRetries(count)` - Set retry count for flaky tests
- `addTags(...tags)` - Add categorization tags
- `setSetup(fn)` - Set test setup function
- `setTeardown(fn)` - Set test cleanup function

#### Execution
- `run()` - Execute the test case with timeout and retry handling

### MCPTestSuite

#### Constructor
```javascript
new MCPTestSuite(name, description, options)
```

#### Options
```javascript
{
  parallel: boolean,       // Run tests in parallel
  stopOnFailure: boolean,  // Stop on first failure
  timeout: number,         // Suite timeout
  verbose: boolean         // Verbose output
}
```

#### Abstract Methods (Override in subclasses)
- `setupSuite()` - Suite-level setup
- `teardownSuite()` - Suite-level cleanup
- `createTests()` - Return array of test cases

#### Execution
- `run()` - Execute all test cases with reporting

## 📊 Performance Monitoring

The framework includes built-in performance monitoring:

### Tracked Metrics
- **Request Count**: Total and completed requests
- **Response Times**: Min, max, average, and 95th percentile
- **Error Rates**: Categorized by type (network, protocol, timeout)
- **Message History**: Recent request/response correlation data

### Performance Statistics Example
```javascript
const stats = framework.getPerformanceStats();
console.log(`Average Response Time: ${stats.responseTimes.avg}ms`);
console.log(`95th Percentile: ${stats.responseTimes.p95}ms`);
console.log(`Error Rate: ${stats.errorCounts.total}/${stats.totalRequests}`);
```

## 🔄 CI/CD Integration

### GitHub Actions Integration

Create `.github/workflows/e2e-tests.yml`:

```yaml
name: E2E Tests
on: [push, pull_request]

jobs:
  e2e-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
      - name: Install dependencies
        run: npm install
      - name: Run E2E tests
        run: node tests/e2e/run-all-tests.js
```

### NPM Scripts Integration

Add to `package.json`:

```json
{
  "scripts": {
    "test:e2e": "node tests/e2e/run-all-tests.js",
    "test:e2e:basic": "node tests/e2e/example-server-tests.js",
    "test:e2e:integration": "node tests/e2e/integration-tests.js"
  }
}
```

### Exit Codes
- `0` - All tests passed
- `1` - One or more tests failed

## 🐛 Troubleshooting

### Common Issues

1. **Server Startup Timeout**
   ```
   Error: Server initialization timeout
   ```
   - **Solution**: Increase timeout in framework config
   - **Check**: Server path is correct and executable

2. **JSON Parsing Errors**
   ```
   Failed to parse JSON: Unexpected token
   ```
   - **Solution**: Enable debug mode to see raw server output
   - **Check**: Server is outputting valid JSON-RPC messages

3. **Tool Not Found Errors**
   ```
   Tool "tool-name" not found
   ```
   - **Solution**: Verify tool name spelling and server configuration
   - **Check**: Use `listTools()` to see available tools

4. **Timeout Errors**
   ```
   Request timeout after 30000ms
   ```
   - **Solution**: Increase timeout for slow operations
   - **Check**: Server is responding and not blocked

### Debug Mode

Enable debug logging to troubleshoot issues:

```javascript
const framework = new MCPTestFramework({
  debug: true,      // Enable debug output
  verbose: true     // Enable verbose messaging
});
```

### Environment Requirements

- Node.js 16+ (ES modules support)
- MCP server executable at specified path
- Sufficient permissions to spawn processes
- Available ports for stdio communication

## 🏆 Best Practices

### Test Organization
1. Group related tests into suites
2. Use descriptive test names and descriptions
3. Implement proper setup/teardown
4. Use tags for test categorization

### Error Handling
1. Always use assertions instead of manual checks
2. Provide descriptive error messages
3. Clean up resources in teardown methods
4. Handle async operations properly

### Performance
1. Use concurrent tests for independent operations
2. Monitor response times and set reasonable timeouts
3. Clear performance stats between test suites
4. Use retries for flaky network operations

### Maintenance
1. Keep test data minimal and focused
2. Update tests when server API changes
3. Review performance benchmarks regularly
4. Document test scenarios and expected outcomes

## 📚 Advanced Examples

### Custom Assertion Example
```javascript
// Custom assertion for task validation
framework.assertTaskValid = function(task) {
  this.assertProperty(task, 'id');
  this.assertProperty(task, 'title');
  this.assertProperty(task, 'status');
  this.assertTrue(
    ['pending', 'in-progress', 'done'].includes(task.status),
    `Invalid status: ${task.status}`
  );
};
```

### Parallel Test Suite Example
```javascript
class ParallelTests extends MCPTestSuite {
  constructor() {
    super('Parallel Tests', 'Tests that run concurrently', {
      parallel: true,      // Enable parallel execution
      stopOnFailure: false // Continue on failures
    });
  }

  createTests() {
    return [
      new MCPTestCase('test1', 'First test', async () => { /* test */ }),
      new MCPTestCase('test2', 'Second test', async () => { /* test */ }),
      new MCPTestCase('test3', 'Third test', async () => { /* test */ })
    ];
  }
}
```

### Performance Benchmark Example
```javascript
const benchmark = new MCPTestCase(
  'performance-benchmark',
  'Measure tool call performance',
  async () => {
    const iterations = 100;
    const startTime = Date.now();

    for (let i = 0; i < iterations; i++) {
      await framework.callTool('list-tags');
    }

    const totalTime = Date.now() - startTime;
    const avgTime = totalTime / iterations;

    framework.assertTrue(
      avgTime < 100,
      `Average response time ${avgTime}ms exceeds 100ms threshold`
    );
  }
).setTimeout(60000);
```

## 📈 Metrics and Reporting

The framework generates comprehensive test reports including:

- **Execution Summary**: Total duration, suite count, pass/fail rates
- **Suite Details**: Individual suite results and timing
- **Performance Metrics**: Response times, throughput, error rates
- **Historical Tracking**: Performance trends over time (when integrated with CI)

Report data is structured for easy integration with monitoring and alerting systems.

---

**Framework Version**: 1.0.0
**Compatibility**: Node.js 16+, MCP Protocol 2024-11-05
**License**: MIT
**Last Updated**: October 2025