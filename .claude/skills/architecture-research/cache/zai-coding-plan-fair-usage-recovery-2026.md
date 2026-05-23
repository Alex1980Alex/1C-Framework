# Z.AI Coding Plan — Fair Usage Policy violation (code 1313) recovery

**Last verified:** 2026-05-01
**Domain:** developer-tools / external-services / llm-billing
**Cross-ref:** `glm-5.1-claude-code-integration-2026.md`, `src/shared/llm_rotation/service.py` (zai-glm5 provider)

---

## TL;DR

Z.AI имеет **два независимых биллинговых трека** на одном API key, с разными лимитами и разными ошибками:

| Трек | Endpoint | Ошибка при исчерпании | Восстановление |
|---|---|---|---|
| **PAYG** (pay-as-you-go) | `/api/paas/v4/chat/completions` (OpenAI format) | HTTP 429, `code 1113` "Insufficient balance or no resource package" | Пополнить баланс / купить resource package в console |
| **Coding Plan** (subscription) | `/api/anthropic/v1/messages` (Anthropic format) | HTTP 429, `code 1313` "Fair Usage Policy violation, request frequency limited" | **Нет публичного appeal**, ждать reset (до 7 дней) |

API key валидится одинаково на обоих треках (один аккаунт), но лимиты учитываются раздельно.

---

## Code 1313 — Fair Usage Policy

### Что триггерит
- Non-coding workloads на Coding Plan endpoint (Z.AI агрессивно детектит и троттлит non-coding requests с октября 2025)
- Превышение weekly quota (refresh = **7-day cycle**, не daily)
- Высокая concurrent нагрузка (на Pro плане undocumented limit = 1 concurrent request, см. opencode#8618)
- Использование плана для агентских/multi-agent workflows за пределами IDE-coding

### Эскалация нарушений
1. **1-я violation** → high-intensity throttling (текущее состояние при 1313)
2. **2-я violation** → длительный throttle
3. **3-я violation** → **permanent ban** аккаунта без warning

### Восстановление
- **Нет публичного appeals process** — Z.AI не опубликовала формальную процедуру обжалования
- Пользователи многократно жалуются (Hacker News, XDA, awesomeagents.ai) на отсутствие предупреждений и недоступность support
- Единственные практические опции:
  1. **Wait 7-day reset cycle** — quota пересчитывается еженедельно от даты заказа
  2. **Switch to PAYG** (другой эндпоинт, другой биллинг, тот же ключ) — но требует пополнения баланса (`code 1113`)
  3. Попробовать обращение через `service@z.ai` или dashboard support widget (без гарантии)
  4. Снизить нагрузку на Coding Plan: использовать только из IDE (Cursor/Claude Code), убрать batch/agentic вызовы

---

## Code 1113 — Insufficient balance (PAYG)

### Что триггерит
- Нулевой баланс на PAYG счёте
- Истёкший resource package

### Восстановление
- Пополнение баланса в [Z.AI console](https://z.ai) → Billing
- Покупка resource package (фикс. количество токенов)
- Активация в течение нескольких минут после оплаты
- **Не имеет связи с Coding Plan статусом** — можно использовать PAYG даже когда Coding Plan под Fair Usage блоком

---

## Стратегия для LLM Rotation в проекте

При получении 429 от `zai-glm5`:
- **`code 1113`** → перевести провайдер в long cooldown (manual recharge required), не пытаться авто-восстановление
- **`code 1313`** → cooldown минимум 7 дней или до ручного reset (текущая дефолтная 60s cooldown недостаточна)
- Различать коды через парсинг JSON body, не только по HTTP status

Текущий `src/shared/llm_rotation/service.py` обрабатывает 429 как универсальный rate limit с 60s cooldown — для Z.AI этого мало. Рекомендация (не реализовано): добавить парсинг `error.code` из тела ответа и mapping на разные cooldown политики.

---

## Источники

- [Z.AI DevPack Overview](https://docs.z.ai/devpack/overview)
- [Z.AI DevPack FAQ — quota cycle](https://docs.z.ai/devpack/faq) — "7-day cycle reset"
- [GLM Coding Plan subscription page](https://z.ai/subscribe)
- [Z.AI Will Ban Your Coding Plan For Non-Coding Use — awesomeagents.ai](https://awesomeagents.ai/news/zai-coding-plan-bans-non-coding-use/)
- [I tested Claude's two biggest competitors — XDA Developers](https://www.xda-developers.com/claude-biggest-competitors-usage-limits-banned-account/)
- [BUG: GLM Coding Plan Pro concurrent request limit of 1 — opencode#8618](https://github.com/anomalyco/opencode/issues/8618)
- [Hacker News discussion — GLM Coding Plan with GLM-4.6 $3/month](https://news.ycombinator.com/item?id=45856628)
- [Z.ai API Complete Guide — aimadetools.com](https://www.aimadetools.com/blog/z-ai-api-complete-guide/)
- [Zhipu AI GLM Coding Plan Review 2026 — vibecoding.app](https://vibecoding.app/blog/zhipu-ai-glm-coding-plan-review)
