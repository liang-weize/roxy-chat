/* 洛琪希 AI 对话网站 - 前端逻辑 */
const $ = (s) => document.querySelector(s);

const messagesEl = $("#messages");
const inputEl = $("#input");
const sendBtn = $("#send");
const voiceToggleEl = $("#voiceToggle");
const statusEl = $("#status");
const backToBottomEl = $("#backToBottom");
const clearBtnEl = $("#clearBtn");
const portraitEl = $("#portrait");
const portraitGazeEl = $("#portraitGaze");
const portraitWrapEl = $("#portraitWrap");
const moodBubbleEl = $("#moodBubble");
const sparkleLayerEl = $("#sparkleLayer");
const moodEmojiEl = $("#moodEmoji");
const moodTextEl = $("#moodText");

const EMOTION_EMOJI = {
  happy: "😊", shy: "😳", surprised: "😲", sad: "😢", gentle: "🥰", calm: "😌",
};
let currentGreeting = "";

let autoScroll = true;      // 是否贴近底部（用于决定新消息是否自动滚动）

// 每个浏览器独立一份会话 ID（存 localStorage），朋友之间互不串话
function getSessionId() {
  let id = localStorage.getItem("roxySessionId");
  if (!id) {
    id = (window.crypto && crypto.randomUUID)
      ? crypto.randomUUID()
      : "s-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 10);
    localStorage.setItem("roxySessionId", id);
  }
  return id;
}
const SESSION_ID = getSessionId();

// 用户开关：是否播放语音。开过一次就记住（按浏览器保存），刷新后保持
let voiceOn = localStorage.getItem("roxyVoice") === "1";
let busy = false;            // 是否正在等待回复
let composing = false;
let requestController = null;
let typewriterTimer = null;
const audioCache = new Map(); // text -> ObjectURL（供重播）
const WELCOME_MESSAGE = "初次见面，我是洛琪希。（微微一笑）\n有什么想聊的，尽管说吧——我很擅长倾听哦。";
let activeAudio = null;

function isWelcomeOnly(messages) {
  return !messages || messages.length === 0;
}

function renderHistory(messages) {
  messagesEl.textContent = "";
  if (isWelcomeOnly(messages)) {
    addWelcome();
    return;
  }
  for (const message of messages) {
    if (message.role === "user" || message.role === "assistant") {
      addBubble(message.role === "assistant" ? "roxy" : "user", message.content || "", message.time);
    }
  }
}

async function loadHistory() {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);
    const resp = await fetch(`/api/history?session_id=${encodeURIComponent(SESSION_ID)}`, { signal: controller.signal });
    clearTimeout(timeout);
    if (!resp.ok) throw new Error("history request failed");
    const data = await resp.json();
    renderHistory(data.messages);
  } catch (_) {
    renderHistory([]);
  }
}

function addWelcome() {
  const bubble = addBubble("roxy", "");
  typewriter(bubble, currentGreeting || WELCOME_MESSAGE);
}

/* ---------------- 工具 ---------------- */
function toast(msg, ms = 2600) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.remove("show"), ms);
}

function fmtTime(epochSec) {
  try {
    return new Date(epochSec * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch (_) {
    return "";
  }
}

function addBubble(cls, text, time) {
  const div = document.createElement("div");
  div.className = "msg " + cls;
  const textEl = document.createElement("span");
  textEl.className = "msg-text";
  textEl.textContent = text || "";
  div.appendChild(textEl);
  if (time) {
    const timeEl = document.createElement("span");
    timeEl.className = "msg-time";
    timeEl.textContent = fmtTime(time);
    div.appendChild(timeEl);
  }
  messagesEl.appendChild(div);
  scrollBottom();
  div._textEl = textEl;  // 供打字机/流式输出定位文本节点
  return div;
}

function scrollBottom() {
  if (autoScroll) messagesEl.scrollTop = messagesEl.scrollHeight;
}

// 贴近底部才自动滚动；向上翻历史时不再被新消息拽下去，并显示「回到底部」按钮
messagesEl.addEventListener("scroll", () => {
  const nearBottom = messagesEl.scrollHeight - messagesEl.scrollTop - messagesEl.clientHeight < 80;
  autoScroll = nearBottom;
  backToBottomEl.hidden = nearBottom;
});

/* 去掉（动作/神态）描写，并把标点统一为适合日语朗读的短停顿 */
function speakableText(text) {
  return text
    .replace(/（[^）]*）/g, "")
    .replace(/\([^)]*\)/g, "")
    .replace(/[\r\n]+/g, "")
    .replace(/…+|\.{2,}/g, "")
    .replace(/[。！？!?]+/g, (m) => m[0])
    .trim();
}

/* ---------------- 打字机效果 ---------------- */
function typewriter(el, text, done) {
  if (typewriterTimer) clearInterval(typewriterTimer);
  const target = el._textEl || el;
  let i = 0;
  const caret = document.createElement("span");
  caret.className = "caret";
  target.textContent = "";
  target.appendChild(caret);
  const timer = setInterval(() => {
    i += 1;
    target.textContent = text.slice(0, i);
    target.appendChild(caret);
    scrollBottom();
    if (i >= text.length) {
      clearInterval(timer);
      if (typewriterTimer === timer) typewriterTimer = null;
      caret.remove();
      done && done();
    }
  }, 28);
  typewriterTimer = timer;
}

/* ---------------- 语音 ---------------- */
async function speak(text) {
  if (!voiceOn) return false;
  const content = speakableText(text);
  if (!content) return false;

  let url = audioCache.get(content);
  if (!url) {
    const resp = await fetch("/api/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: content }),
    });
    if (!resp.ok) {
      let msg = "语音合成失败";
      try { msg = (await resp.json()).error || msg; } catch (_) {}
      toast(msg);
      return false;
    }
    const blob = await resp.blob();
    url = URL.createObjectURL(blob);
    audioCache.set(content, url);
  }

  return new Promise((resolve) => {
    const audio = new Audio(url);
    if (activeAudio) activeAudio.pause();
    activeAudio = audio;
    audio.onended = () => {
      if (activeAudio === audio) activeAudio = null;
      resolve(true);
    };
    audio.onerror = () => {
      if (activeAudio === audio) activeAudio = null;
      resolve(false);
    };
    audio.play().catch(() => resolve(false));
  });
}

function addActionButtons(text, voiceText) {
  const wrap = document.createElement("div");
  wrap.className = "msg-tools";
  const btn = document.createElement("button");
  btn.className = "replay-btn";
  btn.textContent = "📋 复制";
  btn.onclick = async () => {
    try { await navigator.clipboard.writeText(text); toast("已复制回复"); }
    catch (_) { toast("复制失败，请手动选择文字"); }
  };
  wrap.appendChild(btn);
  if (voiceText && voiceOn) {
    const replay = document.createElement("button");
    replay.className = "replay-btn";
    replay.textContent = "🔊 重播日语语音";
    replay.onclick = () => speak(voiceText);
    wrap.appendChild(replay);
  }
  messagesEl.appendChild(wrap);
  scrollBottom();
}

/* ---------------- 发送消息 ---------------- */
async function streamChat(text, onDelta, signal) {
  const resp = await fetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: text, session_id: SESSION_ID }),
    signal,
  });
  if (!resp.ok) {
    let msg = "请求失败";
    try { msg = (await resp.json()).error || msg; } catch (_) {}
    throw new Error(msg);
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buf = "";
  let reply = "";
  let voiceText = "";
  let emotion = "calm";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buf.indexOf("\n\n")) !== -1) {
      const line = buf.slice(0, idx).trim();
      buf = buf.slice(idx + 2);
      if (!line.startsWith("data:")) continue;
      const payload = line.slice(5).trim();
      if (payload === "[DONE]") return { reply, voiceText, emotion };
      let obj;
      try { obj = JSON.parse(payload); } catch (_) { continue; }
      if (obj.error) throw new Error(obj.error);
      if (obj.delta) { reply += obj.delta; onDelta(obj.delta); }
      if (obj.done) { reply = obj.reply || reply; voiceText = obj.voice_text || ""; emotion = obj.emotion || "calm"; }
    }
  }
  return { reply, voiceText, emotion };
}

async function send() {
  const text = inputEl.value.trim();
  if (!text || busy) return;
  busy = true;
  inputEl.value = "";
  inputEl.disabled = true;
  sendBtn.disabled = true;
  sendBtn.textContent = "停止";
  requestController = new AbortController();

  addBubble("user", text, Date.now() / 1000);
  const bubble = addBubble("roxy", "");
  bubble._textEl.textContent = "…";
  let received = false;

  try {
    const result = await streamChat(text, (delta) => {
      if (!received) { received = true; bubble._textEl.textContent = ""; }
      bubble._textEl.textContent += delta;
      scrollBottom();
    }, requestController.signal);
    const reply = result.reply;
    const voiceText = result.voiceText || reply;
    showEmotion(result.emotion);
    const played = await speak(voiceText);
    addActionButtons(reply, played ? voiceText : "");
  } catch (e) {
    if (e.name === "AbortError") {
      bubble.remove();
      return;
    }
    if (!received) {
      // 流式没拿到内容时，回退到非流式接口兜底
      try {
        const resp = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: text, session_id: SESSION_ID }),
          signal: requestController.signal,
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error || "请求失败");
        received = true;
        bubble._textEl.textContent = "";
        showEmotion(data.emotion);
        typewriter(bubble, data.reply, async () => {
          const played = await speak(data.voice_text || data.reply);
          addActionButtons(data.reply, played ? (data.voice_text || data.reply) : "");
        });
        return;
      } catch (e2) {
        if (e2.name === "AbortError") { bubble.remove(); return; }
        bubble.classList.add("error");
        bubble._textEl.textContent = e2.message || "请求失败";
        return;
      }
    }
    bubble.classList.add("error");
    bubble._textEl.textContent = received
      ? bubble._textEl.textContent + "\n（连接中断）"
      : (e.message || "网络错误");
  } finally {
    busy = false;
    inputEl.disabled = false;
    sendBtn.disabled = false;
    sendBtn.textContent = "发送";
    requestController = null;
    inputEl.focus();
  }
}

function stopGeneration() {
  if (!busy) return;
  if (requestController) requestController.abort();
  if (typewriterTimer) { clearInterval(typewriterTimer); typewriterTimer = null; }
  if (activeAudio) { activeAudio.pause(); activeAudio = null; }
  busy = false;
  inputEl.disabled = false;
  sendBtn.disabled = false;
  sendBtn.textContent = "发送";
  inputEl.focus();
  toast("已停止生成");
}

sendBtn.onclick = () => busy ? stopGeneration() : send();
inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !composing) { e.preventDefault(); send(); }
});
inputEl.addEventListener("compositionstart", () => { composing = true; });
inputEl.addEventListener("compositionend", () => { composing = false; });
inputEl.addEventListener("input", () => {
  inputEl.style.height = "auto";
  inputEl.style.height = Math.min(inputEl.scrollHeight, 132) + "px";
});

/* ---------------- 表情面板 ---------------- */
const emojiToggleEl = $("#emojiToggle");
const emojiPanelEl = $("#emojiPanel");
const emojiGridEl = $("#emojiGrid");
const emojiCategories = {
  faces: "😀 😃 😄 😁 😆 😅 😂 🤣 😊 😇 🙂 🙃 😉 😌 😍 🥰 😘 😗 😙 😚 😋 😛 😝 😜 🤪 🤨 🧐 🤓 😎 🤩 🥳 😏 😒 😞 😔 😟 😕 🙁 ☹️ 😣 😖 😫 😩 🥺 😢 😭 😤 😠 😡 🤬 🤯 😳 🥵 🥶 😱 😨 😰 😥 😓 🤗 🤔 🤭 🤫 🤥 😶 😐 😑 😬 🙄 😯 😦 😧 😮 😲 🥱 😴 🤤 😪 😵 🤐 🤑 🤠 😈 👿 👹 👺 🤡 💩 👻 💀 ☠️ 👽 👾 🤖 🎃 😺 😸 😹 😻 😼 😽 🙀 😿 😾",
  gestures: "👍 👎 👌 ✌️ 🤞 🤟 🤘 🤙 👈 👉 👆 👇 ☝️ ✋ 🤚 🖐️ 🖖 👋 🤏 💪 🖕 🙏 👏 🙌 👐 🤝 💅 👂 👃 👀 👁️ 🧠 👤 👥 🫶 🫰 🤲 🤳 💋 💯",
  hearts: "❤️ 🧡 💛 💚 💙 💜 🖤 🤍 🤎 💔 ❣️ 💕 💞 💓 💗 💖 💘 💝 💟 💌 💋 😘 🥰 😍 🥺 😊 🤗 🎉 🎊 ✨ ⭐ 🌟 💫 🔥 💥 💦 💨 💢 💬 💤",
  magic: "✨ ⭐ 🌟 💫 ⚡ 🔥 💧 🌊 ❄️ ☀️ 🌙 🌈 🪄 🧙 🧙‍♀️ 🧙‍♂️ 🧝 🧝‍♀️ 🧚 🧚‍♀️ 🧞 🧜 🐉 🔮 🧿 🪬 🗝️ 📜 🏰 🏹 ⚔️ 🛡️ 🗡️ 🧪 ⚗️ 🕯️ 🌀 ☄️ 🌌 🪐",
  nature: "🌊 💧 🌧️ ⛈️ 🌩️ ❄️ ☃️ ☀️ 🌤️ ⛅ 🌈 🌙 🌕 🌟 🌸 🌹 🌺 🌻 🌼 🌷 🌱 🌿 🍀 ☘️ 🍁 🍂 🌴 🌵 🍄 🌳 🐚 🦋 🐝 🐞 🐠 🐟 🐬 🐳 🐋 🐈 🐕 🐇 🦊 🐻 🐼 🐨 🐯 🦁 🐮 🐷 🐸 🐵 🐔 🐧 🦄",
  objects: "🎁 🎀 🎈 🎂 🍰 🍪 🍩 🍫 🍬 🍭 🍓 🍒 🍎 🍑 🍊 🍋 🍉 🍇 🍌 🍍 🥝 🍀 ☕ 🍵 🧋 🍜 🍙 🍣 🍱 🍛 🍕 🍔 🎮 🎧 🎵 🎶 🎤 📚 📖 ✏️ 📝 💡 🔔 🔒 🔑 💎 💍 👑 🧸 🛍️ 💰 💳 📱 💻 📷 🎥 🚗 ✈️ 🚀 🏠 🏫 🏥"
};
function renderEmojiCategory(category) {
  emojiGridEl.textContent = "";
  [...emojiCategories[category].matchAll(/\S+/g)].forEach((match) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = match[0];
    button.title = "插入 " + match[0];
    button.onclick = () => {
      inputEl.value += button.textContent;
      inputEl.focus();
    };
    emojiGridEl.appendChild(button);
  });
}
renderEmojiCategory("faces");
emojiPanelEl.querySelectorAll(".emoji-tab").forEach((tab) => {
  tab.onclick = () => {
    emojiPanelEl.querySelectorAll(".emoji-tab").forEach((x) => x.classList.remove("active"));
    tab.classList.add("active");
    renderEmojiCategory(tab.dataset.emojiCategory);
  };
});
emojiToggleEl.onclick = () => {
  const willOpen = emojiPanelEl.hidden;
  emojiPanelEl.hidden = !willOpen;
  emojiToggleEl.classList.toggle("active", willOpen);
};
document.addEventListener("click", (event) => {
  if (!emojiPanelEl.hidden && !event.target.closest(".emoji-wrap")) {
    emojiPanelEl.hidden = true;
    emojiToggleEl.classList.remove("active");
  }
});


/* ---------------- 语音开关 ---------------- */
function updateVoiceBtn() {
  voiceToggleEl.textContent = voiceOn ? "🔊 语音开" : "🔇 语音关";
  voiceToggleEl.classList.toggle("muted", !voiceOn);
}

voiceToggleEl.onclick = () => {
  voiceOn = !voiceOn;
  localStorage.setItem("roxyVoice", voiceOn ? "1" : "0");
  updateVoiceBtn();
  if (!voiceOn) {
    if (activeAudio) {
      activeAudio.pause();
      activeAudio = null;
    }
    window.speechSynthesis && speechSynthesis.cancel();
  }
};

updateVoiceBtn();

/* ---------------- 回到底部 & 清空对话 ---------------- */
backToBottomEl.onclick = () => {
  autoScroll = true;
  scrollBottom();
  backToBottomEl.hidden = true;
};

clearBtnEl.onclick = async () => {
  if (!confirm("确定清空当前对话记录吗？")) return;
  try {
    await fetch(`/api/history?session_id=${encodeURIComponent(SESSION_ID)}`, { method: "DELETE" });
  } catch (_) {}
  messagesEl.textContent = "";
  addWelcome();
};

/* ---------------- 状态检测 ---------------- */
async function checkHealth() {
  try {
    const resp = await fetch("/api/health");
    const data = await resp.json();
    const cls = (c) => {
      statusEl.className = "status " + c;
    };
    const textEl = statusEl.querySelector(".status-text");
    if (!data.llm_configured) {
      cls("bad");
      textEl.textContent = "请配置接口地址、模型和 ROXY_LLM_API_KEY";
    } else if (data.voice_enabled && data.voice_online) {
      cls("ok");
      textEl.textContent = "洛琪希在线 · 语音就绪";
    } else if (data.voice_enabled && !data.voice_online) {
      cls("warn");
      textEl.textContent = "在线 · 语音服务未启动（仅文字）";
    } else {
      cls("ok");
      textEl.textContent = "洛琪希在线 · 语音未启用";
    }
  } catch (_) {
    statusEl.className = "status bad";
  }
}

/* ---------------- 立绘动画 & 情绪 & 心情 ---------------- */
// 点击立绘：撒花 + 弹跳反馈（立绘固定为 portrait_roxy.jpg，不再切换）
portraitEl.addEventListener("click", () => {
  burstSparkles();
  portraitGazeEl.animate(
    [{ transform: "scale(1)" }, { transform: "scale(.92)" }, { transform: "scale(1.06)" }, { transform: "scale(1)" }],
    { duration: 420, easing: "ease-out" }
  );
});

// 立绘轻微跟随鼠标（注视效果）
document.addEventListener("mousemove", (e) => {
  const dx = (e.clientX - window.innerWidth / 2) / (window.innerWidth / 2);
  const dy = (e.clientY - window.innerHeight / 2) / (window.innerHeight / 2);
  portraitGazeEl.style.transform =
    `translate(${(dx * 6).toFixed(1)}px, ${(dy * 5).toFixed(1)}px) rotate(${(dx * 1.5).toFixed(1)}deg)`;
});

function burstSparkles() {
  const emojis = ["💙", "✨", "❤️", "💧", "⭐"];
  for (let i = 0; i < 8; i++) {
    const s = document.createElement("span");
    s.className = "sparkle";
    s.textContent = emojis[Math.floor(Math.random() * emojis.length)];
    s.style.left = (20 + Math.random() * 60) + "%";
    s.style.top = (30 + Math.random() * 40) + "%";
    s.style.fontSize = (14 + Math.random() * 12) + "px";
    sparkleLayerEl.appendChild(s);
    setTimeout(() => s.remove(), 1000);
  }
}

function showEmotion(emotion) {
  const emoji = EMOTION_EMOJI[emotion] || EMOTION_EMOJI.calm;
  moodBubbleEl.textContent = emoji;
  moodBubbleEl.hidden = false;
  moodBubbleEl.style.animation = "none";
  void moodBubbleEl.offsetWidth; // 强制重排以重新触发动画
  moodBubbleEl.style.animation = "";
  clearTimeout(showEmotion._t);
  showEmotion._t = setTimeout(() => { moodBubbleEl.hidden = true; }, 1600);
}

async function initCompanion() {
  try {
    const resp = await fetch(`/api/state?session_id=${encodeURIComponent(SESSION_ID)}`);
    const data = await resp.json();
    moodEmojiEl.textContent = data.mood_emoji || "😌";
    moodTextEl.textContent = data.mood_label || "心情平静";
    if (data.greeting) currentGreeting = data.greeting;
  } catch (_) {}
}

/* ---------------- 动态背景: 多背景轮换（视频 + 图片） ---------------- */
const bgVideoEl = $("#bgVideo");
const bgImageEl = $("#bgImage");
const bgOverlayEl = $(".bg-overlay");
const bgToggleEl = $("#bgToggle");
const BG_OFF = { name: "背景关", src: null, type: "off" };
let bgList = [
  { name: "洛琪希·水之问候", src: "/assets/images/bg/bg_3304137609.jpg", type: "image" },
  { name: "洛琪希·魔法阵", src: "/assets/images/bg/bg_3329004013.jpg", type: "image" },
  { name: "洛琪希·眨眼", src: "/assets/images/bg/bg_3371359611.jpg", type: "image" },
  { name: "洛琪希·夜色", src: "/assets/images/bg/bg_2941994990.jpg", type: "image" },
  { name: "洛琪希·戏水", src: "/assets/images/bg/bg_3721991999.jpg", type: "image" },
  BG_OFF,
];
let bgIdx = 0;
let bgReady = true;

function applyBackground(item) {
  if (item.src) {
    bgOverlayEl.classList.remove("hidden");
    bgToggleEl.textContent = "🎬 " + item.name;
    bgToggleEl.classList.remove("off");
    if (item.type === "image") {
      bgVideoEl.pause();
      bgVideoEl.style.display = "none";
      if (bgImageEl.getAttribute("src") !== item.src) {
        bgImageEl.setAttribute("src", item.src);
      }
      bgImageEl.hidden = false;
      bgImageEl.style.display = "block";
    } else {
      bgImageEl.hidden = true;
      bgImageEl.style.display = "none";
      if (bgVideoEl.getAttribute("src") !== item.src) {
        bgVideoEl.setAttribute("src", item.src);
        bgVideoEl.load();
      }
      bgVideoEl.style.display = "block";
      bgVideoEl.play().catch(() => {});
    }
  } else {
    bgVideoEl.pause();
    bgVideoEl.style.display = "none";
    bgImageEl.hidden = true;
    bgImageEl.style.display = "none";
    bgOverlayEl.classList.add("hidden");
    bgToggleEl.textContent = "🎬 背景关";
    bgToggleEl.classList.add("off");
  }
  localStorage.setItem("roxyBgIdx", String(bgIdx));
}

bgToggleEl.onclick = () => {
  bgIdx = (bgIdx + 1) % bgList.length;
  applyBackground(bgList[bgIdx]);
};

async function initBackgrounds() {
  try {
    const resp = await fetch("/api/backgrounds");
    const data = await resp.json();
    const items = (data.backgrounds || []).map((b) => ({ name: b.name, src: b.src, type: b.type || "video" }));
    if (items.length) bgList = [...items, BG_OFF];
  } catch (_) {}
  const saved = parseInt(localStorage.getItem("roxyBgIdx"), 10);
  bgIdx = saved >= 0 && saved < bgList.length ? saved : 0;
  applyBackground(bgList[bgIdx]);
}

/* ---------------- 登录鉴权 ---------------- */
const loginScreenEl = $("#loginScreen");
const loginFormEl = $("#loginForm");
const loginPasswordEl = $("#loginPassword");
const loginErrorEl = $("#loginError");
const logoutBtnEl = $("#logoutBtn");

function showLogin() {
  loginScreenEl.hidden = false;
  loginPasswordEl.focus();
}

function hideLogin() {
  loginScreenEl.hidden = true;
}

async function ensureAuth() {
  try {
    const resp = await fetch("/api/auth_status");
    if (resp.ok) {
      const data = await resp.json();
      if (!data.enabled || data.authed) return true;
    }
  } catch (_) {}
  showLogin();
  return false;
}

loginFormEl.onsubmit = async (e) => {
  e.preventDefault();
  const pw = loginPasswordEl.value.trim();
  if (!pw) return;
  loginErrorEl.textContent = "";
  const btn = loginFormEl.querySelector("button[type=submit]");
  btn.disabled = true;
  try {
    const resp = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password: pw }),
    });
    if (resp.ok) {
      hideLogin();
      startApp();
    } else {
      let msg = "口令错误，请重试";
      try { msg = (await resp.json()).error || msg; } catch (_) {}
      loginErrorEl.textContent = msg;
      loginPasswordEl.select();
    }
  } catch (_) {
    loginErrorEl.textContent = "网络错误，请重试";
  } finally {
    btn.disabled = false;
  }
};

logoutBtnEl.onclick = async () => {
  try { await fetch("/api/logout", { method: "POST" }); } catch (_) {}
  location.reload();
};

/* ---------------- 初始化 ---------------- */
async function startApp() {
  checkHealth();
  setInterval(checkHealth, 30000);
  initBackgrounds();
  await initCompanion();
  loadHistory();
}

(async function init() {
  if (await ensureAuth()) {
    startApp();
  }
})();
