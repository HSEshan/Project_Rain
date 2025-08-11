type EventPayload = {
  event_id: string;
  event_type: string;
  sender_id: string;
  receiver_id: string;
  text: string;
  metadata?: Record<string, any>;
  timestamp: string;
};

type EventCallback = (event: EventPayload) => void;

class EventBus {
  private listeners: Record<string, EventCallback[]> = {};

  subscribe(eventType: string, callback: EventCallback) {
    if (!this.listeners[eventType]) {
      this.listeners[eventType] = [];
    }
    this.listeners[eventType].push(callback);
    return () => {
      this.listeners[eventType] = this.listeners[eventType].filter(
        (cb) => cb !== callback
      );
    };
  }

  emit(event: EventPayload) {
    if (this.listeners[event.event_type]) {
      this.listeners[event.event_type].forEach((cb) => cb(event));
    }
  }
}

export const eventBus = new EventBus();
