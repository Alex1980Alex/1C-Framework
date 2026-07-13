# 02 Дизайн — P2

## P2.1
invocation_logger: единый `err_type`/`success`; dotted-ключи `gen_ai.tool.name`/`gen_ai.tool.call.id`/`error.type` дублируют плоские поля дословно (additionalProperties:true в схеме → валидация не ломается).

## P2.2
Новый `scripts/tool_effectiveness.py` (stdlib-only): pair_durations/percentile/effectiveness_from_posts/step_efficiency/server_of/rollup_by_server. analyze_tool_health и tool_usage_report делегируют ему (алиасы `_pct`/`_pair_duration_list` сохранены для тестов). Per-server rollup (Tool Success Rate + step-eff) → compute_health/render_md/sidecar.

sys.path bootstrap: каталог scripts на path идемпотентно (модуль грузится и скриптом, и через importlib в тестах).
