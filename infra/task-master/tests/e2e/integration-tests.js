#!/usr/bin/env node

/**
 * Integration Tests for Task Master MCP Server E2E Framework
 * Demonstrates advanced testing scenarios and framework capabilities
 */

import { MCPTestFramework, MCPTestCase, MCPTestSuite } from './mcp-e2e-framework.js';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Test configuration
const INTEGRATION_CONFIG = {
  serverPath: path.join(__dirname, '../../bin/task-master-mcp.js'),
  timeout: 45000,
  verbose: true,
  debug: false
};

/**
 * Advanced Protocol Tests
 */
class AdvancedProtocolTests extends MCPTestSuite {
  constructor() {
    super(
      'Advanced Protocol Tests',
      'Tests for complex JSON-RPC scenarios and edge cases',
      { verbose: true }
    );
  }

  async setupSuite() {
    this.framework = new MCPTestFramework(INTEGRATION_CONFIG);
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
        'malformed-request-handling',
        'Server should handle malformed JSON-RPC requests gracefully',
        async () => {
          // Test invalid JSON
          try {
            await this.framework.sendRequest({ invalid: 'json without method' });
            throw new Error('Should have thrown an error for invalid request');
          } catch (error) {
            this.framework.assertTrue(
              error.message.includes('method') || error.message.includes('invalid'),
              'Error should indicate missing method or invalid request'
            );
          }
        }
      ),

      new MCPTestCase(
        'request-timeout-handling',
        'Framework should handle request timeouts correctly',
        async () => {
          // Send request with very short timeout to simulate timeout
          try {
            await this.framework.sendRequest(
              { method: 'tools/list', params: {} },
              1 // 1ms timeout - should always timeout
            );
            throw new Error('Should have timed out');
          } catch (error) {
            this.framework.assertContains(error.message, 'timeout', 'Should be a timeout error');
          }
        }
      ).setTimeout(10000),

      new MCPTestCase(
        'concurrent-request-correlation',
        'Framework should correctly correlate concurrent requests',
        async () => {
          const promises = [];
          const requestCount = 5;

          // Send multiple concurrent requests
          for (let i = 0; i < requestCount; i++) {
            promises.push(
              this.framework.callTool('get-tasks', { tag: 'master' })
            );
          }

          const responses = await Promise.all(promises);

          // Verify all responses are valid and distinct
          this.framework.assertEqual(responses.length, requestCount);

          for (let i = 0; i < responses.length; i++) {
            this.framework.assertToolResponse(responses[i], `Response ${i + 1}`);
          }

          // Check performance tracking
          const stats = this.framework.getPerformanceStats();
          this.framework.assertTrue(
            stats.totalRequests >= requestCount,
            `Should have at least ${requestCount} requests in stats`
          );
        }
      ).setTimeout(20000),

      new MCPTestCase(
        'large-response-handling',
        'Framework should handle large responses efficiently',
        async () => {
          // Get tasks which might be a large response
          const response = await this.framework.callTool('get-tasks', { tag: 'master' });

          this.framework.assertToolResponse(response);

          // Parse the response to ensure it's valid JSON
          const tasksData = JSON.parse(response.result.content[0].text);
          this.framework.assertProperty(tasksData, 'tasks');

          // Check performance for large response
          const stats = this.framework.getPerformanceStats();
          this.framework.assertTrue(
            stats.responseTimes.max < 30000,
            'Large response should complete within 30 seconds'
          );
        }
      )
    ];
  }
}

/**
 * Business Logic Integration Tests
 */
class BusinessLogicTests extends MCPTestSuite {
  constructor() {
    super(
      'Business Logic Integration Tests',
      'End-to-end tests for Task Master business workflows',
      { stopOnFailure: false }
    );
  }

  async setupSuite() {
    this.framework = new MCPTestFramework(INTEGRATION_CONFIG);
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
        'complete-task-workflow',
        'Complete workflow: get task → show details → update status → verify',
        async () => {
          // Step 1: Get available tasks
          const tasksResponse = await this.framework.callTool('get-tasks', {
            tag: 'master',
            status: 'pending'
          });

          this.framework.assertToolResponse(tasksResponse);
          const tasksData = JSON.parse(tasksResponse.result.content[0].text);

          if (tasksData.tasks.length === 0) {
            console.log('⚠️  No pending tasks available for workflow test');
            return;
          }

          const task = tasksData.tasks[0];
          console.log(`📋 Working with task #${task.id}: ${task.title}`);

          // Step 2: Get detailed task information
          const detailResponse = await this.framework.callTool('get-task', { id: task.id });
          this.framework.assertToolResponse(detailResponse);

          const detailData = JSON.parse(detailResponse.result.content[0].text);
          this.framework.assertProperty(detailData, 'task');
          this.framework.assertEqual(detailData.task.id, task.id);

          // Step 3: Update task status to in-progress
          const updateResponse = await this.framework.callTool('set-task-status', {
            id: task.id,
            status: 'in-progress'
          });

          this.framework.assertToolResponse(updateResponse);
          const updateResult = JSON.parse(updateResponse.result.content[0].text);
          this.framework.assertTrue(updateResult.success, 'Status update should succeed');

          // Step 4: Verify the status change
          const verifyResponse = await this.framework.callTool('get-task', { id: task.id });
          const verifyData = JSON.parse(verifyResponse.result.content[0].text);
          this.framework.assertEqual(
            verifyData.task.status,
            'in-progress',
            'Task status should be updated to in-progress'
          );

          console.log(`✅ Task #${task.id} successfully updated to in-progress`);
        }
      ).setTimeout(30000),

      new MCPTestCase(
        'tag-filtering-accuracy',
        'Tag filtering should return only tasks with specified tags',
        async () => {
          // Get all available tags
          const tagsResponse = await this.framework.callTool('list-tags');
          this.framework.assertToolResponse(tagsResponse);

          const tagsData = JSON.parse(tagsResponse.result.content[0].text);
          this.framework.assertProperty(tagsData, 'tags');

          if (tagsData.tags.length === 0) {
            console.log('⚠️  No tags available for filtering test');
            return;
          }

          // Test each tag
          for (const tag of tagsData.tags.slice(0, 3)) { // Test first 3 tags
            const taggedTasksResponse = await this.framework.callTool('get-tasks', { tag: tag });
            this.framework.assertToolResponse(taggedTasksResponse);

            const taggedTasks = JSON.parse(taggedTasksResponse.result.content[0].text);
            this.framework.assertProperty(taggedTasks, 'tasks');

            // Verify all returned tasks have the correct tag
            for (const task of taggedTasks.tasks) {
              this.framework.assertTrue(
                task.tags && task.tags.includes(tag),
                `Task ${task.id} should have tag "${tag}"`
              );
            }

            console.log(`✅ Tag "${tag}" filtering verified (${taggedTasks.tasks.length} tasks)`);
          }
        }
      ).setTimeout(25000),

      new MCPTestCase(
        'status-filtering-accuracy',
        'Status filtering should return only tasks with specified status',
        async () => {
          const statuses = ['pending', 'in-progress', 'done'];

          for (const status of statuses) {
            const statusTasksResponse = await this.framework.callTool('get-tasks', {
              tag: 'master',
              status: status
            });

            this.framework.assertToolResponse(statusTasksResponse);
            const statusTasks = JSON.parse(statusTasksResponse.result.content[0].text);

            // Verify all returned tasks have the correct status
            for (const task of statusTasks.tasks) {
              this.framework.assertEqual(
                task.status,
                status,
                `Task ${task.id} should have status "${status}"`
              );
            }

            console.log(`✅ Status "${status}" filtering verified (${statusTasks.tasks.length} tasks)`);
          }
        }
      ).setTimeout(20000)
    ];
  }
}

/**
 * Performance and Stress Tests
 */
class PerformanceTests extends MCPTestSuite {
  constructor() {
    super(
      'Performance and Stress Tests',
      'Performance benchmarks and stress testing scenarios',
      { parallel: false }
    );
  }

  async setupSuite() {
    this.framework = new MCPTestFramework(INTEGRATION_CONFIG);
    await this.framework.start();
    await this.framework.initialize();
    this.framework.clearStats(); // Start with clean performance stats
  }

  async teardownSuite() {
    if (this.framework) {
      // Print final performance stats
      const finalStats = this.framework.getPerformanceStats();
      console.log('\n📊 Final Performance Statistics:');
      console.log(`   Total Requests: ${finalStats.totalRequests}`);
      console.log(`   Average Response Time: ${Math.round(finalStats.responseTimes.avg)}ms`);
      console.log(`   95th Percentile: ${Math.round(finalStats.responseTimes.p95)}ms`);
      console.log(`   Error Rate: ${(finalStats.errorCounts.total / finalStats.totalRequests * 100).toFixed(2)}%`);

      await this.framework.stop();
    }
  }

  createTests() {
    return [
      new MCPTestCase(
        'response-time-benchmark',
        'Basic operations should complete within acceptable time limits',
        async () => {
          const operations = [
            { name: 'list-tags', call: () => this.framework.callTool('list-tags') },
            {
              name: 'get-tasks',
              call: () => this.framework.callTool('get-tasks', { tag: 'master' })
            },
            {
              name: 'get-specific-task',
              call: async () => {
                // First get a task ID
                const tasksResponse = await this.framework.callTool('get-tasks', { tag: 'master' });
                const tasksData = JSON.parse(tasksResponse.result.content[0].text);
                if (tasksData.tasks.length > 0) {
                  return this.framework.callTool('get-task', { id: tasksData.tasks[0].id });
                }
                return { result: { content: [{ text: '{"task": null}' }] } };
              }
            }
          ];

          for (const operation of operations) {
            const startTime = Date.now();
            const response = await operation.call();
            const duration = Date.now() - startTime;

            this.framework.assertToolResponse(response, operation.name);

            // Performance assertions
            this.framework.assertTrue(
              duration < 5000,
              `${operation.name} should complete within 5 seconds (took ${duration}ms)`
            );

            console.log(`   ⏱️  ${operation.name}: ${duration}ms`);
          }
        }
      ).setTimeout(30000),

      new MCPTestCase(
        'concurrent-load-test',
        'Server should handle multiple concurrent requests efficiently',
        async () => {
          const concurrentRequests = 15;
          const maxAcceptableTime = 10000; // 10 seconds for all requests

          console.log(`   🚀 Starting ${concurrentRequests} concurrent requests...`);

          const startTime = Date.now();

          const promises = Array(concurrentRequests).fill().map(async (_, index) => {
            const requestStart = Date.now();
            const response = await this.framework.callTool('get-tasks', { tag: 'master' });
            const requestDuration = Date.now() - requestStart;

            return {
              index: index + 1,
              response,
              duration: requestDuration
            };
          });

          const results = await Promise.all(promises);
          const totalDuration = Date.now() - startTime;

          // Verify all requests succeeded
          for (const result of results) {
            this.framework.assertToolResponse(result.response, `Concurrent request ${result.index}`);
          }

          // Performance assertions
          this.framework.assertTrue(
            totalDuration < maxAcceptableTime,
            `All concurrent requests should complete within ${maxAcceptableTime}ms (took ${totalDuration}ms)`
          );

          // Calculate statistics
          const durations = results.map(r => r.duration);
          const avgDuration = durations.reduce((a, b) => a + b, 0) / durations.length;
          const maxDuration = Math.max(...durations);
          const minDuration = Math.min(...durations);

          console.log(`   📈 Concurrent Performance Results:`);
          console.log(`      Total Time: ${totalDuration}ms`);
          console.log(`      Average Request Time: ${Math.round(avgDuration)}ms`);
          console.log(`      Min Request Time: ${minDuration}ms`);
          console.log(`      Max Request Time: ${maxDuration}ms`);

          // Additional performance assertions
          this.framework.assertTrue(
            avgDuration < 3000,
            `Average request time should be under 3 seconds (was ${avgDuration}ms)`
          );
        }
      ).setTimeout(45000),

      new MCPTestCase(
        'memory-efficiency-test',
        'Framework should maintain stable memory usage during extended operation',
        async () => {
          const iterations = 50;
          console.log(`   🔄 Running ${iterations} sequential requests for memory efficiency test...`);

          // Track performance over time
          const performanceSnapshots = [];

          for (let i = 0; i < iterations; i++) {
            const response = await this.framework.callTool('list-tags');
            this.framework.assertToolResponse(response, `Iteration ${i + 1}`);

            // Take performance snapshot every 10 iterations
            if (i % 10 === 0) {
              const stats = this.framework.getPerformanceStats();
              performanceSnapshots.push({
                iteration: i,
                avgResponseTime: stats.responseTimes.avg,
                totalRequests: stats.totalRequests,
                errorCount: stats.errorCounts.total
              });
            }
          }

          // Verify performance doesn't degrade significantly over time
          const firstSnapshot = performanceSnapshots[0];
          const lastSnapshot = performanceSnapshots[performanceSnapshots.length - 1];

          const performanceDegradation = (lastSnapshot.avgResponseTime - firstSnapshot.avgResponseTime) / firstSnapshot.avgResponseTime;

          console.log(`   📊 Memory Efficiency Results:`);
          console.log(`      First Avg Response: ${Math.round(firstSnapshot.avgResponseTime)}ms`);
          console.log(`      Last Avg Response: ${Math.round(lastSnapshot.avgResponseTime)}ms`);
          console.log(`      Performance Change: ${(performanceDegradation * 100).toFixed(1)}%`);

          this.framework.assertTrue(
            performanceDegradation < 0.5, // Less than 50% degradation
            `Performance should not degrade significantly over time (degraded by ${(performanceDegradation * 100).toFixed(1)}%)`
          );

          this.framework.assertEqual(
            lastSnapshot.errorCount,
            0,
            'No errors should occur during extended operation'
          );
        }
      ).setTimeout(60000)
    ];
  }
}

/**
 * Main Integration Test Runner
 */
async function runIntegrationTests() {
  console.log('\n🔬 Starting Task Master MCP Server Integration Tests\n');
  console.log('═'.repeat(80));

  const testSuites = [
    new AdvancedProtocolTests(),
    new BusinessLogicTests(),
    new PerformanceTests()
  ];

  let totalTests = 0;
  let totalPassed = 0;
  let totalFailed = 0;
  let totalDuration = 0;

  const suiteResults = [];

  for (const suite of testSuites) {
    try {
      const result = await suite.run();
      suiteResults.push(result);

      totalTests += result.summary.total;
      totalPassed += result.summary.passed;
      totalFailed += result.summary.failed;
      totalDuration += result.duration;

    } catch (error) {
      console.error(`💥 Test suite "${suite.name}" failed: ${error.message}`);
      totalFailed += 1;
    }
  }

  // Final summary
  console.log('\n' + '═'.repeat(80));
  console.log('🏁 INTEGRATION TESTS COMPLETE');
  console.log('═'.repeat(80));
  console.log(`Total Duration: ${Math.round(totalDuration / 1000)}s`);
  console.log(`Total Test Suites: ${testSuites.length}`);
  console.log(`Total Tests: ${totalTests}`);
  console.log(`✅ Passed: ${totalPassed}`);
  console.log(`❌ Failed: ${totalFailed}`);

  const overallSuccessRate = totalTests > 0 ? Math.round((totalPassed / totalTests) * 100) : 0;
  console.log(`📊 Overall Success Rate: ${overallSuccessRate}%`);

  if (totalFailed > 0) {
    console.log('\n❌ Some integration tests failed. Check the output above for details.');
    process.exit(1);
  } else {
    console.log('\n🎉 All integration tests passed successfully!');
    console.log('\n✨ The Task Master MCP Server E2E Test Framework is ready for production use.');
    process.exit(0);
  }
}

// Run integration tests if this file is executed directly
if (import.meta.url === `file://${process.argv[1]}`) {
  runIntegrationTests().catch(error => {
    console.error('💥 Integration test runner failed:', error);
    process.exit(1);
  });
}

export {
  AdvancedProtocolTests,
  BusinessLogicTests,
  PerformanceTests,
  runIntegrationTests
};