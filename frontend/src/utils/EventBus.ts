import type { EventPayload } from "./eventType";

type EventHandler<EventPayload> = (event: EventPayload) => void;

class EventBus {
  private handlers: Map<string, Set<EventHandler<EventPayload>>> = new Map();

  on<T extends EventPayload>(type: T["event_type"], handler: EventHandler<T>) {
    if (!this.handlers.has(type)) {
      this.handlers.set(type, new Set());
    }
    this.handlers.get(type)!.add(handler as EventHandler<EventPayload>);
  }

  off<T extends EventPayload>(type: T["event_type"], handler: EventHandler<T>) {
    this.handlers.get(type)?.delete(handler as EventHandler<EventPayload>);
  }

  emit(event: EventPayload) {
    this.handlers.get(event.event_type)?.forEach((handler) => handler(event));
  }
}

export const eventBus = new EventBus();
