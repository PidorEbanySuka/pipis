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
const goBtn = document.getElementById("go");

function setHint(text) {
  hintEl.textContent = text || "";
}

function swapLanguages() {
  const a = fromEl.value;
  fromEl.value = toEl.value;
  toEl.value = a;

  // Меняем местами текст, чтобы было "как в переводчике"
  const t = srcEl.value;
  srcEl.value = dstEl.value;
  dstEl.value = t;
}

async function translateOnce() {
  const q = (srcEl.value || "").trim();
  if (!q) {
    dstEl.value = "";
    setHint("");
    return;
  }

  setHint("Перевожу...");
  goBtn.disabled = true;

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

    // ВАЖНО: читаем как текст, потом пытаемся JSON.parse
    const text = await r.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch {
      // Если сервер вернул HTML/текст ошибки, покажем кусок
      throw new Error(text.slice(0, 160) || "Ответ сервера не JSON");
    }

    if (!r.ok) {
      throw new Error(data?.error || "Ошибка перевода");
    }

    dstEl.value = data.translatedText || "";
    setHint("");
  } catch (e) {
    setHint("Ошибка: " + (e?.message || e));
  } finally {
    goBtn.disabled = false;
  }
}

// Кнопки
swapBtn.addEventListener("click", () => swapLanguages());
goBtn.addEventListener("click", () => translateOnce());

// Дополнительно: если поменяли язык — очистим подсказку
fromEl.addEventListener("change", () => setHint(""));
toEl.addEventListener("change", () => setHint(""));