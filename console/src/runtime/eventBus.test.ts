import { describe, it, expect, beforeEach } from "vitest";
import {
  subscribe,
  emit,
  type RuntimeEvent,
} from "../runtime/eventBus";

function makeEvent(name: string, payload: Record<string, unknown> = {}): RuntimeEvent {
  return { event_name: name, payload, timestamp: new Date().toISOString() };
}

describe("eventBus", () => {
  // Each test gets a fresh subscription scope — unsubscribe after each
  const unsubs: Array<() => void> = [];
  beforeEach(() => {
    unsubs.forEach((fn) => fn());
    unsubs.length = 0;
  });

  it("wildcard subscriber receives all events", () => {
    const received: string[] = [];
    unsubs.push(subscribe("*", (e) => received.push(e.event_name)));

    emit(makeEvent("actor.updated"));
    emit(makeEvent("model.changed"));
    emit(makeEvent("governance.paused"));

    expect(received).toEqual(["actor.updated", "model.changed", "governance.paused"]);
  });

  it("exact topic match", () => {
    const received: string[] = [];
    unsubs.push(subscribe("actor.updated", (e) => received.push(e.event_name)));

    emit(makeEvent("actor.updated"));
    emit(makeEvent("actor.deleted"));
    emit(makeEvent("model.changed"));

    expect(received).toEqual(["actor.updated"]);
  });

  it("prefix topic match (e.g. 'actor' matches 'actor.updated')", () => {
    const received: string[] = [];
    unsubs.push(subscribe("actor", (e) => received.push(e.event_name)));

    emit(makeEvent("actor.updated"));
    emit(makeEvent("actor.deleted"));
    emit(makeEvent("model.changed"));

    expect(received).toEqual(["actor.updated", "actor.deleted"]);
  });

  it("unsubscribe stops delivery", () => {
    const received: string[] = [];
    const unsub = subscribe("actor", (e) => received.push(e.event_name));
    unsubs.push(unsub);

    emit(makeEvent("actor.updated"));
    unsub();
    emit(makeEvent("actor.deleted"));

    expect(received).toEqual(["actor.updated"]);
  });

  it("wildcard unsubscribe stops delivery", () => {
    const received: string[] = [];
    const unsub = subscribe("*", (e) => received.push(e.event_name));
    unsubs.push(unsub);

    emit(makeEvent("foo"));
    unsub();
    emit(makeEvent("bar"));

    expect(received).toEqual(["foo"]);
  });

  it("subscriber errors do not break other subscribers", () => {
    const received: string[] = [];
    unsubs.push(
      subscribe("test", () => {
        throw new Error("boom");
      }),
    );
    unsubs.push(subscribe("test", (e) => received.push(e.event_name)));

    emit(makeEvent("test.event"));

    expect(received).toEqual(["test.event"]);
  });

  it("multiple subscribers on same topic all receive events", () => {
    const a: string[] = [];
    const b: string[] = [];
    unsubs.push(subscribe("x", (e) => a.push(e.event_name)));
    unsubs.push(subscribe("x", (e) => b.push(e.event_name)));

    emit(makeEvent("x.y"));

    expect(a).toEqual(["x.y"]);
    expect(b).toEqual(["x.y"]);
  });
});
