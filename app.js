const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
}

// DOM
const fromEl = document.getElementById("from");
const toEl = document.getElementById("to");
const srcEl = document.getElementById("src");
const dstEl = document.getElementById("dst");
const hintEl = document.getElementById("hint");
const swapBtn = document.getElementById("swap");
const statusPill = document.getElementById("statusPill");
const detectedLine = document.getElementById("detectedLine");
const toastEl = document.getElementById("toast");
const copyBtn = document.getElementById("copyBtn");
const srcCount = document.getElementById("srcCount");

function setHint(text) {
  hintEl.textContent = text || "";
}

function setStatus(text, ok = true) {
  statusPill.textContent = text;
  statusPill.style.color = ok ? "var(--muted)" : "var(--danger)";
}

function showToast(text) {
  toastEl.textContent = text;
  toastEl.classList.add("show");
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => toastEl.classList.remove("show"), 1100);
}

// Языки (можешь расширять — добавил больше популярных)
const LANGS = [
  { code: "auto", name: "Определить язык" },

  { code: "ru", name: "Русский" },
  { code: "en", name: "English" },
  { code: "de", name: "Deutsch" },
  { code: "fr", name: "Français" },
  { code: "es", name: "Español" },
  { code: "it", name: "Italiano" },
  { code: "pt", name: "Português" },
  { code: "tr", name: "Türkçe" },
  { code: "pl", name: "Polski" },
  { code: "nl", name: "Nederlands" },
  { code: "cs", name: "Čeština" },
  { code: "sv", name: "Svenska" },
  { code: "no", name: "Norsk" },
  { code: "da", name: "Dansk" },
  { code: "fi", name: "Suomi" },

  { code: "uk", name: "Українська" },
  { code: "be", name: "Беларуская" },

  { code: "kk", name: "Қазақша" },
  { code: "uz", name: "O‘zbek" },

  { code: "zh", name: "中文" },
  { code: "ja", name: "日本語" },
  { code: "ko", name: "한국어" },

  { code: "ar", name: "العربية" },
  { code: "he", name: "עברית" },
  { code: "hi", name: "हिन्दी" },
];

const LANG_NAME_BY_CODE = Object.fromEntries(
  LANGS.filter(x => x.code !== "auto").map(x => [x.code, x.name])
);

// Заполнение селектов
function fillSelect(sel, items) {
  sel.innerHTML = "";
  for (const it of items) {
    const opt = document.createElement("option");
    opt.value = it.code;
    opt.textContent = it.name;
    sel.appendChild(opt);
  }
}
fillSelect(fromEl, LANGS);
fillSelect(toEl, LANGS.filter(x => x.code !== "auto"));

// дефолты
fromEl.value = "auto";
toEl.value = "en";

function swapLanguages() {
  // если from=auto — swapping смысла мало, но сделаем “как есть”:
  const a = fromEl.value;
  fromEl.value = toEl.value;
  toEl.value = a === "auto" ? "en" : a; // чтобы справа не оказалось auto

  // местами текст
  const t = srcEl.value;
  srcEl.value = dstEl.value;
  dstEl.value = t;

  detectedLine.textContent = "";
  setHint("");
  scheduleTranslate(0);
}

// копирование
async function copyTranslation() {
  const text = (dstEl.value || "").trim();
  if (!text) return;

  try {
    await navigator.clipboard.writeText(text);
    showToast("Скопировано ✅");
  } catch {
    // fallback для старых браузеров
    dstEl.focus();
    dstEl.select();
    document.execCommand("copy");
    showToast("Скопировано ✅");
  }
}

// Debounce перевод
let _timer = null;
let _lastReqId = 0;

function scheduleTranslate(delay = 350) {
  clearTimeout(_timer);
  _timer = setTimeout(() => translateOnce(), delay);
}

function updateCounter() {
  const n = (srcEl.value || "").length;
  srcCount.textContent = String(n);
}

function prettyDetected(code) {
  if (!code) return "";
  const c = String(code).toLowerCase();
  return LANG_NAME_BY_CODE[c] || c.toUpperCase();
}

async function translateOnce() {
  const q = (srcEl.value || "").trim();
  updateCounter();

  if (!q) {
    dstEl.value = "";
    detectedLine.textContent = "";
    setHint("");
    setStatus("Готов", true);
    return;
  }

  const reqId = ++_lastReqId;

  setStatus("Перевожу…", true);
  setHint("");

  try {
    const r = await fetch("/api/translate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        q,
        source: fromEl.value, // "auto" или "ru" и т.д.
        target: toEl.value,
      }),
    });

    const text = await r.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch {
      throw new Error(text.slice(0, 200) || "Ответ сервера не JSON");
    }

    // если есть более новый запрос — этот игнорим
    if (reqId !== _lastReqId) return;

    if (!r.ok) {
      // показываем код ошибки Яндекса, который отдаёт твой бэкенд
      const msg = data?.error || `HTTP ${r.status}`;
      const details = data?.details ? ` — ${data.details}` : "";
      throw new Error(msg + details);
    }

    dstEl.value = data.translatedText || "";

    // detectedLanguageCode приходит, когда source=auto (и иногда даже когда не auto)
    if (fromEl.value === "auto") {
      const det = data.detectedLanguageCode || data.detected || data.sourceLanguageCode;
      if (det) {
        detectedLine.textContent = `Определить язык (${prettyDetected(det)})`;
      } else {
        detectedLine.textContent = "Определить язык";
      }
    } else {
      detectedLine.textContent = "";
    }

    setStatus("Готов", true);
  } catch (e) {
    if (reqId !== _lastReqId) return;
    setStatus("Ошибка", false);
    setHint("Ошибка: " + (e?.message || e));
  }
}

// события
swapBtn.addEventListener("click", swapLanguages);

srcEl.addEventListener("input", () => {
  updateCounter();
  scheduleTranslate(350);
});
fromEl.addEventListener("change", () => {
  detectedLine.textContent = "";
  scheduleTranslate(0);
});
toEl.addEventListener("change", () => scheduleTranslate(0));

// клик по переводу = копировать
dstEl.addEventListener("click", copyTranslation);
copyBtn.addEventListener("click", copyTranslation);

// старт
updateCounter();
