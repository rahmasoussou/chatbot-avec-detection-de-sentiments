const messagesEl = document.getElementById("messages");
const inputEl    = document.getElementById("userInput");
const sendBtn    = document.getElementById("sendBtn");

// ── Envoyer un message ────────────────────────────────────────────────────────
async function sendMessage() {
  const text = inputEl.value.trim();
  if (!text) return;

  appendMessage("user", text);
  inputEl.value = "";
  autoResize(inputEl);
  sendBtn.disabled = true;

  const typingId = showTyping();

  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text })
    });

    const data = await res.json();
    removeTyping(typingId);

    if (data.reply) {
      appendMessage("bot", data.reply);
    } else {
      appendMessage("bot", "❌ Erreur : " + (data.error || "réponse invalide"));
    }
  } catch (err) {
    removeTyping(typingId);
    appendMessage("bot", "❌ Impossible de contacter le serveur. Vérifiez que Flask tourne.");
  }

  sendBtn.disabled = false;
  inputEl.focus();
}

// ── Ajouter un message dans le DOM ────────────────────────────────────────────
function appendMessage(role, text) {
  const div = document.createElement("div");
  div.className = `message ${role}`;

  const avatar = role === "bot" ? "🤖" : "👤";
  div.innerHTML = `
    <div class="avatar">${avatar}</div>
    <div class="bubble">${escapeHtml(text).replace(/\n/g, "<br>")}</div>
  `;

  messagesEl.appendChild(div);
  scrollBottom();
}

// ── Indicateur de frappe ──────────────────────────────────────────────────────
function showTyping() {
  const id = "typing-" + Date.now();
  const div = document.createElement("div");
  div.className = "message bot typing";
  div.id = id;
  div.innerHTML = `<div class="avatar">🤖</div><div class="bubble"><span></span><span></span><span></span></div>`;
  messagesEl.appendChild(div);
  scrollBottom();
  return id;
}

function removeTyping(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

// ── Utilitaires ───────────────────────────────────────────────────────────────
function scrollBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function escapeHtml(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function autoResize(el) {
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 120) + "px";
}

function handleKey(e) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
}

function sendSuggestion(btn) {
  inputEl.value = btn.textContent;
  sendMessage();
}

async function resetChat() {
  await fetch("/reset", { method: "POST" });
  messagesEl.innerHTML = `
    <div class="message bot" style="animation:none">
      <div class="avatar">🤖</div>
      <div class="bubble">Nouvelle conversation démarrée ! Comment puis-je vous aider ?</div>
    </div>`;
}
