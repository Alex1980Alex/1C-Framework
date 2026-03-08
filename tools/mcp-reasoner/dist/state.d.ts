import { ThoughtNode } from './types.js';
export declare class StateManager {
    private cache;
    private nodes;
    constructor(cacheSize: number);
    getNode(id: string): Promise<ThoughtNode | undefined>;
    saveNode(node: ThoughtNode): Promise<void>;
    getChildren(nodeId: string): Promise<ThoughtNode[]>;
    getPath(nodeId: string): Promise<ThoughtNode[]>;
    getAllNodes(): Promise<ThoughtNode[]>;
    getNodeCount(): Promise<number>;
    clear(): void;
}
