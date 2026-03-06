import * as path from 'path';
import { getBSLAnalyzer, BSLAnalysisResult, BSLCodeElement } from './bsl-treesitter-analyzer.js';

/**
 * Enhanced analysis result that includes BSL-specific information
 */
export interface EnhancedAnalysisFile {
  path: string;
  content: string;
  extension: string;
  bslAnalysis?: BSLAnalysisResult;
}

/**
 * Formats BSL analysis result as markdown for documentation
 */
export function formatBSLAnalysisAsMarkdown(analysis: BSLAnalysisResult, filePath: string): string {
  const fileName = path.basename(filePath);
  let markdown = `### ${fileName}\n\n`;

  // Statistics
  markdown += `**Статистика:**\n`;
  markdown += `- Всего строк: ${analysis.totalLines}\n`;
  markdown += `- Строк кода: ${analysis.codeLines}\n`;
  markdown += `- Строк комментариев: ${analysis.commentLines}\n`;
  markdown += `- Процедур: ${analysis.procedures.length}\n`;
  markdown += `- Функций: ${analysis.functions.length}\n`;
  markdown += `- Экспортных: ${analysis.exports.length}\n\n`;

  // Regions
  if (analysis.regions.length > 0) {
    markdown += `**Области кода:**\n`;
    analysis.regions.forEach(region => {
      markdown += `- ${region.name}\n`;
    });
    markdown += '\n';
  }

  // Exported procedures and functions
  if (analysis.exports.length > 0) {
    markdown += `**Экспортные процедуры и функции:**\n\n`;
    analysis.exports.forEach(element => {
      const params = element.parameters?.join(', ') || '';
      const typeLabel = element.type === 'procedure' ? 'Процедура' : 'Функция';
      markdown += `#### ${typeLabel} \`${element.name}(${params})\` Экспорт\n\n`;

      if (element.comment) {
        markdown += `${element.comment}\n\n`;
      }

      markdown += `**Строки:** ${element.startLine}-${element.endLine}\n\n`;
    });
  }

  // Internal procedures and functions
  const internal = [...analysis.procedures, ...analysis.functions].filter(e => !e.isExport);
  if (internal.length > 0) {
    markdown += `**Внутренние процедуры и функции:**\n\n`;
    internal.forEach(element => {
      const params = element.parameters?.join(', ') || '';
      const typeLabel = element.type === 'procedure' ? 'Процедура' : 'Функция';
      markdown += `- \`${typeLabel} ${element.name}(${params})\``;
      if (element.comment) {
        markdown += ` - ${element.comment.split('\n')[0]}`; // First line of comment
      }
      markdown += `\n`;
    });
    markdown += '\n';
  }

  return markdown;
}

/**
 * Creates a structured summary of BSL code for LLM analysis
 */
export function createBSLSummary(analysis: BSLAnalysisResult, filePath: string): string {
  const fileName = path.basename(filePath);

  let summary = `File: ${fileName}\n`;
  summary += `Type: BSL (1C:Enterprise Module)\n\n`;

  summary += `Statistics:\n`;
  summary += `- Total lines: ${analysis.totalLines}\n`;
  summary += `- Code lines: ${analysis.codeLines}\n`;
  summary += `- Comment lines: ${analysis.commentLines}\n`;
  summary += `- Procedures: ${analysis.procedures.length}\n`;
  summary += `- Functions: ${analysis.functions.length}\n`;
  summary += `- Exported: ${analysis.exports.length}\n\n`;

  // List all procedures and functions with signatures
  if (analysis.exports.length > 0) {
    summary += `Exported API:\n`;
    analysis.exports.forEach(element => {
      const params = element.parameters?.join(', ') || '';
      const type = element.type === 'procedure' ? 'Procedure' : 'Function';
      summary += `- ${type} ${element.name}(${params}) Export\n`;
      if (element.comment) {
        summary += `  // ${element.comment.replace(/\n/g, '\n  // ')}\n`;
      }
    });
    summary += '\n';
  }

  // Regions provide structural information
  if (analysis.regions.length > 0) {
    summary += `Code Regions:\n`;
    analysis.regions.forEach(region => {
      summary += `- ${region.name}\n`;
    });
    summary += '\n';
  }

  return summary;
}

/**
 * Analyzes BSL file and enhances it with BSL-specific information
 */
export async function analyzeBSLFile(filePath: string, content: string): Promise<EnhancedAnalysisFile> {
  const extension = path.extname(filePath).toLowerCase();

  if (extension !== '.bsl') {
    return {
      path: filePath,
      content,
      extension
    };
  }

  try {
    const analyzer = await getBSLAnalyzer();
    const bslAnalysis = analyzer.analyze(content, filePath);

    return {
      path: filePath,
      content,
      extension,
      bslAnalysis
    };
  } catch (error: any) {
    console.error(`Error analyzing BSL file ${filePath}:`, error.message);
    return {
      path: filePath,
      content,
      extension
    };
  }
}

/**
 * Checks if BSL file should be included in documentation
 * BSL files with only internal procedures might be utility modules
 */
export function shouldDocumentBSLFile(analysis: BSLAnalysisResult): boolean {
  // Always document files with exports (public API)
  if (analysis.exports.length > 0) {
    return true;
  }

  // Document files with significant code (not just empty modules)
  if (analysis.codeLines > 10) {
    return true;
  }

  // Skip empty or near-empty files
  return false;
}

/**
 * Extracts key information for LLM prompt
 * Returns concise summary suitable for inclusion in documentation prompt
 */
export function extractBSLKeyInfo(analysis: BSLAnalysisResult): {
  isPublicAPI: boolean;
  exportedMethods: string[];
  internalMethods: string[];
  regions: string[];
  complexity: 'low' | 'medium' | 'high';
} {
  const exportedMethods = analysis.exports.map(e => {
    const params = e.parameters?.join(', ') || '';
    return `${e.name}(${params})`;
  });

  const internal = [...analysis.procedures, ...analysis.functions].filter(e => !e.isExport);
  const internalMethods = internal.map(e => {
    const params = e.parameters?.join(', ') || '';
    return `${e.name}(${params})`;
  });

  const regions = analysis.regions.map(r => r.name);

  // Determine complexity based on number of methods and code lines
  const totalMethods = analysis.procedures.length + analysis.functions.length;
  let complexity: 'low' | 'medium' | 'high';
  if (totalMethods <= 5 && analysis.codeLines <= 100) {
    complexity = 'low';
  } else if (totalMethods <= 15 && analysis.codeLines <= 500) {
    complexity = 'medium';
  } else {
    complexity = 'high';
  }

  return {
    isPublicAPI: analysis.exports.length > 0,
    exportedMethods,
    internalMethods,
    regions,
    complexity
  };
}
