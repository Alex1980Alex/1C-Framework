import { ReasoningRequest, ReasoningResponse } from '../types.js';
import { BaseStrategy, StrategyMetrics } from './base.js';
import { StateManager } from '../state.js';
interface BSLDocumentMetrics extends StrategyMetrics {
    documentsAnalyzed: number;
    postingAlgorithmsChecked: number;
    businessLogicPatterns: number;
    performanceIssues: number;
}
export declare class BSLDocumentPatternAnalyzer extends BaseStrategy {
    private documentsAnalyzed;
    private postingAlgorithmsChecked;
    private businessLogicPatterns;
    private performanceIssues;
    constructor(stateManager: StateManager);
    processThought(request: ReasoningRequest): Promise<ReasoningResponse>;
    private generateDocumentPatternThought;
    private analyzeDocumentStructure;
    private analyzePostingAlgorithms;
    private analyzeBusinessLogicPatterns;
    private analyzePerformancePatterns;
    private generateDocumentRecommendations;
    private evaluateBSLDocumentPatterns;
    private generateNodeId;
    getMetrics(): Promise<BSLDocumentMetrics>;
    clear(): Promise<void>;
}
export {};
