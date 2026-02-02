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

document.getElementById("swap").addEventListener("click", () => {
  const a = fromEl.value;
  fromEl.value = toEl.value;
  toEl.value = a;
  const t = srcEl.value;
  srcEl.value = dstEl.value;
  dstEl.value = t;
});

document.getElementById("go").addEventListener("click", async () => {
  const q = srcEl.value.trim();
  if (!q) return;

  hintEl.textContent = "Перевожу...";
  dstEl.value = "";

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

    const data = await r.json();
    if (!r.ok) throw new Error(data?.error || "Ошибка перевода");

    dstEl.value = data.translatedText || "";
    hintEl.textContent = "";
  } catch (e) {
    hintEl.textContent = "Ошибка: " + e.message;
  }
});