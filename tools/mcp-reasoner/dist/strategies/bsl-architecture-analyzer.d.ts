import { ReasoningRequest, ReasoningResponse } from '../types.js';
import { BaseStrategy, StrategyMetrics } from './base.js';
import { StateManager } from '../state.js';
interface BSLArchitectureMetrics extends StrategyMetrics {
    subsystemsAnalyzed: number;
    dependencyIssues: number;
    architecturalPatterns: number;
    complexityScore: number;
}
export declare class BSLArchitectureAnalyzer extends BaseStrategy {
    private subsystemsAnalyzed;
    private dependencyIssues;
    private architecturalPatterns;
    private complexityScore;
    constructor(stateManager: StateManager);
    processThought(request: ReasoningRequest): Promise<ReasoningResponse>;
    private generateArchitectureThought;
    private generateSubsystemAnalysis;
    private generateDependencyAnalysis;
    private generatePatternAnalysis;
    private generateArchitectureRecommendations;
    private evaluateBSLArchitecture;
    private generateNodeId;
    getMetrics(): Promise<BSLArchitectureMetrics>;
    clear(): Promise<void>;
}
export {};
