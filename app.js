const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
}

const fromEl = document.getElementById("from");
const toEl = document.getElementById("to");
const srcEl = document.getElementById("src");
const dstEl = document.getElementById("dst");
const hintEl = document.getElementById("hint");
const swapBtn = document.getElementById("swap");
// Кнопка больше не нужна, но если она в HTML есть — можно скрыть
const goBtn = document.getElementById("go");

if (goBtn) goBtn.style.display = "none";

function setHint(text) {
  hintEl.textContent = text || "";
}

function swapLanguages() {
  const a = fromEl.value;
  const b = toEl.value;

  // если слева auto — при swap сделаем слева язык справа, а справа auto не ставим
  fromEl.value = b;
  toEl.value = a === "auto" ? "en" : a;

  const t = srcEl.value;
  srcEl.value = dstEl.value;
  dstEl.value = t;

  scheduleTranslate();
}

// --- мгновенный перевод (debounce) + abort предыдущего запроса ---
let debounceTimer = null;
let currentAbort = null;
let lastPayloadKey = "";

function payloadKey(q, source, target) {
  return `${source}>>${target}::${q}`;
}

function scheduleTranslate() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => translateOnce(), 450);
}

async function translateOnce() {
  const q = (srcEl.value || "").trim();
  if (!q) {
    dstEl.value = "";
    setHint("");
    lastPayloadKey = "";
    if (currentAbort) currentAbort.abort();
    currentAbort = null;
    return;
  }

  const source = fromEl.value;
  const target = toEl.value;

  const key = payloadKey(q, source, target);
  if (key === lastPayloadKey) return; // не дергаем API, если ничего не поменялось
  lastPayloadKey = key;

  if (currentAbort) currentAbort.abort();
  currentAbort = new AbortController();

  setHint("Перевожу…");

  try {
    const r = await fetch("/api/translate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ q, source, target }),
      signal: currentAbort.signal,
    });

    const text = await r.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch {
      throw new Error(text.slice(0, 200) || "Ответ сервера не JSON");
    }

    if (!r.ok) {
      // показываем максимально понятную ошибку от твоего API
      const msg =
        data?.error ||
        `HTTP ${r.status}` +
          (data?.details ? `: ${data.details}` : "");
      throw new Error(msg);
    }

    dstEl.value = data.translatedText || "";
    setHint("");
  } catch (e) {
    // abort — это нормально, не показываем как ошибку
    if (e?.name === "AbortError") return;
    setHint("Ошибка: " + (e?.message || e));
  }
}

// События
swapBtn.addEventListener("click", swapLanguages);

// печатаешь — переводит
srcEl.addEventListener("input", scheduleTranslate);

// поменял язык — сразу переводит
fromEl.addEventListener("change", scheduleTranslate);
toEl.addEventListener("change", scheduleTranslate);

// бонус: Ctrl+Enter — вставить перевод обратно (по желанию)
srcEl.addEventListener("keydown", (ev) => {
  if ((ev.ctrlKey || ev.metaKey) && ev.key === "Enter") {
    srcEl.value = dstEl.value || srcEl.value;
    scheduleTranslate();
  }
});
