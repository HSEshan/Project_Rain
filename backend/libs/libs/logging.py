import enum
import functools
import inspect
import logging
import sys

import structlog


class LogFormat(enum.Enum):
    JSON = "json"
    PRETTY = "pretty"


def setup_logging(
    service_name: str,
    log_format: str = LogFormat.JSON.value,
    level: str = logging.INFO,
):
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.CallsiteParameterAdder(
            [
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.FUNC_NAME,
                structlog.processors.CallsiteParameter.LINENO,
            ]
        ),
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.format_exc_info,
    ]

    if log_format == LogFormat.PRETTY.value:
        renderer = structlog.dev.ConsoleRenderer()
    elif log_format == LogFormat.JSON.value:
        renderer = structlog.processors.JSONRenderer()
    else:
        raise ValueError(f"Invalid log format: {log_format}")

    structlog.configure(
        processors=shared_processors + [renderer],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    structlog.get_logger().bind(service=service_name)


def bind_event_context(
    event_arg_name: str = "event",
    trace_id_arg_name: str = "trace_id",
    fallback_id: str = None,
    extra: dict = None,
):
    """
    Decorator to bind logging context from an event-like argument before calling the function.

    Args:
        event_arg_name: Name of the argument holding the event object.
        trace_id_arg_name: Name of the argument holding the trace ID (if applicable).
        fallback_id: Fallback ID if event_id/trace_id are missing.
        extra: Additional context vars to bind.
    """

    def decorator(func):
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                # Get event from args or kwargs
                event = kwargs.get(event_arg_name)
                if event is None:
                    # Try to get by position if possible
                    try:
                        sig = inspect.signature(func)
                        param_pos = list(sig.parameters).index(event_arg_name)
                        event = args[param_pos]
                    except Exception:
                        event = None

                if event is not None:
                    # Clear old context and bind new
                    structlog.contextvars.clear_contextvars()
                    event_id = (
                        getattr(event, "event_id", None)
                        or (event.get("event_id") if isinstance(event, dict) else None)
                        or fallback_id
                    )
                    trace_id = (
                        getattr(event, trace_id_arg_name, None)
                        or (
                            event.get(trace_id_arg_name)
                            if isinstance(event, dict)
                            else None
                        )
                        or event_id
                    )
                    context = {"event_id": event_id, "trace_id": trace_id}
                    if extra:
                        context.update(extra)
                    structlog.contextvars.bind_contextvars(**context)
                return await func(*args, **kwargs)

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                event = kwargs.get(event_arg_name)
                if event is None:
                    sig = inspect.signature(func)
                    try:
                        param_pos = list(sig.parameters).index(event_arg_name)
                        event = args[param_pos]
                    except Exception:
                        event = None

                if event is not None:
                    structlog.contextvars.clear_contextvars()
                    event_id = (
                        getattr(event, "event_id", None)
                        or (event.get("event_id") if isinstance(event, dict) else None)
                        or fallback_id
                    )
                    trace_id = (
                        getattr(event, trace_id_arg_name, None)
                        or (
                            event.get(trace_id_arg_name)
                            if isinstance(event, dict)
                            else None
                        )
                        or event_id
                    )
                    context = {"event_id": event_id, "trace_id": trace_id}
                    if extra:
                        context.update(extra)
                    structlog.contextvars.bind_contextvars(**context)
                return func(*args, **kwargs)

            return sync_wrapper

    return decorator
