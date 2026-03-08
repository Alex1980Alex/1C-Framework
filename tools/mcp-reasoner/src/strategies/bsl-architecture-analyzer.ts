import { ThoughtNode, ReasoningRequest, ReasoningResponse } from '../types.js';
import { BaseStrategy, StrategyMetrics } from './base.js';
import { StateManager } from '../state.js';

interface BSLArchitectureMetrics extends StrategyMetrics {
  subsystemsAnalyzed: number;
  dependencyIssues: number;
  architecturalPatterns: number;
  complexityScore: number;
}

export class BSLArchitectureAnalyzer extends BaseStrategy {
  private subsystemsAnalyzed = 0;
  private dependencyIssues = 0;
  private architecturalPatterns = 0;
  private complexityScore = 0;

  constructor(stateManager: StateManager) {
    super(stateManager);
  }

  async processThought(request: ReasoningRequest): Promise<ReasoningResponse> {
    // Generate architecture-focused thoughts based on BSL context
    const currentNode = await this.generateArchitectureThought(request);
    
    // Enhanced evaluation for 1C architecture
    currentNode.score = this.evaluateBSLArchitecture(currentNode);
    
    await this.saveNode(currentNode);
    
    return {
      nodeId: currentNode.id,
      thought: currentNode.thought,
      score: currentNode.score,
      depth: currentNode.depth,
      isComplete: currentNode.isComplete,
      nextThoughtNeeded: !currentNode.isComplete && currentNode.depth < 8,
      strategyUsed: 'BSL Architecture Analysis'
    };
  }

  private async generateArchitectureThought(request: ReasoningRequest): Promise<ThoughtNode> {
    const nodeId = this.generateNodeId();
    
    // Architecture-specific thought generation
    let architectureThought = '';
    
    if (request.thoughtNumber <= 2) {
      architectureThought = this.generateSubsystemAnalysis(request.thought);
    } else if (request.thoughtNumber <= 4) {
      architectureThought = this.generateDependencyAnalysis(request.thought);
    } else if (request.thoughtNumber <= 6) {
      architectureThought = this.generatePatternAnalysis(request.thought);
    } else {
      architectureThought = this.generateArchitectureRecommendations(request.thought);
    }

    return {
      id: nodeId,
      thought: architectureThought,
      score: 0,
      depth: request.thoughtNumber,
      children: [],
      parentId: request.parentId,
      isComplete: request.thoughtNumber >= 7,
      timestamp: Date.now()
    };
  }

  private generateSubsystemAnalysis(originalThought: string): string {
    this.subsystemsAnalyzed++;
    
    const subsystemPatterns = [
      'Анализирую архитектуру подсистем 1С для выявления нарушений принципов разделения ответственности',
      'Исследую взаимодействие между подсистемами для обнаружения циклических зависимостей',
      'Проверяю соответствие структуры подсистем принципам модульной архитектуры',
      'Оцениваю глубину вложенности подсистем и их влияние на сложность поддержки'
    ];

    const basePattern = subsystemPatterns[Math.floor(Math.random() * subsystemPatterns.length)];
    
    return `${basePattern}. В контексте "${originalThought}" особое внимание уделяю:
    
1. **Выявление границ подсистем**: проверяю, четко ли разграничены зоны ответственности
2. **Анализ связанности**: ищу случаи слишком тесной связи между подсистемами  
3. **Оценка когезии**: проверяю, насколько логично сгруппированы объекты внутри подсистем
4. **Поиск "божественных объектов"**: выявляю объекты с избыточной функциональностью

Это критично для масштабируемости и поддерживаемости 1С решения.`;
  }

  private generateDependencyAnalysis(originalThought: string): string {
    this.dependencyIssues++;
    
    return `Провожу глубокий анализ зависимостей в архитектуре 1С. Основываясь на предыдущем анализе подсистем:

**Выявленные проблемы зависимостей:**
1. **Циклические зависимости**: ищу взаимные ссылки между подсистемами, которые усложняют тестирование
2. **Нарушение принципа инверсии зависимостей**: проверяю случаи, когда высокоуровневые модули зависят от низкоуровневых
3. **Избыточные зависимости**: выявляю ненужные связи, увеличивающие сложность
4. **Отсутствующая инкапсуляция**: ищу прямые обращения к внутренним объектам подсистем

**Методы анализа:**
- Построение графа зависимостей между общими модулями
- Анализ использования метаданных через конфигурацию
- Проверка обращений к объектам других подсистем в BSL коде
- Оценка глубины цепочек вызовов

Это поможет выработать стратегию рефакторинга для улучшения архитектуры.`;
  }

  private generatePatternAnalysis(originalThought: string): string {
    this.architecturalPatterns++;
    
    return `Анализирую применение архитектурных паттернов в 1С решении:

**Обнаруженные паттерны:**
1. **MVC в формах**: проверяю разделение логики представления и бизнес-логики
2. **Factory для создания объектов**: ищу централизованное создание однотипных объектов
3. **Strategy для алгоритмов**: выявляю возможности вынесения алгоритмов в отдельные модули
4. **Observer для событий**: анализирую механизмы подписки на события

**Антипаттерны (требующие устранения):**
- **God Object**: объекты с избыточной ответственностью  
- **Spaghetti Code**: запутанная логика без четкой структуры
- **Copy-Paste Programming**: дублирование кода вместо выделения общих функций
- **Hard Coding**: захардкоженные значения вместо параметризации

**Рекомендации по улучшению:**
- Внедрение паттерна Repository для работы с данными
- Использование Command для инкапсуляции операций
- Применение Decorator для расширения функциональности объектов

Это повысит качество кода и упростит дальнейшее развитие.`;
  }

  private generateArchitectureRecommendations(originalThought: string): string {
    return `На основе проведенного анализа архитектуры формирую конкретные рекомендации:

**Приоритетные улучшения:**
1. **Рефакторинг подсистем**: 
   - Разделить избыточно связанные подсистемы
   - Выделить общую инфраструктурную подсистему
   - Создать четкие API для межсистемного взаимодействия

2. **Оптимизация зависимостей**:
   - Устранить циклические зависимости через введение посреднических интерфейсов
   - Применить паттерн Dependency Injection для слабой связанности
   - Вынести общие функции в отдельные сервисные модули

3. **Внедрение лучших практик**:
   - Стандартизировать именование и структуру модулей
   - Создать архитектурные соглашения для команды
   - Внедрить автоматизированные проверки качества архитектуры

**Долгосрочная стратегия:**
- Поэтапный переход к микросервисной архитектуре через HTTP-сервисы
- Создание централизованной системы логирования и мониторинга
- Внедрение паттернов Domain Driven Design для сложных предметных областей

**Метрики для отслеживания прогресса:**
- Цикломатическая сложность модулей
- Коэффициент связанности между подсистемами  
- Количество нарушений архитектурных принципов
- Время, необходимое для внедрения новых функций

Эти меры существенно улучшат качество и поддерживаемость 1С решения.`;
  }

  private evaluateBSLArchitecture(node: ThoughtNode): number {
    let score = 0;

    // Architecture-specific scoring
    const thought = node.thought.toLowerCase();
    
    // Bonus for architectural terms
    const architectureTerms = [
      'подсистема', 'зависимость', 'паттерн', 'архитектура', 'модуль',
      'инкапсуляция', 'связанность', 'когезия', 'рефакторинг', 'api'
    ];
    
    for (const term of architectureTerms) {
      if (thought.includes(term)) {
        score += 0.15;
      }
    }

    // Bonus for 1C-specific analysis
    const bslTerms = [
      'общий модуль', 'объектный модуль', 'модуль формы', 'bsl', '1с',
      'метаданные', 'конфигурация', 'подписка на события'
    ];
    
    for (const term of bslTerms) {
      if (thought.includes(term)) {
        score += 0.2;
      }
    }

    // Bonus for concrete recommendations
    if (thought.includes('рекомендации') || thought.includes('улучшения')) {
      score += 0.25;
    }

    // Bonus for mentioning specific patterns or anti-patterns
    if (thought.includes('mvc') || thought.includes('factory') || thought.includes('god object')) {
      score += 0.15;
    }

    // Complexity assessment bonus
    if (thought.includes('сложность') || thought.includes('метрики')) {
      score += 0.1;
      this.complexityScore += 0.1;
    }

    // Cap at 1.0
    return Math.min(score, 1.0);
  }

  private generateNodeId(): string {
    return `bsl-arch-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  public async getMetrics(): Promise<BSLArchitectureMetrics> {
    const baseMetrics = await super.getMetrics();
    
    return {
      ...baseMetrics,
      name: 'BSL Architecture Analyzer',
      subsystemsAnalyzed: this.subsystemsAnalyzed,
      dependencyIssues: this.dependencyIssues,
      architecturalPatterns: this.architecturalPatterns,
      complexityScore: this.complexityScore
    };
  }

  public async clear(): Promise<void> {
    this.subsystemsAnalyzed = 0;
    this.dependencyIssues = 0;
    this.architecturalPatterns = 0;
    this.complexityScore = 0;
  }
}