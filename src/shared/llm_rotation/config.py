"""
LLM Rotation configuration via pydantic-settings.

Environment variables with LLM_ROTATION_ prefix.
"""

from pydantic_settings import BaseSettings


class LLMRotationSettings(BaseSettings):
    """Settings for LLM Rotation Service.

    Default 3-tier rotation (sonnet-first order, 2026-07-04):
      0. claude-cli-sonnet — subscription quota, primary (higher quality)
      1. claude-cli-haiku  — subscription quota, faster CLI fallback
      2. ollama-local      — local Ollama (qwen2.5-coder:7b), $0 fallback
    """

    primary_provider: str = "claude-cli-sonnet"
    # 3 → 5 (2026-07-26, «максимальное использование»): авто-ротация видит РОВНО трёх
    # провайдеров (sonnet → haiku → ollama; opus explicit_only, anthropic-sonnet без
    # ключа), и при трёх ротациях каждый получал одну попытку — повторить упавший тир
    # было нечем. 5 даёт второй заход, НЕ удлиняя вызов: верхняя граница по-прежнему
    # total_budget_seconds, который режет раньше, чем исчерпаются ротации.
    max_retries: int = 5
    # CLI subprocess startup adds ~5s overhead; bump default timeout vs old HTTP defaults
    timeout: int = 90
    timeout_generation: int = 120
    timeout_heavy: int = 240
    cooldown_seconds: int = 300
    rate_limit_cooldown: int = 60

    # Сквозной бюджет ВСЕГО complete() (2026-07-26): обе фазы (force-primary + fallback)
    # обязаны уложиться, per-попытка timeout режется остатком. Согласован с per-server
    # `timeout: 300000` в .mcp.json (⚠ per-server поле СИЛЬНЕЕ env MCP_TOOL_TIMEOUT —
    # именно оно рвало вызовы на 60с). primary_budget_share гарантирует фоллбэку время:
    # раньше primary с ретраями съедал всё окно и ротация не успевала ротировать.
    # 240 → 270 (2026-07-26): per-server `timeout: 300000` — потолок КЛИЕНТА, дальше он
    # обрывает вызов независимо от нас. 60с бюджета простаивало; 30с зазора хватает на
    # сериализацию ответа и обвязку логов. Инвариант прежний: бюджет < клиентского окна.
    total_budget_seconds: int = 270
    primary_budget_share: float = 0.6

    # Force-primary mode: retry primary provider before any fallback
    force_primary: bool = True
    primary_max_retries: int = 2
    primary_retry_delay: float = 3.0
    primary_cooldown_seconds: int = 30

    # Потолок конкурентности батча ДЛЯ СПАВН-ПРОВАЙДЕРОВ (format="claude-cli"), 2026-07-26.
    # Общий старт задаётся LLM_ROTATION_BATCH_CONCURRENCY (см. adaptive_concurrency.py) и
    # поднят до 6 ради пропускной способности, но для claude-cli это означало бы 6
    # параллельных ПОЛНЫХ Claude Code: каждый вызов спавнит вторую сессию со своей
    # цепочкой хуков (~35 python-процессов, ~2.8 ГБ commit). Инцидент 2026-07-26 16:51 —
    # сессия оборвалась молча ровно на llm_complete при запасе commit ~4 ГБ
    # ([[reference-machine-commit-exhaustion]]). Дешёвые провайдеры (ollama/HTTP) потолком
    # не задеты. Поднимать осознанно, глядя на `\Memory\Committed Bytes`.
    batch_cli_concurrency: int = 3

    # Агрегатный бюджет ВСЕГО батча (2026-07-26, находка ревьюера Р2). total_budget_seconds
    # ограничивает ОДИН complete(), а батч — это ceil(N/concurrency) волн: при потолке
    # claude-cli=3 и реальных 25-150с на вызов уже N≈10-15 выходит за клиентское окно 300с.
    # Результаты отдаются только после сбора, поэтому обрыв клиентом выбрасывал бы ВСЮ
    # выполненную работу. Теперь по истечении бюджета невыполненные снимаются, а готовые
    # возвращаются с пометкой — частичный результат честнее пустого.
    batch_budget_seconds: int = 250

    # Потолок кредита за ожидание в гейте спавнов (2026-07-26, находка ревьюера М1).
    # Кредит компенсирует очередь, чтобы она не съедала бюджет ротации, но БЕЗ потолка
    # фактический потолок стенного времени complete() становился total_budget + Σочередей:
    # батч защищён своим batch_budget_seconds (он меряет реальные часы), а прямой
    # llm_complete backstop'а не имеет и вылезал за клиентское окно 300с — работа при этом
    # выбрасывается целиком (форма client_timeout). Инвариант: total + credit < окно
    # (270 + 20 = 290 < 300), он и запинен тестом. Хочешь больше кредита — снижай
    # total_budget_seconds на столько же, а не расширяй сумму.
    queue_credit_max_seconds: int = 20

    # Circuit Breaker
    cb_fail_threshold: int = 3
    cb_success_threshold: int = 1
    cb_reset_timeout: float = 60.0

    # Backoff Strategy (Iteration 2)
    backoff_base_delay: float = 1.0
    backoff_max_delay: float = 30.0
    backoff_jitter: float = 1.0
    backoff_multiplier: float = 2.0

    # Health Check (Iteration 3)
    health_check_enabled: bool = True
    health_check_interval: int = 120  # seconds between probes

    # Rate Limiting (Iteration 6)
    rate_limiting_enabled: bool = True

    # Adaptive Routing + Budget (Iteration 5)
    adaptive_routing: bool = True
    daily_budget: float = 1.0  # dollars
    budget_alert_threshold: float = 0.8  # warn at 80%

    # Persistence (Iteration 7)
    persist_adaptive: bool = True
    adaptive_data_path: str = "data/llm-rotation-adaptive.json"
    budget_data_path: str = "data/llm-rotation-budget.json"

    # API Keys (from environment)
    zhipu_api_key: str = ""
    gemini_api_key: str = ""
    openrouter_api_key: str = ""
    mistral_api_key: str = ""

    # Ollama
    ollama_url: str = "http://localhost:11434"
    ollama_cloud_url: str = "http://localhost:11434"

    model_config = {
        "env_prefix": "LLM_ROTATION_",
        "env_file": ".env",
        "extra": "ignore",
    }


_settings: LLMRotationSettings | None = None


def get_settings() -> LLMRotationSettings:
    """Get or create singleton settings."""
    global _settings
    if _settings is None:
        _settings = LLMRotationSettings()
    return _settings
