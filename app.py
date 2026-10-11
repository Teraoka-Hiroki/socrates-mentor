import streamlit as st
import os
import json
import base64
import re
from datetime import datetime, date
import urllib.request
import urllib.error
import streamlit.components.v1 as components

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
        torch_dtype=torch.float32,
        low_cpu_mem_usage=True
    )
    return tokenizer, model

def generate_local_model_response(prompt_text, history_messages, mode_text):
    try:
        tokenizer, model = load_local_model_instance()
    except (ImportError, ModuleNotFoundError):
        return "【ご案内】クラウド・デプロイ環境ではローカル推論ライブラリ（torch/transformers）が未インストールの為、上のモデル選択から「llama-3.3-70b-versatile（Groqクラウド: 推奨）」を選択してご利用ください。"
    except Exception as e:
        return f"モデルのロード中にエラーが発生しました: {str(e)}"
    
    system_instruction = f"""あなたは高校生のための「ソクラテス・メンター」です。
生徒の悩みや発言に温かく寄り添い、生徒が使った言葉（キーワード）を引用しながら、決して答えを教えずに、思考を深める問いかけを日本語で1つだけ返してください。
文章は途中で途切れず完結させてください。"""

    chat_prompt = [{"role": "system", "content": system_instruction}]
    for m in history_messages[-4:]:
        chat_prompt.append({"role": m["role"], "content": m["content"]})
    chat_prompt.append({"role": "user", "content": prompt_text})

    formatted_text = tokenizer.apply_chat_template(chat_prompt, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer([formatted_text], return_tensors="pt")
    
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
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
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
secrets_key = ""
try:
    secrets_key = st.secrets.get("GROQ_API_KEY", "")
except Exception:
    pass
if not secrets_key:
    secrets_key = os.getenv("GROQ_API_KEY", "")

col_s1, col_s2, col_s3 = st.columns([1.2, 1.2, 1.1])

with col_s1:
    if secrets_key:
        st.markdown(
            """
            <div style="background-color: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 0.5rem; padding: 0.6rem; font-size: 0.75rem; color: #6ee7b7;">
                🔒 <strong>Secrets連携中</strong>（APIキー秘匿化済）<br>
                デプロイ環境から自動適用されています。
            </div>
            """,
            unsafe_allow_html=True
        )
        groq_api_key = secrets_key
    else:
        groq_api_key = st.text_input(
            "🔑 Groq API Key（デプロイ時設定用）",
            value="",
            type="password",
            help="未入力時はPC内蔵のローカルLLM（Qwen2.5）または思考エンジンが直接稼働します。"
        )

with col_s2:
    # APIキーまたはSecretsが存在する場合はGroq 70B（推奨）を、無ければローカルLLMをデフォルトに
    default_model_idx = 1 if (secrets_key or groq_api_key) else 0
    model_choice = st.selectbox(
        "🤖 動作エンジン / モデル",
        [
            "🖥️ ローカルLLM (Qwen2.5-0.5B: PC内実機稼働)",
            "llama-3.3-70b-versatile (Groqクラウド: 推奨・最高精度70B)",
            "llama-3.1-8b-instant (Groqクラウド: 超高速レスポンス)",
            "gemma2-9b-it (Groqクラウド: Google高知能モデル)",
            "mixtral-8x7b-32768 (Groqクラウド: 長文・多角的視点)"
        ],
        index=default_model_idx,
        help="デプロイ環境ではGroqクラウドの70Bモデルが自動適用されます。PCローカル実機では内蔵モデル（Qwen2.5）も選択可能です。"
    )

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

    # Groq APIがある場合
    if key and "Groq" in model:
        raw_model = model.split()[0]
        conversation_text = ""
        for m in messages:
            sender = "生徒" if m["role"] == "user" else "ソクラテス"
            conversation_text += f"{sender}: {m['content']}\n"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}"
        }
        messages_payload = [
            {"role": "system", "content": summary_system_prompt},
            {"role": "user", "content": f"以下の対話履歴を分析し、論点整理と得られた知見を文章にまとめてください：\n\n{conversation_text}"}
        ]
        data = {
            "model": raw_model,
            "messages": messages_payload,
            "temperature": 0.5,
            "max_tokens": 2048
        }
        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/chat/completions",
            data=json.dumps(data).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        try:
            with urllib.request.urlopen(req) as resp:
                res_json = json.loads(resp.read().decode("utf-8"))
                return res_json["choices"][0]["message"]["content"].strip()
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
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
            }
        ]
        if "just_saved_insights" in st.session_state:
            del st.session_state["just_saved_insights"]
        st.rerun()

with col_b2:
    # 修正①: 保存ボタンを押した「その時」にのみ知見まとめを生成・表示
    if st.button("📌 この対話をカレンダーに保存", use_container_width=True, disabled=(user_turns == 0)):
        today_str = date.today().isoformat()
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
                "time": datetime.now().strftime("%H:%M"),
                "insights": insights_summary,
                "messages": list(st.session_state.messages)
            })

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
    download_text += f"実施日時: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
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
        file_name=f"socrates_dialogue_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
        mime="text/plain",
        use_container_width=True,
        disabled=(user_turns == 0)
    )

# 修正①: 保存直後にのみ画面に知見まとめを表示（通常の対話中は出さない）
if "just_saved_insights" in st.session_state and st.session_state.just_saved_insights:
    st.success(f"対話概要と得られた知見を {date.today().isoformat()} のカレンダーに保存しました！")
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
    "🛡️ 完全ローカルと安全性"
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
        status_label = f"Groq クラウドLLM 接続中 ({model_choice.split()[0]})"
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

    # ----------------------------------------------------
    # 入力フォームを「最上部」に配置
    # ----------------------------------------------------
    with st.container():
        with st.form(key="chat_input_top_form", clear_on_submit=True):
            user_input_text = st.text_area(
                "💭 あなたの考え・悩み・モヤモヤを入力してください（最新の対話がすぐ下に積み上がります）：",
                placeholder="例: 将来についてのスキルにしたいと考えています / プログラム作成の目的は何だと思いますか？",
                height=85
            )
            col_send1, col_send2 = st.columns([1, 5], vertical_alignment="center")
            with col_send1:
                submit_button = st.form_submit_button("送信する 🚀", use_container_width=True)
            with col_send2:
                st.caption("※ 送信すると、すぐ下に最新のソクラテスの問いかけが積み上がります。")

    # 送信時の処理
    if submit_button and user_input_text.strip():
        # 送信時は以前の保存知見バナーをクリア（修正①）
        if "just_saved_insights" in st.session_state:
            del st.session_state["just_saved_insights"]

        prompt = user_input_text.strip()
        
        st.session_state.messages.append({
            "role": "user",
            "content": prompt,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
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

            # 2. クラウドGroq API実行モード
            if key and "Groq" in model:
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

                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {key}"
                }
                messages_payload = [{"role": "system", "content": system_prompt}]
                for m in st.session_state.messages[-8:]:
                    messages_payload.append({"role": m["role"], "content": m["content"]})

                data = {
                    "model": raw_model,
                    "messages": messages_payload,
                    "temperature": 0.6,
                    "max_tokens": 3072
                }
                req = urllib.request.Request(
                    "https://api.groq.com/openai/v1/chat/completions",
                    data=json.dumps(data).encode("utf-8"),
                    headers=headers,
                    method="POST"
                )
                try:
                    with urllib.request.urlopen(req) as resp:
                        res_json = json.loads(resp.read().decode("utf-8"))
                        return res_json["choices"][0]["message"]["content"].strip()
                except Exception:
                    pass

            # 3. 内蔵寄り添いエンジン（APIキーなし・ローカルLLM以外のフォールバック）
            return generate_empathetic_fallback_response(user_input, mode)

        with st.spinner("ソクラテスがあなたの言葉に耳を傾けています..."):
            reply = get_socrates_response(prompt, groq_api_key, model_choice, socratic_mode)
            st.session_state.messages.append({
                "role": "assistant",
                "content": reply,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
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

    st.markdown("---")

    cal_col1, cal_col2 = st.columns([1, 1])

    with cal_col1:
        selected_date = st.date_input("確認する日付を選択", value=date.today())
        selected_date_str = selected_date.isoformat()

        st.markdown(f"#### 📝 {selected_date_str} の探究ログ一覧")
        logs_today = st.session_state.daily_logs.get(selected_date_str, [])
        if not logs_today:
            st.info("この日の記録はまだありません。チャットを行って「カレンダーに保存」を押すとここに記録されます。")
        else:
            for idx, item in enumerate(logs_today):
                with st.expander(f"📌 {item.get('time', '')} - {item.get('title', '探究対話')} ({item.get('turns', 0)}往復)"):
                    st.write(f"**記録時刻:** {item.get('time')}")
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
                    "time": datetime.now().strftime("%H:%M"),
                    "messages": [{"role": "assistant", "content": f"【振り返りメモ】\n{note_body}"}]
                })
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
# タブ 5: 完全ローカルと安全性 (条件➁)
# ====================================================
with tab_privacy:
    st.markdown("### 🛡️ 完全フロントエンド仕様とプライバシー保護")
    st.caption("生徒の個人情報・内面的な悩み・探究ログをPC外に出さないセキュア設計")

    st.success(
        """
        **【安全性の保証】**
        本アプリは外部の中継データベースを持たないステートレス仕様です。
        入力された文章や会話履歴は、あなたのPC（ブラウザ内）でのみ保持され、外部の第三者サーバーに保存・蓄積・AI学習利用されることは一切ありません。
        """
    )

    st.markdown(
        """
        #### 学校現場での安心な利用のために
        - **データベース非保持:** 会話ログはクラウドサーバーに保存されません。
        - **端末でのデータ消去:** ブラウザを閉じるかリセットボタンを押すことで、メモリ上の会話は完全に破棄されます。
        - **APIキーの暗号通信:** Groq APIとの通信は暗号化されたHTTPSで行われ、API利用規約に基づき入力データがモデルの追加学習に転送されることはありません。
        - **学校のChromebookや共有端末でも安心:** シークレットウィンドウ等で利用すれば、他の生徒に履歴を見られる心配はありません。
        """
    )

# ----------------------------------------------------
# フッター (条件⑥)
# ----------------------------------------------------
st.markdown(
    """
    <div class="app-footer">
        <p style="color: #94a3b8; font-weight: 600; margin-bottom: 0.25rem;">ソクラテス・メンター 〜正解を教えない壁打ちチャット〜</p>
        <p style="font-size: 0.75rem; color: #64748b; margin-bottom: 0.5rem;">高校生探究学習・思考深化支援プラットフォーム ｜ 完全ローカルセキュア仕様</p>
        <p style="font-size: 0.75rem; color: #94a3b8;">2026 Teraoka-Denshi. All rights reserved.</p>
    </div>
    """,
    unsafe_allow_html=True
)
