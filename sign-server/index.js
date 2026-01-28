import express from 'express';
import cors from 'cors';
import bodyParser from 'body-parser';

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

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`TTBoost Sign Server running on http://localhost:${PORT}`);
});
