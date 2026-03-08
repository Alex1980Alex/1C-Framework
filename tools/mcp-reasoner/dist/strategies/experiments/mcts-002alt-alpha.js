import { v4 as uuidv4 } from 'uuid';
import { CONFIG } from '../../types.js';
import { MCTS002AlphaStrategy } from './mcts-002-alpha.js';
// Queue implementation for bidirectional search
class Queue {
    constructor() {
        this.items = [];
    }
    enqueue(item) {
        this.items.push(item);
    }
    dequeue() {
        return this.items.shift();
    }
    isEmpty() {
        return this.items.length === 0;
    }
    size() {
        return this.items.length;
    }
}
export class MCTS002AltAlphaStrategy extends MCTS002AlphaStrategy {
    constructor(stateManager, numSimulations = CONFIG.numSimulations) {
        super(stateManager, numSimulations);
        this.startNode = null;
        this.goalNode = null;
        this.bidirectionalStats = {
            forwardExplorationRate: Math.sqrt(2),
            backwardExplorationRate: Math.sqrt(2),
            meetingPoints: 0,
            pathQuality: 0
        };
    }
    async processThought(request) {
        // Get base response first to ensure proper MCTS initialization
        const baseResponse = await super.processThought(request);
        const nodeId = uuidv4();
        const parentNode = request.parentId ?
            await this.getNode(request.parentId) : undefined;
        const node = {
            id: nodeId,
            thought: request.thought,
            depth: request.thoughtNumber - 1,
            score: 0,
            children: [],
            parentId: request.parentId,
            isComplete: !request.nextThoughtNeeded,
            visits: 0,
            totalReward: 0,
            untriedActions: [],
            g: parentNode ? parentNode.g + 1 : 0,
            h: 0,
            f: 0,
            policyScore: 0,
            valueEstimate: 0,
            priorActionProbs: new Map(),
            actionHistory: parentNode ?
                [...(parentNode.actionHistory || []), this.getActionKey(request.thought)] :
                [this.getActionKey(request.thought)],
            searchDepth: 0,
            direction: parentNode ? parentNode.direction : 'forward'
        };
        // Track start and goal nodes for bidirectional search
        if (!parentNode) {
            this.startNode = node;
            node.direction = 'forward';
        }
        if (node.isComplete) {
            this.goalNode = node;
            node.direction = 'backward';
        }
        // Run bidirectional search if we have both endpoints
        if (this.startNode && this.goalNode) {
            const path = await this.bidirectionalSearch(this.startNode, this.goalNode);
            if (path.length > 0) {
                await this.updatePathWithPolicyGuidance(path);
            }
        }
        // Calculate enhanced path statistics
        const currentPath = await this.stateManager.getPath(nodeId);
        const enhancedScore = this.calculateBidirectionalPolicyScore(currentPath);
        return {
            ...baseResponse,
            score: enhancedScore,
            bestScore: Math.max(baseResponse.bestScore || 0, enhancedScore)
        };
    }
    getActionKey(thought) {
        // Simple action extraction based on first few words
        return thought.split(/\s+/).slice(0, 3).join('_').toLowerCase();
    }
    async searchLevel(queue, visited, otherVisited, direction) {
        const levelSize = queue.size();
        for (let i = 0; i < levelSize; i++) {
            const current = queue.dequeue();
            if (!current)
                continue;
            // Check if we've found a meeting point
            if (otherVisited.has(current.id)) {
                current.meetingPoint = true;
                this.bidirectionalStats.meetingPoints++;
                await this.saveNode(current);
                return current;
            }
            // Get neighbors based on direction and policy scores
            const neighbors = direction === 'forward' ?
                await Promise.all(current.children.map(id => this.getNode(id))) :
                await Promise.all([current.parentId].filter((id) => !!id).map(id => this.getNode(id)));
            const validNeighbors = neighbors.filter((n) => !!n)
                .sort((a, b) => b.policyScore - a.policyScore); // Use policy scores for neighbor selection
            for (const neighbor of validNeighbors) {
                if (!visited.has(neighbor.id)) {
                    visited.set(neighbor.id, neighbor);
                    neighbor.parent = current.id;
                    neighbor.direction = direction;
                    neighbor.searchDepth = (current.searchDepth || 0) + 1;
                    await this.saveNode(neighbor);
                    queue.enqueue(neighbor);
                }
            }
        }
        return null;
    }
    async bidirectionalSearch(start, goal) {
        const forwardQueue = new Queue();
        const backwardQueue = new Queue();
        const forwardVisited = new Map();
        const backwardVisited = new Map();
        forwardQueue.enqueue(start);
        backwardQueue.enqueue(goal);
        forwardVisited.set(start.id, start);
        backwardVisited.set(goal.id, goal);
        while (!forwardQueue.isEmpty() && !backwardQueue.isEmpty()) {
            // Search from both directions with policy guidance
            const meetingPoint = await this.searchLevel(forwardQueue, forwardVisited, backwardVisited, 'forward');
            if (meetingPoint) {
                const path = this.reconstructPath(meetingPoint, forwardVisited, backwardVisited);
                this.updateBidirectionalStats(path);
                return path;
            }
            const backMeetingPoint = await this.searchLevel(backwardQueue, backwardVisited, forwardVisited, 'backward');
            if (backMeetingPoint) {
                const path = this.reconstructPath(backMeetingPoint, forwardVisited, backwardVisited);
                this.updateBidirectionalStats(path);
                return path;
            }
            // Adapt exploration rates based on progress
            this.adaptBidirectionalExploration(forwardVisited, backwardVisited);
        }
        return [];
    }
    reconstructPath(meetingPoint, forwardVisited, backwardVisited) {
        const path = [meetingPoint];
        // Reconstruct forward path
        let current = meetingPoint;
        while (current.parent && forwardVisited.has(current.parent)) {
            current = forwardVisited.get(current.parent);
            path.unshift(current);
        }
        // Reconstruct backward path
        current = meetingPoint;
        while (current.parent && backwardVisited.has(current.parent)) {
            current = backwardVisited.get(current.parent);
            path.push(current);
        }
        return path;
    }
    async updatePathWithPolicyGuidance(path) {
        const pathBonus = 0.2;
        for (const node of path) {
            // Boost both policy and value estimates for nodes along the path
            node.policyScore += pathBonus;
            node.valueEstimate = (node.valueEstimate + 1) / 2;
            // Update action probabilities with path information
            if (node.parentId) {
                const parentNode = await this.getNode(node.parentId);
                const actionKey = this.getActionKey(node.thought);
                const currentProb = parentNode.priorActionProbs.get(actionKey) || 0;
                const newProb = Math.max(currentProb, 0.8); // Strong preference for path actions
                parentNode.priorActionProbs.set(actionKey, newProb);
                await this.saveNode(parentNode);
            }
            await this.saveNode(node);
        }
        // Update path quality metric
        this.bidirectionalStats.pathQuality = path.reduce((acc, node) => acc + node.policyScore + node.valueEstimate, 0) / (path.length * 2);
    }
    adaptBidirectionalExploration(forwardVisited, backwardVisited) {
        // Adjust exploration rates based on search progress
        const forwardProgress = Array.from(forwardVisited.values())
            .reduce((acc, node) => acc + node.policyScore, 0) / forwardVisited.size;
        const backwardProgress = Array.from(backwardVisited.values())
            .reduce((acc, node) => acc + node.policyScore, 0) / backwardVisited.size;
        // Increase exploration in the direction making less progress
        if (forwardProgress > backwardProgress) {
            this.bidirectionalStats.backwardExplorationRate *= 1.05;
            this.bidirectionalStats.forwardExplorationRate *= 0.95;
        }
        else {
            this.bidirectionalStats.forwardExplorationRate *= 1.05;
            this.bidirectionalStats.backwardExplorationRate *= 0.95;
        }
    }
    updateBidirectionalStats(path) {
        const forwardNodes = path.filter(n => n.direction === 'forward');
        const backwardNodes = path.filter(n => n.direction === 'backward');
        // Update exploration rates based on path composition
        const forwardQuality = forwardNodes.reduce((acc, n) => acc + n.policyScore, 0) / forwardNodes.length;
        const backwardQuality = backwardNodes.reduce((acc, n) => acc + n.policyScore, 0) / backwardNodes.length;
        this.bidirectionalStats.pathQuality = (forwardQuality + backwardQuality) / 2;
    }
    calculateBidirectionalPolicyScore(path) {
        if (path.length === 0)
            return 0;
        return path.reduce((acc, node) => {
            const biNode = node;
            const baseScore = node.score;
            const policyBonus = biNode.policyScore || 0;
            const valueBonus = biNode.valueEstimate || 0;
            const meetingPointBonus = biNode.meetingPoint ? 0.2 : 0;
            const directionBonus = biNode.direction === 'forward' ?
                this.bidirectionalStats.forwardExplorationRate * 0.1 :
                this.bidirectionalStats.backwardExplorationRate * 0.1;
            return acc + (baseScore +
                policyBonus +
                valueBonus +
                meetingPointBonus +
                directionBonus) / 5;
        }, 0) / path.length;
    }
    async getMetrics() {
        const baseMetrics = await super.getMetrics();
        const nodes = await this.stateManager.getAllNodes();
        const forwardNodes = nodes.filter(n => n.direction === 'forward');
        const backwardNodes = nodes.filter(n => n.direction === 'backward');
        const meetingPoints = nodes.filter(n => n.meetingPoint);
        const bidirectionalMetrics = {
            forwardSearch: {
                nodesExplored: forwardNodes.length,
                averagePolicyScore: forwardNodes.reduce((sum, n) => sum + n.policyScore, 0) / forwardNodes.length,
                explorationRate: this.bidirectionalStats.forwardExplorationRate
            },
            backwardSearch: {
                nodesExplored: backwardNodes.length,
                averagePolicyScore: backwardNodes.reduce((sum, n) => sum + n.policyScore, 0) / backwardNodes.length,
                explorationRate: this.bidirectionalStats.backwardExplorationRate
            },
            meetingPoints: {
                count: this.bidirectionalStats.meetingPoints,
                averageDepth: meetingPoints.reduce((sum, n) => sum + n.depth, 0) / (meetingPoints.length || 1)
            },
            pathQuality: this.bidirectionalStats.pathQuality
        };
        return {
            ...baseMetrics,
            name: 'MCTS-002Alt-Alpha (Bidirectional + Policy Enhanced)',
            hasStartNode: !!this.startNode,
            hasGoalNode: !!this.goalNode,
            bidirectionalMetrics
        };
    }
    async clear() {
        await super.clear();
        this.startNode = null;
        this.goalNode = null;
        this.bidirectionalStats = {
            forwardExplorationRate: Math.sqrt(2),
            backwardExplorationRate: Math.sqrt(2),
            meetingPoints: 0,
            pathQuality: 0
        };
    }
}
