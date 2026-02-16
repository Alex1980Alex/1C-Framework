"""WebSocket endpoint for real-time search streaming (Phase 49, Q3.2).

Provides bidirectional communication:
- Client sends: {"question": "...", "strategy": "hybrid", "k": 5}
- Server streams: JSON messages with type TOKEN/SOURCE/STATUS/DONE/ERROR
- Client can send: {"action": "cancel"} to abort in-flight request
"""

import asyncio
import json
import logging
import time
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.api.dependencies.components import get_components
from src.pdf_framework.chains.qa.retrieval_qa import RetrievalQAChain

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


def _ws_message(msg_type: str, data: Any, metadata: dict | None = None) -> str:
    """Format a WebSocket message as JSON string."""
    return json.dumps(
        {"type": msg_type, "data": data, "metadata": metadata or {}},
        ensure_ascii=False,
    )


@router.websocket("/ws/search")
async def websocket_search(websocket: WebSocket):
    """WebSocket endpoint for streaming search with cancel support.

    Protocol:
        → Client sends JSON: {"question": "...", "strategy": "hybrid", "k": 5}
        ← Server sends JSON messages: {type, data, metadata}
        → Client can send: {"action": "cancel"} to abort
        ← Server sends: {type: "done"} or {type: "error"}
    """
    await websocket.accept()
    components = await get_components()

    try:
        while True:
            # Wait for a query from client
            raw = await websocket.receive_text()
            try:
                request = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(
                    _ws_message("error", "Invalid JSON")
                )
                continue

            # Handle cancel-only messages
            if request.get("action") == "cancel":
                continue

            question = request.get("question", "").strip()
            if not question:
                await websocket.send_text(
                    _ws_message("error", "Missing 'question' field")
                )
                continue

            strategy = request.get("strategy", "hybrid")
            k = request.get("k", 5)
            rerank = request.get("rerank", True)

            # Run search + streaming generation as a cancellable task
            async def _run_search():
                t0 = time.perf_counter()

                # Step 1: Search
                await websocket.send_text(
                    _ws_message("status", "searching")
                )

                search_response = await components.search_manager.search(
                    query=question,
                    strategy=strategy,
                    k=k,
                    rerank=rerank,
                )

                search_ms = (time.perf_counter() - t0) * 1000
                await websocket.send_text(
                    _ws_message("status", "searching_done", {"elapsed_ms": round(search_ms)})
                )

                # Step 2: Early source delivery (before generation)
                sources: list[str] = []
                for r in search_response.results:
                    src = r.chunk.metadata.get("source", "")
                    if src and src not in sources:
                        sources.append(src)

                await websocket.send_text(
                    _ws_message("sources", sources, {
                        "total_found": search_response.total_found,
                        "search_type": search_response.search_type,
                    })
                )

                # Step 3: Stream answer tokens
                await websocket.send_text(
                    _ws_message("status", "generating")
                )

                chain = RetrievalQAChain(
                    settings=components.settings.agent,
                    api_key=components.settings.anthropic_api_key,
                )

                collected: list[str] = []
                async for token in chain.stream_answer(question, search_response):
                    collected.append(token)
                    await websocket.send_text(
                        _ws_message("token", token)
                    )

                # Step 4: Post-processing (section refs)
                full_answer = "".join(collected)
                from src.pdf_framework.utils.section_refs import append_section_refs
                final_answer = append_section_refs(full_answer, search_response.results)
                extra = final_answer[len(full_answer):]
                if extra:
                    await websocket.send_text(
                        _ws_message("token", extra)
                    )

                # Step 5: Done
                elapsed = (time.perf_counter() - t0) * 1000
                await websocket.send_text(
                    _ws_message("done", "", {
                        "elapsed_ms": round(elapsed),
                        "search_type": search_response.search_type,
                        "total_found": search_response.total_found,
                    })
                )

            search_task: asyncio.Task = asyncio.create_task(_run_search())

            # Listen for cancel while search runs
            async def _listen_for_cancel():
                try:
                    while not search_task.done():
                        raw_msg = await asyncio.wait_for(
                            websocket.receive_text(), timeout=0.5
                        )
                        try:
                            msg = json.loads(raw_msg)
                            if msg.get("action") == "cancel":
                                search_task.cancel()
                                await websocket.send_text(
                                    _ws_message("status", "cancelled")
                                )
                                return
                        except json.JSONDecodeError:
                            pass
                except asyncio.TimeoutError:
                    pass

            cancel_listener = asyncio.create_task(_listen_for_cancel())

            try:
                await search_task
            except asyncio.CancelledError:
                logger.info("[WS] Search cancelled by client")
            except Exception as e:
                logger.error("[WS] Search error: %s", e)
                await websocket.send_text(
                    _ws_message("error", str(e))
                )
            finally:
                cancel_listener.cancel()
                try:
                    await cancel_listener
                except asyncio.CancelledError:
                    pass

    except WebSocketDisconnect:
        logger.info("[WS] Client disconnected")
    except Exception as e:
        logger.error("[WS] Unexpected error: %s", e)
