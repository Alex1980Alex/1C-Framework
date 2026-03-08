import { ReasoningRequest, ReasoningResponse } from '../../types.js';
import { MCTS002AlphaStrategy } from './mcts-002-alpha.js';
export declare class MCTS002AltAlphaStrategy extends MCTS002AlphaStrategy {
    private startNode;
    private goalNode;
    private bidirectionalStats;
    constructor(stateManager: any, numSimulations?: number);
    processThought(request: ReasoningRequest): Promise<ReasoningResponse>;
    protected getActionKey(thought: string): string;
    private searchLevel;
    private bidirectionalSearch;
    private reconstructPath;
    private updatePathWithPolicyGuidance;
    private adaptBidirectionalExploration;
    private updateBidirectionalStats;
    private calculateBidirectionalPolicyScore;
    getMetrics(): Promise<any>;
    clear(): Promise<void>;
}
