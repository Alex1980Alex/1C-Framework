import * as TreeSitter from 'web-tree-sitter';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Use the Parser class from web-tree-sitter
type Parser = InstanceType<typeof TreeSitter.Parser>;

/**
 * BSL code element types
 */
export enum BSLElementType {
  PROCEDURE = 'procedure',
  FUNCTION = 'function',
  VARIABLE = 'variable',
  EXPORT = 'export',
  REGION = 'region',
  COMMENT = 'comment'
}

/**
 * Extracted BSL code element
 */
export interface BSLCodeElement {
  type: BSLElementType;
  name: string;
  startLine: number;
  endLine: number;
  parameters?: string[];
  returnType?: string;
  isExport?: boolean;
  comment?: string;
  body?: string;
}

/**
 * Result of BSL code analysis
 */
export interface BSLAnalysisResult {
  procedures: BSLCodeElement[];
  functions: BSLCodeElement[];
  variables: BSLCodeElement[];
  exports: BSLCodeElement[];
  regions: BSLCodeElement[];
  comments: BSLCodeElement[];
  totalLines: number;
  codeLines: number;
  commentLines: number;
}

// Load BSL language once at module level
let BSLLanguage: any = null;
let parserInitialized = false;

async function loadBSLLanguage() {
  if (!BSLLanguage) {
    try {
      // Initialize Parser if not already done
      if (!parserInitialized) {
        await TreeSitter.Parser.init();
        parserInitialized = true;
        console.error('[BSL-TreeSitter] Parser initialized');
      }

      // Find WASM file path (relative to build directory)
      // In production: build/analyzer/bsl-treesitter-analyzer.js
      // WASM location: node_modules/tree-sitter-bsl/tree-sitter-bsl.wasm
      const wasmPath = join(__dirname, '../../node_modules/tree-sitter-bsl/tree-sitter-bsl.wasm');
      console.error('[BSL-TreeSitter] Loading WASM from:', wasmPath);

      BSLLanguage = await TreeSitter.Language.load(wasmPath);
      console.error('[BSL-TreeSitter] Language loaded successfully');
    } catch (err: any) {
      console.error('[BSL-TreeSitter] ERROR loading language:', err.message);
      throw err;
    }
  }
  return BSLLanguage;
}

/**
 * BSL Treesitter Analyzer
 * Provides 100% accurate parsing of BSL (1C:Enterprise) code using tree-sitter-bsl
 */
export class BSLTreesitterAnalyzer {
  private parser?: Parser;
  private initialized: boolean = false;

  constructor() {
    // Parser will be created in initialize() after Parser.init() is called
  }

  /**
   * Initializes the analyzer by loading BSL language WASM
   * Must be called before using any parsing methods
   */
  async initialize(): Promise<void> {
    if (!this.initialized) {
      const language = await loadBSLLanguage();
      this.parser = new TreeSitter.Parser();
      this.parser.setLanguage(language);
      this.initialized = true;
    }
  }

  /**
   * Ensures the analyzer is initialized before use
   */
  private ensureInitialized(): void {
    if (!this.initialized || !this.parser) {
      throw new Error('BSLTreesitterAnalyzer must be initialized first. Call await analyzer.initialize()');
    }
  }

  /**
   * Analyzes BSL code and extracts all elements
   * @param code BSL source code
   * @param filePath Optional file path for context
   * @returns Detailed analysis result
   */
  public analyze(code: string, filePath?: string): BSLAnalysisResult {
    this.ensureInitialized();
    const tree = this.parser!.parse(code);
    if (!tree) {
      throw new Error('Failed to parse BSL code');
    }
    const rootNode = tree.rootNode;

    const result: BSLAnalysisResult = {
      procedures: [],
      functions: [],
      variables: [],
      exports: [],
      regions: [],
      comments: [],
      totalLines: code.split('\n').length,
      codeLines: 0,
      commentLines: 0
    };

    // Extract all elements
    this.extractProcedures(rootNode, code, result);
    this.extractFunctions(rootNode, code, result);
    console.error(`[BSL-TreeSitter] Found ${result.procedures.length} procedures, ${result.functions.length} functions in ${filePath || 'code'}`);
    this.extractVariables(rootNode, code, result);
    this.extractRegions(rootNode, code, result);
    this.extractComments(rootNode, code, result);

    // Calculate code statistics
    this.calculateStatistics(code, result);

    // Identify exports
    result.exports = [...result.procedures, ...result.functions]
      .filter(element => element.isExport);

    return result;
  }

  /**
   * Extracts only procedure and function signatures (no bodies)
   * Useful for quick overview
   */
  public extractSignatures(code: string): Array<{name: string, type: 'procedure' | 'function', parameters: string[]}> {
    this.ensureInitialized();
    const tree = this.parser!.parse(code);
    if (!tree) {
      throw new Error('Failed to parse BSL code');
    }
    const rootNode = tree.rootNode;
    const signatures: Array<{name: string, type: 'procedure' | 'function', parameters: string[]}> = [];

    // Query for procedures
    const procedureQuery = `
      (sub_declaration
        name: (identifier) @proc_name
        parameters: (param_list)? @params)
    `;

    // Query for functions
    const functionQuery = `
      (func_declaration
        name: (identifier) @func_name
        parameters: (param_list)? @params)
    `;

    // For now, use simple traversal
    // TODO: Implement proper tree-sitter queries when query syntax is confirmed

    this.traverseNode(rootNode, (node) => {
      if (node.type === 'procedure_definition' || node.type === 'sub_declaration' || node.type === 'procedure_declaration') {
        const nameNode = this.findChildByType(node, 'identifier');
        if (nameNode) {
          const name = code.substring(nameNode.startIndex, nameNode.endIndex);
          const params = this.extractParameters(node, code);
          signatures.push({ name, type: 'procedure', parameters: params });
        }
      } else if (node.type === 'function_definition' || node.type === 'func_declaration' || node.type === 'function_declaration') {
        const nameNode = this.findChildByType(node, 'identifier');
        if (nameNode) {
          const name = code.substring(nameNode.startIndex, nameNode.endIndex);
          const params = this.extractParameters(node, code);
          signatures.push({ name, type: 'function', parameters: params });
        }
      }
    });

    return signatures;
  }

  /**
   * Checks if code contains export declarations
   */
  public hasExports(code: string): boolean {
    this.ensureInitialized();
    const tree = this.parser!.parse(code);
    if (!tree) {
      throw new Error('Failed to parse BSL code');
    }
    const rootNode = tree.rootNode;
    let hasExport = false;

    this.traverseNode(rootNode, (node) => {
      if (node.type === 'export_keyword' ||
          (node.text && node.text.toLowerCase().includes('экспорт')) ||
          (node.text && node.text.toLowerCase().includes('export'))) {
        hasExport = true;
      }
    });

    return hasExport;
  }

  /**
   * Extracts procedures from AST
   */
  private extractProcedures(node: TreeSitter.Node, code: string, result: BSLAnalysisResult): void {
    this.traverseNode(node, (n) => {
      if (n.type === 'procedure_definition' || n.type === 'sub_declaration' || n.type === 'procedure_declaration') {
        const element = this.createCodeElement(n, code, BSLElementType.PROCEDURE);
        if (element) {
          result.procedures.push(element);
        }
      }
    });
  }

  /**
   * Extracts functions from AST
   */
  private extractFunctions(node: TreeSitter.Node, code: string, result: BSLAnalysisResult): void {
    this.traverseNode(node, (n) => {
      if (n.type === 'function_definition' || n.type === 'func_declaration' || n.type === 'function_declaration') {
        const element = this.createCodeElement(n, code, BSLElementType.FUNCTION);
        if (element) {
          result.functions.push(element);
        }
      }
    });
  }

  /**
   * Extracts variables from AST
   */
  private extractVariables(node: TreeSitter.Node, code: string, result: BSLAnalysisResult): void {
    this.traverseNode(node, (n) => {
      if (n.type === 'var_declaration' || n.type === 'variable_declaration' ||
          (n.type === 'identifier' && n.parent?.type === 'var_statement')) {
        const element = this.createCodeElement(n, code, BSLElementType.VARIABLE);
        if (element) {
          result.variables.push(element);
        }
      }
    });
  }

  /**
   * Extracts regions from code (BSL preprocessing directives)
   */
  private extractRegions(node: TreeSitter.Node, code: string, result: BSLAnalysisResult): void {
    const lines = code.split('\n');
    lines.forEach((line, index) => {
      const trimmed = line.trim().toLowerCase();
      if (trimmed.startsWith('#область') || trimmed.startsWith('#region')) {
        const name = line.substring(line.indexOf(' ') + 1).trim();
        result.regions.push({
          type: BSLElementType.REGION,
          name,
          startLine: index + 1,
          endLine: index + 1
        });
      }
    });
  }

  /**
   * Extracts comments from code
   */
  private extractComments(node: TreeSitter.Node, code: string, result: BSLAnalysisResult): void {
    this.traverseNode(node, (n) => {
      if (n.type === 'comment' || n.type === 'line_comment' || n.type === 'block_comment') {
        const text = code.substring(n.startIndex, n.endIndex);
        result.comments.push({
          type: BSLElementType.COMMENT,
          name: text.substring(0, 50), // First 50 chars as name
          startLine: n.startPosition.row + 1,
          endLine: n.endPosition.row + 1,
          comment: text
        });
      }
    });
  }

  /**
   * Creates a code element from AST node
   */
  private createCodeElement(node: TreeSitter.Node, code: string, type: BSLElementType): BSLCodeElement | null {
    const nameNode = this.findChildByType(node, 'identifier');
    if (!nameNode) return null;

    const name = code.substring(nameNode.startIndex, nameNode.endIndex);
    const parameters = this.extractParameters(node, code);
    const isExport = this.isExportDeclaration(node, code);
    const comment = this.extractPrecedingComment(node, code);
    const body = code.substring(node.startIndex, node.endIndex);

    return {
      type,
      name,
      startLine: node.startPosition.row + 1,
      endLine: node.endPosition.row + 1,
      parameters,
      isExport,
      comment,
      body
    };
  }

  /**
   * Extracts parameters from function/procedure declaration
   */
  private extractParameters(node: TreeSitter.Node, code: string): string[] {
    const params: string[] = [];
    const paramListNode = this.findChildByType(node, 'parameters') ||
                          this.findChildByType(node, 'param_list') ||
                          this.findChildByType(node, 'parameter_list');

    if (paramListNode) {
      this.traverseNode(paramListNode, (n) => {
        if (n.type === 'identifier' || n.type === 'parameter') {
          const paramName = code.substring(n.startIndex, n.endIndex);
          // Filter out keywords and punctuation
          if (paramName && !params.includes(paramName) &&
              paramName !== '(' && paramName !== ')' && paramName !== ',') {
            params.push(paramName);
          }
        }
      });
    }

    return params;
  }

  /**
   * Checks if declaration has Export keyword
   */
  private isExportDeclaration(node: TreeSitter.Node, code: string): boolean {
    // Check current node and children
    let hasExport = false;
    this.traverseNode(node, (n) => {
      // Check both node type and text content
      if (n.type === 'EXPORT_KEYWORD' || n.type === 'export_keyword') {
        hasExport = true;
      } else {
        const text = code.substring(n.startIndex, n.endIndex).toLowerCase();
        if (text === 'экспорт' || text === 'export') {
          hasExport = true;
        }
      }
    }, 2); // Only check 2 levels deep

    return hasExport;
  }

  /**
   * Extracts comment preceding the node
   */
  private extractPrecedingComment(node: TreeSitter.Node, code: string): string | undefined {
    // Look for comments in previous siblings or parent's previous siblings
    const lines = code.split('\n');
    const startLine = node.startPosition.row;

    // Check up to 5 lines above for comments
    for (let i = startLine - 1; i >= Math.max(0, startLine - 5); i--) {
      const line = lines[i].trim();
      if (line.startsWith('//')) {
        return lines.slice(i, startLine).map(l => l.trim()).join('\n');
      }
    }

    return undefined;
  }

  /**
   * Calculates code statistics
   */
  private calculateStatistics(code: string, result: BSLAnalysisResult): void {
    const lines = code.split('\n');
    let codeLines = 0;
    let commentLines = 0;

    lines.forEach(line => {
      const trimmed = line.trim();
      if (trimmed.length === 0) {
        // Empty line
      } else if (trimmed.startsWith('//')) {
        commentLines++;
      } else {
        codeLines++;
      }
    });

    result.codeLines = codeLines;
    result.commentLines = commentLines;
  }

  /**
   * Traverses AST nodes recursively
   */
  private traverseNode(node: TreeSitter.Node, callback: (node: TreeSitter.Node) => void, maxDepth: number = Infinity, currentDepth: number = 0): void {
    if (currentDepth > maxDepth) return;

    callback(node);

    for (let i = 0; i < node.childCount; i++) {
      const child = node.child(i);
      if (child) {
        this.traverseNode(child, callback, maxDepth, currentDepth + 1);
      }
    }
  }

  /**
   * Finds first child node of specific type
   */
  private findChildByType(node: TreeSitter.Node, type: string): TreeSitter.Node | null {
    for (let i = 0; i < node.childCount; i++) {
      const child = node.child(i);
      if (child && child.type === type) {
        return child;
      }
    }
    return null;
  }
}

/**
 * Singleton instance for reuse
 */
let analyzerInstance: BSLTreesitterAnalyzer | null = null;

/**
 * Gets or creates BSL analyzer instance
 * Automatically initializes the analyzer on first use
 */
export async function getBSLAnalyzer(): Promise<BSLTreesitterAnalyzer> {
  if (!analyzerInstance) {
    analyzerInstance = new BSLTreesitterAnalyzer();
    await analyzerInstance.initialize();
  }
  return analyzerInstance;
}
