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
const errorEl = document.getElementById("error");
const toastEl = document.getElementById("toast");

// Список языков (можешь дополнять)
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
  { code: "uk", name: "Українська" },
  { code: "pl", name: "Polski" },
  { code: "cs", name: "Čeština" },
  { code: "sv", name: "Svenska" },
  { code: "fi", name: "Suomi" },
  { code: "nl", name: "Nederlands" },
  { code: "ja", name: "日本語" },
  { code: "zh", name: "中文" },
  { code: "ko", name: "한국어" },
];

function setHint(text) {
  hintEl.textContent = text || "";
}

function setError(text) {
  errorEl.textContent = text || "";
}

function toast(text) {
  toastEl.textContent = text;
  toastEl.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => toastEl.classList.remove("show"), 900);
}

function langName(code) {
  const c = (code || "").toLowerCase();
  const found = LANGS.find(x => x.code === c);
  return found ? found.name : (code || "");
}

function fillSelect(el, selected) {
  el.innerHTML = "";
  for (const l of LANGS) {
    const opt = document.createElement("option");
    opt.value = l.code;
    opt.textContent = l.name;
    el.appendChild(opt);
  }
  el.value = selected;
}

function setAutoLabel(detectedCode) {
  const opt = [...fromEl.options].find(o => o.value === "auto");
  if (!opt) return;

  if (detectedCode) {
    opt.textContent = `Определить язык (${langName(detectedCode)})`;
  } else {
    opt.textContent = "Определить язык";
  }
}

// debounce
function debounce(fn, ms) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}

async function copyText(text) {
  const value = (text || "").trim();
  if (!value) return;

  try {
    await navigator.clipboard.writeText(value);
    toast("Скопировано");
  } catch {
    // fallback
    const ta = document.createElement("textarea");
    ta.value = value;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    ta.remove();
    toast("Скопировано");
  }
}

function swapLanguages() {
  const a = fromEl.value;
  fromEl.value = toEl.value;
  toEl.value = a;

  // тексты местами
  const t = srcEl.value;
  srcEl.value = dstEl.value;
  dstEl.value = t;

  // сброс подписи автоязыка
  setAutoLabel(null);

  translateDebounced();
}

async function translateOnce() {
  const q = (srcEl.value || "").trim();

  counterEl.textContent = `${(srcEl.value || "").length}/5000`;
  setError("");

  if (!q) {
    dstEl.value = "";
    setHint("");
    setAutoLabel(null);
    return;
  }

  setHint("Перевожу…");

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
      throw new Error(text.slice(0, 200) || "Ответ сервера не JSON");
    }

    if (!r.ok) {
      // покажем код и сообщение как есть
      const msg = data?.error || "Ошибка перевода";
      const details = data?.details ? ` — ${data.details}` : "";
      throw new Error(`${msg}${details}`);
    }

    dstEl.value = data.translatedText || "";
    setHint("");

    // автоязык: поддерживаем разные имена полей
    const detected =
      data.detectedLanguage ||
      data.detected ||
      data.sourceLanguage ||
      data.lang ||
      null;

    setAutoLabel(detected);
  } catch (e) {
    setHint("");
    setError(e?.message || String(e));
  }
}

const translateDebounced = debounce(translateOnce, 350);

// events
swapBtn.addEventListener("click", swapLanguages);

srcEl.addEventListener("input", () => {
  counterEl.textContent = `${(srcEl.value || "").length}/5000`;
  translateDebounced();
});

fromEl.addEventListener("change", () => {
  setAutoLabel(null);
  translateDebounced();
});
toEl.addEventListener("change", () => translateDebounced());

copyBtn.addEventListener("click", () => copyText(dstEl.value));
dstEl.addEventListener("click", () => copyText(dstEl.value));

// init
fillSelect(fromEl, "auto");
fillSelect(toEl, "en");
counterEl.textContent = "0/5000";
setAutoLabel(null);
