import { describe, expect, it } from "vitest";

import {
  DEFAULT_RECONNECT_POLICY,
  RealtimeTransport,
  type RealtimeScheduler,
  type RealtimeSocket,
  type RealtimeStatus
} from "./realtime";

class FakeSocket implements RealtimeSocket {
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onmessage: ((event: { data: unknown }) => void) | null = null;
  closeCalls = 0;

  close(): void {
    this.closeCalls += 1;
  }
}

class FakeScheduler implements RealtimeScheduler {
  readonly scheduled: Array<{ delayMs: number; task: () => void }> = [];
  clearCalls = 0;

  setTimeout(task: () => void, delayMs: number): number {
    this.scheduled.push({ task, delayMs });
    return this.scheduled.length;
  }

  clearTimeout(_handle: unknown): void {
    this.clearCalls += 1;
    this.scheduled.shift();
  }

  runNext(): void {
    const next = this.scheduled.shift();
    if (!next) throw new Error("no scheduled task");
    next.task();
  }
}

function harness() {
  const sockets: FakeSocket[] = [];
  const scheduler = new FakeScheduler();
  const statuses: RealtimeStatus[] = [];
  const transport = new RealtimeTransport({
    url: "wss://stream.example.invalid/events",
    socketFactory: () => {
      const socket = new FakeSocket();
      sockets.push(socket);
      return socket;
    },
    scheduler,
    policy: { maxAttempts: 2, baseDelayMs: 1000, maxDelayMs: 1500 },
    onStatus: (status) => statuses.push(status)
  });
  return { sockets, scheduler, statuses, transport };
}

describe("RealtimeTransport", () => {
  it("stays explicitly disabled when no public endpoint is configured", () => {
    const statuses: RealtimeStatus[] = [];
    let sockets = 0;
    const transport = new RealtimeTransport({
      socketFactory: () => {
        sockets += 1;
        return new FakeSocket();
      },
      onStatus: (status) => statuses.push(status)
    });

    transport.start();

    expect(sockets).toBe(0);
    expect(statuses.at(-1)).toEqual({
      state: "DISABLED",
      attempt: 0,
      reason: "realtime endpoint not configured"
    });
  });

  it("connects and resets the retry counter after an open event", () => {
    const { sockets, statuses, transport } = harness();

    transport.start();
    expect(statuses.at(-1)).toEqual({ state: "CONNECTING", attempt: 0 });
    sockets[0].onopen?.();
    expect(statuses.at(-1)).toEqual({ state: "CONNECTED", attempt: 0 });

    sockets[0].onclose?.();
    expect(statuses.at(-1)).toEqual({
      state: "RECONNECTING",
      attempt: 1,
      reason: "connection closed"
    });
  });

  it("uses bounded exponential reconnect delays and degrades after exhaustion", () => {
    const { sockets, scheduler, statuses, transport } = harness();

    transport.start();
    sockets[0].onclose?.();
    expect(scheduler.scheduled[0]?.delayMs).toBe(1000);
    scheduler.runNext();
    expect(sockets).toHaveLength(2);
    sockets[1].onclose?.();
    expect(scheduler.scheduled[0]?.delayMs).toBe(1500);
    scheduler.runNext();
    expect(sockets).toHaveLength(3);
    sockets[2].onclose?.();

    expect(scheduler.scheduled).toHaveLength(0);
    expect(statuses.at(-1)).toEqual({
      state: "DEGRADED",
      attempt: 2,
      reason: "reconnect attempts exhausted"
    });
  });

  it("does not schedule twice when an error is followed by close", () => {
    const { sockets, scheduler, transport } = harness();

    transport.start();
    sockets[0].onerror?.();
    sockets[0].onclose?.();

    expect(scheduler.scheduled).toHaveLength(1);
  });

  it("stops cleanly and ignores incoming message data", () => {
    const { sockets, scheduler, statuses, transport } = harness();

    transport.start();
    sockets[0].onclose?.();
    expect(scheduler.scheduled).toHaveLength(1);
    const event = {
      get data(): unknown {
        throw new Error("message data must not be inspected");
      }
    };
    expect(() => sockets[0].onmessage?.(event)).not.toThrow();

    transport.stop();

    expect(scheduler.clearCalls).toBe(1);
    expect(sockets[0].closeCalls).toBe(1);
    expect(statuses.at(-1)).toEqual({ state: "STOPPED", attempt: 1 });
  });

  it("exposes a bounded default reconnect policy", () => {
    expect(DEFAULT_RECONNECT_POLICY).toEqual({
      maxAttempts: 5,
      baseDelayMs: 1000,
      maxDelayMs: 15000
    });
  });
});
