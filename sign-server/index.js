import express from 'express';
import cors from 'cors';
import bodyParser from 'body-parser';
import { createServer } from 'node:http';
import { WebSocketServer } from 'ws';
import { TikTokLiveBridge } from './live-bridge.js';

// Плагин-подписчик. По умолчанию отсутствует.
// Если вы добавите файл ./tiktok_signer.js и экспортируете функцию signWebcastRequest({ url, userAgent }),
// сервер начнет подписывать запросы. Без него сервер вернет 501.
let signer = null;
try {
  const mod = await import('./tiktok_signer.js');
  if (typeof mod.signWebcastRequest === 'function') {
    signer = mod.signWebcastRequest;
    console.log('Signer loaded from tiktok_signer.js');
  } else {
    console.warn('tiktok_signer.js найден, но не экспортирует signWebcastRequest().');
  }
} catch {
  console.warn('tiktok_signer.js не найден. Сервер будет отвечать 501 Not Implemented.');
}

const app = express();
app.use(cors());
app.use(bodyParser.json());
const httpServer = createServer(app);

const bridge = new TikTokLiveBridge({
  backendToken: process.env.TIKTOK_BRIDGE_TOKEN || '',
  maxSessions: Number(process.env.TIKTOK_BRIDGE_MAX_SESSIONS || 1000),
  baseReconnectDelaySec: Number(process.env.TIKTOK_BRIDGE_RECONNECT_BASE_SEC || 2),
  maxReconnectDelaySec: Number(process.env.TIKTOK_BRIDGE_RECONNECT_MAX_SEC || 30),
  maxReconnectAttempts: Number(process.env.TIKTOK_BRIDGE_RECONNECT_ATTEMPTS || 8),
});

const bridgeServer = new WebSocketServer({ noServer: true });

httpServer.on('upgrade', (request, socket, head) => {
  const url = new URL(request.url || '/', 'http://localhost');
  if (url.pathname !== '/bridge') {
    socket.destroy();
    return;
  }

  const token = url.searchParams.get('token') || request.headers['x-bridge-token'] || '';
  if (!bridge.isAuthorized(token)) {
    socket.write('HTTP/1.1 401 Unauthorized\r\n\r\n');
    socket.destroy();
    return;
  }

  bridgeServer.handleUpgrade(request, socket, head, (ws) => {
    bridgeServer.emit('connection', ws, request);
  });
});

bridgeServer.on('connection', (ws) => {
  bridge.addBackendClient(ws);

  ws.on('message', async (raw) => {
    let data;
    try {
      data = JSON.parse(String(raw || '{}'));
    } catch {
      ws.send(JSON.stringify({ op: 'error', code: 'BAD_JSON', message: 'Invalid JSON' }));
      return;
    }

    try {
      if (data?.op === 'ping') {
        ws.send(JSON.stringify({ op: 'pong', ts: Date.now() }));
        return;
      }

      if (data?.op === 'subscribe') {
        await bridge.subscribe({ userId: data.userId, username: data.username });
        ws.send(JSON.stringify({ op: 'ack', requestId: data.requestId || null, userId: data.userId }));
        return;
      }

      if (data?.op === 'unsubscribe') {
        await bridge.unsubscribe(data.userId);
        ws.send(JSON.stringify({ op: 'ack', requestId: data.requestId || null, userId: data.userId }));
        return;
      }

      if (data?.op === 'stats') {
        ws.send(JSON.stringify({ op: 'stats', ...bridge.stats() }));
        return;
      }

      ws.send(JSON.stringify({ op: 'error', code: 'UNKNOWN_OP', message: 'Unknown operation' }));
    } catch (error) {
      ws.send(JSON.stringify({
        op: 'error',
        requestId: data?.requestId || null,
        userId: data?.userId || null,
        code: 'COMMAND_FAILED',
        message: error instanceof Error ? error.message : 'Command failed',
      }));
    }
  });

  ws.on('close', () => {
    bridge.removeBackendClient(ws);
  });
});

app.post('/sign', (req, res) => {
  const { url, userAgent } = req.body || {};
  if (!url) {
    return res.status(400).json({ error: 'url is required' });
  }
  if (!signer) {
    return res.status(501).json({
      error: 'signer not implemented',
      hint: 'Добавьте файл sign-server/tiktok_signer.js с экспортом функции signWebcastRequest({ url, userAgent })'
    });
  }
  try {
    const result = signer({ url, userAgent });
    return res.json(result);
  } catch (err) {
    console.error('SIGN ERROR:', err);
    return res.status(500).json({ error: 'failed to sign' });
  }
});

app.get('/health', (_req, res) => {
  res.json({ ok: true, bridge: bridge.stats(), signerEnabled: Boolean(signer) });
});

const PORT = process.env.PORT || 3000;
httpServer.listen(PORT, () => {
  console.log(`TTBoost Sign Server running on http://localhost:${PORT}`);
});
