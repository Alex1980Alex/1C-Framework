import { StateManager } from '../state.js';
import { BaseStrategy } from './base.js';
export declare enum ReasoningStrategy {
    BEAM_SEARCH = "beam_search",
    MCTS = "mcts",
    MCTS_002_ALPHA = "mcts_002_alpha",
    MCTS_002_ALT_ALPHA = "mcts_002_alt_alpha",
    BSL_ARCHITECTURE = "bsl_architecture",
    BSL_DOCUMENT_PATTERNS = "bsl_document_patterns",
    BSL_SUBSYSTEM_ANALYSIS = "bsl_subsystem_analysis"
}
export declare class StrategyFactory {
    static createStrategy(type: ReasoningStrategy, stateManager: StateManager, beamWidth?: number, numSimulations?: number): BaseStrategy;
}
