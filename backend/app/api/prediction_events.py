import json
import time
import queue
from typing import Dict, Any

from flask import Blueprint, Response, stream_with_context


_subscribers = set()


def init_prediction_events_routes() -> Blueprint:
    """SSE stream for prediction events.

    Clients connect to /api/predictions/stream and receive JSON lines as
    Server-Sent Events. Each event is a single line of JSON in the `data:` field.
    """
    bp = Blueprint('prediction_events_api', __name__, url_prefix='/api')

    @bp.get('/predictions/stream')
    def predictions_stream() -> Response:
        client_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue(maxsize=100)
        _subscribers.add(client_queue)

        def event_generator():
            try:
                # Send an initial hello to open the stream
                yield f"data: {json.dumps({'event':'hello','ts': time.time()})}\n\n"
                while True:
                    event = client_queue.get()
                    yield f"data: {json.dumps(event)}\n\n"
            finally:
                _subscribers.discard(client_queue)

        headers = {
            'Cache-Control': 'no-cache',
            'Content-Type': 'text/event-stream',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        }
        return Response(stream_with_context(event_generator()), headers=headers)

    return bp


def publish_prediction_event(event: Dict[str, Any]) -> None:
    """Publish a prediction event to all connected SSE subscribers."""
    dead = []
    for q in list(_subscribers):
        try:
            q.put_nowait(event)
        except Exception:
            dead.append(q)
    for q in dead:
        _subscribers.discard(q)


