class LRUCache {
    constructor(maxSize) {
        this.cache = new Map();
        this.maxSize = maxSize;
    }
    get(key) {
        const value = this.cache.get(key);
        if (value) {
            // Refresh by removing and re-adding
            this.cache.delete(key);
            this.cache.set(key, value);
        }
        return value;
    }
    set(key, value) {
        // Remove oldest if at capacity
        if (this.cache.size >= this.maxSize) {
            const firstKey = Array.from(this.cache.keys())[0];
            if (firstKey !== undefined) {
                this.cache.delete(firstKey);
            }
        }
        // Add new value
        this.cache.set(key, value);
    }
    clear() {
        this.cache.clear();
    }
    size() {
        return this.cache.size;
    }
    has(key) {
        return this.cache.has(key);
    }
}
export class StateManager {
    constructor(cacheSize) {
        this.nodes = new Map();
        this.cache = new LRUCache(cacheSize);
    }
    async getNode(id) {
        // Check cache first
        const cached = this.cache.get(id);
        if (cached)
            return cached;
        // Check main storage
        const node = this.nodes.get(id);
        if (node) {
            this.cache.set(id, node);
            return node;
        }
        return undefined;
    }
    async saveNode(node) {
        this.nodes.set(node.id, node);
        this.cache.set(node.id, node);
    }
    async getChildren(nodeId) {
        const node = await this.getNode(nodeId);
        if (!node)
            return [];
        const children = await Promise.all(node.children.map(id => this.getNode(id)));
        return children.filter((n) => n !== undefined);
    }
    async getPath(nodeId) {
        const path = [];
        let currentId = nodeId;
        while (currentId) {
            const node = await this.getNode(currentId);
            if (!node)
                break;
            path.unshift(node);
            currentId = node.parentId || '';
        }
        return path;
    }
    async getAllNodes() {
        return Array.from(this.nodes.values());
    }
    async getNodeCount() {
        return this.nodes.size;
    }
    clear() {
        this.nodes.clear();
        this.cache.clear();
    }
}
