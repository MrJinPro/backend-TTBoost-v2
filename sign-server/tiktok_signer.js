// Пример простого подписчика (DEMO). Замените на свою реализацию.
// Экспортируемая функция должна принимать объект { url, userAgent }
// и возвращать объект { signed_url, xBogus, userAgent }.

import crypto from 'crypto';

export function signWebcastRequest({ url, userAgent = defaultUserAgent() }) {
  const xBogus = generateXBogus(url, userAgent);
  const glue = url.includes('?') ? '&' : '?';
  const signed_url = `${url}${glue}X-Bogus=${xBogus}`;
  return { signed_url, xBogus, userAgent };
}

function generateXBogus(url, userAgent) {
  const md5 = crypto.createHash('md5').update(url + userAgent).digest('hex');
  const sha = crypto.createHash('sha256').update(md5).digest('hex');
  // Упрощенный пример. Для продакшена замените алгоритм на актуальный.
  return Buffer.from(sha.substring(0, 16)).toString('base64url');
}

function defaultUserAgent() {
  return 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)';
}
