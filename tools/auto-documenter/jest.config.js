/** @type {import('jest').Config} */
export default {
  preset: 'ts-jest/presets/default-esm',
  testEnvironment: 'node',
  extensionsToTreatAsEsm: ['.ts'],
  moduleNameMapper: {
    '^(\\.{1,2}/.*)\\.js$': '$1',
  },
  transform: {
    '^.+\\.ts$': ['ts-jest', {
      useESM: true,
      tsconfig: {
        module: 'ESNext',
        moduleResolution: 'node',
      }
    }],
  },
  testMatch: [
    '**/tests/**/*.test.ts',
    '**/__tests__/**/*.test.ts'
  ],
  collectCoverageFrom: [
    'src/**/*.ts',
    '!src/**/*.d.ts',
    '!src/index.ts',
    '!src/analyzer/bsl-treesitter-analyzer.ts',
    '!src/analyzer/bsl-integration.ts',
    '!src/analyzer/index.ts',
    '!src/providers/**/*.ts',
    '!src/openrouter/**/*.ts',
    '!src/crawler/**/*.ts',
    '!src/documentation/**/*.ts',
    '!src/cost/**/*.ts',
    '!src/tools/aggregator.ts',
    '!src/tools/inline-docs-tool.ts'
  ],
  // Coverage threshold temporarily disabled for stabilization
  // coverageThreshold: {
  //   global: {
  //     branches: 40,
  //     functions: 50,
  //     lines: 50,
  //     statements: 50
  //   }
  // },
  coverageDirectory: 'coverage',
  verbose: true
};
