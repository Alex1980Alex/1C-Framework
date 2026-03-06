import { calculateCost, formatCost, getModelPricing, getDailyLimits } from './pricing-config.js';
/**
 * Cost tracker for monitoring LLM API costs
 * Tracks per-request costs and provides aggregated statistics
 */
export class CostTracker {
    constructor(budgetLimit) {
        this.requests = [];
        this.providerStats = new Map();
        this.budgetWarningIssued = false;
        this.startTime = new Date();
        this.budgetLimit = budgetLimit;
    }
    /**
     * Record a request and its cost
     * @param provider Provider name
     * @param model Model name
     * @param inputTokens Input tokens count
     * @param outputTokens Output tokens count
     * @returns Request cost information
     */
    recordRequest(provider, model, inputTokens, outputTokens) {
        const cost = calculateCost(provider, model, inputTokens, outputTokens);
        const pricing = getModelPricing(provider, model);
        const requestCost = {
            timestamp: new Date(),
            provider,
            model,
            inputTokens,
            outputTokens,
            totalTokens: inputTokens + outputTokens,
            cost,
            isFree: pricing?.isFree ?? false,
        };
        // Add to request history
        this.requests.push(requestCost);
        // Update provider stats
        this.updateProviderStats(requestCost);
        return requestCost;
    }
    /**
     * Update aggregated statistics for a provider
     */
    updateProviderStats(request) {
        let stats = this.providerStats.get(request.provider);
        if (!stats) {
            stats = {
                provider: request.provider,
                requests: 0,
                totalTokens: 0,
                inputTokens: 0,
                outputTokens: 0,
                totalCost: 0,
                isFree: request.isFree,
                averageCostPerRequest: 0,
                averageTokensPerRequest: 0,
            };
            this.providerStats.set(request.provider, stats);
        }
        // Update counters
        stats.requests++;
        stats.totalTokens += request.totalTokens;
        stats.inputTokens += request.inputTokens;
        stats.outputTokens += request.outputTokens;
        stats.totalCost += request.cost;
        stats.lastRequest = request.timestamp;
        if (!stats.firstRequest) {
            stats.firstRequest = request.timestamp;
        }
        // Update averages
        stats.averageCostPerRequest = stats.totalCost / stats.requests;
        stats.averageTokensPerRequest = stats.totalTokens / stats.requests;
    }
    /**
     * Get cost summary for the session
     * @returns Cost summary
     */
    getSummary() {
        const totalRequests = this.requests.length;
        const totalTokens = this.requests.reduce((sum, r) => sum + r.totalTokens, 0);
        const totalInputTokens = this.requests.reduce((sum, r) => sum + r.inputTokens, 0);
        const totalOutputTokens = this.requests.reduce((sum, r) => sum + r.outputTokens, 0);
        const totalCost = this.requests.reduce((sum, r) => sum + r.cost, 0);
        const freeRequests = this.requests.filter(r => r.isFree).length;
        const paidRequests = totalRequests - freeRequests;
        return {
            totalRequests,
            totalTokens,
            totalInputTokens,
            totalOutputTokens,
            totalCost,
            freeRequests,
            paidRequests,
            providerStats: new Map(this.providerStats),
            startTime: this.startTime,
            endTime: new Date(),
        };
    }
    /**
     * Get statistics for a specific provider
     * @param provider Provider name
     * @returns Provider statistics or undefined
     */
    getProviderStats(provider) {
        return this.providerStats.get(provider);
    }
    /**
     * Check budget status
     * @returns Budget status
     */
    checkBudget() {
        const summary = this.getSummary();
        const status = {
            exceeded: false,
            warningTriggered: false,
            currentCost: summary.totalCost,
            currentTokens: summary.totalTokens,
            currentRequests: summary.totalRequests,
        };
        if (!this.budgetLimit) {
            return status;
        }
        const warningThreshold = this.budgetLimit.warningThreshold ?? 0.8; // 80% default
        // Check cost limit
        if (this.budgetLimit.maxCost !== undefined) {
            status.costLimit = this.budgetLimit.maxCost;
            status.costPercentage = summary.totalCost / this.budgetLimit.maxCost;
            if (summary.totalCost >= this.budgetLimit.maxCost) {
                status.exceeded = true;
                status.message = `❌ Budget exceeded: ${formatCost(summary.totalCost)} / ${formatCost(this.budgetLimit.maxCost)}`;
            }
            else if (status.costPercentage >= warningThreshold && !this.budgetWarningIssued) {
                status.warningTriggered = true;
                this.budgetWarningIssued = true;
                status.message = `⚠️ Budget warning: ${formatCost(summary.totalCost)} / ${formatCost(this.budgetLimit.maxCost)} (${(status.costPercentage * 100).toFixed(1)}%)`;
            }
        }
        // Check token limit
        if (this.budgetLimit.maxTokens !== undefined) {
            status.tokenLimit = this.budgetLimit.maxTokens;
            status.tokenPercentage = summary.totalTokens / this.budgetLimit.maxTokens;
            if (summary.totalTokens >= this.budgetLimit.maxTokens) {
                status.exceeded = true;
                status.message = `❌ Token limit exceeded: ${summary.totalTokens.toLocaleString()} / ${this.budgetLimit.maxTokens.toLocaleString()}`;
            }
            else if (status.tokenPercentage >= warningThreshold && !this.budgetWarningIssued) {
                status.warningTriggered = true;
                this.budgetWarningIssued = true;
                status.message = `⚠️ Token warning: ${summary.totalTokens.toLocaleString()} / ${this.budgetLimit.maxTokens.toLocaleString()} (${(status.tokenPercentage * 100).toFixed(1)}%)`;
            }
        }
        // Check request limit
        if (this.budgetLimit.maxRequests !== undefined) {
            status.requestLimit = this.budgetLimit.maxRequests;
            status.requestPercentage = summary.totalRequests / this.budgetLimit.maxRequests;
            if (summary.totalRequests >= this.budgetLimit.maxRequests) {
                status.exceeded = true;
                status.message = `❌ Request limit exceeded: ${summary.totalRequests} / ${this.budgetLimit.maxRequests}`;
            }
            else if (status.requestPercentage >= warningThreshold && !this.budgetWarningIssued) {
                status.warningTriggered = true;
                this.budgetWarningIssued = true;
                status.message = `⚠️ Request warning: ${summary.totalRequests} / ${this.budgetLimit.maxRequests} (${(status.requestPercentage * 100).toFixed(1)}%)`;
            }
        }
        return status;
    }
    /**
     * Set or update budget limit
     * @param budgetLimit New budget limit
     */
    setBudgetLimit(budgetLimit) {
        this.budgetLimit = budgetLimit;
        this.budgetWarningIssued = false; // Reset warning flag
    }
    /**
     * Get budget limit
     * @returns Current budget limit
     */
    getBudgetLimit() {
        return this.budgetLimit;
    }
    /**
     * Reset all tracking data
     */
    reset() {
        this.requests = [];
        this.providerStats.clear();
        this.startTime = new Date();
        this.budgetWarningIssued = false;
    }
    /**
     * Print cost summary to console
     */
    printSummary() {
        const summary = this.getSummary();
        console.error('\n💰 Cost Summary:\n');
        console.error(`Total Requests: ${summary.totalRequests}`);
        console.error(`  Free: ${summary.freeRequests} | Paid: ${summary.paidRequests}`);
        console.error(`Total Tokens: ${summary.totalTokens.toLocaleString()}`);
        console.error(`  Input: ${summary.totalInputTokens.toLocaleString()} | Output: ${summary.totalOutputTokens.toLocaleString()}`);
        console.error(`Total Cost: ${formatCost(summary.totalCost)}\n`);
        if (summary.providerStats.size > 0) {
            console.error('📊 Per-Provider Breakdown:\n');
            for (const [provider, stats] of summary.providerStats.entries()) {
                console.error(`${provider.toUpperCase()}:`);
                console.error(`  Requests: ${stats.requests}`);
                console.error(`  Tokens: ${stats.totalTokens.toLocaleString()} (avg: ${Math.round(stats.averageTokensPerRequest)}/request)`);
                console.error(`  Cost: ${formatCost(stats.totalCost)} ${stats.isFree ? '(FREE)' : `(avg: ${formatCost(stats.averageCostPerRequest)}/request)`}`);
                // Check daily limits for free providers
                if (stats.isFree) {
                    const limits = getDailyLimits(provider);
                    if (limits) {
                        if (limits.requests) {
                            const requestPercentage = (stats.requests / limits.requests) * 100;
                            console.error(`  Daily Limit: ${stats.requests}/${limits.requests.toLocaleString()} requests (${requestPercentage.toFixed(1)}%)`);
                        }
                        if (limits.tokens) {
                            const tokenPercentage = (stats.totalTokens / limits.tokens) * 100;
                            console.error(`  Token Limit: ${stats.totalTokens.toLocaleString()}/${limits.tokens.toLocaleString()} tokens (${tokenPercentage.toFixed(1)}%)`);
                        }
                    }
                }
                console.error('');
            }
        }
        // Print budget status if configured
        if (this.budgetLimit) {
            const budgetStatus = this.checkBudget();
            console.error('🎯 Budget Status:\n');
            if (budgetStatus.costLimit !== undefined) {
                console.error(`  Cost: ${formatCost(budgetStatus.currentCost)} / ${formatCost(budgetStatus.costLimit)} (${((budgetStatus.costPercentage ?? 0) * 100).toFixed(1)}%)`);
            }
            if (budgetStatus.tokenLimit !== undefined) {
                console.error(`  Tokens: ${budgetStatus.currentTokens.toLocaleString()} / ${budgetStatus.tokenLimit.toLocaleString()} (${((budgetStatus.tokenPercentage ?? 0) * 100).toFixed(1)}%)`);
            }
            if (budgetStatus.requestLimit !== undefined) {
                console.error(`  Requests: ${budgetStatus.currentRequests} / ${budgetStatus.requestLimit} (${((budgetStatus.requestPercentage ?? 0) * 100).toFixed(1)}%)`);
            }
            if (budgetStatus.message) {
                console.error(`  ${budgetStatus.message}`);
            }
            console.error('');
        }
        const duration = summary.endTime
            ? (summary.endTime.getTime() - summary.startTime.getTime()) / 1000
            : 0;
        console.error(`⏱️  Session Duration: ${Math.round(duration)}s\n`);
    }
    /**
     * Export cost data to JSON
     * @returns JSON string with cost data
     */
    exportToJSON() {
        const summary = this.getSummary();
        return JSON.stringify({
            summary: {
                totalRequests: summary.totalRequests,
                totalTokens: summary.totalTokens,
                totalInputTokens: summary.totalInputTokens,
                totalOutputTokens: summary.totalOutputTokens,
                totalCost: summary.totalCost,
                freeRequests: summary.freeRequests,
                paidRequests: summary.paidRequests,
                startTime: summary.startTime,
                endTime: summary.endTime,
            },
            providerStats: Array.from(summary.providerStats.entries()).map(([_, stats]) => stats),
            budgetLimit: this.budgetLimit,
            budgetStatus: this.checkBudget(),
            requests: this.requests,
        }, null, 2);
    }
}
//# sourceMappingURL=cost-tracker.js.map