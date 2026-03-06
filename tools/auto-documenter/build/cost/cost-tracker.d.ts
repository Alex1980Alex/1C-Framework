import { Provider } from './pricing-config.js';
/**
 * Cost tracking for a single request
 */
export interface RequestCost {
    timestamp: Date;
    provider: Provider;
    model: string;
    inputTokens: number;
    outputTokens: number;
    totalTokens: number;
    cost: number;
    isFree: boolean;
}
/**
 * Aggregated cost statistics per provider
 */
export interface ProviderCostStats {
    provider: Provider;
    requests: number;
    totalTokens: number;
    inputTokens: number;
    outputTokens: number;
    totalCost: number;
    isFree: boolean;
    averageCostPerRequest: number;
    averageTokensPerRequest: number;
    firstRequest?: Date;
    lastRequest?: Date;
}
/**
 * Session cost summary
 */
export interface CostSummary {
    totalRequests: number;
    totalTokens: number;
    totalInputTokens: number;
    totalOutputTokens: number;
    totalCost: number;
    freeRequests: number;
    paidRequests: number;
    providerStats: Map<Provider, ProviderCostStats>;
    startTime: Date;
    endTime?: Date;
}
/**
 * Budget limit configuration
 */
export interface BudgetLimit {
    maxCost?: number;
    maxTokens?: number;
    maxRequests?: number;
    warningThreshold?: number;
}
/**
 * Budget status
 */
export interface BudgetStatus {
    exceeded: boolean;
    warningTriggered: boolean;
    currentCost: number;
    costLimit?: number;
    costPercentage?: number;
    currentTokens: number;
    tokenLimit?: number;
    tokenPercentage?: number;
    currentRequests: number;
    requestLimit?: number;
    requestPercentage?: number;
    message?: string;
}
/**
 * Cost tracker for monitoring LLM API costs
 * Tracks per-request costs and provides aggregated statistics
 */
export declare class CostTracker {
    private requests;
    private providerStats;
    private startTime;
    private budgetLimit?;
    private budgetWarningIssued;
    constructor(budgetLimit?: BudgetLimit);
    /**
     * Record a request and its cost
     * @param provider Provider name
     * @param model Model name
     * @param inputTokens Input tokens count
     * @param outputTokens Output tokens count
     * @returns Request cost information
     */
    recordRequest(provider: Provider, model: string, inputTokens: number, outputTokens: number): RequestCost;
    /**
     * Update aggregated statistics for a provider
     */
    private updateProviderStats;
    /**
     * Get cost summary for the session
     * @returns Cost summary
     */
    getSummary(): CostSummary;
    /**
     * Get statistics for a specific provider
     * @param provider Provider name
     * @returns Provider statistics or undefined
     */
    getProviderStats(provider: Provider): ProviderCostStats | undefined;
    /**
     * Check budget status
     * @returns Budget status
     */
    checkBudget(): BudgetStatus;
    /**
     * Set or update budget limit
     * @param budgetLimit New budget limit
     */
    setBudgetLimit(budgetLimit: BudgetLimit): void;
    /**
     * Get budget limit
     * @returns Current budget limit
     */
    getBudgetLimit(): BudgetLimit | undefined;
    /**
     * Reset all tracking data
     */
    reset(): void;
    /**
     * Print cost summary to console
     */
    printSummary(): void;
    /**
     * Export cost data to JSON
     * @returns JSON string with cost data
     */
    exportToJSON(): string;
}
