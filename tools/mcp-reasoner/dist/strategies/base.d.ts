import { ThoughtNode, ReasoningRequest, ReasoningResponse } from '../types.js';
import { StateManager } from '../state.js';
export interface StrategyMetrics {
    name: string;
    nodesExplored: number;
    averageScore: number;
    maxDepth: number;
    active?: boolean;
    [key: string]: number | string | boolean | undefined;
}
export declare abstract class BaseStrategy {
    protected stateManager: StateManager;
    constructor(stateManager: StateManager);
    abstract processThought(request: ReasoningRequest): Promise<ReasoningResponse>;
    protected getNode(id: string): Promise<ThoughtNode | undefined>;
    protected saveNode(node: ThoughtNode): Promise<void>;
    protected evaluateThought(node: ThoughtNode, parent?: ThoughtNode): number;
    private calculateLogicalScore;
    private calculateDepthPenalty;
    private calculateCoherence;
    getBestPath(): Promise<ThoughtNode[]>;
    getMetrics(): Promise<StrategyMetrics>;
    clear(): Promise<void>;
}
