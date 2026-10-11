import streamlit as st
import os
import json
import base64
import re
from datetime import datetime, date, timezone, timedelta
import urllib.request
import urllib.error
import streamlit.components.v1 as components

# ----------------------------------------------------
# 日本標準時 (JST = UTC+9) 定義（クラウドサーバーのUTC時間ズレを完全解消）
# ----------------------------------------------------
JST = timezone(timedelta(hours=9), name="JST")

def get_now_jst():
    """日本時間 (JST) の現在日時 datetime を返す"""
    return datetime.now(JST)

def get_today_jst():
    """日本時間 (JST) の今日の日付 date を返す"""
    return datetime.now(JST).date()

def get_today_str_jst():
    """日本時間 (JST) の今日の日付文字列 (YYYY-MM-DD) を返す"""
    return get_today_jst().isoformat()

def get_time_str_jst():
    """日本時間 (JST) の現在時刻文字列 (HH:MM) を返す"""
    return get_now_jst().strftime("%H:%M")

def get_datetime_str_jst():
    """日本時間 (JST) の現在日時文字列 (YYYY-MM-DD HH:MM) を返す"""
    return get_now_jst().strftime("%Y-%m-%d %H:%M")

def calculate_streak_days(daily_logs):
    """記録されたカレンダーログから実際の連続継続日数を自動算出"""
    if not daily_logs:
        return 1
    saved_dates = set()
    for d_str in daily_logs.keys():
        try:
            saved_dates.add(date.fromisoformat(d_str))
        except Exception:
            pass
    if not saved_dates:
        return 1
    today = get_today_jst()
    current_check = today if today in saved_dates else today - timedelta(days=1)
    if current_check not in saved_dates:
        return max(len(saved_dates), 1)
    streak = 0
    while current_check in saved_dates:
        streak += 1
        current_check -= timedelta(days=1)
    return max(streak, 1)

# ページ基本設定
st.set_page_config(
    page_title="ソクラテス・メンター 〜正解を教えない壁打ちチャット〜",
    page_icon="💡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 画像のBase64エンコード処理
def get_image_base64(image_path):
    if os.path.exists(image_path):
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode("utf-8")
    return ""

img_b64 = get_image_base64("teraoka.png")
data_uri = f"data:image/png;base64,{img_b64}" if img_b64 else "./teraoka.png"

# スタイルの適用
st.markdown(
r"""<style>
/* ダークモード背景とスクロールバー */
.stApp {
    background-color: #090d16 !important;
}
::-webkit-scrollbar {
    width: 8px;
    height: 8px;
}
::-webkit-scrollbar-track {
    background: #0f172a;
}
::-webkit-scrollbar-thumb {
    background: #334155;
    border-radius: 4px;
}
::-webkit-scrollbar-thumb:hover {
    background: #06b6d4;
}

/* ロゴ用Tailwindスタイルのインライン補完 */
.flex { display: flex !important; }
.items-center { align-items: center !important; }
.justify-between { justify-content: space-between !important; }
.bg-slate-900\/80 { background-color: rgba(15, 23, 42, 0.95) !important; }
.p-3 { padding: 0.75rem !important; }
.pr-6 { padding-right: 1.5rem !important; }
.rounded-full { border-radius: 9999px !important; }
.border { border-width: 1px !important; border-style: solid !important; }
.border-slate-700 { border-color: #334155 !important; }
.border-slate-800 { border-color: #1e293b !important; }
.shadow-xl { box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.6) !important; }
.ml-4 { margin-left: 1rem !important; }
.w-14 { width: 3.5rem !important; min-width: 3.5rem !important; max-width: 3.5rem !important; }
.h-14 { height: 3.5rem !important; min-height: 3.5rem !important; max-height: 3.5rem !important; }
.object-cover { object-fit: cover !important; }
.border-2 { border-width: 2px !important; border-style: solid !important; }
.border-cyan-500\/30 { border-color: rgba(6, 182, 212, 0.4) !important; }
.text-right { text-align: right !important; }
.font-bold { font-weight: 700 !important; }
.text-sm { font-size: 0.875rem !important; }
.text-cyan-400 { color: #22d3ee !important; }
.text-xs { font-size: 0.75rem !important; }
.text-gray-400 { color: #9ca3af !important; }
.max-w-\[200px\] { max-width: 200px !important; }
.leading-tight { line-height: 1.25 !important; }
.mt-1 { margin-top: 0.25rem !important; }
.cursor-default { cursor: default !important; }

/* チャットメッセージのスタイリング */
.stChatMessage {
    background-color: #0f172a !important;
    border: 1px solid #1e293b !important;
    border-radius: 1rem !important;
    margin-bottom: 0.75rem !important;
}

/* フッター */
.app-footer {
    border-top: 1px solid #1e293b;
    padding: 2rem 0;
    margin-top: 3rem;
    text-align: center;
    color: #64748b;
    font-size: 0.8rem;
}
</style>
""",
unsafe_allow_html=True
)

# ----------------------------------------------------
# ローカルLLMモデルのロード（PC内部で実稼働）
# ----------------------------------------------------
@st.cache_resource
def load_local_model_instance():
    from transformers import AutoModelForCausalLM, AutoTokenizer
    import torch
    model_id = "Qwen/Qwen2.5-0.5B-Instruct"
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        dtype=torch.float32,
        low_cpu_mem_usage=True
    )
    return tokenizer, model

def generate_local_model_response(prompt_text, history_messages, mode_text):
    try:
        tokenizer, model = load_local_model_instance()
    except (ImportError, ModuleNotFoundError):
        return (
            "【ご案内】クラウド環境（Streamlit Community Cloud）は共有コンテナのメモリ上限（1GB）制限があるため、"
            "PC実機内蔵のローカルLLM（PyTorch/Transformers）はローカルPC環境でのみ稼働します。\n\n"
            "クラウド上では、上のモデル選択から「gemini-1.5-flash（推奨）」または「llama-3.3-70b-versatile」を選択してご利用ください。"
        )
    except Exception as e:
        return f"ローカルモデルのロード中にエラーが発生しました: {str(e)}"
    
    import torch

    mode_hint = {
        "前提の確認（当たり前や定義を疑う）": "特に前提や言葉の定義を問い直しなさい。",
        "視点の転換（他者の立場・逆から見る）": "特に異なる他者の立場からの視点を促しなさい。",
        "根拠の提示（なぜそう言えるのかを突く）": "特にそう考えるに至った体験や根拠を問いなさい。",
        "未来の予測（もしそれが起きたらどうなるか）": "特にそれが起きた未来の波及効果を問いなさい。",
        "総合（共感と寄り添い深掘り）": "温かく受け止め、最も探究が深まる核心を問いなさい。"
    }.get(mode_text, "")

    system_instruction = f"""あなたは高校生のための「ソクラテス・メンター」です。
生徒の悩みや発言に温かく寄り添い、生徒が使った言葉（キーワード）を引用しながら、決して答えを教えずに、思考を深める問いかけを日本語で1つだけ返してください。{mode_hint}
文章は途中で途切れず完結させてください。"""

    chat_prompt = [{"role": "system", "content": system_instruction}]
    for m in history_messages[-4:]:
        if m["role"] == "user" and m["content"] == prompt_text:
            continue
        chat_prompt.append({"role": m["role"], "content": m["content"]})
    chat_prompt.append({"role": "user", "content": prompt_text})

    formatted_text = tokenizer.apply_chat_template(chat_prompt, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer([formatted_text], return_tensors="pt")
    
    with torch.inference_mode():
        outputs = model.generate(
            **inputs,
            max_new_tokens=150,
            temperature=0.7,
            do_sample=True,
            repetition_penalty=1.15
        )
    new_tokens = outputs[0][len(inputs.input_ids[0]):]
    reply = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
    return reply

# ----------------------------------------------------
# セッション状態の初期化
# ----------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "こんにちは！今日はどんなテーマや悩みについて、一緒に考えを深めていきましょうか？頭の中にあるモヤモヤをそのまま言葉にしてみてくださいね。",
            "timestamp": get_datetime_str_jst()
        }
    ]

if "daily_logs" not in st.session_state:
    st.session_state.daily_logs = {}

if "streak_days" not in st.session_state:
    st.session_state.streak_days = 1

# ----------------------------------------------------
# ヘッダーエリア：水平配置（左：タイトル、右：指定ロゴ）
# ----------------------------------------------------
col_header_left, col_header_right = st.columns([1.5, 1.5], vertical_alignment="center")

with col_header_left:
    st.markdown(
"""<div style="display: flex; align-items: center; gap: 0.75rem;">
    <div style="width: 3rem; height: 3rem; border-radius: 1rem; background: linear-gradient(135deg, #0891b2, #3b82f6); display: flex; align-items: center; justify-content: center; font-size: 1.5rem; box-shadow: 0 4px 15px rgba(6, 182, 212, 0.3);">
        💡
    </div>
    <div>
        <div style="display: flex; align-items: center; gap: 0.5rem;">
            <h1 style="font-size: 1.5rem; font-weight: 800; margin: 0; background: linear-gradient(to right, #22d3ee, #e0f2fe, #a5b4fc); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
                ソクラテス・メンター
            </h1>
            <span style="font-size: 0.7rem; background-color: rgba(8, 47, 73, 0.8); color: #7dd3fc; border: 1px solid rgba(14, 116, 144, 0.6); padding: 0.15rem 0.5rem; border-radius: 9999px;">
                高校生探究教材
            </span>
        </div>
        <p style="font-size: 0.75rem; color: #94a3b8; margin: 0.2rem 0 0 0;">
            〜正解を教えない壁打ちチャット〜 ｜ 言語化・思考深化・メタ認知
        </p>
    </div>
</div>
""",
        unsafe_allow_html=True
    )

with col_header_right:
    logo_code = f"""<!-- プロフィール -->
<div style="display: flex; justify-content: flex-end; width: 100%;">
    <div class="flex items-center mt-6 md:mt-0 bg-slate-900/80 p-3 pr-6 rounded-full border border-slate-700 shadow-xl ml-4 hover:border-cyan-500/50 transition-colors cursor-default" style="width: fit-content; max-width: 370px;">
        <img src="{data_uri}" onerror="this.src='https://ui-avatars.com/api/?name=Teraoka&background=0f172a&color=fff'" alt="Profile" class="w-14 h-14 rounded-full object-cover border-2 border-cyan-500/30" style="width: 3.5rem; height: 3.5rem; border-radius: 9999px; object-fit: cover;">
        <div class="text-right ml-4">
            <p class="font-bold text-sm text-cyan-400">テラオカ電子の自由探究ゼミ</p>
            <p class="text-xs text-gray-400 max-w-[200px] leading-tight mt-1">自分が価値を置くものに向かって<br>こつこつ努力する姿ほど<br>素晴らしいものはない</p>
        </div>
    </div>
</div>"""
    st.markdown(logo_code, unsafe_allow_html=True)

st.markdown("<hr style='border: none; border-top: 1px solid #1e293b; margin: 1.2rem 0;'>", unsafe_allow_html=True)

# ----------------------------------------------------
# 上部：探究・AI設定 & 操作パネル
# ----------------------------------------------------
# Secrets および 環境変数のスマート自動解析（キーの内容から判別）
raw_secrets = {}
try:
    for k, v in st.secrets.items():
        if isinstance(v, str):
            raw_secrets[k] = v.strip().strip("'\"")
except Exception:
    pass

for k, v in os.environ.items():
    if k in ["GROQ_API_KEY", "GEMINI_API_KEY", "API_KEY"] and isinstance(v, str):
        raw_secrets.setdefault(k, v.strip().strip("'\""))

# 内容（AIza... / gsk_...）に基づく確実な自動判別
detected_gemini_key = ""
detected_groq_key = ""

for k, val in raw_secrets.items():
    if "AIza" in val:
        detected_gemini_key = val
    elif val.startswith("gsk_"):
        detected_groq_key = val

# 変数名からのフォールバック
if not detected_gemini_key:
    for k in ["GEMINI_API_KEY", "API_KEY"]:
        v = raw_secrets.get(k, "")
        if v and not v.startswith("gsk_"):
            detected_gemini_key = v
            break

if not detected_groq_key:
    v = raw_secrets.get("GROQ_API_KEY", "")
    if v and v.startswith("gsk_"):
        detected_groq_key = v

has_gemini = bool(detected_gemini_key)
has_groq = bool(detected_groq_key)
has_any_secret = has_gemini or has_groq

col_s1, col_s2, col_s3 = st.columns([1.2, 1.2, 1.1])

with col_s1:
    if has_any_secret:
        if has_gemini and has_groq:
            provider_desc = "Gemini & Groq 両方連携済"
        elif has_gemini:
            provider_desc = "Google Gemini API 連携済"
        else:
            provider_desc = "Groq API 連携済"

        st.markdown(
            f"""
            <div style="background-color: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 0.5rem; padding: 0.6rem; font-size: 0.75rem; color: #6ee7b7;">
                🔒 <strong>Secrets連携中</strong>（{provider_desc}）<br>
                APIキーは安全に秘匿化され自動適用されています。<br>
                <span style="color: #cbd5e1; font-size: 0.7rem;">※ クラウド推論時は氏名等の個人情報は入力しないでください。</span>
            </div>
            """,
            unsafe_allow_html=True
        )
        input_manual_key = ""
    else:
        input_manual_key = st.text_input(
            "🔑 API Key（Gemini または Groq）",
            value="",
            type="password",
            help="Google Gemini（AIza...）またはGroq（gsk_...）のキーを入力してください。未入力時はPC内蔵ローカルLLMが稼働します。"
        )

with col_s2:
    model_list = [
        "gemini-1.5-flash (Google公式: 高速・無料・推奨)",
        "gemini-2.0-flash (Google公式: 次世代最新モデル)",
        "gemini-1.5-flash-8b (Google公式: 超軽量・低遅延)",
        "gemini-1.5-pro (Google公式: 最深思考・最高精度)",
        "llama-3.3-70b-versatile (Groqクラウド: 最高精度70B)",
        "llama-3.1-8b-instant (Groqクラウド: 超高速レスポンス)",
        "gemma2-9b-it (Groqクラウド: Google高知能モデル)",
        "mixtral-8x7b-32768 (Groqクラウド: 長文・多角的視点)",
        "🖥️ ローカルLLM (Qwen2.5-0.5B: PC内実機稼働)"
    ]

    # デフォルトモデル決定: Geminiキーがあれば最優先でGemini 1.5 Flash、GroqキーのみならLlama
    if has_gemini:
        default_model_idx = 0
    elif has_groq:
        default_model_idx = 4
    elif input_manual_key.startswith("AIza"):
        default_model_idx = 0
    elif input_manual_key.startswith("gsk_"):
        default_model_idx = 4
    else:
        default_model_idx = 0  # クラウド運用時はGemini-1.5-flashをデフォルト推奨

    model_choice = st.selectbox(
        "🤖 動作エンジン / モデル",
        model_list,
        index=default_model_idx,
        help="Google Gemini系モデルとGroq系モデルの両方に対応しています。"
    )

def get_active_model_key(selected_model):
    raw_m = selected_model.split()[0].lower()
    if "gemini" in raw_m:
        return detected_gemini_key or (input_manual_key if "AIza" in input_manual_key else "") or detected_groq_key or input_manual_key
    elif any(x in raw_m for x in ["llama", "gemma", "mixtral"]):
        return detected_groq_key or (input_manual_key if input_manual_key.startswith("gsk_") else "") or detected_gemini_key or input_manual_key
    return detected_gemini_key or detected_groq_key or input_manual_key

groq_api_key = get_active_model_key(model_choice)

with col_s3:
    socratic_mode = st.selectbox(
        "🧭 探究の切り口",
        [
            "総合（共感と寄り添い深掘り）",
            "前提の確認（当たり前や定義を疑う）",
            "視点の転換（他者の立場・逆から見る）",
            "根拠の提示（なぜそう言えるのかを突く）",
            "未来の予測（もしそれが起きたらどうなるか）"
        ],
        index=0
    )

# ----------------------------------------------------
# 対話の論点整理と得られた知見の自動要約関数
# ----------------------------------------------------
def extract_core_topic(text):
    phrases = re.split(r'[、。！？\n\r]+', text)
    phrases = [p.strip() for p in phrases if p.strip()]
    stopwords = [
        "と考えています", "と考えてる", "と思います", "と思う", "について",
        "でしょうか", "ですか", "何ですか", "どうですか", "したいです",
        "したいと考えています", "しています", "なんです", "ことです",
        "あります", "います", "です", "ます", "ほしい", "になります",
        "の目的は何だと思いますか", "目的は何ですか", "何だと思いますか"
    ]
    meaningful = []
    for p in phrases:
        temp = p
        for sw in stopwords:
            temp = temp.replace(sw, "")
        temp = temp.strip()
        if len(temp) >= 2:
            meaningful.append(temp)
    return meaningful[0] if meaningful else (phrases[0] if phrases else "そのテーマ")

@st.cache_data(ttl=1800, show_spinner=False)
def get_available_gemini_models(api_key):
    """
    Google AI Studio APIキーから、現在有効かつ利用可能なモデル一覧（generateContent対応）を取得
    """
    if not api_key:
        return []
    available = []
    for ver in ["v1beta", "v1"]:
        endpoint = f"https://generativelanguage.googleapis.com/{ver}/models?key={api_key}"
        try:
            req = urllib.request.Request(endpoint, method="GET")
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for m in data.get("models", []):
                    methods = m.get("supportedGenerationMethods", [])
                    if "generateContent" in methods:
                        raw_id = m.get("name", "").replace("models/", "").strip()
                        if raw_id and (ver, raw_id) not in available:
                            available.append((ver, raw_id))
        except Exception:
            continue
    return available

def build_gemini_contents(messages_history, user_input):
    """
    Gemini APIの仕様に100%厳格に準拠したcontents配列を構築する。
    - ロールは 'user' または 'model' のみ
    - 先頭は必ず 'user'
    - 'user' と 'model' が厳格に交互
    - 末尾は必ず最新の 'user' 発言
    """
    raw_turns = []
    for m in messages_history[-10:]:
        role = "user" if m.get("role") == "user" else "model"
        text = m.get("content", "").strip()
        if text:
            raw_turns.append({"role": role, "text": text})

    cleaned_input = (user_input or "").strip()
    if cleaned_input:
        if not raw_turns or raw_turns[-1]["role"] != "user" or raw_turns[-1]["text"] != cleaned_input:
            raw_turns.append({"role": "user", "text": cleaned_input})

    # 先頭が model の場合は取り除く（最初の歓迎挨拶などを除外）
    while raw_turns and raw_turns[0]["role"] != "user":
        raw_turns.pop(0)

    if not raw_turns:
        raw_turns.append({"role": "user", "text": cleaned_input if cleaned_input else "こんにちは"})

    # 同一ロールの連続を結合して交互シーケンスを保証
    merged = []
    for turn in raw_turns:
        if not merged:
            merged.append(turn)
        elif merged[-1]["role"] == turn["role"]:
            merged[-1]["text"] += "\n" + turn["text"]
        else:
            merged.append(turn)

    return [{"role": item["role"], "parts": [{"text": item["text"]}]} for item in merged]

def call_llm_api(api_key, model_name, messages_history, user_input, system_prompt):
    raw_model = model_name.split()[0]
    is_gemini = api_key.startswith("AIza") or "gemini" in raw_model.lower()
    
    # 1. Google Gemini公式ネイティブREST API
    if is_gemini:
        # 動的に利用可能モデルを検出
        dynamic_models = get_available_gemini_models(api_key)
        
        # 試行候補の選定
        trials = []
        clean_selected = raw_model.lower().replace("models/", "").strip()
        
        # 画面選択モデルに合致するものを最優先
        for ver, mid in dynamic_models:
            if clean_selected in mid.lower():
                trials.append((ver, mid))
                
        # flash 系モデルを優先追加
        for ver, mid in dynamic_models:
            if "flash" in mid.lower() and (ver, mid) not in trials:
                trials.append((ver, mid))
                
        # 残りの動的モデルを追加
        for ver, mid in dynamic_models:
            if (ver, mid) not in trials:
                trials.append((ver, mid))
                
        # 動的検出が取得できなかった場合の静的フォールバック
        static_fallbacks = [
            ("v1beta", "gemini-1.5-flash"),
            ("v1beta", "gemini-2.0-flash"),
            ("v1beta", "gemini-1.5-flash-8b"),
            ("v1beta", "gemini-1.5-pro"),
            ("v1", "gemini-1.5-flash"),
            ("v1", "gemini-pro"),
        ]
        for item in static_fallbacks:
            if item not in trials:
                trials.append(item)

        contents = build_gemini_contents(messages_history, user_input)
        
        # ① systemInstruction あり（v1beta標準）
        payload_sys = {
            "contents": contents,
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "generationConfig": {
                "temperature": 0.6,
                "maxOutputTokens": 3072
            }
        }
        # ② systemInstruction 代替（先頭userに埋め込み：v1や一部モデル対応）
        contents_alt = [dict(c) for c in contents]
        if contents_alt:
            orig_text = contents_alt[0]["parts"][0]["text"]
            contents_alt[0] = {
                "role": "user",
                "parts": [{"text": f"【システム指示】\n{system_prompt}\n\n{orig_text}"}]
            }
        payload_alt = {
            "contents": contents_alt,
            "generationConfig": {
                "temperature": 0.6,
                "maxOutputTokens": 3072
            }
        }

        last_err = None
        attempted_info = []

        for ver, mid in trials:
            url = f"https://generativelanguage.googleapis.com/{ver}/models/{mid}:generateContent?key={api_key}"
            
            # systemInstruction ありと代替の順に試行
            for p_load in [payload_sys, payload_alt]:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(p_load).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                try:
                    with urllib.request.urlopen(req, timeout=20) as resp:
                        res_json = json.loads(resp.read().decode("utf-8"))
                        candidates = res_json.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts:
                                reply_text = parts[0].get("text", "").strip()
                                if reply_text:
                                    st.session_state["active_engine_name"] = f"Google Gemini ({mid})"
                                    return reply_text
                except urllib.error.HTTPError as e:
                    last_err = e
                    attempted_info.append(f"{mid}({e.code})")
                    if e.code == 404:
                        break  # このバージョン/モデル名は存在しないので次のモデルへ
                    elif e.code == 400 and p_load is payload_sys:
                        continue  # systemInstruction非対応の可能性があるため代替payloadを試す
                    else:
                        break
                except Exception as e:
                    last_err = e
                    attempted_info.append(f"{mid}(err)")
                    break

        if last_err:
            raise last_err
        raise Exception(f"Geminiからの回答が空でした。(試行: {', '.join(attempted_info[:5])})")

    # 2. Groq Cloud API
    else:
        url = "https://api.groq.com/openai/v1/chat/completions"
        messages_payload = [{"role": "system", "content": system_prompt}]
        for m in messages_history[-10:]:
            messages_payload.append({"role": m["role"], "content": m["content"]})
        if user_input and (not messages_history or messages_history[-1].get("content") != user_input):
            messages_payload.append({"role": "user", "content": user_input})
            
        payload = {
            "model": raw_model,
            "messages": messages_payload,
            "temperature": 0.6,
            "max_tokens": 3072
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            res_json = json.loads(resp.read().decode("utf-8"))
            return res_json["choices"][0]["message"]["content"].strip()

def generate_dialogue_insights(messages, key, model):
    user_msgs = [m["content"] for m in messages if m["role"] == "user"]
    if not user_msgs:
        return "対話データがまだありません。まずは対話を行ってください。"

    summary_system_prompt = """
あなたは高校生の探究学習・自己分析を伴走するメンターです。
これまでの生徒とソクラテスの対話履歴を分析し、生徒が探究ポートフォリオや振り返りシート、小論文のネタとしてそのまま活用できるように、以下のフォーマットで客観的かつ温かい文章で「論点整理と得られた知見」をまとめてください。
子ども扱いのお説教はせず、高校生の思考の深化を的確に言語化してください。

【出力フォーマット】
■ 探究テーマ・出発点
（生徒が最初に抱いていた疑問やモヤモヤの本質）

■ 対話の展開と論点整理
（ソクラテスの問いかけによって、どのような前提が揺さぶられ、どのような視点の転換が起きたか）

■ この対話で得られた知見・深まった思考
（対話を通じて言語化された、生徒自身の価値観、目的意識、または独自の気づき）

■ 次の探究に向けた問い（ネクストアクション）
（この知見をもとに、次に具体的に調べるべきことや、検証すべき実践的な問い）
""".strip()

    # クラウドAPI（Gemini または Groq）がある場合
    if key and ("Groq" in model or "Google" in model or "gemini" in model.lower()):
        conversation_text = ""
        for m in messages:
            sender = "生徒" if m["role"] == "user" else "ソクラテス"
            conversation_text += f"{sender}: {m['content']}\n"

        user_prompt = f"以下の対話履歴を分析し、論点整理と得られた知見を文章にまとめてください：\n\n{conversation_text}"
        try:
            return call_llm_api(key, model, [], user_prompt, summary_system_prompt)
        except Exception:
            pass

    # ローカルLLM（Qwen2.5-0.5B）に対話履歴を投入してニューラルネットワーク自律生成
    try:
        tokenizer, local_model = load_local_model_instance()
        conv_text = ""
        for m in messages:
            sender = "高校生" if m["role"] == "user" else "ソクラテス"
            conv_text += f"{sender}: {m['content']}\n"

        local_prompt = [
            {
                "role": "system",
                "content": (
                    "あなたは高校生の教育メンターです。高校生とソクラテスの対話履歴を読み込み、"
                    "「■ 探究テーマ」「■ 対話の展開」「■ 得られた知見」「■ 次の問い」の4つの項目で、"
                    "対話の内容に即して具体的に文章で整理してください。高校生の言葉に寄り添ってまとめてください。"
                )
            },
            {
                "role": "user",
                "content": f"【対話履歴】\n{conv_text}\n\nこの対話の論点整理と得られた知見を分かりやすく文章にまとめてください。"
            }
        ]
        formatted_input = tokenizer.apply_chat_template(local_prompt, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer([formatted_input], return_tensors="pt")
        outputs = local_model.generate(
            **inputs,
            max_new_tokens=280,
            temperature=0.6,
            do_sample=True,
            repetition_penalty=1.12
        )
        new_tokens = outputs[0][len(inputs.input_ids[0]):]
        insights_res = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
        if insights_res and len(insights_res) > 20:
            return insights_res
    except Exception as e:
        pass

    # 例外時フォールバック
    first_topic = extract_core_topic(user_msgs[0])
    last_topic = extract_core_topic(user_msgs[-1])
    return f"""■ 探究テーマ・出発点
生徒は「{first_topic}」に関する問題意識や素朴な疑問から思考をスタートさせました。

■ 対話の展開と論点整理
対話を通じて、「{first_topic}」についての当たり前の前提や自分自身の立ち位置を問い直しました。言葉の定義を整理し、単なる一般論ではなく自分自身の視点で捉え直す中で、後半は「{last_topic}」というより本質的・具体的な論点へと対話が深まりました。

■ この対話で得られた知見・深まった思考
表面的な答えを求めるのではなく、自らの頭で言語化（外化）することで、「{last_topic}」に真の価値や目的意識があることに気づくことができました。客観的なメタ認知が働き、思考の解像度が一段階向上しています。

■ 次の探究に向けた問い（ネクストアクション）
「{last_topic}」をより確かなものにするために、自分とは異なる立場の人に意見を聞いてみたり、身近な実例を調べてみましょう。自分にとっての『理想の基準』を明確にすることが次のステップです。"""

# ----------------------------------------------------
# 操作ボタン群
# ----------------------------------------------------
col_b1, col_b2, col_b3 = st.columns([1, 1.2, 1.2])
user_turns = len([m for m in st.session_state.messages if m["role"] == "user"])

with col_b1:
    if st.button("🔄 会話をリセットする", use_container_width=True):
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "こんにちは！今日はどんなテーマや悩みについて、一緒に考えを深めていきましょうか？頭の中にあるモヤモヤをそのまま言葉にしてみてくださいね。",
                "timestamp": get_datetime_str_jst()
            }
        ]
        if "just_saved_insights" in st.session_state:
            del st.session_state["just_saved_insights"]
        st.rerun()

with col_b2:
    # 修正①: 保存ボタンを押した「その時」にのみ知見まとめを生成・表示
    if st.button("📌 この対話をカレンダーに保存", use_container_width=True, disabled=(user_turns == 0)):
        today_str = get_today_str_jst()
        if today_str not in st.session_state.daily_logs:
            st.session_state.daily_logs[today_str] = []
        
        spinner_msg = "🧠 PC内ローカルLLM (Qwen2.5) が対話履歴をじっくり読み込み、論点整理と知見を自律生成中...（CPU推論のため約15〜20秒かかります）" if "ローカル" in model_choice else "🧠 GroqクラウドLLMが対話の論点を整理し、得られた知見を文章にまとめています..."
        with st.spinner(spinner_msg):
            insights_summary = generate_dialogue_insights(st.session_state.messages, groq_api_key, model_choice)
            st.session_state.just_saved_insights = insights_summary
            st.session_state.current_insights = insights_summary

            first_user_msg = next((m["content"] for m in st.session_state.messages if m["role"] == "user"), "探究対話")
            summary = extract_core_topic(first_user_msg)
            if len(summary) > 30:
                summary = summary[:30] + "..."
            
            st.session_state.daily_logs[today_str].append({
                "title": summary,
                "turns": user_turns,
                "time": get_time_str_jst(),
                "insights": insights_summary,
                "messages": list(st.session_state.messages)
            })
            st.session_state.streak_days = calculate_streak_days(st.session_state.daily_logs)

with col_b3:
    first_user_msg = next((m["content"] for m in st.session_state.messages if m["role"] == "user"), "対話")
    topic_title = extract_core_topic(first_user_msg)
    
    insights_for_download = st.session_state.get("current_insights", "")
    if not insights_for_download and user_turns > 0:
        insights_for_download = generate_dialogue_insights(st.session_state.messages, groq_api_key, model_choice)
        st.session_state.current_insights = insights_for_download

    download_text = f"============================================================\n"
    download_text += f"ソクラテス・メンター 〜正解を教えない壁打ちチャット〜 対話記録\n"
    download_text += f"============================================================\n"
    download_text += f"実施日時: {get_datetime_str_jst()} (JST)\n"
    download_text += f"探究テーマ（初期発言）: {topic_title}\n"
    download_text += f"対話往復数: {user_turns} 往復\n"
    download_text += f"著作権表示: 2026 Teraoka-Denshi. All rights reserved.\n"
    download_text += f"============================================================\n\n"

    if insights_for_download:
        download_text += f"【AIによる対話の論点整理と得られた知見】\n"
        download_text += f"------------------------------------------------------------\n"
        download_text += f"{insights_for_download}\n"
        download_text += f"------------------------------------------------------------\n\n"

    download_text += f"【対話ログ詳細】\n\n"
    for idx, m in enumerate(st.session_state.messages):
        sender = "あなた（高校生）" if m["role"] == "user" else "ソクラテス・メンター"
        download_text += f"[{idx+1}] {sender} ({m.get('timestamp', '')}):\n{m['content']}\n\n"

    download_text += "============================================================\n"
    download_text += "【自身の振り返り・気づきメモ】\n"
    download_text += "（この対話と知見まとめを通じて、自分の考えがどう深まりましたか？自由に書き留めてください）\n\n"
    download_text += "============================================================\n"
    download_text += "Produced by テラオカ電子の自由探究ゼミ\n"

    st.download_button(
        label="📥 対話記録ダウンロード (.txt)",
        data=download_text,
        file_name=f"socrates_dialogue_{get_now_jst().strftime('%Y%m%d_%H%M')}.txt",
        mime="text/plain",
        use_container_width=True,
        disabled=(user_turns == 0)
    )

# 修正①: 保存直後にのみ画面に知見まとめを表示（通常の対話中は出さない）
if "just_saved_insights" in st.session_state and st.session_state.just_saved_insights:
    st.success(f"対話概要と得られた知見を {get_today_str_jst()} のカレンダーに保存しました！")
    with st.expander("📝 保存された対話の論点整理と得られた知見（クリックで確認）", expanded=True):
        st.markdown(
            f"""
            <div style="background-color: rgba(6, 182, 212, 0.08); border: 1px solid rgba(6, 182, 212, 0.4); border-radius: 0.5rem; padding: 1rem; color: #f1f5f9; font-size: 0.85rem; line-height: 1.6; white-space: pre-wrap;">
{st.session_state.just_saved_insights}
            </div>
            """,
            unsafe_allow_html=True
        )

# ----------------------------------------------------
# 音声入力（Speech-to-Text）コンポーネント (修正②: 「テキストを入力欄に転送」ボタン)
# ----------------------------------------------------
with st.expander("🎙️ 音声入力（マイクで話して壁打ちする）", expanded=False):
    st.markdown(
        """
        <div style="font-size: 0.8rem; color: #94a3b8; margin-bottom: 0.5rem;">
            マイクに向かって話した言葉が自動で日本語に変換されます。「🚀 テキストを入力欄に転送」を押すと、下のチャット入力欄に自動転送されます。
        </div>
        """,
        unsafe_allow_html=True
    )
    speech_html = """
    <div style="background-color: #0c1220; border: 1px solid #1e293b; border-radius: 0.75rem; padding: 1rem; color: #f8fafc; font-family: sans-serif; box-sizing: border-box;">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.6rem;">
            <button id="record-btn" onclick="toggleSpeech()" style="background: linear-gradient(135deg, #06b6d4, #2563eb); border: none; border-radius: 0.5rem; padding: 0.55rem 1.1rem; color: #fff; font-weight: bold; font-size: 0.85rem; cursor: pointer; display: flex; align-items: center; gap: 0.5rem; box-shadow: 0 4px 12px rgba(6, 182, 212, 0.25);">
                <span id="mic-icon">🎙️</span> <span id="record-text">音声入力を開始（マイクON）</span>
            </button>
            <span id="speech-status" style="font-size: 0.75rem; color: #94a3b8; font-weight: 500;">待機中</span>
        </div>
        <textarea id="recognized-text" rows="2" style="width: 100%; box-sizing: border-box; background-color: #090d16; border: 1px solid #334155; border-radius: 0.5rem; padding: 0.6rem; color: #fff; font-size: 0.85rem; resize: none; margin-bottom: 0.6rem;" placeholder="ここに話した内容がリアルタイムに文字起こしされます..."></textarea>
        <div style="display: flex; justify-content: flex-end; align-items: center; gap: 0.5rem;">
            <span id="copy-hint" style="font-size: 0.75rem; color: #10b981; display: none; font-weight: bold;"></span>
            <button onclick="transferTextToInput()" style="background: linear-gradient(135deg, #0891b2, #0284c7); border: 1px solid #38bdf8; border-radius: 0.4rem; padding: 0.5rem 1.2rem; color: #fff; font-size: 0.82rem; font-weight: bold; cursor: pointer; box-shadow: 0 2px 8px rgba(6, 182, 212, 0.3);">
                🚀 テキストを入力欄に転送
            </button>
        </div>
    </div>
    <script>
    let recognition = null;
    let isRecording = false;

    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
        const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
        recognition = new SpeechRec();
        recognition.lang = 'ja-JP';
        recognition.continuous = true;
        recognition.interimResults = true;

        recognition.onstart = function() {
            isRecording = true;
            document.getElementById('record-btn').style.background = '#dc2626';
            document.getElementById('record-text').textContent = '音声入力を停止（マイクOFF）';
            document.getElementById('speech-status').textContent = '🔴 お話しください（聞き取り中...）';
            document.getElementById('speech-status').style.color = '#f87171';
        };

        recognition.onresult = function(event) {
            let finalTranscript = '';
            for (let i = 0; i < event.results.length; ++i) {
                finalTranscript += event.results[i][0].transcript;
            }
            document.getElementById('recognized-text').value = finalTranscript;
        };

        recognition.onerror = function(event) {
            console.error('Speech error:', event.error);
            document.getElementById('speech-status').textContent = 'エラー: ' + event.error;
            stopSpeech();
        };

        recognition.onend = function() {
            stopSpeech();
        };
    } else {
        document.getElementById('speech-status').textContent = 'お使いのブラウザは音声認識に対応していません（Chrome/Edge推奨）';
    }

    function toggleSpeech() {
        if (!recognition) return;
        if (!isRecording) {
            try { recognition.start(); } catch(e) {}
        } else {
            recognition.stop();
        }
    }

    function stopSpeech() {
        isRecording = false;
        document.getElementById('record-btn').style.background = 'linear-gradient(135deg, #06b6d4, #2563eb)';
        document.getElementById('record-text').textContent = '音声入力を開始（マイクON）';
        document.getElementById('speech-status').textContent = '停止中';
        document.getElementById('speech-status').style.color = '#94a3b8';
    }

    function transferTextToInput() {
        const text = document.getElementById('recognized-text').value.trim();
        const hint = document.getElementById('copy-hint');
        if (!text) {
            alert('音声がまだ認識されていません。マイクで話してから転送してください。');
            return;
        }

        try {
            // 親ウィンドウ（Streamlit）のチャット入力テキストエリアを取得
            const parentDoc = window.parent.document;
            const textarea = parentDoc.querySelector('textarea');
            if (textarea) {
                // Reactのvalue setterを呼び出して確実にStreamlit Stateに反映
                const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value").set;
                nativeSetter.call(textarea, text);
                textarea.dispatchEvent(new Event('input', { bubbles: true }));
                textarea.dispatchEvent(new Event('change', { bubbles: true }));
                textarea.focus();

                hint.textContent = '✅ 入力欄に転送しました！';
                hint.style.display = 'inline';
                setTimeout(() => { hint.style.display = 'none'; }, 3000);
            } else {
                fallbackCopy(text);
            }
        } catch (e) {
            console.error(e);
            fallbackCopy(text);
        }
    }

    function fallbackCopy(text) {
        const textarea = document.getElementById('recognized-text');
        textarea.select();
        document.execCommand('copy');
        const hint = document.getElementById('copy-hint');
        hint.textContent = '📋 コピーしました！入力欄に貼り付けてください';
        hint.style.display = 'inline';
        setTimeout(() => { hint.style.display = 'none'; }, 4000);
    }
    </script>
    """
    components.html(speech_html, height=185)

st.markdown("<hr style='border: none; border-top: 1px solid #1e293b; margin: 1rem 0 1.5rem 0;'>", unsafe_allow_html=True)

# ----------------------------------------------------
# メイン画面：タブ構成
# ----------------------------------------------------
tab_chat, tab_calendar, tab_llm, tab_dialogue, tab_privacy = st.tabs([
    "💬 壁打ちチャット",
    "📅 探究カレンダー＆継続記録",
    "🔬 LLMのアルゴリズム解説",
    "💡 対話による思考深化の効用",
    "🛡️ セキュリティ・プライバシーと注意事項"
])

# ====================================================
# タブ 1: チャット画面（新しい入力文章が上に積み上がる仕様）
# ====================================================
with tab_chat:
    is_local_model = "ローカルLLM" in model_choice
    if is_local_model:
        status_color = "#10b981"
        status_icon = "🖥️"
        status_label = "ローカルLLM実機稼働中 (Qwen2.5-0.5B - API不要・PC内で推論)"
    elif groq_api_key:
        status_color = "#22d3ee"
        status_icon = "🟢"
        active_label = st.session_state.get("active_engine_name")
        if active_label:
            status_label = f"{active_label} 稼働中"
        else:
            provider_tag = "Google Gemini" if "gemini" in model_choice.lower() else "Groq"
            status_label = f"{provider_tag} クラウドLLM 接続中 ({model_choice.split()[0]})"
    else:
        status_color = "#f59e0b"
        status_icon = "🟡"
        status_label = "内蔵ソクラテス思考エンジン動作中（APIキーを入力またはローカルLLM選択で稼働）"

    st.markdown(
        f"""
        <div style="display: flex; align-items: center; justify-content: space-between; font-size: 0.75rem; color: #94a3b8; background-color: rgba(15, 23, 42, 0.6); padding: 0.6rem 1rem; border-radius: 0.75rem; border: 1px solid #1e293b; margin-bottom: 1rem;">
            <span style="display: flex; align-items: center; gap: 0.5rem;">
                <span>{status_icon}</span>
                <span style="color: {status_color}; font-weight: 500;">{status_label}</span>
                <span style="color: #475569;">|</span>
                <span>対話ラリー: <strong style="color: #67e8f9;">{user_turns}</strong> 往復</span>
            </span>
            <span style="color: #38bdf8; font-weight: 500;">⬆️ 新しい会話が上に積み上がります</span>
        </div>
        """,
        unsafe_allow_html=True
    )

    if st.session_state.get("last_api_error"):
        st.error(f"⚠️ {st.session_state.last_api_error}")

    # ----------------------------------------------------
    # 入力フォームを「最上部」に配置
    # ----------------------------------------------------
    with st.container():
        with st.form(key="chat_input_top_form", clear_on_submit=True):
            user_input_text = st.text_area(
                "💭 あなたの考え・悩み・モヤモヤを入力してください（最新の対話がすぐ下に積み上がります）：",
                placeholder="例: 将来についてのスキルにしたいと考えています / プログラム作成の目的は何だと思いますか？\n⚠️【個人情報保護のお願い】本名や学校名、住所などの個人情報は入力しないでください。",
                height=85
            )
            col_send1, col_send2 = st.columns([1, 5], vertical_alignment="center")
            with col_send1:
                submit_button = st.form_submit_button("送信する 🚀", use_container_width=True)
            with col_send2:
                st.caption("🔒 **安全な利用のために:** 氏名・学校名等の個人情報は入力しないでください。対話はAI推論のため暗号化送信されます。")

    # 送信時の処理
    if submit_button and user_input_text.strip():
        # 送信時は以前の保存知見バナーをクリア（修正①）
        if "just_saved_insights" in st.session_state:
            del st.session_state["just_saved_insights"]

        prompt = user_input_text.strip()
        
        st.session_state.messages.append({
            "role": "user",
            "content": prompt,
            "timestamp": get_datetime_str_jst()
        })

        # 寄り添い型ソクラテス応答生成
        def generate_empathetic_fallback_response(user_text, mode):
            core_topic = extract_core_topic(user_text)

            if "前提" in mode:
                return f"なるほど、「{core_topic}」について深く考えているのですね。あなたがそう捉えるようになった背景には、どのような実体験や出来事があったのでしょうか？"
            elif "視点" in mode:
                return f"「{core_topic}」という視点、とても重要ですね。もしこの件について、立場が全く異なる人や別の世代の人が見たら、どのように映ると思いますか？"
            elif "根拠" in mode:
                return f"「{core_topic}」と感じるに至った理由について、もう少し詳しく聞かせてください。あなたがそう確信する一番の決め手は何ですか？"
            elif "未来" in mode:
                return f"もしその「{core_topic}」についてのあなたの思いが実現したとしたら、その先の未来であなた自身や周囲はどう変化していると思いますか？"
            else:
                templates = [
                    f"「{core_topic}」について真剣に向き合っているのですね、素晴らしい着眼点です。あなたが考える「{core_topic}」において、最も大切にしたい理想の状態とはどのようなものですか？",
                    f"なるほど。「{core_topic}」とおっしゃいましたが、その想いの奥にある、あなた自身の本当の動機やこだわりはどこにありますか？",
                    f"「{core_topic}」という言葉に込められた想いが伝わってきます。その中で、今あなたが一番『もっと突き詰めたい』あるいは『解決したい』と感じている核心部分は何ですか？",
                    f"お話を聞いて、「{core_topic}」についてのあなたの問題意識の深さを感じます。誰のためでもなく、あなた自身の本音としては、今後どうしていきたいと感じていますか？"
                ]
                import random
                return random.choice(templates)

        def get_socrates_response(user_input, key, model, mode):
            # 1. ローカルLLM実機推論モード (修正③: Qwen2.5-0.5Bをローカル実行)
            if "ローカルLLM" in model:
                try:
                    return generate_local_model_response(user_input, st.session_state.messages, mode)
                except Exception as e:
                    st.warning(f"ローカルモデル推論中にエラーが発生したため、内蔵エンジンに切り替えました: {e}")
                    return generate_empathetic_fallback_response(user_input, mode)

            # 2. クラウドAPI（Google Gemini または Groq）実行モード
            if "Groq" in model or "Google" in model or "gemini" in model.lower():
                if not key:
                    st.warning("⚠️ APIキーが未設定です。画面上の「🔑 API Key」欄にGeminiキー（AIza...）を入力するか、Streamlit CloudのSecretsをご確認ください。")
                    return generate_empathetic_fallback_response(user_input, mode)

                raw_model = model.split()[0]
                mode_map = {
                    "前提の確認（当たり前や定義を疑う）": "特にユーザーの発言の背景にある『前提や当たり前の定義』に寄り添い、優しく疑い直す問いを投げなさい。",
                    "視点の転換（他者の立場・逆から見る）": "特に『異なる立場の人（反対派、当事者、未来の人）』から見た視点の転換を促す問いを投げなさい。",
                    "根拠の提示（なぜそう言えるのかを突く）": "特に『そう考えるに至った具体的な原体験や根拠』を丁寧に掘り下げる問いを投げなさい。",
                    "未来の予測（もしそれが起きたらどうなるか）": "特に『もしそれが現実になったときの未来の波及効果や副作用』を想像させる問いを投げなさい。",
                    "総合（共感と寄り添い深掘り）": "相手の気持ちや問題意識を温かく受け止め、最も探究を深められる核心的な問いを投げなさい。"
                }
                extra_instruction = mode_map.get(mode, "")

                system_prompt = f"""
あなたは高校生のための「ソクラテス・メンター」です。
目的は、生徒が探究学習、進路、身近な悩みについて、自らの頭で思考を深め、言葉を研ぎ澄まし、メタ認知を獲得できるように温かく寄り添いながら支援することです。

【対話の鉄則：徹底した寄り添いと傾聴】
1. 相手の発言をまずしっかりと受け止めること：
   冷たく突き放すような質問ではなく、相手の悩みや発言内容を尊重し、「〜〜について考えているのですね」「〜〜という視点ですね」と、相手の言葉や気持ちを丁寧に受け止めなさい。
2. 相手が使った具体的な言葉（キーワード）を必ず拾い上げること：
   「と考えています」のような文末ではなく、生徒が口にした具体的な名詞・テーマ（例: 将来のスキル、プログラミングの目的）を正確に引用しなさい。
3. 答えは教えず、思考を一段深める「1つの問い」で返すこと：
   知識の講釈やアドバイスを一方的に教えるのではなく、生徒自身が「なるほど！」と自ら気づけるような、核心を突く優しい問いかけを1つだけ投げなさい。
4. 高校生への敬意と温かみ：
   子ども扱いのお説教や尋問をせず、対等で知的な対話相手として、親しみやすく論理的な日本語で接しなさい。
5. 出力の完結性：
   文章は途中で絶対に途切れることなく、まとまりのある完結した日本語の文章（末尾は「？」）で終話すること。
{extra_instruction}
""".strip()

                try:
                    res = call_llm_api(key, model, st.session_state.messages, user_input, system_prompt)
                    st.session_state.last_api_error = ""
                    return res
                except urllib.error.HTTPError as e:
                    err_msg = e.read().decode("utf-8", errors="ignore")
                    if e.code in [400, 401, 403]:
                        st.session_state.last_api_error = f"APIキー認証エラー ({e.code}): キーが無効か権限がありません。Google AI Studioでキーをご確認ください。\n詳細: {err_msg[:200]}"
                    elif e.code == 429:
                        st.session_state.last_api_error = "レート制限エラー (429): APIの利用頻度制限に達しました。1分ほど待ってからお試しください。"
                    else:
                        st.session_state.last_api_error = f"APIエラー ({e.code}): {err_msg[:200]}"
                    return generate_empathetic_fallback_response(user_input, mode)
                except Exception as e:
                    st.session_state.last_api_error = f"通信エラー: {str(e)}"
                    return generate_empathetic_fallback_response(user_input, mode)

            # 3. 内蔵寄り添いエンジン（ローカルLLM以外のフォールバック）
            return generate_empathetic_fallback_response(user_input, mode)

        with st.spinner("ソクラテスがあなたの言葉に耳を傾けています..."):
            reply = get_socrates_response(prompt, groq_api_key, model_choice, socratic_mode)
            st.session_state.messages.append({
                "role": "assistant",
                "content": reply,
                "timestamp": get_datetime_str_jst()
            })
            st.rerun()

    # ----------------------------------------------------
    # メッセージ履歴表示（新しい発言が上に積み上がる逆順表示）
    # ----------------------------------------------------
    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)
    
    reversed_messages = list(reversed(st.session_state.messages))
    
    for idx, message in enumerate(reversed_messages):
        with st.chat_message(message["role"], avatar="💡" if message["role"] == "assistant" else "👤"):
            time_label = f"<span style='font-size: 0.65rem; color: #64748b; margin-left: 0.5rem;'>({message.get('timestamp', '')})</span>"
            role_label = "ソクラテス・メンター" if message["role"] == "assistant" else "あなた（高校生）"
            st.markdown(f"**{role_label}** {time_label}", unsafe_allow_html=True)
            st.markdown(message["content"])

# ====================================================
# タブ 2: カレンダー＆継続記録 (条件➂)
# ====================================================
with tab_calendar:
    st.markdown("### 📅 探究カレンダー＆学習継続の記録")
    
    # ストリーク日数を最新の記録ログから自動再計算
    st.session_state.streak_days = calculate_streak_days(st.session_state.daily_logs)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(label="🔥 連続壁打ち日数", value=f"{st.session_state.streak_days} 日間")
    with col2:
        saved_dates_count = len(st.session_state.daily_logs.keys())
        st.metric(label="📆 記録された思考日数", value=f"{saved_dates_count} 日")
    with col3:
        total_sessions = sum(len(items) for items in st.session_state.daily_logs.values())
        st.metric(label="💬 累計保存セッション", value=f"{total_sessions} 回")
    with col4:
        rank_name = "Lv.1 問いの芽生え"
        if total_sessions >= 10: rank_name = "Lv.4 メタ認知の達人"
        elif total_sessions >= 5: rank_name = "Lv.3 ロジックの探究者"
        elif total_sessions >= 2: rank_name = "Lv.2 前提の破壊者"
        st.metric(label="🏆 探究者ランク", value=rank_name)

    # ----------------------------------------------------
    # 探究ポートフォリオのファイル保存・バックアップ＆完全復元エリア
    # ----------------------------------------------------
    st.markdown(
        """
        <div style="background-color: rgba(15, 23, 42, 0.7); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 0.75rem; padding: 0.85rem 1.2rem; margin: 1rem 0;">
            <div style="display: flex; align-items: center; justify-content: space-between;">
                <div>
                    <strong style="color: #38bdf8; font-size: 0.95rem;">💾 探究データの保存と次回への引き継ぎ（完全再現）</strong>
                    <p style="font-size: 0.75rem; color: #94a3b8; margin: 0.2rem 0 0 0;">
                        Streamlitはブラウザを閉じると初期化されますが、以下の機能を使うことで<strong>次にアクセスした際も前回の全カレンダー記録と知見を100%復元</strong>できます。
                    </p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    port_col1, port_col2 = st.columns([1, 1])

    with port_col1:
        export_bundle = {
            "app": "socrates-mentor",
            "version": "2.0",
            "export_time": get_datetime_str_jst(),
            "streak_days": st.session_state.streak_days,
            "daily_logs": st.session_state.daily_logs
        }
        export_json_str = json.dumps(export_bundle, ensure_ascii=False, indent=2)
        st.download_button(
            label="📥 探究ポートフォリオをファイル保存 (.json)",
            data=export_json_str,
            file_name=f"socrates_portfolio_{get_now_jst().strftime('%Y%m%d_%H%M')}.json",
            mime="application/json",
            use_container_width=True,
            help="カレンダー記録・知見まとめ・ストリークを含む全データをJSONファイルとして手元のPC/スマホに保存します。"
        )

    with port_col2:
        uploaded_portfolio = st.file_uploader(
            "📂 保存した探究ファイル (.json) を読み込んで復元",
            type=["json"],
            label_visibility="collapsed",
            help="以前保存した探究ポートフォリオ（.json）を選択すると、一瞬で前回のカレンダーと全知見が復元されます。"
        )
        if uploaded_portfolio is not None:
            try:
                loaded_bundle = json.loads(uploaded_portfolio.read().decode("utf-8"))
                if "daily_logs" in loaded_bundle:
                    st.session_state.daily_logs = loaded_bundle["daily_logs"]
                    st.session_state.streak_days = calculate_streak_days(st.session_state.daily_logs)
                    st.success(f"✅ 過去の探究記録（{len(st.session_state.daily_logs)}日分）を完全に復元しました！")
                    st.rerun()
                else:
                    st.error("⚠️ 探究ポートフォリオの形式が正しくありません。")
            except Exception as e:
                st.error(f"⚠️ ファイルの読み込みに失敗しました: {e}")

    st.markdown("<hr style='border: none; border-top: 1px solid #1e293b; margin: 1rem 0;'>", unsafe_allow_html=True)

    cal_col1, cal_col2 = st.columns([1, 1])

    with cal_col1:
        selected_date = st.date_input("確認する日付を選択 (日本時間)", value=get_today_jst())
        selected_date_str = selected_date.isoformat()

        st.markdown(f"#### 📝 {selected_date_str} の探究ログ一覧")
        logs_today = st.session_state.daily_logs.get(selected_date_str, [])
        if not logs_today:
            st.info("この日の記録はまだありません。チャットを行って「カレンダーに保存」を押すとここに記録されます。")
        else:
            for idx, item in enumerate(logs_today):
                with st.expander(f"📌 {item.get('time', '')} - {item.get('title', '探究対話')} ({item.get('turns', 0)}往復)"):
                    st.write(f"**記録時刻 (JST):** {item.get('time')}")
                    st.write(f"**ラリー往復数:** {item.get('turns')} 回")
                    if "insights" in item and item["insights"]:
                        st.markdown("##### 📝 対話の論点整理と得られた知見")
                        st.info(item["insights"])
                    if st.button("この対話をチャットに復元", key=f"restore_{selected_date_str}_{idx}"):
                        st.session_state.messages = list(item.get("messages", []))
                        if "insights" in item:
                            st.session_state.current_insights = item["insights"]
                        st.success("チャット画面に対話を復元しました。「壁打ちチャット」タブを開いてください。")

    with cal_col2:
        st.markdown("#### ✍️ 今日の探究振り返りメモの手動追加")
        note_title = st.text_input("探究テーマ・気づきのタイトル", placeholder="例: 地方衰退の根本的な原因について")
        note_body = st.text_area("気づき・思考の変化の要約", placeholder="ソクラテスと対話して自分の思い込みに気づいた点...", height=120)
        if st.button("メモを保存する"):
            if note_title:
                if selected_date_str not in st.session_state.daily_logs:
                    st.session_state.daily_logs[selected_date_str] = []
                st.session_state.daily_logs[selected_date_str].append({
                    "title": note_title,
                    "turns": 1,
                    "time": get_time_str_jst(),
                    "messages": [{"role": "assistant", "content": f"【振り返りメモ】\n{note_body}"}]
                })
                st.session_state.streak_days = calculate_streak_days(st.session_state.daily_logs)
                st.success("振り返りメモをカレンダーに保存しました！")
                st.rerun()
            else:
                st.warning("タイトルを入力してください。")

# ====================================================
# タブ 3: LLMのアルゴリズム解説 (条件① & ➁)
# ====================================================
with tab_llm:
    st.markdown("### 🔬 大規模言語モデル（LLM）の構造とそのアルゴリズム")
    st.caption("高校生のための情報科学：次トークン予測の数理とTransformer機構の全貌")

    st.markdown(
        """
        #### 1. LLMの本質：「超高精度の次単語予測機」
        LLM（Large Language Model）は、コンピュータサイエンスにおける「言語モデル」の究極形です。
        ユーザーが入力したプロンプトに対し、モデルは自律的な意志で喋っているのではなく、
        **「これまでの文脈に照らし合わせて、統計的に次に来る確率が最も高いトークン（単語・文字の断片）は何か」**
        を数式に基づいて連続的に計算し続けています。

        #### 2. Transformerアーキテクチャの革新
        2017年のGoogle論文「Attention Is All You Need」により登場したTransformerは、以下の革新によりLLMの爆発的進化を牽引しました：
        - **Self-Attention（自己注意機構）**: 文中のすべての単語同士の関連度（注意スコア）を行列計算（Scaled Dot-Product Attention）で一括算出します。文脈が数千単語離れていても、代名詞が何を指しているかを正確に捉えます。
        - **並列処理の実現**: 過去のRNNのように一文字ずつ直列処理する必要がなくなり、数千台のGPUを用いた超並列学習が可能になりました。
        - **高次元ベクトル空間（Embedding）**: 単語を数千次元の空間内の幾何学的ベクトルとして配置し、意味的な類似度をコサイン類似度で計算します。

        #### 3. モデルができるまでの3段階学習プロセス
        1. **事前学習（Pre-training）**: インターネット上の数兆トークンの巨大テキストから次単語を当てる膨大な自己教師あり学習。言語の構造や世界の知識をパラメータに蓄積します。
        2. **指示微調整（SFT: Supervised Fine-Tuning）**: 「質問」と「回答」のペアを与え、対話形式で適切に振る舞うよう調教します。
        3. **強化学習（RLHF / DPO）**: 人間の評価者の採点に基づき、安全で論理的な応答を出力するよう報酬モデルで最適化します。

        #### 4. 本アプリのソクラテス制約とトークン切れ防止
        本アプリでは、通常「親切に回答する」よう調教されたLLMに対し、システムプロンプトによって
        **「相手の言葉を温かく受け止めること」「直接的な答えの禁止」「1つの鋭い問いかけ」**を厳格に指示しています。
        また、文章が途中で不自然に途切れないよう、**3,000トークン以上の十分な生成トークン数（max_tokens）**を確保しています。
        """
    )

# ====================================================
# タブ 4: 対話による思考深化の効用 (条件➁)
# ====================================================
with tab_dialogue:
    st.markdown("### 💡 「壁打ち対話」によって思考が深まるメカニズムと効用")
    st.caption("認知心理学と構成主義学習理論：なぜ正解を教えてもらわない方が思考力が伸びるのか？")

    st.markdown(
        """
        #### なぜ正解を教えられると「思考停止」するのか？
        人間の脳は進化の過程で、エネルギーを節約する傾向（**認知の怠惰：Cognitive Miser**）を持っています。
        AIからわかりやすい「正解」や「解決策」をポンと与えられると、脳は「わかった気」になり、自力で深く探る探究回路を閉じてしまいます。

        #### 壁打ち対話がもたらす3つの認知的効果
        1. **外化（Externalization）**: 頭の中の曖昧な思考を文字にして画面に打ち出すことで、客観的な分析対象に変換されます。
        2. **メタ認知（Metacognition）の活性化**: 「なぜそう言えるのか？」「前提は何か？」と問われることで、自分自身の思考プロセスを一段高い視点から見下ろし、論理の飛躍に自ら気づきます。
        3. **概念の再構成（産婆術）**: 古代ギリシャの哲学者ソクラテスが実践したように、真の洞察は他者から与えられるものではなく、対話を通じて自分自身の内側から生まれ落ちるものです。

        ---
        #### 【具体的事例】高校生の日常における壁打ちの劇的変化
        
        - **事例 1：総合的な探究の時間のテーマ設定**
          - *生徒:* 「プラスチックごみを減らすためにポスターを作って啓発したい」
          - *ソクラテス:* 「ポスターを見るだけで人が行動を変えるなら、なぜ今もゴミは減らないのだと思う？生活者が分別をしない本当の理由は何だろう？」
          - *生徒の深化:* 「意識の問題ではなく、ゴミ箱の配置や回収インフラの不便さが原因かもしれない。地域の動線調査をテーマにしよう！」
        
        - **事例 2：総合型選抜・推薦入試の志望理由書**
          - *生徒:* 「人の役に立ちたいので看護師になりたいです」
          - *ソクラテス:* 「人を助ける仕事が無数にある中で、あなたが医師ではなく、特に『看護』という距離感にこだわる原体験は何ですか？」
          - *生徒の深化:* 「祖母が入院したとき、技術以上に日々の不安を聞いてくれた看護師さんに救われた。自分は心に寄り添うケアを学びたいのだ」
        
        - **事例 3：プログラミングのエラー解決（ラバーダック効果）**
          - *生徒:* 「コードが思った通りに動かない。原因がわからない」
          - *ソクラテス:* 「その関数を実行するとき、コンピュータは一行ずつどのような順序で何を処理していると想定していますか？」
          - *生徒の深化:* 「あ！ループの中で変数が毎回初期化されてしまっていた！」
        """
    )

# ====================================================
# タブ 5: セキュリティ・プライバシーと注意事項
# ====================================================
with tab_privacy:
    st.markdown("### 🛡️ セキュリティ設計と探究学習における注意事項")
    st.caption("生徒の個人情報保護、データ送信の仕組み、および教育現場での安心な利用ガイドライン")

    st.markdown(
        """
        <div style="background-color: rgba(14, 165, 233, 0.1); border: 1px solid rgba(14, 165, 233, 0.3); border-radius: 0.75rem; padding: 1rem; margin-bottom: 1.5rem;">
            <h4 style="color: #38bdf8; margin: 0 0 0.5rem 0; font-size: 1.05rem;">💡 本アプリのセキュリティ設計思想</h4>
            <p style="color: #cbd5e1; font-size: 0.85rem; line-height: 1.6; margin: 0;">
                本アプリは、<strong>「クラウドAIの高い思考力」</strong>と<strong>「ローカル環境の安全性」</strong>を用途に応じて柔軟に選択できるハイブリッド構造を採用しています。<br>
                独自のデータベースを持たないステートレス設計により、生徒の対話データが外部サーバーに蓄積・漏洩するリスクを根本から遮断しています。
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    col_sec1, col_sec2 = st.columns(2)

    with col_sec1:
        st.markdown(
            """
            #### 🌐 1. クラウドLLM利用時（Gemini / Groq）
            *現在の標準推奨モードです*

            - **🔒 APIキーの完全秘匿化:**  
              教員や管理者が設定したAPIキーは、Streamlit Cloudの暗号化領域（Secrets）で安全に隔離・保管されています。生徒側のブラウザや画面ソースコードにキーが漏洩することは絶対にありません。
            - **🗑️ ステートレス（DB非保持）設計:**  
              独自の保存サーバーや中継データベースを一切持っていません。会話ログは生徒のブラウザ上の一時メモリにのみ保持され、ブラウザを閉じるか「会話をリセット」を押せば**完全に消去**されます。
            - **⚠️ 【重要】個人情報の非入力（教育的指導事項）:**  
              AI推論のために暗号化通信（HTTPS）でGoogle等のサーバーへテキストが送信されます。無料枠APIの特性上、**生徒の氏名、学校名、住所、電話番号、友人の個人名などの個人情報は入力させず**、探究テーマや概念的な悩みのみを入力するようご指導ください。
            """
        )

    with col_sec2:
        st.markdown(
            """
            #### 🖥️ 2. ローカルLLM利用時（Qwen2.5-0.5B）
            *真の「完全ローカル・セキュア仕様」*

            - **🛡️ 外部通信 0%（完全遮断）:**  
              インターネットへの外部送信を一切行いません。端末（パソコン）のCPUとメモリ上だけで直接ニューラルネットワーク計算（推論）を実行します。
            - **📶 オフライン環境でも完全動作:**  
              ネット回線が切断された状態でも動作し、入力したテキストは1文字たりとも端末の外に出ません。
            - **🏫 厳格なセキュリティポリシーへの適合:**  
              教育委員会や学校のネットワーク制限により「外部クラウドAIとの通信が禁止」されている現場でも、安全にご活用いただけます。
            """
        )

    st.markdown("---")

    st.markdown(
        """
        #### 📋 高校生のための「生成AI×探究学習」利用の約束（3つのルール）

        1. **「個人情報」や「秘密」は書かない**
           - 自分や友達の名前、学校名、住んでいる場所などの個人情報は絶対に書かないようにしましょう。
        2. **「答え」を求めるのではなく「自分の考えを深める鏡」として使う**
           - ソクラテス・メンターは正解を教えてくれません。「問いかけ」に対して自分の頭で考え、自分の言葉で打ち返すことで思考力（メタ認知）が鍛えられます。
        3. **共有端末（学校のChromebookやPC）では使用後にリセット**
           - 学校のパソコンを利用する際は、シークレットウィンドウを使うか、終了時に「🔄 会話をリセットする」を押してからブラウザを閉じましょう。
        """
    )

# ----------------------------------------------------
# フッター (条件⑥)
# ----------------------------------------------------
st.markdown(
    """
    <div class="app-footer">
        <p style="color: #94a3b8; font-weight: 600; margin-bottom: 0.25rem;">ソクラテス・メンター 〜正解を教えない壁打ちチャット〜</p>
        <p style="font-size: 0.75rem; color: #64748b; margin-bottom: 0.5rem;">高校生探究学習・思考深化支援プラットフォーム ｜ ハイブリッド対応（クラウド推論 / 完全ローカル推論）</p>
        <p style="font-size: 0.75rem; color: #94a3b8;">2026 Teraoka-Denshi. All rights reserved.</p>
    </div>
    """,
    unsafe_allow_html=True
)
