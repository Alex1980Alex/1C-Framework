export class BaseStrategy {
    constructor(stateManager) {
        this.stateManager = stateManager;
    }
    async getNode(id) {
        return this.stateManager.getNode(id);
    }
    async saveNode(node) {
        return this.stateManager.saveNode(node);
    }
    evaluateThought(node, parent) {
        // Base evaluation logic
        const logicalScore = this.calculateLogicalScore(node, parent);
        const depthPenalty = this.calculateDepthPenalty(node);
        const completionBonus = node.isComplete ? 0.2 : 0;
        return (logicalScore + depthPenalty + completionBonus) / 3;
    }
    calculateLogicalScore(node, parent) {
        let score = 0;
        // Length and complexity
        score += Math.min(node.thought.length / 200, 0.3);
        // Logical connectors
        if (/\b(therefore|because|if|then|thus|hence|so)\b/i.test(node.thought)) {
            score += 0.2;
        }
        // Mathematical/logical expressions
        if (/[+\-*/=<>]/.test(node.thought)) {
            score += 0.2;
        }
        // Parent-child coherence
        if (parent) {
            const coherence = this.calculateCoherence(parent.thought, node.thought);
            score += coherence * 0.3;
        }
        return score;
    }
    calculateDepthPenalty(node) {
        return Math.max(0, 1 - (node.depth / 10) * 0.3);
    }
    calculateCoherence(parentThought, childThought) {
        // Simple coherence based on shared terms
        const parentTerms = new Set(parentThought.toLowerCase().split(/\W+/));
        const childTerms = childThought.toLowerCase().split(/\W+/);
        const sharedTerms = childTerms.filter(term => parentTerms.has(term)).length;
        return Math.min(sharedTerms / childTerms.length, 1);
    }
    // Required methods for all strategies
    async getBestPath() {
        const nodes = await this.stateManager.getAllNodes();
        if (nodes.length === 0)
            return [];
        // Default implementation - find highest scoring complete path
        const completedNodes = nodes.filter(n => n.isComplete)
            .sort((a, b) => b.score - a.score);
        if (completedNodes.length === 0)
            return [];
        return this.stateManager.getPath(completedNodes[0].id);
    }
    async getMetrics() {
        const nodes = await this.stateManager.getAllNodes();
        return {
            name: this.constructor.name,
            nodesExplored: nodes.length,
            averageScore: nodes.length > 0
                ? nodes.reduce((sum, n) => sum + n.score, 0) / nodes.length
                : 0,
            maxDepth: nodes.length > 0
                ? Math.max(...nodes.map(n => n.depth))
                : 0
        };
    }
    async clear() {
        // Optional cleanup method for strategies
        // Default implementation does nothing
    }
}
