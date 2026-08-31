export type RealtimeState =
  | "DISABLED"
  | "CONNECTING"
  | "CONNECTED"
  | "RECONNECTING"
  | "DEGRADED"
  | "STOPPED";

export interface RealtimeStatus {
  state: RealtimeState;
  attempt: number;
  reason?: string;
}

export interface RealtimeSocket {
  onopen: (() => void) | null;
  onerror: (() => void) | null;
  onclose: (() => void) | null;
  onmessage: ((event: { data: unknown }) => void) | null;
  close(): void;
}

export interface RealtimeScheduler {
  setTimeout(task: () => void, delayMs: number): unknown;
  clearTimeout(handle: unknown): void;
}

export interface ReconnectPolicy {
  maxAttempts: number;
  baseDelayMs: number;
  maxDelayMs: number;
}

export const DEFAULT_RECONNECT_POLICY: Readonly<ReconnectPolicy> = {
  maxAttempts: 5,
  baseDelayMs: 1000,
  maxDelayMs: 15000
};

type SocketFactory = (url: string) => RealtimeSocket;

interface RealtimeTransportOptions {
  url?: string;
  socketFactory?: SocketFactory;
  scheduler?: RealtimeScheduler;
  policy?: ReconnectPolicy;
  onStatus?: (status: RealtimeStatus) => void;
}

const browserSocketFactory: SocketFactory = (url) => {
  const browserSocket = new WebSocket(url);
  const socket: RealtimeSocket = {
    onopen: null,
    onerror: null,
    onclose: null,
    onmessage: null,
    close: () => browserSocket.close()
  };
  browserSocket.addEventListener("open", () => socket.onopen?.());
  browserSocket.addEventListener("error", () => socket.onerror?.());
  browserSocket.addEventListener("close", () => socket.onclose?.());
  browserSocket.addEventListener("message", (event) => socket.onmessage?.({ data: event.data }));
  return socket;
};
const browserScheduler: RealtimeScheduler = {
  setTimeout: (task, delayMs) => window.setTimeout(task, delayMs),
  clearTimeout: (handle) => window.clearTimeout(handle as number)
};

function statusValue(state: RealtimeState, attempt: number, reason?: string): RealtimeStatus {
  return reason ? { state, attempt, reason } : { state, attempt };
}

function boundedPolicy(policy: ReconnectPolicy): ReconnectPolicy {
  const maxAttempts = Number.isFinite(policy.maxAttempts)
    ? Math.max(0, Math.floor(policy.maxAttempts))
    : DEFAULT_RECONNECT_POLICY.maxAttempts;
  const baseDelayMs = Number.isFinite(policy.baseDelayMs)
    ? Math.max(0, policy.baseDelayMs)
    : DEFAULT_RECONNECT_POLICY.baseDelayMs;
  const maxDelayMs = Number.isFinite(policy.maxDelayMs)
    ? Math.max(baseDelayMs, policy.maxDelayMs)
    : DEFAULT_RECONNECT_POLICY.maxDelayMs;
  return { maxAttempts, baseDelayMs, maxDelayMs };
}

export class RealtimeTransport {
  private readonly url: string | undefined;
  private readonly socketFactory: SocketFactory;
  private readonly scheduler: RealtimeScheduler;
  private readonly policy: ReconnectPolicy;
  private readonly onStatus: (status: RealtimeStatus) => void;
  private socket: RealtimeSocket | null = null;
  private retryHandle: unknown = null;
  private retries = 0;
  private stopped = true;

  constructor(options: RealtimeTransportOptions = {}) {
    this.url = options.url;
    this.socketFactory = options.socketFactory ?? browserSocketFactory;
    this.scheduler = options.scheduler ?? browserScheduler;
    this.policy = boundedPolicy(options.policy ?? DEFAULT_RECONNECT_POLICY);
    this.onStatus = options.onStatus ?? (() => undefined);
  }

  start(): void {
    if (!this.stopped) return;
    this.stopped = false;
    this.retries = 0;
    if (!this.url) {
      this.onStatus(statusValue("DISABLED", 0, "realtime endpoint not configured"));
      return;
    }
    this.connect();
  }

  stop(): void {
    if (this.stopped) return;
    this.stopped = true;
    if (this.retryHandle !== null) {
      this.scheduler.clearTimeout(this.retryHandle);
      this.retryHandle = null;
    }
    const socket = this.socket;
    this.socket = null;
    if (socket) {
      this.detach(socket);
      socket.close();
    }
    this.onStatus(statusValue("STOPPED", this.retries));
  }

  private connect(): void {
    if (this.stopped || !this.url) return;
    const socket = this.socketFactory(this.url);
    this.socket = socket;
    this.onStatus(statusValue(this.retries ? "RECONNECTING" : "CONNECTING", this.retries));
    socket.onopen = () => {
      if (this.socket !== socket || this.stopped) return;
      this.retries = 0;
      this.onStatus(statusValue("CONNECTED", 0));
    };
    socket.onerror = () => this.disconnect(socket, "connection error");
    socket.onclose = () => this.disconnect(socket, "connection closed");
    // The first sprint owns lifecycle only. Never parse or forward stream data.
    socket.onmessage = () => undefined;
  }

  private disconnect(socket: RealtimeSocket, reason: string): void {
    if (this.socket !== socket) return;
    this.socket = null;
    this.detach(socket);
    socket.close();
    if (this.stopped) return;
    if (this.retries >= this.policy.maxAttempts) {
      this.onStatus(statusValue("DEGRADED", this.retries, "reconnect attempts exhausted"));
      return;
    }
    this.retries += 1;
    const delayMs = Math.min(
      this.policy.baseDelayMs * 2 ** (this.retries - 1),
      this.policy.maxDelayMs
    );
    this.onStatus(statusValue("RECONNECTING", this.retries, reason));
    this.retryHandle = this.scheduler.setTimeout(() => {
      this.retryHandle = null;
      this.connect();
    }, delayMs);
  }

  private detach(socket: RealtimeSocket): void {
    socket.onopen = null;
    socket.onerror = null;
    socket.onclose = null;
    socket.onmessage = null;
  }
}
