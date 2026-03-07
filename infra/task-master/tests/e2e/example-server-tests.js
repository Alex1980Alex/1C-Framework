#!/usr/bin/env node

/**
 * Example E2E Tests for Task Master MCP Server
 * Demonstrates FastMCP Server Launcher functionality
 */

import { MCPTestFramework, MCPTestCase, MCPTestSuite } from './mcp-e2e-framework.js';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Test configuration
const TEST_CONFIG = {
  serverPath: path.join(__dirname, '../../bin/task-master-mcp.js'),
  timeout: 30000,
  verbose: true
};

/**
 * Basic Server Connection Tests
 */
class ServerConnectionTests extends MCPTestSuite {
  constructor() {
    super('Server Connection Tests', 'Basic server startup and connection validation');
  }

  async setupSuite() {
    this.framework = new MCPTestFramework(TEST_CONFIG);
  }

  async teardownSuite() {
    if (this.framework) {
      await this.framework.stop();
    }
  }

  createTests() {
    return [
      new MCPTestCase(
        'server-startup',
        'Server should start successfully',
        async () => {
          await this.framework.start();
          this.framework.assertServerRunning();
          console.log('✓ Server started successfully');
        }
      ),

      new MCPTestCase(
        'server-initialization',
        'Server should respond to initialization',
        async () => {
          const response = await this.framework.initialize({
            protocolVersion: '2024-11-05',
            capabilities: {
              tools: {}
            },
            clientInfo: {
              name: 'test-client',
              version: '1.0.0'
            }
          });

          this.framework.assertResponse(response);
          this.framework.assertProperty(response, 'capabilities');
          console.log('✓ Server initialization successful');
        }
      ),

      new MCPTestCase(
        'list-tools',
        'Server should list available tools',
        async () => {
          const response = await this.framework.listTools();

          this.framework.assertResponse(response);
          this.framework.assertProperty(response, 'tools');
          this.framework.assertArrayNotEmpty(response.tools);

          const expectedTools = ['get-tasks', 'set-task-status', 'get-task', 'list-tags'];
          for (const tool of expectedTools) {
            this.framework.assertToolExists(response.tools, tool);
          }
          console.log(`✓ Found ${response.tools.length} available tools`);
        }
      )
    ];
  }
}

/**
 * Task Management Tool Tests
 */
class TaskManagementTests extends MCPTestSuite {
  constructor() {
    super('Task Management Tests', 'Test core task management functionality');
  }

  async setupSuite() {
    this.framework = new MCPTestFramework(TEST_CONFIG);
    await this.framework.start();
    await this.framework.initialize({
      protocolVersion: '2024-11-05',
      capabilities: { tools: {} },
      clientInfo: { name: 'test-client', version: '1.0.0' }
    });
  }

  async teardownSuite() {
    if (this.framework) {
      await this.framework.stop();
    }
  }

  createTests() {
    return [
      new MCPTestCase(
        'get-tasks-tool',
        'get-tasks tool should return task list',
        async () => {
          const response = await this.framework.callTool('get-tasks', {
            tag: 'master',
            status: 'pending'
          });

          this.framework.assertToolResponse(response);
          this.framework.assertProperty(response.content[0], 'text');

          const tasksData = JSON.parse(response.content[0].text);
          this.framework.assertProperty(tasksData, 'tasks');
          this.framework.assertArray(tasksData.tasks);
          console.log(`✓ Retrieved ${tasksData.tasks.length} tasks`);
        }
      ),

      new MCPTestCase(
        'get-task-by-id',
        'get-task tool should return specific task',
        async () => {
          // First get a task ID
          const tasksResponse = await this.framework.callTool('get-tasks', { tag: 'master' });
          const tasksData = JSON.parse(tasksResponse.content[0].text);

          if (tasksData.tasks.length === 0) {
            throw new Error('No tasks available for testing');
          }

          const taskId = tasksData.tasks[0].id;

          // Now get the specific task
          const response = await this.framework.callTool('get-task', { id: taskId });

          this.framework.assertToolResponse(response);
          const taskData = JSON.parse(response.content[0].text);
          this.framework.assertProperty(taskData, 'task');
          this.framework.assertEqual(taskData.task.id, taskId);
          console.log(`✓ Retrieved task #${taskId}: ${taskData.task.title}`);
        }
      ),

      new MCPTestCase(
        'set-task-status',
        'set-task-status tool should update task status',
        async () => {
          // Get a pending task
          const tasksResponse = await this.framework.callTool('get-tasks', {
            tag: 'master',
            status: 'pending'
          });
          const tasksData = JSON.parse(tasksResponse.content[0].text);

          if (tasksData.tasks.length === 0) {
            console.log('⚠ No pending tasks available for status change test');
            return;
          }

          const task = tasksData.tasks[0];
          const newStatus = 'in-progress';

          // Update task status
          const response = await this.framework.callTool('set-task-status', {
            id: task.id,
            status: newStatus
          });

          this.framework.assertToolResponse(response);
          const result = JSON.parse(response.content[0].text);
          this.framework.assertProperty(result, 'success');
          this.framework.assertEqual(result.success, true);

          // Verify the change
          const verifyResponse = await this.framework.callTool('get-task', { id: task.id });
          const verifyData = JSON.parse(verifyResponse.content[0].text);
          this.framework.assertEqual(verifyData.task.status, newStatus);

          console.log(`✓ Successfully updated task #${task.id} status to ${newStatus}`);
        }
      ),

      new MCPTestCase(
        'list-tags-tool',
        'list-tags tool should return available tags',
        async () => {
          const response = await this.framework.callTool('list-tags');

          this.framework.assertToolResponse(response);
          const tagsData = JSON.parse(response.content[0].text);
          this.framework.assertProperty(tagsData, 'tags');
          this.framework.assertArray(tagsData.tags);

          console.log(`✓ Found ${tagsData.tags.length} available tags`);
        }
      )
    ];
  }
}

/**
 * Error Handling Tests
 */
class ErrorHandlingTests extends MCPTestSuite {
  constructor() {
    super('Error Handling Tests', 'Test error conditions and edge cases');
  }

  async setupSuite() {
    this.framework = new MCPTestFramework(TEST_CONFIG);
    await this.framework.start();
    await this.framework.initialize({
      protocolVersion: '2024-11-05',
      capabilities: { tools: {} },
      clientInfo: { name: 'test-client', version: '1.0.0' }
    });
  }

  async teardownSuite() {
    if (this.framework) {
      await this.framework.stop();
    }
  }

  createTests() {
    return [
      new MCPTestCase(
        'invalid-tool-call',
        'Should handle invalid tool calls gracefully',
        async () => {
          try {
            await this.framework.callTool('non-existent-tool', {});
            throw new Error('Should have thrown an error for invalid tool');
          } catch (error) {
            this.framework.assertErrorType(error, 'METHOD_NOT_FOUND');
            console.log('✓ Invalid tool call handled correctly');
          }
        }
      ),

      new MCPTestCase(
        'invalid-task-id',
        'Should handle invalid task IDs gracefully',
        async () => {
          const response = await this.framework.callTool('get-task', { id: 999999 });

          this.framework.assertToolResponse(response);
          const result = JSON.parse(response.content[0].text);

          // Should return error or empty result
          this.framework.assertTrue(
            result.error || result.task === null,
            'Should handle invalid task ID'
          );
          console.log('✓ Invalid task ID handled correctly');
        }
      ),

      new MCPTestCase(
        'invalid-status-change',
        'Should handle invalid status changes',
        async () => {
          const response = await this.framework.callTool('set-task-status', {
            id: 1,
            status: 'invalid-status'
          });

          this.framework.assertToolResponse(response);
          const result = JSON.parse(response.content[0].text);

          // Should indicate error or validation failure
          this.framework.assertTrue(
            result.success === false || result.error,
            'Should reject invalid status'
          );
          console.log('✓ Invalid status change handled correctly');
        }
      )
    ];
  }
}

/**
 * Performance and Load Tests
 */
class PerformanceTests extends MCPTestSuite {
  constructor() {
    super('Performance Tests', 'Test server performance under load');
  }

  async setupSuite() {
    this.framework = new MCPTestFramework(TEST_CONFIG);
    await this.framework.start();
    await this.framework.initialize({
      protocolVersion: '2024-11-05',
      capabilities: { tools: {} },
      clientInfo: { name: 'test-client', version: '1.0.0' }
    });
  }

  async teardownSuite() {
    if (this.framework) {
      await this.framework.stop();
    }
  }

  createTests() {
    return [
      new MCPTestCase(
        'concurrent-requests',
        'Should handle concurrent requests efficiently',
        async () => {
          const concurrentRequests = 10;
          const startTime = Date.now();

          const promises = Array(concurrentRequests).fill().map(async (_, index) => {
            return this.framework.callTool('get-tasks', { tag: 'master' });
          });

          const responses = await Promise.all(promises);
          const duration = Date.now() - startTime;

          // Verify all responses are valid
          responses.forEach((response, index) => {
            this.framework.assertToolResponse(response, `Request ${index + 1}`);
          });

          console.log(`✓ Handled ${concurrentRequests} concurrent requests in ${duration}ms`);

          // Performance assertion: should complete within reasonable time
          this.framework.assertTrue(
            duration < 5000,
            `Concurrent requests took too long: ${duration}ms`
          );
        }
      ),

      new MCPTestCase(
        'rapid-sequential-requests',
        'Should handle rapid sequential requests',
        async () => {
          const requestCount = 20;
          const startTime = Date.now();

          for (let i = 0; i < requestCount; i++) {
            const response = await this.framework.callTool('list-tags');
            this.framework.assertToolResponse(response, `Request ${i + 1}`);
          }

          const duration = Date.now() - startTime;
          console.log(`✓ Completed ${requestCount} sequential requests in ${duration}ms`);

          // Performance assertion
          this.framework.assertTrue(
            duration < 10000,
            `Sequential requests took too long: ${duration}ms`
          );
        }
      )
    ];
  }
}

/**
 * Main Test Runner
 */
async function runAllTests() {
  console.log('\n🚀 Starting Task Master MCP Server E2E Tests\n');

  const testSuites = [
    new ServerConnectionTests(),
    new TaskManagementTests(),
    new ErrorHandlingTests(),
    new PerformanceTests()
  ];

  let totalTests = 0;
  let passedTests = 0;
  let failedTests = 0;

  for (const suite of testSuites) {
    console.log(`\n📋 Running ${suite.name}`);
    console.log(`   ${suite.description}`);
    console.log('   ' + '─'.repeat(50));

    try {
      const results = await suite.run();

      totalTests += results.total;
      passedTests += results.passed;
      failedTests += results.failed;

      console.log(`   ✅ Passed: ${results.passed}`);
      console.log(`   ❌ Failed: ${results.failed}`);
      console.log(`   ⏱️  Duration: ${results.duration}ms`);

    } catch (error) {
      console.error(`   💥 Suite failed: ${error.message}`);
      failedTests += 1;
    }
  }

  console.log('\n' + '═'.repeat(60));
  console.log('📊 TEST SUMMARY');
  console.log('═'.repeat(60));
  console.log(`Total Tests: ${totalTests}`);
  console.log(`Passed: ${passedTests}`);
  console.log(`Failed: ${failedTests}`);
  console.log(`Success Rate: ${totalTests > 0 ? Math.round((passedTests / totalTests) * 100) : 0}%`);

  if (failedTests > 0) {
    console.log('\n❌ Some tests failed. Check the output above for details.');
    process.exit(1);
  } else {
    console.log('\n✅ All tests passed successfully!');
    process.exit(0);
  }
}

// Run tests if this file is executed directly
if (import.meta.url === `file://${process.argv[1]}`) {
  runAllTests().catch(error => {
    console.error('💥 Test runner failed:', error);
    process.exit(1);
  });
}

export {
  ServerConnectionTests,
  TaskManagementTests,
  ErrorHandlingTests,
  PerformanceTests,
  runAllTests
};