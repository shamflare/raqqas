/**
 * خدمة واتساب لسوق الرقة — ترسل رموز استعادة كلمة المرور.
 *
 * ⚠️ **مسار غير رسمي.** هذه الخدمة تتصل بواتساب كأنها «جهاز مرتبط» عبر
 * Baileys. تشغيل بوت على رقم واتساب عادي مخالف لشروط الاستخدام، وقد تحظر Meta
 * الرقم بلا إنذار. استعمل رقمًا **مخصّصًا للتطبيق** لا رقمًا شخصيًا.
 * التفاصيل والبدائل في deploy/WHATSAPP.md.
 *
 * تصميمها:
 * - تُصغي على 127.0.0.1 وحدها — لا منفذ مكشوف على الإنترنت، ونقارن رمزًا
 *   مشتركًا في الترويسة فوق ذلك (دفاعان لا واحد).
 * - تحفظ الجلسة على القرص، فلا تحتاج مسح QR إلا مرّة واحدة.
 * - تعيد الاتصال تلقائيًا، وتميّز «انقطاع» من «خروج نهائي» — الثاني يحتاج
 *   إعادة ربط بشرية ولا فائدة من محاولات لا تنتهي.
 * - تُباعد بين الرسائل بفاصل عشوائي: دفقة رسائل متطابقة التوقيت من رقم واحد
 *   هي بعينها ما ترصده أنظمة الحظر الآلي.
 */

import { createServer } from 'node:http';
import { setTimeout as sleep } from 'node:timers/promises';

import makeWASocket, {
  DisconnectReason,
  useMultiFileAuthState,
} from '@whiskeysockets/baileys';
import qrcode from 'qrcode-terminal';

const PORT = Number(process.env.WA_BOT_PORT || 8787);
const HOST = process.env.WA_BOT_HOST || '127.0.0.1';
const TOKEN = process.env.WA_BOT_TOKEN || '';
const SESSION_DIR = process.env.WA_SESSION_DIR || '/etc/souq/wa-session';
/** وضع الربط: يعرض رمز QR ثم يخرج فور نجاح الاتصال. */
const PAIR_ONLY = process.env.WA_PAIR_ONLY === '1';

/** فاصل بين رسالتين متتاليتين — يُشوّش على كاشفات الإرسال الآلي. */
const MIN_GAP_MS = 1500;
const MAX_GAP_MS = 4000;

if (!TOKEN && !PAIR_ONLY) {
  console.error('WA_BOT_TOKEN غير مضبوط — لن تُقبل أي طلبات. أوقفت التشغيل.');
  process.exit(1);
}

const log = (...args) => console.log(new Date().toISOString(), ...args);

/** واجهة pino صامتة — `child()` يعيد نفسه فتعمل أي سلسلة استدعاءات. */
const silentLogger = {
  level: 'silent',
  trace() {},
  debug() {},
  info() {},
  warn() {},
  error() {},
  fatal() {},
  child() {
    return silentLogger;
  },
};

/* ------------------------------------------------------------------ واتساب */

let sock = null;
let ready = false;
let lastSentAt = 0;

async function connect() {
  const { state, saveCreds } = await useMultiFileAuthState(SESSION_DIR);

  sock = makeWASocket({
    auth: state,
    // لا نطبع QR بأنفسنا من داخل المكتبة: نتحكّم بالعرض في `connection.update`
    printQRInTerminal: false,
    // Baileys يتوقّع واجهة pino كاملة — وهو ثرثار جدًا على المستوى الافتراضي،
    // فنمرّر صامتًا. سجلّنا نحن في `log()` أعلاه ويكفي للتشخيص.
    logger: silentLogger,
    syncFullHistory: false,
    markOnlineOnConnect: false,
  });

  sock.ev.on('creds.update', saveCreds);

  sock.ev.on('connection.update', async (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      console.log('\n امسح رمز QR من واتساب ← الأجهزة المرتبطة ← ربط جهاز:\n');
      qrcode.generate(qr, { small: true });
    }

    if (connection === 'open') {
      ready = true;
      log('متصل بواتساب ✅', sock.user?.id ?? '');
      if (PAIR_ONLY) {
        log('تم الربط. الجلسة محفوظة في', SESSION_DIR);
        // مهلة قصيرة ليُكتب الاعتماد على القرص قبل الخروج
        await sleep(2000);
        process.exit(0);
      }
    }

    if (connection === 'close') {
      ready = false;
      const status = lastDisconnect?.error?.output?.statusCode;
      // `loggedOut` يعني أن الربط أُلغي من الهاتف أو حُظر الرقم: إعادة المحاولة
      // لن تنجح أبدًا، وتكرارها بلا نهاية يملأ السجلّ ويخفي السبب الحقيقي.
      if (status === DisconnectReason.loggedOut) {
        log('انتهى الربط نهائيًا — يلزم مسح QR من جديد: npm run pair');
        return;
      }
      log('انقطع الاتصال، إعادة المحاولة بعد 5 ثوانٍ…', status ?? '');
      await sleep(5000);
      connect().catch((error) => log('فشل إعادة الاتصال:', error?.message));
    }
  });
}

async function sendText(to, text) {
  if (!ready || !sock) throw new Error('غير متصل بواتساب');

  const gap = MIN_GAP_MS + Math.random() * (MAX_GAP_MS - MIN_GAP_MS);
  const wait = lastSentAt + gap - Date.now();
  if (wait > 0) await sleep(wait);
  lastSentAt = Date.now();

  const digits = String(to).replace(/\D/g, '');
  if (digits.length < 8) throw new Error('رقم غير صالح');

  const [result] = await sock.onWhatsApp(digits);
  if (!result?.exists) {
    // خطأ يُعرَض للمستخدم عبر Django: «هذا الرقم ليس عليه واتساب»
    const error = new Error('no_whatsapp');
    error.expected = true;
    throw error;
  }

  await sock.sendMessage(result.jid, { text });
}

/* -------------------------------------------------------------------- HTTP */

function readBody(request) {
  return new Promise((resolve, reject) => {
    let raw = '';
    request.on('data', (chunk) => {
      raw += chunk;
      // حدّ أعلى: لا سبب لجسم أكبر من هذا، ووجوده يعني خطأً أو عبثًا
      if (raw.length > 8192) reject(new Error('الجسم كبير جدًا'));
    });
    request.on('end', () => resolve(raw));
    request.on('error', reject);
  });
}

const json = (response, code, payload) => {
  response.writeHead(code, { 'Content-Type': 'application/json; charset=utf-8' });
  response.end(JSON.stringify(payload));
};

const server = createServer(async (request, response) => {
  if (request.method === 'GET' && request.url === '/health') {
    return json(response, ready ? 200 : 503, { ready });
  }

  if (request.method !== 'POST' || request.url !== '/send') {
    return json(response, 404, { error: 'not_found' });
  }

  if (request.headers['x-bot-token'] !== TOKEN) {
    log('طلب برمز خاطئ — مرفوض');
    return json(response, 401, { error: 'unauthorized' });
  }

  let payload;
  try {
    payload = JSON.parse((await readBody(request)) || '{}');
  } catch {
    return json(response, 400, { error: 'bad_json' });
  }

  const { to, text } = payload;
  if (!to || !text) return json(response, 400, { error: 'missing_fields' });

  try {
    await sendText(to, text);
    // لا نسجّل نصّ الرسالة: فيه رمز الاستعادة، ولا مكان له في سجلّ الخادم
    log('أُرسلت رسالة إلى', String(to).slice(0, 5) + '…');
    return json(response, 200, { sent: true });
  } catch (error) {
    log('فشل الإرسال:', error?.message);
    return json(response, error?.expected ? 422 : 502, {
      error: error?.message || 'send_failed',
    });
  }
});

server.listen(PORT, HOST, () => log(`تُصغي على http://${HOST}:${PORT}`));

connect().catch((error) => {
  log('تعذّر الاتصال بواتساب:', error?.message);
  process.exit(1);
});
