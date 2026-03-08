import { StateManager } from '../state.js';
import { BaseStrategy } from './base.js';
import { BeamSearchStrategy } from './beam-search.js';
import { MonteCarloTreeSearchStrategy } from './mcts.js';
import { MCTS002AlphaStrategy } from './experiments/mcts-002-alpha.js';
import { MCTS002AltAlphaStrategy } from './experiments/mcts-002alt-alpha.js';
import { BSLArchitectureAnalyzer } from './bsl-architecture-analyzer.js';
import { BSLDocumentPatternAnalyzer } from './bsl-document-patterns.js';
import { BSLSubsystemAnalyzer } from './bsl-subsystem-analyzer.js';

export enum ReasoningStrategy {
  BEAM_SEARCH = 'beam_search',
  MCTS = 'mcts',
  MCTS_002_ALPHA = 'mcts_002_alpha',
  MCTS_002_ALT_ALPHA = 'mcts_002_alt_alpha',
  BSL_ARCHITECTURE = 'bsl_architecture',
  BSL_DOCUMENT_PATTERNS = 'bsl_document_patterns',
  BSL_SUBSYSTEM_ANALYSIS = 'bsl_subsystem_analysis'
}

export class StrategyFactory {
  static createStrategy(
    type: ReasoningStrategy,
    stateManager: StateManager,
    beamWidth?: number,
    numSimulations?: number
  ): BaseStrategy {
    switch (type) {
      case ReasoningStrategy.BEAM_SEARCH:
        return new BeamSearchStrategy(stateManager, beamWidth);
      case ReasoningStrategy.MCTS:
        return new MonteCarloTreeSearchStrategy(stateManager, numSimulations);
      case ReasoningStrategy.MCTS_002_ALPHA:
        return new MCTS002AlphaStrategy(stateManager, numSimulations);
      case ReasoningStrategy.MCTS_002_ALT_ALPHA:
        return new MCTS002AltAlphaStrategy(stateManager, numSimulations);
      case ReasoningStrategy.BSL_ARCHITECTURE:
        return new BSLArchitectureAnalyzer(stateManager);
      case ReasoningStrategy.BSL_DOCUMENT_PATTERNS:
        return new BSLDocumentPatternAnalyzer(stateManager);
      case ReasoningStrategy.BSL_SUBSYSTEM_ANALYSIS:
        return new BSLSubsystemAnalyzer(stateManager);
      default:
        throw new Error(`Unknown strategy type: ${type}`);
    }
  }
}
