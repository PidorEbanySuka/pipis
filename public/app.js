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
const counterEl = document.getElementById("counter");
const swapBtn = document.getElementById("swap");
const copyBtn = document.getElementById("copy");
const toastEl = document.getElementById("toast");
const detectedBadgeEl = document.getElementById("detectedBadge");

const MAX_LEN = 5000;

// Больше языков (можешь дополнять)
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
  { code: "uk", name: "Українська" },
  { code: "cs", name: "Čeština" },
  { code: "sk", name: "Slovenčina" },
  { code: "sv", name: "Svenska" },
  { code: "no", name: "Norsk" },
  { code: "da", name: "Dansk" },
  { code: "fi", name: "Suomi" },
  { code: "nl", name: "Nederlands" },

  { code: "zh", name: "中文" },
  { code: "ja", name: "日本語" },
  { code: "ko", name: "한국어" },

  { code: "ar", name: "العربية" },
  { code: "he", name: "עברית" },
  { code: "hi", name: "हिन्दी" },
];

function setHint(text, isError = false) {
  hintEl.textContent = text || "";
  hintEl.classList.toggle("err", !!isError);
}

function langName(code) {
  const c = (code || "").toLowerCase();
  return (LANGS.find(x => x.code === c)?.name) || (code || "");
}

function showToast(text = "Скопировано") {
  toastEl.textContent = text;
  toastEl.hidden = false;
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => {
    toastEl.hidden = true;
  }, 900);
}

function updateCounter() {
  const len = (srcEl.value || "").length;
  counterEl.textContent = `${len}/${MAX_LEN}`;
}

function updateSwapState() {
  const isAuto = (fromEl.value === "auto");
  swapBtn.disabled = isAuto;
  swapBtn.title = isAuto ? "Нельзя менять местами при автоопределении" : "Поменять языки";
}

function setDetectedBadge(detectedCode) {
  const isAuto = (fromEl.value === "auto");

  if (isAuto && detectedCode) {
    detectedBadgeEl.hidden = false;
    detectedBadgeEl.textContent = `Определён: ${langName(detectedCode)}`;
  } else {
    detectedBadgeEl.hidden = true;
    detectedBadgeEl.textContent = "";
  }
}

function fillLangSelects() {
  fromEl.innerHTML = "";
  toEl.innerHTML = "";

  for (const l of LANGS) {
    const o1 = document.createElement("option");
    o1.value = l.code;
    o1.textContent = l.name;
    fromEl.appendChild(o1);

    // в целевой список auto не добавляем
    if (l.code !== "auto") {
      const o2 = document.createElement("option");
      o2.value = l.code;
      o2.textContent = l.name;
      toEl.appendChild(o2);
    }
  }

  fromEl.value = "auto";
  toEl.value = "en";
}

function swapLanguages() {
  if (fromEl.value === "auto") return;

  const a = fromEl.value;
  fromEl.value = toEl.value;
  toEl.value = a;

  // swap текста как в переводчиках
  const t = srcEl.value;
  srcEl.value = dstEl.value;
  dstEl.value = t;

  setDetectedBadge(null);
  updateSwapState();
  updateCounter();
  translateDebounced();
}

async function copyTranslation() {
  const text = (dstEl.value || "").trim();
  if (!text) return;

  try {
    await navigator.clipboard.writeText(text);
    showToast("Скопировано");
  } catch {
    // fallback
    dstEl.focus();
    dstEl.select();
    document.execCommand("copy");
    showToast("Скопировано");
  }
}

// debounce
let tmr = null;
function translateDebounced() {
  clearTimeout(tmr);
  tmr = setTimeout(() => translateOnce(), 350);
}

async function translateOnce() {
  const q = (srcEl.value || "").trim();
  updateCounter();

  if (!q) {
    dstEl.value = "";
    setHint("");
    setDetectedBadge(null);
    copyBtn.disabled = true;
    return;
  }

  setHint("Перевожу...");
  copyBtn.disabled = true;

  try {
    const r = await fetch("/api/translate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        q,
        source: fromEl.value,
        target: toEl.value,
      }),
    });

    const text = await r.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch {
      throw new Error(text.slice(0, 180) || "Ответ сервера не JSON");
    }

    if (!r.ok) {
      // показываем максимально полезно
      const code = data?.status || data?.code || r.status;
      const msg = data?.error || "Ошибка перевода";
      const details = data?.details ? ` • ${String(data.details).slice(0, 140)}` : "";
      throw new Error(`${msg} (${code})${details}`);
    }

    dstEl.value = data.translatedText || "";
    copyBtn.disabled = !(dstEl.value || "").trim();

    // подхватим язык из любого разумного поля
    const detected =
      data.detectedLanguage ||
      data.detected ||
      data.sourceLanguage ||
      data.lang ||
      data.source;

    setDetectedBadge(detected || null);
    setHint("");
  } catch (e) {
    setHint("Ошибка: " + (e?.message || e), true);
    copyBtn.disabled = true;
  }
}

function init() {
  fillLangSelects();
  updateCounter();
  updateSwapState();
  setDetectedBadge(null);
  copyBtn.disabled = true;

  // события
  swapBtn.addEventListener("click", swapLanguages);
  copyBtn.addEventListener("click", copyTranslation);

  fromEl.addEventListener("change", () => {
    setDetectedBadge(null);
    updateSwapState();
    translateDebounced();
  });

  toEl.addEventListener("change", () => {
    translateDebounced();
  });

  srcEl.addEventListener("input", () => {
    updateCounter();
    translateDebounced();
  });

  // Клик по переводу тоже копирует (по желанию — удобно)
  dstEl.addEventListener("click", () => {
    if ((dstEl.value || "").trim()) copyTranslation();
  });
}

init();
