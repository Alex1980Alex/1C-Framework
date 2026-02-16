# Streaming API — Клиентские примеры

## SSE (Server-Sent Events)

### JavaScript (EventSource)

```javascript
const question = "Что такое справочники в 1С?";
const url = "http://localhost:8000/search/ask";

const response = await fetch(url, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ question, stream: true, strategy: "hybrid", k: 5 }),
});

const reader = response.body.getReader();
const decoder = new TextDecoder();
let buffer = "";

while (true) {
  const { done, value } = await reader.read();
  if (done) break;

  buffer += decoder.decode(value, { stream: true });
  const lines = buffer.split("\n\n");
  buffer = lines.pop(); // keep incomplete chunk

  for (const line of lines) {
    if (!line.startsWith("data: ")) continue;
    const event = JSON.parse(line.slice(6));

    switch (event.type) {
      case "status":
        console.log(`[${event.data}]`, event.metadata);
        break;
      case "sources":
        console.log("Sources:", event.data);
        break;
      case "ttft":
        console.log(`TTFT: ${event.metadata.ttft_ms}ms`);
        break;
      case "token":
        process.stdout.write(event.data); // append token
        break;
      case "done":
        console.log("\n---");
        console.log(`Total: ${event.metadata.elapsed_ms}ms`);
        console.log(`Search: ${event.metadata.search_ms}ms`);
        console.log(`TTFT: ${event.metadata.ttft_ms}ms`);
        break;
    }
  }
}
```

### Python (httpx)

```python
import httpx
import json

url = "http://localhost:8000/search/ask"
payload = {"question": "Что такое справочники в 1С?", "stream": True, "strategy": "hybrid"}

with httpx.stream("POST", url, json=payload, timeout=60) as response:
    buffer = ""
    for chunk in response.iter_text():
        buffer += chunk
        while "\n\n" in buffer:
            event_str, buffer = buffer.split("\n\n", 1)
            if not event_str.startswith("data: "):
                continue
            event = json.loads(event_str[6:])

            if event["type"] == "token":
                print(event["data"], end="", flush=True)
            elif event["type"] == "sources":
                print(f"\nИсточники: {event['data']}")
            elif event["type"] == "ttft":
                print(f"\nTTFT: {event['metadata']['ttft_ms']}ms")
            elif event["type"] == "done":
                meta = event["metadata"]
                print(f"\n--- Готово за {meta['elapsed_ms']}ms ---")
```

---

## WebSocket

### JavaScript

```javascript
const ws = new WebSocket("ws://localhost:8000/ws/search");

ws.onopen = () => {
  ws.send(JSON.stringify({
    question: "Как работает проведение документов?",
    strategy: "hybrid",
    k: 5,
  }));
};

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);

  switch (msg.type) {
    case "status":
      console.log(`[${msg.data}]`, msg.metadata);
      break;
    case "sources":
      console.log("Sources:", msg.data);
      break;
    case "ttft":
      console.log(`TTFT: ${msg.metadata.ttft_ms}ms`);
      break;
    case "token":
      document.getElementById("answer").textContent += msg.data;
      break;
    case "done":
      console.log("Done:", msg.metadata);
      break;
    case "error":
      console.error("Error:", msg.data);
      break;
  }
};

// Cancel in-flight request
function cancel() {
  ws.send(JSON.stringify({ action: "cancel" }));
}
```

### Python (websockets)

```python
import asyncio
import json
import websockets

async def search():
    async with websockets.connect("ws://localhost:8000/ws/search") as ws:
        await ws.send(json.dumps({
            "question": "Что такое регистры накопления?",
            "strategy": "hybrid",
            "k": 5,
        }))

        async for raw in ws:
            msg = json.loads(raw)
            if msg["type"] == "token":
                print(msg["data"], end="", flush=True)
            elif msg["type"] == "ttft":
                print(f"\nTTFT: {msg['metadata']['ttft_ms']}ms")
            elif msg["type"] == "done":
                print(f"\n--- Done: {msg['metadata']['elapsed_ms']}ms ---")
                break

asyncio.run(search())
```

---

## Протокол событий

| Тип | Данные | Метаданные | Когда |
|-----|--------|------------|-------|
| `status` | `"searching_done"` | `elapsed_ms` | После поиска |
| `sources` | `["file.pdf", ...]` | `total_found`, `search_type` | До генерации |
| `status` | `"generating"` | — | Начало LLM |
| `ttft` | `""` | `ttft_ms` | Первый токен |
| `token` | `"текст"` | — | Каждый токен |
| `done` | `""` | `elapsed_ms`, `ttft_ms`, `search_ms`, `search_type` | Конец |
| `error` | `"message"` | — | При ошибке |

## Cancel (только WebSocket)

```json
{"action": "cancel"}
```

Сервер ответит `{"type": "status", "data": "cancelled"}` и прервёт генерацию.
