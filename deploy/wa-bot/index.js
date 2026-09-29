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
 * - **رمز QR يُقدَّم صورةً عبر `/status`** ليمسحه الأدمن من لوحة الإدارة بلا
 *   طرفية ولا SSH. القرار: من يملك الرقم ليس بالضرورة من يملك الخادم.
 * - تعيد الاتصال تلقائيًا، وتميّز «انقطاع» من «خروج نهائي» — الثاني يحتاج
 *   إعادة ربط بشرية ولا فائدة من محاولات لا تنتهي.
 * - تُباعد بين الرسائل بفاصل عشوائي: دفقة رسائل متطابقة التوقيت من رقم واحد
 *   هي بعينها ما ترصده أنظمة الحظر الآلي.
 */

import { createServer } from 'node:http';
import { readdir, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { setTimeout as sleep } from 'node:timers/promises';

import makeWASocket, {
  DisconnectReason,
  useMultiFileAuthState,
} from '@whiskeysockets/baileys';
import QRCode from 'qrcode';
import qrcodeTerminal from 'qrcode-terminal';

const PORT = Number(process.env.WA_BOT_PORT || 8787);
const HOST = process.env.WA_BOT_HOST || '127.0.0.1';
const TOKEN = process.env.WA_BOT_TOKEN || '';
const SESSION_DIR = process.env.WA_SESSION_DIR || '/etc/souq/wa-session';
/** وضع الربط من الطرفية: يطبع QR ثم يخرج فور نجاح الاتصال. */
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

/* ------------------------------------------------------------------ الحالة */

let sock = null;
let ready = false;
let lastSentAt = 0;
let connectedAt = null;
/** آخر رمز QR صالح، صورةً جاهزة للعرض. يُمسح فور نجاح الربط. */
let qrImage = null;
let qrIssuedAt = null;
/** يصير true حين يُلغى الربط نهائيًا — تقرؤه اللوحة فتعرض «أعد الربط». */
let loggedOut = false;

function state() {
  return {
    ready,
    /** الرقم المرتبط، بلا لاحقة الجهاز */
    number: sock?.user?.id ? '+' + sock.user.id.split(':')[0].split('@')[0] : null,
    name: sock?.user?.name ?? null,
    connected_at: connectedAt,
    qr: qrImage,
    qr_age: qrIssuedAt ? Math.round((Date.now() - qrIssuedAt) / 1000) : null,
    logged_out: loggedOut,
  };
}

/* ---------------------------------------------------------------- واتساب */

async function connect() {
  const { state: auth, saveCreds } = await useMultiFileAuthState(SESSION_DIR);

  sock = makeWASocket({
    auth,
    // لا نطبع QR من داخل المكتبة: نتحكّم بالعرض في `connection.update`
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
      loggedOut = false;
      qrIssuedAt = Date.now();
      // صورة للوحة الإدارة…
      qrImage = await QRCode.toDataURL(qr, { margin: 1, width: 320 })
        .catch((error) => {
          log('تعذّر توليد صورة QR:', error?.message);
          return null;
        });
      // …ونصّ للطرفية، لمن يفضّل الربط عبر SSH
      if (PAIR_ONLY) {
        console.log('\n امسح رمز QR من واتساب ← الأجهزة المرتبطة ← ربط جهاز:\n');
        qrcodeTerminal.generate(qr, { small: true });
      } else {
        log('رمز QR جديد جاهز — افتح لوحة الإدارة ← واتساب');
      }
    }

    if (connection === 'open') {
      ready = true;
      loggedOut = false;
      qrImage = null;
      qrIssuedAt = null;
      connectedAt = new Date().toISOString();
      log('متصل بواتساب ✅', sock.user?.id ?? '');
      if (PAIR_ONLY) {
        log('تم الربط. الجلسة محفوظة في', SESSION_DIR);
        await sleep(2000); // ليُكتب الاعتماد على القرص قبل الخروج
        process.exit(0);
      }
    }

    if (connection === 'close') {
      ready = false;
      connectedAt = null;
      const status = lastDisconnect?.error?.output?.statusCode;
      // `loggedOut` يعني أن الربط أُلغي من الهاتف أو حُظر الرقم: إعادة المحاولة
      // بنفس الجلسة لن تنجح أبدًا. نمسح الجلسة ونعيد الاتصال ليُولَّد QR جديد،
      // فيستطيع الأدمن الربط من اللوحة بلا لمس الخادم.
      if (status === DisconnectReason.loggedOut) {
        log('انتهى الربط — نمسح الجلسة ونعرض رمزًا جديدًا');
        loggedOut = true;
        await resetSession();
        return;
      }
      log('انقطع الاتصال، إعادة المحاولة بعد 5 ثوانٍ…', status ?? '');
      await sleep(5000);
      connect().catch((error) => log('فشل إعادة الاتصال:', error?.message));
    }
  });
}

/** يمحو ملفات الجلسة ويعيد الاتصال — فيبدأ الربط من الصفر. */
async function resetSession() {
  try {
    sock?.ev?.removeAllListeners?.();
    sock?.end?.(undefined);
  } catch {
    /* السوكيت ميت أصلًا */
  }
  sock = null;
  ready = false;
  qrImage = null;
  // نمحو **محتوى** المجلد لا المجلد نفسه: systemd يربطه وحده قابلًا للكتابة
  // داخل /etc المقفلة (ReadWritePaths)، فحذفه يرمي EROFS ويُسقط الخدمة —
  // وهكذا بقيت تسقط وتقوم آلاف المرات بلا QR بعد أول فكّ ربط.
  const entries = await readdir(SESSION_DIR).catch(() => []);
  await Promise.all(
    entries.map((name) => rm(join(SESSION_DIR, name), { recursive: true, force: true })),
  );
  await sleep(1000);
  return connect();
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

const authorized = (request) => request.headers['x-bot-token'] === TOKEN;

const ROUTES = {
  'GET /health': async (request, response) => json(response, ready ? 200 : 503, { ready }),

  'GET /status': async (request, response) => {
    if (!authorized(request)) return json(response, 401, { error: 'unauthorized' });
    return json(response, 200, state());
  },

  'POST /logout': async (request, response) => {
    if (!authorized(request)) return json(response, 401, { error: 'unauthorized' });
    // فكّ الربط من طرفنا **وطرف واتساب**: مسح الملفات وحده يترك الجهاز ظاهرًا
    // في قائمة «الأجهزة المرتبطة» على هاتف صاحب الرقم إلى الأبد.
    try {
      await sock?.logout?.();
    } catch (error) {
      log('تعذّر إبلاغ واتساب بفكّ الربط:', error?.message);
    }
    await resetSession();
    log('فُكّ الربط بطلب من اللوحة');
    return json(response, 200, { ok: true });
  },

  'POST /send': async (request, response) => {
    if (!authorized(request)) return json(response, 401, { error: 'unauthorized' });

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
  },
};

const server = createServer(async (request, response) => {
  const path = (request.url || '').split('?')[0];
  const handler = ROUTES[`${request.method} ${path}`];
  if (!handler) return json(response, 404, { error: 'not_found' });
  try {
    await handler(request, response);
  } catch (error) {
    log('خطأ غير متوقّع:', error?.message);
    if (!response.headersSent) json(response, 500, { error: 'internal' });
  }
});

server.listen(PORT, HOST, () => log(`تُصغي على http://${HOST}:${PORT}`));

connect().catch((error) => {
  log('تعذّر الاتصال بواتساب:', error?.message);
  process.exit(1);
});
