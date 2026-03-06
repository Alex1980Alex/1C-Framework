/**
 * Integration module for 1C Metadata Analyzer with Documentation Tool
 *
 * This module provides functions to enrich documentation generation
 * with metadata information from XML files.
 */

import * as fs from 'fs';
import * as path from 'path';
import { MetadataParser } from './metadata-parser.js';
import { IMetadataAnalysisResult } from './metadata-types.js';
import { AnalysisResult } from '../analyzer/index.js';
import { EventHandlerDetector, IEventHandlerAnalysis } from './event-handler-detector.js';
import { FormExtendedValidator } from './form-extended-validator.js';
import { IExtendedFormValidationResult } from './form-types.js';

/**
 * Check if directory contains 1C metadata XML files
 * @param directoryPath Path to directory
 * @returns True if directory contains metadata XML
 */
export function hasMetadataXML(directoryPath: string): boolean {
  const catalogXml = path.join(directoryPath, '..', path.basename(directoryPath) + '.xml');
  if (fs.existsSync(catalogXml)) return true;

  // Check for Configuration.xml
  const configXml = path.join(directoryPath, 'Configuration.xml');
  if (fs.existsSync(configXml)) return true;

  // Check for CommonModule XML in parent directory
  const commonModuleXml = path.join(directoryPath, '..', path.basename(directoryPath) + '.xml');
  if (fs.existsSync(commonModuleXml)) return true;

  return false;
}

/**
 * Find metadata XML file for a given directory
 * @param directoryPath Path to directory (e.g., src/Catalogs/Валюты/Ext)
 * @returns Path to metadata XML file or null
 */
export function findMetadataXML(directoryPath: string): string | null {
  // Strategy 1: For Ext directories, go up and look for <parent>.xml
  if (path.basename(directoryPath) === 'Ext') {
    const parentDir = path.dirname(directoryPath);
    const parentName = path.basename(parentDir);
    const xmlFile = path.join(parentDir, '..', parentName + '.xml');
    if (fs.existsSync(xmlFile)) return xmlFile;

    // Also check in parent directory directly
    const xmlFileInParent = path.join(parentDir, parentName + '.xml');
    if (fs.existsSync(xmlFileInParent)) return xmlFileInParent;
  }

  // Strategy 2: For object directories (Catalogs/Валюты), check parent level
  const parentName = path.basename(directoryPath);
  const xmlFile = path.join(directoryPath, '..', parentName + '.xml');
  if (fs.existsSync(xmlFile)) return xmlFile;

  // Strategy 3: Check current directory for object XML
  const xmlFileInDir = path.join(directoryPath, parentName + '.xml');
  if (fs.existsSync(xmlFileInDir)) return xmlFileInDir;

  // Strategy 4: For Configuration directory
  const configXml = path.join(directoryPath, 'Configuration.xml');
  if (fs.existsSync(configXml)) return configXml;

  // Strategy 5: Look for any .xml file that is not Form.xml
  try {
    const files = fs.readdirSync(directoryPath);
    for (const file of files) {
      if (file.endsWith('.xml') && file !== 'Form.xml' && file !== 'Help.xml') {
        const xmlPath = path.join(directoryPath, file);
        // Check if it's a metadata file (contains MetaDataObject root)
        const content = fs.readFileSync(xmlPath, 'utf-8');
        if (content.includes('<MetaDataObject')) {
          return xmlPath;
        }
      }
    }
  } catch (err) {
    // Directory read error
  }

  return null;
}

/**
 * Enrich analysis result with metadata information
 * @param directoryPath Directory being analyzed
 * @param analysisResult Current analysis result
 * @returns Metadata analysis result if available, null otherwise
 */
export async function enrichWithMetadata(
  directoryPath: string,
  analysisResult: AnalysisResult
): Promise<IMetadataAnalysisResult | null> {
  const xmlFile = findMetadataXML(directoryPath);
  if (!xmlFile) return null;

  try {
    const parser = new MetadataParser();
    const metadataResult = await parser.parseMetadataFile(xmlFile);
    return metadataResult;
  } catch (err) {
    console.error(`[Metadata] Failed to parse ${xmlFile}:`, err);
    return null;
  }
}

/**
 * Analyze form modules for event handlers
 * @param metadataResult Metadata analysis result
 * @returns Map of form names to event handler analysis results
 */
export async function analyzeFormEventHandlers(
  metadataResult: IMetadataAnalysisResult
): Promise<Map<string, IEventHandlerAnalysis>> {
  const detector = new EventHandlerDetector();
  const formHandlers = new Map<string, IEventHandlerAnalysis>();

  if (metadataResult.relatedFiles.formModules) {
    for (const formModule of metadataResult.relatedFiles.formModules) {
      try {
        const analysis = await detector.analyzeFormModule(formModule);
        // Extract form name from path: .../Forms/FormName/Ext/Form/Module.bsl
        const formDir = path.dirname(path.dirname(path.dirname(formModule)));
        const formName = path.basename(formDir);
        formHandlers.set(formName, analysis);
      } catch (err) {
        console.error(`[EventHandler] Failed to analyze ${formModule}:`, err);
      }
    }
  }

  return formHandlers;
}

/**
 * Validate all form modules using FormExtendedValidator
 * @param metadataResult Metadata analysis result
 * @returns Map of form names to extended validation results
 */
export async function validateFormModules(
  metadataResult: IMetadataAnalysisResult
): Promise<Map<string, IExtendedFormValidationResult>> {
  const validator = new FormExtendedValidator();
  const formValidationResults = new Map<string, IExtendedFormValidationResult>();

  if (metadataResult.relatedFiles.formModules) {
    for (const formModule of metadataResult.relatedFiles.formModules) {
      try {
        // Convert Module.bsl path to Form.xml path
        // .../Forms/FormName/Ext/Form/Module.bsl -> .../Forms/FormName/Ext/Form.xml
        const formDir = path.dirname(formModule); // .../Forms/FormName/Ext/Form
        const extDir = path.dirname(formDir); // .../Forms/FormName/Ext
        const formXmlPath = path.join(extDir, 'Form.xml');

        if (!fs.existsSync(formXmlPath)) {
          console.error(`[FormValidation] Form.xml not found for ${formModule}`);
          continue;
        }

        // Run extended validation
        const validationResult = await validator.validateFormExtended(formXmlPath, formModule);

        // Extract form name from path
        const formsDir = path.dirname(extDir); // .../Forms/FormName
        const formName = path.basename(formsDir);

        formValidationResults.set(formName, validationResult);
        console.error(`[FormValidation] Validated ${formName} - Quality: ${validationResult.qualityScore}/100`);
      } catch (err) {
        console.error(`[FormValidation] Failed to validate ${formModule}:`, err);
      }
    }
  }

  return formValidationResults;
}

/**
 * Generate form validation context prompt for LLM
 * @param formValidationResults Map of form validation results
 * @returns Context prompt describing form validation status
 */
export function generateFormValidationPrompt(
  formValidationResults: Map<string, IExtendedFormValidationResult>
): string {
  if (!formValidationResults || formValidationResults.size === 0) {
    return '';
  }

  let prompt = `\n\n=== ВАЛИДАЦИЯ ФОРМ ===\n`;
  prompt += `Проанализировано форм: ${formValidationResults.size}\n\n`;

  for (const [formName, result] of formValidationResults.entries()) {
    const meta = result.formStructure.formName;
    prompt += `### Форма: ${meta}\n`;
    prompt += `**Оценка качества:** ${result.qualityScore}/100\n`;
    prompt += `**Статистика:**\n`;
    prompt += `- Всего элементов управления: ${result.totalControls}\n`;
    prompt += `- Элементов с обработчиками: ${result.controlsWithHandlers}\n`;
    prompt += `- Всего событий: ${result.totalEvents}\n`;
    prompt += `- Событий с обработчиками: ${result.eventsWithHandlers}\n`;
    prompt += `- Покрытие событий: ${result.coverage.eventCoverage.toFixed(1)}%\n`;

    // Commands statistics
    if (result.totalCommands > 0) {
      prompt += `- Всего команд: ${result.totalCommands}\n`;
      prompt += `- Команд с обработчиками: ${result.commandsWithHandlers}\n`;
    }

    // Conditional appearance statistics
    if (result.totalConditionalAppearance > 0) {
      prompt += `- Условное оформление: ${result.totalConditionalAppearance} элементов\n`;
    }

    // Missing handlers
    if (result.missingHandlers.length > 0) {
      prompt += `\n**Отсутствующие обработчики (${result.missingHandlers.length}):**\n`;
      result.missingHandlers.slice(0, 5).forEach(handler => {
        prompt += `  - ${handler.controlName} (${handler.controlType}): ${handler.handlerName}\n`;
      });
      if (result.missingHandlers.length > 5) {
        prompt += `  ... и еще ${result.missingHandlers.length - 5}\n`;
      }
    }

    // Missing command handlers
    if (result.missingCommandHandlers.length > 0) {
      prompt += `\n**Отсутствующие обработчики команд (${result.missingCommandHandlers.length}):**\n`;
      result.missingCommandHandlers.slice(0, 3).forEach(handler => {
        prompt += `  - ${handler.commandName}: ${handler.handlerName}\n`;
      });
      if (result.missingCommandHandlers.length > 3) {
        prompt += `  ... и еще ${result.missingCommandHandlers.length - 3}\n`;
      }
    }

    // DataPath issues
    if (result.dataPathIssues.length > 0) {
      prompt += `\n**Проблемы DataPath (${result.dataPathIssues.length}):**\n`;
      result.dataPathIssues.slice(0, 3).forEach(issue => {
        prompt += `  - ${issue.controlName}: ${issue.dataPath} (${issue.issueType})\n`;
      });
      if (result.dataPathIssues.length > 3) {
        prompt += `  ... и еще ${result.dataPathIssues.length - 3}\n`;
      }
    }

    // Conditional appearance issues
    if (result.conditionalAppearanceIssues.length > 0) {
      prompt += `\n**Проблемы условного оформления (${result.conditionalAppearanceIssues.length}):**\n`;
      result.conditionalAppearanceIssues.slice(0, 3).forEach(issue => {
        prompt += `  - ${issue.itemId}: ${issue.description}\n`;
      });
      if (result.conditionalAppearanceIssues.length > 3) {
        prompt += `  ... и еще ${result.conditionalAppearanceIssues.length - 3}\n`;
      }
    }

    // High-priority recommendations
    const highPriorityRecs = result.recommendations.filter(r => r.priority === 'high');
    if (highPriorityRecs.length > 0) {
      prompt += `\n**Важные рекомендации (${highPriorityRecs.length}):**\n`;
      highPriorityRecs.slice(0, 3).forEach(rec => {
        prompt += `  - [${rec.category}] ${rec.title}\n`;
      });
    }

    prompt += `\n`;
  }

  prompt += `**ВАЖНО для документирования:**\n`;
  prompt += `1. Укажите качество реализации формы на основе оценки качества\n`;
  prompt += `2. Опишите отсутствующие обработчики и их влияние на функциональность\n`;
  prompt += `3. Отметьте проблемы с DataPath и их возможные последствия\n`;
  prompt += `4. Включите рекомендации по улучшению качества форм\n`;
  prompt += `5. Опишите проверенные команды и условное оформление\n`;

  return prompt;
}

/**
 * Generate metadata context prompt for LLM
 * @param metadataResult Metadata analysis result
 * @param formEventHandlers Optional event handler analysis for forms
 * @param formValidationResults Optional form validation results
 * @returns Context prompt describing metadata structure
 */
export function generateMetadataContextPrompt(
  metadataResult: IMetadataAnalysisResult,
  formEventHandlers?: Map<string, IEventHandlerAnalysis>,
  formValidationResults?: Map<string, IExtendedFormValidationResult>
): string {
  const meta = metadataResult.metadata;
  const lang = meta.synonym?.items[0]?.lang || 'ru';
  const displayName = meta.synonym?.items.find((i) => i.lang === lang)?.content || meta.name;

  let prompt = `\n\n=== КОНТЕКСТ МЕТАДАННЫХ 1С ===\n`;
  prompt += `Объект: ${metadataResult.objectType}\n`;
  prompt += `Имя: ${meta.name}\n`;
  prompt += `Отображаемое имя: ${displayName}\n`;
  prompt += `UUID: ${meta.uuid}\n\n`;

  if (meta.type === 'Catalog') {
    const catalog = meta as any;
    prompt += `**Справочник (Catalog):**\n`;
    prompt += `- Длина кода: ${catalog.codeLength}\n`;
    prompt += `- Тип кода: ${catalog.codeType}\n`;
    prompt += `- Длина наименования: ${catalog.descriptionLength}\n`;
    prompt += `- Иерархический: ${catalog.hierarchical ? 'Да' : 'Нет'}\n`;
    prompt += `- Проверка уникальности: ${catalog.checkUnique ? 'Да' : 'Нет'}\n`;

    if (catalog.attributes && catalog.attributes.length > 0) {
      prompt += `\n**Реквизиты (${catalog.attributes.length}):**\n`;
      catalog.attributes.slice(0, 10).forEach((attr: any) => {
        const attrName = attr.synonym?.items[0]?.content || attr.name;
        prompt += `  - ${attrName} (${attr.name})\n`;
      });
      if (catalog.attributes.length > 10) {
        prompt += `  ... и еще ${catalog.attributes.length - 10} реквизитов\n`;
      }
    }

    if (catalog.forms && catalog.forms.length > 0) {
      prompt += `\n**Формы (${catalog.forms.length}):**\n`;
      catalog.forms.forEach((form: any) => {
        const formName = form.synonym?.items[0]?.content || form.name;
        prompt += `  - ${formName} (${form.name})\n`;
      });
    }
  } else if (meta.type === 'Document') {
    const doc = meta as any;
    prompt += `**Документ (Document):**\n`;
    prompt += `- Длина номера: ${doc.numberLength}\n`;
    prompt += `- Тип номера: ${doc.numberType}\n`;
    prompt += `- Проверка уникальности: ${doc.checkUnique ? 'Да' : 'Нет'}\n`;

    if (doc.attributes && doc.attributes.length > 0) {
      prompt += `\n**Реквизиты (${doc.attributes.length}):**\n`;
      doc.attributes.slice(0, 10).forEach((attr: any) => {
        const attrName = attr.synonym?.items[0]?.content || attr.name;
        prompt += `  - ${attrName} (${attr.name})\n`;
      });
      if (doc.attributes.length > 10) {
        prompt += `  ... и еще ${doc.attributes.length - 10} реквизитов\n`;
      }
    }

    if (doc.tabularSections && doc.tabularSections.length > 0) {
      prompt += `\n**Табличные части (${doc.tabularSections.length}):**\n`;
      doc.tabularSections.forEach((ts: any) => {
        const tsName = ts.synonym?.items[0]?.content || ts.name;
        prompt += `  - ${tsName} (${ts.name})\n`;
      });
    }
  } else if (meta.type === 'DataProcessor') {
    const dp = meta as any;
    prompt += `**Обработка (DataProcessor):**\n`;

    if (dp.attributes && dp.attributes.length > 0) {
      prompt += `\n**Реквизиты (${dp.attributes.length}):**\n`;
      dp.attributes.slice(0, 10).forEach((attr: any) => {
        const attrName = attr.synonym?.items[0]?.content || attr.name;
        prompt += `  - ${attrName} (${attr.name})\n`;
      });
    }

    if (dp.tabularSections && dp.tabularSections.length > 0) {
      prompt += `\n**Табличные части (${dp.tabularSections.length}):**\n`;
      dp.tabularSections.forEach((ts: any) => {
        const tsName = ts.synonym?.items[0]?.content || ts.name;
        prompt += `  - ${tsName} (${ts.name})\n`;
      });
    }
  } else if (meta.type === 'CommonModule') {
    const cm = meta as any;
    prompt += `**Общий модуль (CommonModule):**\n`;
    prompt += `- Глобальный: ${cm.global ? 'Да' : 'Нет'}\n`;
    prompt += `- Клиент (управляемое приложение): ${cm.clientManagedApplication ? 'Да' : 'Нет'}\n`;
    prompt += `- Сервер: ${cm.server ? 'Да' : 'Нет'}\n`;
    prompt += `- Внешнее соединение: ${cm.externalConnection ? 'Да' : 'Нет'}\n`;
    prompt += `- Привилегированный: ${cm.privileged ? 'Да' : 'Нет'}\n`;
  }

  prompt += `\n**Связанные файлы:**\n`;
  if (metadataResult.relatedFiles.managerModule) {
    prompt += `- Модуль менеджера: ${path.basename(metadataResult.relatedFiles.managerModule)}\n`;
  }
  if (metadataResult.relatedFiles.objectModule) {
    prompt += `- Модуль объекта: ${path.basename(metadataResult.relatedFiles.objectModule)}\n`;
  }
  if (metadataResult.relatedFiles.formModules && metadataResult.relatedFiles.formModules.length > 0) {
    prompt += `- Модули форм: ${metadataResult.relatedFiles.formModules.length}\n`;
  }
  if (metadataResult.relatedFiles.commandModules && metadataResult.relatedFiles.commandModules.length > 0) {
    prompt += `- Модули команд: ${metadataResult.relatedFiles.commandModules.length}\n`;
  }

  // Add event handler information for forms if available
  if (formEventHandlers && formEventHandlers.size > 0) {
    prompt += `\n**Обработчики событий форм:**\n`;
    const detector = new EventHandlerDetector();

    for (const [formName, analysis] of formEventHandlers.entries()) {
      const meta = metadataResult.metadata as any;
      const form = meta.forms?.find((f: any) => f.name === formName);
      const formDisplayName = form?.synonym?.items[0]?.content || formName;

      prompt += `\n### Форма: ${formDisplayName} (${formName})\n`;
      prompt += detector.generateContextPrompt(analysis);
    }
  }

  // Add form validation results if available
  if (formValidationResults && formValidationResults.size > 0) {
    prompt += generateFormValidationPrompt(formValidationResults);
  }

  prompt += `\n**ВАЖНО для документирования:**\n`;
  prompt += `1. Используйте информацию о реквизитах и табличных частях при описании модулей\n`;
  prompt += `2. Укажите связь между метаданными и кодом модулей\n`;
  prompt += `3. Документируйте назначение реквизитов в контексте бизнес-логики\n`;
  prompt += `4. Опишите связи между формами, командами и модулями объекта\n`;
  if (formEventHandlers && formEventHandlers.size > 0) {
    prompt += `5. Опишите назначение каждого обработчика событий и его взаимодействие с другими элементами формы\n`;
  }
  if (formValidationResults && formValidationResults.size > 0) {
    prompt += `6. Учитывайте результаты валидации форм при описании качества и полноты реализации\n`;
  }

  return prompt;
}

/**
 * Get metadata summary for parent directory aggregation
 * @param metadataResult Metadata analysis result
 * @returns Short metadata summary
 */
export function getMetadataSummary(metadataResult: IMetadataAnalysisResult): string {
  const meta = metadataResult.metadata;
  const displayName = meta.synonym?.items[0]?.content || meta.name;

  let summary = `**${metadataResult.objectType}: ${displayName}**\n`;

  if (meta.type === 'Catalog') {
    const catalog = meta as any;
    summary += `Справочник`;
    if (catalog.hierarchical) summary += ` (иерархический)`;
    if (catalog.attributes.length > 0) {
      summary += `, ${catalog.attributes.length} реквизитов`;
    }
  } else if (meta.type === 'Document') {
    const doc = meta as any;
    summary += `Документ`;
    if (doc.tabularSections && doc.tabularSections.length > 0) {
      summary += `, ${doc.tabularSections.length} табличных частей`;
    }
  } else if (meta.type === 'DataProcessor') {
    summary += `Обработка`;
  } else if (meta.type === 'CommonModule') {
    const cm = meta as any;
    summary += `Общий модуль`;
    if (cm.global) summary += ` (глобальный)`;
    if (cm.server && cm.clientManagedApplication) summary += ` (сервер + клиент)`;
    else if (cm.server) summary += ` (серверный)`;
    else if (cm.clientManagedApplication) summary += ` (клиентский)`;
  }

  return summary;
}
