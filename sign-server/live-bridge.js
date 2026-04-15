import { EventEmitter } from 'node:events';
import pkg from 'tiktok-live-connector';

const { WebcastPushConnection } = pkg;

function normalizeUsername(rawUsername) {
  return String(rawUsername || '').trim().replace(/^@+/, '').toLowerCase();
}

function asNumber(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function getUserLabel(data) {
  return data?.uniqueId || data?.nickname || data?.user?.uniqueId || data?.user?.nickname || 'unknown';
}

function getNickname(data) {
  return data?.nickname || data?.user?.nickname || null;
}

function getGiftName(data) {
  return data?.giftName || data?.giftDetails?.giftName || data?.extendedGiftInfo?.name || 'Gift';
}

function getViewerStats(data) {
  const current = Math.max(
    0,
    asNumber(data?.viewerCount, 0),
    asNumber(data?.viewer_count, 0),
    asNumber(data?.roomUserCount, 0),
    asNumber(data?.roomUserCountStr, 0),
  );
  const total = Math.max(
    current,
    asNumber(data?.topViewers?.length, 0),
    asNumber(data?.total, 0),
    asNumber(data?.totalViewerCount, 0),
  );
  return { current, total };
}

class LiveSession {
  constructor({ userId, username, bridge }) {
    this.userId = String(userId);
    this.username = normalizeUsername(username);
    this.bridge = bridge;
    this.connection = null;
    this.stopping = false;
    this.connected = false;
    this.reconnectTimer = null;
    this.reconnectAttempt = 0;
    this.maxReconnectAttempts = bridge.maxReconnectAttempts;
  }

  emitStatus(state, message, extra = {}) {
    this.bridge.broadcast({
      op: 'status',
      userId: this.userId,
      username: this.username,
      connected: state === 'connected',
      state,
      message,
      ...extra,
    });
  }

  emitError(code, message, extra = {}) {
    this.bridge.broadcast({
      op: 'error',
      userId: this.userId,
      username: this.username,
      code,
      message,
      ...extra,
    });
  }

  emitEvent(event, payload) {
    this.bridge.broadcast({
      op: 'event',
      userId: this.userId,
      username: this.username,
      event,
      payload,
    });
  }

  clearReconnectTimer() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  async connect({ isReconnect = false } = {}) {
    this.clearReconnectTimer();
    this.stopping = false;
    this.connected = false;

    if (!this.username) {
      this.emitError('INVALID_USERNAME', 'TikTok username is required');
      return;
    }

    this.emitStatus(
      isReconnect ? 'reconnecting' : 'connecting',
      isReconnect ? `Reconnecting to @${this.username}` : `Connecting to @${this.username}`,
      { attempt: this.reconnectAttempt || 0 },
    );

    const connection = new WebcastPushConnection(this.username, {
      enableExtendedGiftInfo: true,
      processInitialData: true,
      fetchRoomInfoOnConnect: true,
    });

    this.bindConnectionHandlers(connection);

    try {
      await connection.connect();
      this.connection = connection;
    } catch (error) {
      this.connection = null;
      this.handleConnectionFailure(error, isReconnect);
    }
  }

  bindConnectionHandlers(connection) {
    connection.on('connected', (state) => {
      this.connected = true;
      this.reconnectAttempt = 0;
      this.emitStatus('connected', `Connected to @${this.username}`, {
        roomId: state?.roomId ? String(state.roomId) : null,
      });
    });

    connection.on('disconnected', () => {
      this.handleUnexpectedDisconnect('Connection dropped');
    });

    connection.on('streamEnd', () => {
      this.handleUnexpectedDisconnect('Live stream ended');
    });

    connection.on('error', (error) => {
      this.handleUnexpectedDisconnect(error instanceof Error ? error.message : 'TikTok connection error');
    });

    connection.on('chat', (data) => {
      this.emitEvent('chat', {
        user: getUserLabel(data),
        nickname: getNickname(data),
        message: data?.comment || data?.commentText || '',
      });
    });

    connection.on('gift', (data) => {
      if (typeof data?.repeatEnd === 'boolean' && data.repeatEnd === false) {
        return;
      }

      const count = Math.max(1, asNumber(data?.repeatCount ?? data?.count, 1));
      const diamonds = Math.max(0, asNumber(data?.diamondCount ?? data?.giftDetails?.diamondCount, 0));

      this.emitEvent('gift', {
        user: getUserLabel(data),
        nickname: getNickname(data),
        giftId: String(data?.giftId ?? data?.giftDetails?.giftId ?? ''),
        giftName: getGiftName(data),
        count,
        diamonds,
      });
    });

    connection.on('like', (data) => {
      this.emitEvent('like', {
        user: getUserLabel(data),
        nickname: getNickname(data),
        count: Math.max(1, asNumber(data?.likeCount ?? data?.count, 1)),
      });
    });

    connection.on('member', (data) => {
      this.emitEvent('viewer_join', {
        username: data?.uniqueId || data?.user?.uniqueId || null,
        nickname: getNickname(data),
      });
    });

    connection.on('follow', (data) => {
      this.emitEvent('follow', {
        user: getUserLabel(data),
        nickname: getNickname(data),
      });
    });

    connection.on('subscribe', (data) => {
      this.emitEvent('subscribe', {
        user: getUserLabel(data),
        nickname: getNickname(data),
      });
    });

    connection.on('share', (data) => {
      this.emitEvent('share', {
        user: getUserLabel(data),
        nickname: getNickname(data),
      });
    });

    connection.on('social', (data) => {
      const label = String(data?.displayType || '').toLowerCase();
      if (label.includes('follow')) {
        this.emitEvent('follow', {
          user: getUserLabel(data),
          nickname: getNickname(data),
        });
      } else if (label.includes('share')) {
        this.emitEvent('share', {
          user: getUserLabel(data),
          nickname: getNickname(data),
        });
      }
    });

    connection.on('roomUser', (data) => {
      const { current, total } = getViewerStats(data);
      this.emitEvent('viewer', { current, total });
    });
  }

  handleConnectionFailure(error, isReconnect) {
    const message = error instanceof Error ? error.message : 'TikTok connection failed';
    this.connected = false;
    this.emitError(isReconnect ? 'RECONNECT_FAILED' : 'CONNECT_FAILED', message);
    this.scheduleReconnect(message);
  }

  handleUnexpectedDisconnect(message) {
    if (this.stopping) {
      return;
    }

    if (!this.connected && this.reconnectTimer) {
      return;
    }

    this.connected = false;
    this.scheduleReconnect(message || 'Connection lost');
  }

  scheduleReconnect(reason) {
    if (this.stopping) {
      return;
    }

    this.clearReconnectTimer();

    if (this.reconnectAttempt >= this.maxReconnectAttempts) {
      this.emitStatus('disconnected', `Disconnected from @${this.username}`);
      this.emitError('RECONNECT_EXHAUSTED', reason || 'Reconnect attempts exhausted');
      return;
    }

    this.reconnectAttempt += 1;
    const delaySec = Math.min(this.bridge.maxReconnectDelaySec, Math.max(1, this.bridge.baseReconnectDelaySec * (2 ** (this.reconnectAttempt - 1))));

    this.emitStatus('reconnecting', `Reconnecting to @${this.username}`, {
      attempt: this.reconnectAttempt,
      delaySec,
      reason,
    });

    this.reconnectTimer = setTimeout(async () => {
      this.reconnectTimer = null;
      await this.safeDisconnectConnection();
      await this.connect({ isReconnect: true });
    }, delaySec * 1000);
  }

  async safeDisconnectConnection() {
    if (!this.connection) {
      return;
    }
    try {
      await this.connection.disconnect();
    } catch {
      // ignore
    }
    this.connection = null;
  }

  async shutdown({ manual = false } = {}) {
    this.stopping = true;
    this.clearReconnectTimer();
    await this.safeDisconnectConnection();
    this.connected = false;
    if (!manual) {
      this.emitStatus('disconnected', `Disconnected from @${this.username}`);
    }
  }
}

export class TikTokLiveBridge extends EventEmitter {
  constructor({ backendToken = '', maxSessions = 1000, baseReconnectDelaySec = 2, maxReconnectDelaySec = 30, maxReconnectAttempts = 8 } = {}) {
    super();
    this.backendToken = String(backendToken || '').trim();
    this.maxSessions = maxSessions;
    this.baseReconnectDelaySec = baseReconnectDelaySec;
    this.maxReconnectDelaySec = maxReconnectDelaySec;
    this.maxReconnectAttempts = maxReconnectAttempts;
    this.sessions = new Map();
    this.backendClients = new Set();
  }

  stats() {
    let connected = 0;
    for (const session of this.sessions.values()) {
      if (session.connected) {
        connected += 1;
      }
    }
    return {
      sessions: this.sessions.size,
      connected,
      backendClients: this.backendClients.size,
    };
  }

  isAuthorized(token) {
    if (!this.backendToken) {
      return true;
    }
    return String(token || '').trim() === this.backendToken;
  }

  addBackendClient(ws) {
    this.backendClients.add(ws);
    ws.send(JSON.stringify({ op: 'ready', ...this.stats() }));
    for (const session of this.sessions.values()) {
      ws.send(JSON.stringify({
        op: 'status',
        userId: session.userId,
        username: session.username,
        connected: session.connected,
        state: session.connected ? 'connected' : 'idle',
        message: session.connected ? `Connected to @${session.username}` : `Idle @${session.username}`,
      }));
    }
  }

  removeBackendClient(ws) {
    this.backendClients.delete(ws);
  }

  broadcast(payload) {
    const raw = JSON.stringify(payload);
    for (const client of this.backendClients) {
      if (client.readyState === client.OPEN) {
        client.send(raw);
      }
    }
  }

  async subscribe({ userId, username }) {
    const normalizedUserId = String(userId || '').trim();
    const normalizedUsername = normalizeUsername(username);

    if (!normalizedUserId) {
      throw new Error('userId is required');
    }
    if (!normalizedUsername) {
      throw new Error('username is required');
    }

    const existing = this.sessions.get(normalizedUserId);
    if (existing && existing.username === normalizedUsername) {
      return existing;
    }

    if (!existing && this.sessions.size >= this.maxSessions) {
      throw new Error(`Session limit reached (${this.maxSessions})`);
    }

    if (existing) {
      await existing.shutdown({ manual: true });
      this.sessions.delete(normalizedUserId);
    }

    const session = new LiveSession({ userId: normalizedUserId, username: normalizedUsername, bridge: this });
    this.sessions.set(normalizedUserId, session);
    await session.connect();
    return session;
  }

  async unsubscribe(userId) {
    const normalizedUserId = String(userId || '').trim();
    const session = this.sessions.get(normalizedUserId);
    if (!session) {
      return false;
    }
    await session.shutdown({ manual: true });
    this.sessions.delete(normalizedUserId);
    this.broadcast({ op: 'unsubscribed', userId: normalizedUserId });
    return true;
  }
}