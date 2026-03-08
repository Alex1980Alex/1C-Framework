import { ReasoningRequest, ReasoningResponse } from '../types.js';
import { BaseStrategy, StrategyMetrics } from './base.js';
import { StateManager } from '../state.js';
interface BSLSubsystemMetrics extends StrategyMetrics {
    subsystemsMapping: number;
    crossSubsystemDependencies: number;
    securityViolations: number;
    integrationPoints: number;
}
export declare class BSLSubsystemAnalyzer extends BaseStrategy {
    private subsystemsMapping;
    private crossSubsystemDependencies;
    private securityViolations;
    private integrationPoints;
    constructor(stateManager: StateManager);
    processThought(request: ReasoningRequest): Promise<ReasoningResponse>;
    private generateSubsystemThought;
    private analyzeSubsystemStructure;
    private analyzeCrossSubsystemDependencies;
    private analyzeSecurityAndAccess;
    private analyzeIntegrationPatterns;
    private analyzeDataFlows;
    private generateSubsystemRecommendations;
    private evaluateBSLSubsystemAnalysis;
    private generateNodeId;
    getMetrics(): Promise<BSLSubsystemMetrics>;
    clear(): Promise<void>;
}
export {};
