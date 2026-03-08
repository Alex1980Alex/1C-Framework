import { ReasoningRequest, ReasoningResponse } from '../../types.js';
import { MonteCarloTreeSearchStrategy } from '../mcts.js';
export declare class MCTS002AlphaStrategy extends MonteCarloTreeSearchStrategy {
    private readonly temperature;
    private explorationRate;
    private readonly learningRate;
    private readonly noveltyBonus;
    private policyMetrics;
    protected readonly simulationCount: number;
    constructor(stateManager: any, numSimulations?: number);
    private initializePolicyMetrics;
    processThought(request: ReasoningRequest): Promise<ReasoningResponse>;
    private extractAction;
    private calculatePolicyScore;
    private estimateValue;
    private calculateNovelty;
    private thoughtCoherence;
    private runPolicyGuidedSearch;
    private selectWithPUCT;
    private selectBestPUCTChild;
    private expandWithPolicy;
    private simulateWithValueGuidance;
    private backpropagateWithPolicyUpdate;
    private adaptExplorationRate;
    private updatePolicyMetrics;
    private calculateEntropy;
    private calculatePolicyEnhancedScore;
    getMetrics(): Promise<any>;
}
