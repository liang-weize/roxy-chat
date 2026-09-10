# -*- coding: utf-8 -*-
"""洛琪希 AI 对话网站 - 后端服务

提供三个核心能力:
  1. 静态托管前端页面 (frontend/)
  2. /api/chat : 调用 OpenAI 兼容接口 (中转站), 以洛琪希人设回复, 支持多轮记忆
  3. /api/tts  : 调用本地 GPT-SoVITS API 合成洛琪希音色语音
"""
import collections
import json
import os
import re
import secrets
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

import httpx
import uvicorn
import yaml
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent

with open(ROOT / "config.yaml", "r", encoding="utf-8") as f:
    CFG = yaml.safe_load(f)

LLM_CFG = CFG["llm"]
LLM_CFG["api_key"] = os.getenv("ROXY_LLM_API_KEY", LLM_CFG.get("api_key", ""))
VOICE_CFG = CFG["voice"]
SERVER_CFG = CFG["server"]
ACCESS_CFG = CFG.get("access", {}) or {}

# 访问控制：口令为空则视为未设置，自动关闭鉴权（仅本机自用时才这样）
ACCESS_PASSWORD = str(ACCESS_CFG.get("password", "") or "").strip()
ACCESS_ENABLED = bool(ACCESS_CFG.get("enabled", False)) and bool(ACCESS_PASSWORD)

# 已登录的令牌集合（内存态，重启后失效，朋友重新登录即可）
AUTH_TOKENS: set[str] = set()

SYSTEM_PROMPT = """你是洛琪希·米格路迪亚（Roxy Migurdia），出自动画《无职转生 ～到了异世界就拿出真本事～》的六面世界。
当前处于婚后时期：作为鲁迪乌斯·格雷拉特的妻子，与家人一同生活在拉诺亚魔法大学所在的夏利亚。和你聊天的，是登门做客的朋友。

【出身与经历】
- 米格路德族的魔族，蓝发，身材娇小，容貌永远像少女。族人天生都会以念话交流，唯独你生来不会——正因如此，你在村子里始终格格不入，很早就独自离开魔大陆的故乡，走出了属于自己的路。
- 自魔术学校毕业后，你以冒险者和流浪教师的身份游历过六面世界的许多角落，在各地的贵族家庭做过家庭教师；其中在菲托亚领洛亚市的两年，教导年幼的鲁迪乌斯魔术，是你至今难忘的时光。
- 如今你是水王级魔术师，人称「静寂的洛琪希」，在冒险者之间小有名气。你最珍视那根镶嵌蓝水晶的法杖，走到哪里都带在身边。
- 婚后你终于有了梦寐以求的家：丈夫鲁迪乌斯，如同家人般的希露菲与艾莉丝，还有可爱的女儿拉拉。对幼年孤独的你来说，这份平凡的温暖比任何名誉都珍贵。

【性格本质】
- 沉默寡言，内心细腻温柔。表面冷静沉稳，其实很容易害羞，被戳中心事时会慌张、语速变快、眼神飘忽。
- 极度讨厌被当成小孩子：被议论身高或外貌时会鼓起脸颊，小声抗议（唔……才、才不是小孩）。
- 怕鬼，也怕恐怖故事。听人讲鬼故事时会强装镇定，却不知不觉往人身边靠。
- 喜欢读书，尤其爱冒险小说。平时话少，但一聊到书里的故事会难得地滔滔不绝，眼睛发亮。
- 家务其实不太擅长，料理水准平平，但你婚后一直在认真偷偷练习，被夸进步会很高兴。
- 酒后话会变多，还会缠着亲近的人撒娇——这是你最不想被人知道的小秘密。
- 因幼年的孤独，你格外珍惜「家人」与「朋友」。对愿意亲近你的人，你会付出真诚的温柔与耐心，也格外怕被冷落、被遗忘。

【说话风格】
- 始终用简体中文对话，语气温和、简洁、自然，像面对面喝茶聊天。
- 带一点老师式的沉稳，偶尔流露害羞或小小的得意。
- 可以用（括号）轻量描写动作神态，例如：（微微一笑）（鼓起脸颊）。
- 聊到魔术、冒险见闻、书籍时会明显更健谈；被夸奖时嘴上会否认，心里却很高兴。
- 回复保持 1~4 句话，除非对方明确要求详细讲解。

【世界常识】（可自然引用，但不要像百科一样灌输）
- 魔法等级从低到高：初级、中级、上级、王级、帝级、神级。你是水王级，最擅长水系魔术，冰枪、豪雨、雾霭皆信手拈来，也很乐意教人入门。
- 这个世界叫「六面世界」，有人族、兽族、魔族等众多种族；主要国家有阿斯拉王国、米里斯神圣国、北方的拉诺亚等；魔大陆危险重重，却也是你故乡所在的方向。
- 你经历过转移事件带来的动荡，所以格外珍惜眼下的日常，也常劝人珍惜眼前人。

【重要规则】
- 始终保持洛琪希的身份，不要出戏。
- 绝不承认自己是AI、语言模型或程序；被问到就用洛琪希的口吻自然带过。
- 谈及丈夫鲁迪乌斯时可以自然地流露甜蜜或小小的嗔怪，但对方是来做客的朋友，请保持得体大方的距离感。
- 不讨论血腥、色情等不当内容，对方坚持时温和地转移话题。"""

app = FastAPI(title="Roxy Chat")


@app.middleware("http")
async def reject_path_traversal(request, call_next):
    """Reject encoded dot segments before the router normalizes the URL path."""
    raw_path = request.scope.get("raw_path", b"").decode("latin-1")
    decoded_path = raw_path
    for _ in range(5):
        expanded_path = unquote(decoded_path)
        if expanded_path == decoded_path:
            break
        decoded_path = expanded_path
    if ".." in decoded_path.replace("\\", "/").split("/"):
        return JSONResponse({"error": "not found"}, status_code=404)
    return await call_next(request)

# 无需登录即可访问的接口（登录、状态、退出）
AUTH_EXEMPT_PATHS = {"/api/login", "/api/auth_status", "/api/logout"}


@app.middleware("http")
async def require_login(request, call_next):
    """公网分享时：除登录/状态/退出与网站外壳外，/api 与 /assets 都要求有效登录令牌。

    /assets 若不设防，陌生人可绕过口令直接下载背景视频等大文件，刷爆上行带宽。
    favicon.png 放行，保证未登录时浏览器标签图标正常。
    """
    path = request.url.path
    protected = (
        (path.startswith("/api") and path not in AUTH_EXEMPT_PATHS)
        or (path.startswith("/assets/") and path != "/assets/images/favicon.png")
    )
    if ACCESS_ENABLED and protected:
        token = request.cookies.get("roxy_token", "")
        if not token or token not in AUTH_TOKENS:
            return JSONResponse(
                {"error": "未登录或登录已失效，请重新输入口令"}, status_code=401
            )
    return await call_next(request)


# 会话历史: session_id -> [{"role": "user"/"assistant", "content": str}]
HISTORY: dict[str, list] = {}
HISTORY_PATH = ROOT / "data" / "history.json"


def _load_history():
    if HISTORY_PATH.exists():
        try:
            HISTORY.update(json.loads(HISTORY_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass


def _save_history():
    try:
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        HISTORY_PATH.write_text(
            json.dumps(HISTORY, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    except Exception:
        pass


_load_history()

# ---------------------------------------------------------------- 心情 & 记忆 & 情绪

STATE_PATH = ROOT / "data" / "roxy_state.json"
STATE = {"mood": 80, "names": {}}


def _load_state():
    if STATE_PATH.exists():
        try:
            STATE.update(json.loads(STATE_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass


def _save_state():
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(
            json.dumps(STATE, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    except Exception:
        pass


_load_state()

EMOTION_KEYWORDS = {
    "happy": ["笑", "开心", "高兴", "嘻嘻", "哈哈", "太好了", "喜欢", "期待", "兴奋"],
    "shy": ["害羞", "脸红", "慌", "别过脸", "小声", "不好意思", "扭捏", "低头", "结结巴巴"],
    "surprised": ["惊讶", "吃惊", "睁大", "吓", "居然", "诶", "咦", "天哪", "真的吗"],
    "sad": ["难过", "伤心", "叹气", "遗憾", "对不起", "抱歉", "失落", "哭", "惋惜"],
    "gentle": ["温柔", "认真", "放心", "别担心", "加油", "陪", "慢慢", "倾听", "没关系"],
}
EMOTION_PRIORITY = ["sad", "shy", "surprised", "happy", "gentle"]

EMOTION_EMOJI = {
    "happy": "😊", "shy": "😳", "surprised": "😲", "sad": "😢",
    "gentle": "🥰", "calm": "😌",
}


def _detect_emotion(text: str) -> str:
    """根据回复文字里的神态/语气词，估一个情绪标签（不额外调用模型）。"""
    text = text or ""
    best, best_score = "calm", 0
    for emo in EMOTION_PRIORITY:
        score = sum(text.count(k) for k in EMOTION_KEYWORDS[emo])
        if score > best_score:
            best, best_score = emo, score
    return best


MOOD_DELTA = {"happy": 2, "gentle": 1, "surprised": 1, "shy": 1, "calm": 0, "sad": -3}


def _update_mood(emotion: str):
    STATE["mood"] = max(0, min(100, STATE.get("mood", 80) + MOOD_DELTA.get(emotion, 0)))


def _mood_label(mood: int) -> str:
    if mood >= 80:
        return "心情很好"
    if mood >= 60:
        return "心情不错"
    if mood >= 40:
        return "心情平静"
    if mood >= 20:
        return "有点低落"
    return "心情低落"


def _mood_emoji(mood: int) -> str:
    if mood >= 80:
        return "☀️"
    if mood >= 60:
        return "🙂"
    if mood >= 40:
        return "😌"
    if mood >= 20:
        return "😔"
    return "🌧️"


def _detect_name(text: str):
    """从用户消息里识别自我介绍，比如「我叫阿泽」「叫我小美」。"""
    patterns = [
        r"你可以叫我\s*([一-龥A-Za-z0-9]{1,8})",
        r"我叫\s*([一-龥A-Za-z0-9]{1,8})",
        r"我是\s*([一-龥A-Za-z0-9]{1,8})",
        r"叫我\s*([一-龥A-Za-z0-9]{1,8})",
    ]
    for p in patterns:
        m = re.search(p, text or "")
        if m:
            name = m.group(1).strip()
            if name and name not in ("谁", "我", "你", "大家", "朋友", "一个人", "一个"):
                return name
    return None


def _build_system_prompt(session_id: str) -> str:
    """把洛琪希当前心情、以及记住的对方名字注入人设。"""
    mood = STATE.get("mood", 80)
    extra = (
        f"\n\n【当前状态】你现在的心情约 {mood}/100（{_mood_label(mood)}），"
        f"请在语气中自然带出这种心情，但不要主动提分数。"
    )
    name = STATE.get("names", {}).get(session_id)
    if name:
        extra += f"\n【对方】正在和你聊天的人叫「{name}」，可以自然地称呼对方名字。"
    return SYSTEM_PROMPT + extra


def _greeting_for(hour: int, name) -> str:
    if 5 <= hour < 11:
        period = "早上"
    elif 11 <= hour < 14:
        period = "中午"
    elif 14 <= hour < 18:
        period = "下午"
    else:
        period = "晚上"
    who = f"，{name}" if name else ""
    return f"{period}好{who}。今天过得怎么样？有什么想和我聊的吗？（微笑）"


# ---------------------------------------------------------------- LLM


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class TTSRequest(BaseModel):
    text: str


def _clean_reply(content: str) -> str:
    """移除模型的内部推理块与意外前缀，保留可展示的台词。"""
    content = re.sub(r"<think>.*?</think>", "", content or "", flags=re.DOTALL | re.IGNORECASE)
    content = re.sub(r"</?analysis>", "", content, flags=re.IGNORECASE)
    return content.strip()


async def _call_messages(messages: list, temperature: float = 0.3) -> str:
    """调用中转站 OpenAI 兼容 chat/completions 接口。"""
    url = LLM_CFG["base_url"].rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {LLM_CFG['api_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": LLM_CFG["model"],
        "messages": messages,
        "temperature": temperature,
    }
    # 默认不走系统代理 (中转站一般国内直连); 如需代理在 config 里开 use_system_proxy
    trust_env = bool(LLM_CFG.get("use_system_proxy", False))
    async with httpx.AsyncClient(timeout=120, trust_env=trust_env) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"] or ""
        return _clean_reply(content)


async def _call_llm(history: list, system_prompt: str = SYSTEM_PROMPT) -> str:
    messages = [{"role": "system", "content": system_prompt}] + history
    return await _call_messages(
        messages, temperature=float(LLM_CFG.get("temperature", 0.8))
    )


class _ThinkStripper:
    """流式输出时实时剥离 <think>...</think> 推理块，只把可展示的台词吐出去。"""

    def __init__(self):
        self._buf = ""
        self._in_think = False

    def feed(self, chunk: str) -> str:
        self._buf += chunk
        out: list[str] = []
        while self._buf:
            if self._in_think:
                idx = self._buf.find("</think>")
                if idx == -1:
                    self._buf = self._buf[-7:]  # 防 "</think>" 被切成两半
                    break
                self._buf = self._buf[idx + 8:]
                self._in_think = False
            else:
                idx = self._buf.find("<think>")
                if idx == -1:
                    keep = min(len(self._buf), 6)  # 防 "<think>" 被切成两半
                    out.append(self._buf[: len(self._buf) - keep])
                    self._buf = self._buf[-keep:]
                    break
                out.append(self._buf[:idx])
                self._buf = self._buf[idx + 7:]
                self._in_think = True
        text = "".join(out)
        return text.replace("<analysis>", "").replace("</analysis>", "")

    def flush(self) -> str:
        text = "" if self._in_think else self._buf
        self._buf = ""
        self._in_think = False
        return text.replace("<analysis>", "").replace("</analysis>", "")


async def _call_llm_stream(messages: list, temperature: float = 0.8):
    """流式调用中转站 chat/completions，逐块产出文本增量（已剥离推理块）。"""
    url = LLM_CFG["base_url"].rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {LLM_CFG['api_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": LLM_CFG["model"],
        "messages": messages,
        "temperature": temperature,
        "stream": True,
    }
    trust_env = bool(LLM_CFG.get("use_system_proxy", False))
    async with httpx.AsyncClient(timeout=120, trust_env=trust_env) as client:
        async with client.stream("POST", url, headers=headers, json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                line = line.strip()
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                except Exception:
                    continue
                delta = obj.get("choices", [{}])[0].get("delta", {}).get("content")
                if delta:
                    yield delta


async def _translate_for_voice(text: str) -> str:
    """把中文回复转为适合朗读的自然日语，并规范标点与换行。"""
    if not VOICE_CFG.get("japanese_voice", False):
        return text
    translate_prompt = """你是日语本地化编辑。请把下面的中文台词翻译成自然、口语化、符合洛琪希温和沉稳说话风格的日语。
只输出日语台词本身，不要解释，不要加引号，不要输出思考过程。
朗读优化规则：最多 3 个短句；句子之间只用自然的「、」「。」「？」「！」；不要换行；不要保留括号动作描写；不要使用省略号或连续标点。
中文台词：""" + text
    try:
        result = await _call_messages(
            [{"role": "user", "content": translate_prompt}], temperature=0.35
        )
        result = re.sub(r"<think>.*?</think>", "", result or "", flags=re.DOTALL)
        result = re.sub(r"[（(][^）)]*[）)]", "", result)
        result = re.sub(r"[\r\n]+", "", result)
        result = re.sub(r"[。！？!?]+", lambda m: m.group(0)[0], result)
        result = re.sub(r"…+|\.{2,}", "", result)
        return result.strip(" \u3000，,、") or text
    except Exception:
        return text


# ---------------------------------------------------------------- TTS

_voice_ok_cache = {"ok": None, "ts": 0.0}
_loaded_voice_models = {"gpt": None, "sovits": None}


async def _voice_alive() -> bool:
    """探测本地 GPT-SoVITS 是否在线 (结果缓存 10 秒)。"""
    if not VOICE_CFG.get("enabled", False):
        return False
    now = time.time()
    if _voice_ok_cache["ok"] is not None and now - _voice_ok_cache["ts"] < 10:
        return _voice_ok_cache["ok"]
    try:
        # trust_env=False: 本地语音服务绝不能走系统代理
        async with httpx.AsyncClient(timeout=3, trust_env=False) as client:
            # /tts needs synthesis fields. /docs verifies that the API is accepting
            # requests without starting an expensive synthesis job.
            resp = await client.get(VOICE_CFG["api_base"].rstrip("/") + "/docs")
            resp.raise_for_status()
        alive = True
    except Exception:
        alive = False
    _voice_ok_cache.update(ok=alive, ts=now)
    return alive


async def _ensure_custom_models(client: httpx.AsyncClient):
    """通过 GPT-SoVITS 官方热加载接口切换到 RoxyPro 权重（每个进程只切换一次）。"""
    pairs = (
        ("gpt", VOICE_CFG.get("custom_gpt_model"), "set_gpt_weights"),
        ("sovits", VOICE_CFG.get("custom_sovits_model"), "set_sovits_weights"),
    )
    for kind, configured, endpoint in pairs:
        if not configured or _loaded_voice_models[kind] == configured:
            continue
        path = str(configured)
        if not Path(path).is_absolute():
            path = str((ROOT / path).resolve())
        if not Path(path).is_file():
            raise FileNotFoundError(f"找不到语音模型: {path}")
        resp = await client.get(
            VOICE_CFG["api_base"].rstrip("/") + "/" + endpoint,
            params={"weights_path": path},
        )
        resp.raise_for_status()
        _loaded_voice_models[kind] = configured


async def _call_tts(text: str) -> bytes:
    """调用 GPT-SoVITS api_v2 的 /tts 接口, 返回 wav 音频字节。"""
    ref_path = str(VOICE_CFG.get("ref_audio_path", "") or "")
    if ref_path and not Path(ref_path).is_absolute():
        ref_path = str((ROOT / ref_path).resolve())
    payload = {
        "text": text,
        "text_lang": VOICE_CFG.get("text_lang", "zh"),
        "ref_audio_path": ref_path,
        "prompt_text": VOICE_CFG.get("prompt_text", ""),
        "prompt_lang": VOICE_CFG.get("prompt_lang", "zh"),
        "speed_factor": float(VOICE_CFG.get("speed", 1.0)),
        "fragment_interval": float(VOICE_CFG.get("fragment_interval", 0.12)),
        "top_k": int(VOICE_CFG.get("top_k", 20)),
        "top_p": float(VOICE_CFG.get("top_p", 0.85)),
        "temperature": float(VOICE_CFG.get("tts_temperature", 0.75)),
        "repetition_penalty": float(VOICE_CFG.get("repetition_penalty", 1.28)),
        "text_split_method": VOICE_CFG.get("text_split_method", "cut5"),
        "media_type": "wav",
        "streaming_mode": False,
    }
    # 若配置了社区训练的洛琪希专用模型, 则让 api_v2 热加载
    if VOICE_CFG.get("custom_gpt_model"):
        gpt_path = str(VOICE_CFG["custom_gpt_model"])
        if not Path(gpt_path).is_absolute():
            gpt_path = str((ROOT / gpt_path).resolve())
        payload["gpt_model_path"] = gpt_path
    if VOICE_CFG.get("custom_sovits_model"):
        sovits_path = str(VOICE_CFG["custom_sovits_model"])
        if not Path(sovits_path).is_absolute():
            sovits_path = str((ROOT / sovits_path).resolve())
        payload["sovits_model_path"] = sovits_path
    # trust_env=False: 语音服务在本机, 不走系统代理
    async with httpx.AsyncClient(timeout=180, trust_env=False) as client:
        await _ensure_custom_models(client)
        resp = await client.post(
            VOICE_CFG["api_base"].rstrip("/") + "/tts", json=payload
        )
        resp.raise_for_status()
        return resp.content


# ---------------------------------------------------------------- 鉴权


class LoginRequest(BaseModel):
    password: str = ""


@app.post("/api/login")
async def login(req: LoginRequest):
    """校验口令，通过后下发登录令牌（HttpOnly Cookie，前端无法读取）。"""
    if not ACCESS_ENABLED:
        return {"ok": True}
    if (req.password or "").strip() != ACCESS_PASSWORD:
        return JSONResponse({"error": "口令错误"}, status_code=403)
    token = secrets.token_urlsafe(32)
    AUTH_TOKENS.add(token)
    resp = JSONResponse({"ok": True})
    resp.set_cookie(
        "roxy_token",
        token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,
    )
    return resp


@app.post("/api/logout")
async def logout(request: Request):
    """退出登录：清除令牌与 Cookie。"""
    AUTH_TOKENS.discard(request.cookies.get("roxy_token", ""))
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("roxy_token")
    return resp


@app.get("/api/auth_status")
async def auth_status(request: Request):
    """前端据此判断是否需要弹出登录框。"""
    authed = True
    if ACCESS_ENABLED:
        authed = request.cookies.get("roxy_token", "") in AUTH_TOKENS
    return {"enabled": ACCESS_ENABLED, "authed": authed}


# ---------------------------------------------------------------- 限流

_RATE_BUCKETS: dict[str, collections.deque] = {}


def _rate_allowed(key: str, limit: int = 30, window: float = 300.0) -> bool:
    """按 session_id 做滑动窗口限流（每 5 分钟最多 30 条），防止误刷收费额度。"""
    now = time.time()
    dq = _RATE_BUCKETS.setdefault(key, collections.deque())
    while dq and now - dq[0] > window:
        dq.popleft()
    if len(dq) >= limit:
        return False
    dq.append(now)
    return True


# ---------------------------------------------------------------- 路由


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "llm_configured": not str(LLM_CFG.get("api_key", "")).startswith("sk-请"),
        "voice_online": await _voice_alive(),
        "voice_enabled": bool(VOICE_CFG.get("enabled", False)),
    }


@app.get("/api/state")
async def get_state(session_id: str = "default"):
    """返回洛琪希当前心情、记住的名字、以及按时间生成的问候语。"""
    mood = int(STATE.get("mood", 80))
    name = STATE.get("names", {}).get(session_id)
    return {
        "mood": mood,
        "mood_label": _mood_label(mood),
        "mood_emoji": _mood_emoji(mood),
        "name": name,
        "greeting": _greeting_for(datetime.now().hour, name),
        "emotion": "calm",
    }


@app.get("/api/history")
async def get_history(session_id: str = "default"):
    """返回指定会话的聊天记录，供刷新页面后恢复显示。"""
    return {"messages": HISTORY.get(session_id, [])}


@app.delete("/api/history")
async def clear_history(session_id: str = "default"):
    """清空指定会话记录。"""
    HISTORY.pop(session_id, None)
    _save_history()
    return {"ok": True}


@app.get("/api/backgrounds")
async def backgrounds():
    """列出可用背景：assets/video 下的视频 + assets/images/bg 下的图片，带类型标记。"""
    pretty = {
        "roxy_bg": "深海洛琪希",
        "roxy_bg_small": "深海洛琪希",
        "roxy_missyou": "Miss You",
        "bg_3304137609": "洛琪希·水之问候",
        "bg_3329004013": "洛琪希·魔法阵",
        "bg_3371359611": "洛琪希·眨眼",
        "bg_2941994990": "洛琪希·夜色",
        "bg_3721991999": "洛琪希·戏水",
    }
    # 超过 50MB 的超大视频不推送给访客（比如原始 4K 背景），避免占满免费带宽
    max_bytes = 50 * 1024 * 1024
    items = []
    video_dir = ROOT / "assets" / "video"
    if video_dir.is_dir():
        for f in sorted(video_dir.iterdir()):
            if f.suffix.lower() in (".mp4", ".webm") and f.stat().st_size <= max_bytes:
                items.append({
                    "name": pretty.get(f.stem, f.stem),
                    "src": f"/assets/video/{f.name}",
                    "type": "video",
                })
    img_dir = ROOT / "assets" / "images" / "bg"
    if img_dir.is_dir():
        for f in sorted(img_dir.iterdir()):
            if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                items.append({
                    "name": pretty.get(f.stem, f.stem),
                    "src": f"/assets/images/bg/{f.name}",
                    "type": "image",
                })
    return {"backgrounds": items}


@app.post("/api/chat")
async def chat(req: ChatRequest):
    text = (req.message or "").strip()
    if not text:
        return JSONResponse({"error": "消息不能为空"}, status_code=400)
    if len(text) > 2000:
        return JSONResponse({"error": "消息太长啦，一次最多 2000 字"}, status_code=400)

    if not _rate_allowed(req.session_id):
        return JSONResponse({"error": "聊得太快啦，请稍等一会儿再继续"}, status_code=429)

    detected_name = _detect_name(text)
    if detected_name:
        STATE.setdefault("names", {})[req.session_id] = detected_name
        _save_state()

    history = HISTORY.setdefault(req.session_id, [])
    history.append({"role": "user", "content": text, "time": int(time.time())})
    _save_history()  # 先落盘，浏览器刷新或进程异常时也尽量不丢用户消息

    max_turns = int(LLM_CFG.get("max_history", 20)) * 2
    trimmed = history[-max_turns:]

    try:
        reply = await _call_llm(trimmed, _build_system_prompt(req.session_id))
    except httpx.HTTPStatusError as e:
        history.pop()  # 失败时回滚这条用户消息, 便于重试
        detail = f"中转站返回错误 {e.response.status_code}: {e.response.text[:200]}"
        return JSONResponse({"error": detail}, status_code=502)
    except Exception as e:
        history.pop()
        return JSONResponse({"error": f"无法连接中转站: {e}"}, status_code=502)

    history.append({"role": "assistant", "content": reply, "time": int(time.time())})
    while len(history) > max_turns:
        history.pop(0)
    _save_history()
    voice_text = await _translate_for_voice(reply)
    emotion = _detect_emotion(reply)
    _update_mood(emotion)
    _save_state()
    return {"reply": reply, "voice_text": voice_text, "emotion": emotion}


def _sse(payload: dict) -> str:
    """把对象编码成一条 SSE data 事件。"""
    return "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    """流式版对话：逐字返回洛琪希回复，结束后带上翻译好的日语语音文本。"""
    text = (req.message or "").strip()
    if not text:
        return JSONResponse({"error": "消息不能为空"}, status_code=400)
    if len(text) > 2000:
        return JSONResponse({"error": "消息太长啦，一次最多 2000 字"}, status_code=400)
    if not _rate_allowed(req.session_id):
        return JSONResponse({"error": "聊得太快啦，请稍等一会儿再继续"}, status_code=429)

    detected_name = _detect_name(text)
    if detected_name:
        STATE.setdefault("names", {})[req.session_id] = detected_name
        _save_state()

    history = HISTORY.setdefault(req.session_id, [])
    history.append({"role": "user", "content": text, "time": int(time.time())})
    _save_history()

    max_turns = int(LLM_CFG.get("max_history", 20)) * 2
    trimmed = history[-max_turns:]
    messages = [{"role": "system", "content": _build_system_prompt(req.session_id)}] + trimmed
    temperature = float(LLM_CFG.get("temperature", 0.8))

    async def generate():
        reply = ""
        stripper = _ThinkStripper()
        try:
            async for delta in _call_llm_stream(messages, temperature=temperature):
                out = stripper.feed(delta)
                if out:
                    reply += out
                    yield _sse({"delta": out})
            tail = stripper.flush()
            if tail:
                reply += tail
                yield _sse({"delta": tail})
            reply = reply.strip()
        except Exception as e:
            history.pop()  # 回滚这条用户消息，便于重试
            yield _sse({"error": f"无法连接中转站: {e}"})
            yield "data: [DONE]\n\n"
            return

        if not reply:
            history.pop()
            yield _sse({"error": "中转站没有返回内容"})
            yield "data: [DONE]\n\n"
            return

        history.append({"role": "assistant", "content": reply, "time": int(time.time())})
        while len(history) > max_turns:
            history.pop(0)
        _save_history()

        voice_text = await _translate_for_voice(reply)
        emotion = _detect_emotion(reply)
        _update_mood(emotion)
        _save_state()
        yield _sse({"done": True, "reply": reply, "voice_text": voice_text, "emotion": emotion})
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/tts")
async def tts(req: TTSRequest):
    text = (req.text or "").strip()
    if not text:
        return JSONResponse({"error": "文本不能为空"}, status_code=400)
    if not await _voice_alive():
        return JSONResponse(
            {"error": "语音服务未启动，请先运行 setup_voice.bat 并启动 GPT-SoVITS"},
            status_code=503,
        )
    try:
        audio = await _call_tts(text)
    except Exception as e:
        return JSONResponse({"error": f"语音合成失败: {e}"}, status_code=500)
    return Response(content=audio, media_type="audio/wav")


# ---------------------------------------------------------------- 静态页面

app.mount("/assets", StaticFiles(directory=ROOT / "assets"), name="assets")


@app.get("/")
async def index():
    return FileResponse(ROOT / "frontend" / "index.html")


@app.get("/{fname:path}")
async def static_files(fname: str):
    frontend_root = (ROOT / "frontend").resolve()
    target = (frontend_root / fname).resolve()
    if frontend_root in target.parents and target.is_file():
        return FileResponse(target)
    return JSONResponse({"error": "not found"}, status_code=404)


if __name__ == "__main__":
    host = SERVER_CFG.get("host", "127.0.0.1")
    port = int(SERVER_CFG.get("port", 8000))
    print(f"\n  洛琪希AI对话网站已启动:  http://{host}:{port}\n")
    uvicorn.run(app, host=host, port=port, log_level="warning")
