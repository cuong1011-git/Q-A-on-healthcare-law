import streamlit as st
import re
import math
import time
import os
import urllib.request
import json

try:
    from google import genai
    from google.genai import types
    HAS_GENAI_SDK = True
except ImportError:
    HAS_GENAI_SDK = False

# Cấu hình giao diện Streamlit
st.set_page_config(
    page_title="Chatbot Hỏi Đáp Luật Y Tế",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Giao diện chính và CSS tùy chỉnh mang tính thẩm mỹ cao giống bản Web
st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 805;
        color: #0369a1;
        margin-bottom: 0px;
    }
    .sub-title {
        font-size: 0.95rem;
        color: #64748b;
        margin-bottom: 20px;
    }
    .badge-medic {
        background-color: #f0f9ff;
        color: #0284c7;
        font-size: 0.8rem;
        padding: 4px 10px;
        border-radius: 4px;
        border: 1px solid #e0f2fe;
        font-weight: 500;
        margin-left: 10px;
    }
    .metric-card {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        padding: 12px;
        border-radius: 10px;
        text-align: center;
    }
    .citation-box {
        font-size: 0.85rem;
        background-color: #fafafa;
        border-left: 3px solid #0284c7;
        padding: 10px;
        border-radius: 4px;
        margin-top: 8px;
        font-family: monospace;
    }
</style>
""", unsafe_allow_html=True)

# Tự động quét và nạp file .env (hỗ trợ cả khi file nằm trong thư mục venv/ hoặc thư mục gốc)
if not os.environ.get("GEMINI_API_KEY"):
    for env_path in [".env", "venv/.env", "./venv/.env", "../.env"]:
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            if k.strip() == "GEMINI_API_KEY":
                                os.environ["GEMINI_API_KEY"] = v.strip().strip("'\"")
                                break
            except Exception:
                pass

# Khởi tạo Gemini Client từ khóa môi trường hoặc Streamlit Secrets
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
if not GEMINI_API_KEY:
    try:
        GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        pass


@st.cache_resource
def get_gemini_client(api_key):
    if api_key and HAS_GENAI_SDK:
        try:
            return genai.Client(api_key=api_key)
        except Exception as e:
            st.error(f"Lỗi khởi tạo Gemini SDK: {e}")
    return None


ai_client = get_gemini_client(GEMINI_API_KEY)


# --- Hàm băm Vector tần suất dự phòng (Fallback Embedding) ---
def get_embedding(text: str) -> list:
    """Sinh vector tần suất từ phục vụ đối chiếu cosine nhanh trong RAM."""
    hash_size = 300
    vector = [0.0] * hash_size
    # Dọn dẹp văn bản thô
    clean_text = re.sub(r"[.,\/#!$%\^&\*;:{}=\-_`~()]", "", text.lower())
    words = clean_text.split()
    for word in words:
        # Thuật toán sinh băm chuỗi nội bộ
        h = 0
        for char in word:
            h = (h << 5) - h + ord(char)
            h &= 0xFFFFFFFF  # Khóa lại trong 32-bit int
        index = h % hash_size
        vector[index] += 1.0
    return vector


# --- Hàm tách tài liệu từ đĩa ---
def parse_document_content(name: str, content: str, start_id: int):
    clean_txt = content.strip()
    # Tìm tách theo đầu "Điều X"
    segments = re.split(r"(?=Điều\s+\d+)", clean_txt, flags=re.IGNORECASE)
    segments = [s.strip() for s in segments if len(s.strip()) > 5]

    added_chunks = []
    if len(segments) > 1:
        for idx, seg in enumerate(segments):
            # Tìm metadata Điều
            match = re.match(r"^(Điều\s+\d+[^.\n:]*)", seg, re.IGNORECASE)
            article_header = match.group(1).strip() if match else f"Điều luật bổ sung {idx + 1}"
            added_chunks.append({
                "text": seg,
                "article": article_header,
            })
    else:
        # Nếu không có "Điều", tách theo các đoạn đơn
        paragraphs = [p.strip() for p in clean_txt.split("\n\n") if len(p.strip()) > 10]
        if len(paragraphs) > 1:
            for idx, p in enumerate(paragraphs):
                added_chunks.append({
                    "text": p,
                    "article": f"Đoạn thứ {idx + 1}"
                })
        else:
            # Thất bại thì chia bọc trượt 600 ký tự
            if len(clean_txt) > 600:
                curr_idx = 0
                part_count = 1
                while curr_idx < len(clean_txt):
                    chunk_text = clean_txt[curr_idx:curr_idx + 600]
                    added_chunks.append({
                        "text": chunk_text,
                        "article": f"Phân đoạn {part_count}"
                    })
                    curr_idx += 450
                    part_count += 1
            else:
                added_chunks.append({
                    "text": clean_txt,
                    "article": "Văn bản đặc thù"
                })

    final_chunks = []
    for i, item in enumerate(added_chunks):
        final_chunks.append({
            "id": start_id + i,
            "text": item["text"],
            "source": name,
            "article": item["article"],
            "char_length": len(item["text"]),
            "vector": get_embedding(item["text"])
        })
    return final_chunks


# --- Khởi tạo dữ liệu cơ bản (Session State) ---
if "legal_chunks" not in st.session_state:
    st.session_state.legal_chunks = []
    
    # Quét tất cả file .txt hoặc .md trong thư mục gốc (ngoại trừ một số file hệ thống cấu hình)
    law_files = []
    try:
        raw_files = os.listdir(".")
        for raw_f in raw_files:
            if raw_f.endswith(".txt") and raw_f != "requirements.txt":
                law_files.append(raw_f)
            elif raw_f.endswith(".md") and raw_f not in ["README.md", "AGENTS.md", "GEMINI.md", "metadata.json"]:
                law_files.append(raw_f)
    except Exception:
        pass
        
    law_files = sorted(law_files)
    start_id = 1
    
    for f_name in law_files:
        try:
            with open(f_name, "r", encoding="utf-8") as f_obj:
                content = f_obj.read()
                chunks = parse_document_content(f_name, content, start_id)
                st.session_state.legal_chunks.extend(chunks)
                start_id += len(chunks)
        except Exception as file_err:
            st.warning(f"Không thể nạp tệp luật '{f_name}': {file_err}")

    # Fallback/Dự phòng nếu thư mục hoàn toàn trống rỗng không có file luật
    if not st.session_state.legal_chunks:
        fallback_text = "Điều 1. Phạm vi điều chỉnh: Luật này quy định về quyền, nghĩa vụ của người bệnh; người hành nghề khám bệnh..."
        st.session_state.legal_chunks = [
            {
                "id": 1,
                "text": fallback_text,
                "source": "luat_kham_chua_benh_2023.txt",
                "article": "Điều 1 (Phạm vi điều chỉnh)",
                "char_length": len(fallback_text),
                "vector": get_embedding(fallback_text)
            }
        ]

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "quick_question" not in st.session_state:
    st.session_state.quick_question = ""





# --- Tính toán độ tương đồng Cosine Similarity ---
def cosine_similarity(vec_a, vec_b):
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)


# --- Xử lý tách nhỏ tệp luật tải lên mới ---
def add_new_document(name: str, content: str):
    clean_txt = content.strip()
    # Tìm tách theo đầu "Điều X"
    segments = re.split(r"(?=Điều\s+\d+)", clean_txt, flags=re.IGNORECASE)
    segments = [s.strip() for s in segments if len(s.strip()) > 5]

    added_chunks = []
    if len(segments) > 1:
        for idx, seg in enumerate(segments):
            # Tìm metadata Điều
            match = re.match(r"^(Điều\s+\d+[^.\n:]*)", seg, re.IGNORECASE)
            article_header = match.group(1).strip() if match else f"Điều luật bổ sung {idx + 1}"
            added_chunks.append({
                "text": seg,
                "article": article_header,
            })
    else:
        # Nếu không có "Điều", tách theo các đoạn đơn
        paragraphs = [p.strip() for p in clean_txt.split("\n\n") if len(p.strip()) > 10]
        if len(paragraphs) > 1:
            for idx, p in enumerate(paragraphs):
                added_chunks.append({
                    "text": p,
                    "article": f"Đoạn thứ {idx + 1}"
                })
        else:
            # Thất bại thì chia bọc trượt 600 ký tự
            if len(clean_txt) > 600:
                curr_idx = 0
                part_count = 1
                while curr_idx < len(clean_txt):
                    chunk_text = clean_txt[curr_idx:curr_idx + 600]
                    added_chunks.append({
                        "text": chunk_text,
                        "article": f"Phân đoạn {part_count}"
                    })
                    curr_idx += 450
                    part_count += 1
            else:
                added_chunks.append({
                    "text": clean_txt,
                    "article": "Văn bản đặc thù"
                })

    # Thiết lập Vector và Đẩy dữ liệu vào RAM
    start_id = len(st.session_state.legal_chunks) + 1
    new_records = []
    for i, item in enumerate(added_chunks):
        new_chunk = {
            "id": start_id + i,
            "text": item["text"],
            "source": name,
            "article": item["article"],
            "char_length": len(item["text"]),
            "vector": get_embedding(item["text"])
        }
        st.session_state.legal_chunks.append(new_chunk)
        new_records.append(new_chunk)
    return len(new_records)


# --- Trực quan hoá Sidebar bên trái ---
with st.sidebar:
    st.markdown("### 📚 HỢP PHẦN VĂN BẢN")
    st.write("Cơ sở dữ liệu đang nạp các tệp luật sức khỏe y khoa sau trong bộ nhớ:")

    # Thống kê văn bản hiện có
    doc_stats = {}
    for c in st.session_state.legal_chunks:
        src = c["source"]
        if src not in doc_stats:
            doc_stats[src] = {"chunks": 0, "chars": 0}
        doc_stats[src]["chunks"] += 1
        doc_stats[src]["chars"] += c["char_length"]

    for src, stats in doc_stats.items():
        st.markdown(f"📄 **{src}**")
        st.caption(f"- Tổng số điều khoản: {stats['chunks']} | {stats['chars']} ký tự")

    st.markdown("---")
    st.markdown("### 🏹 NẠP TẬP TIN LUẬT MỚI")
    st.write("Tải lên 1 tập tin luật dưới định dạng `.txt` hoặc `.md` chứa hàng loạt Điều luật. Hệ thống sẽ tự phân tích.")

    # Cấu trúc tải file
    uploaded_file = st.file_uploader(
        "Chọn tệp tin (.txt hoặc .md)",
        type=["txt", "md"],
        help="Hãy chọn một văn bản có ghi rõ 'Điều 1...', 'Điều 2...' để hệ thống cắt cấu trúc."
    )

    if uploaded_file is not None:
        file_name = uploaded_file.name
        file_content = uploaded_file.read().decode("utf-8")

        # Nút xác nhận lập chỉ mục
        if st.button("🚀 Nạp & Lập chỉ mục RAM", use_container_width=True):
            with st.spinner("Đang trích tách bối cảnh..."):
                added_qty = add_new_document(file_name, file_content)
                st.success(f"Đã lập chỉ mục {added_qty} điều khoản mới từ tệp {file_name}!")
                time.sleep(1.5)
                st.rerun()


# --- Trực quan hóa Giao diện Chính ở giữa ---
col1, col2 = st.columns([3, 1.2])

with col1:
    st.markdown(f'<div class="main-title">CHATBOT HỎI ĐÁP LUẬT Y TẾ <span class="badge-medic">Bảo hiểm & Khám bệnh</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Trải nghiệm hệ thống tìm kiếm tăng cường thông tin (RAG LLM) giảm thiểu tối đa hiện tượng ảo giác AI</div>', unsafe_allow_html=True)

    # Khung Gợi ý nhanh
    st.markdown("💡 **Câu hỏi gợi ý nhanh:**")
    quick_col1, quick_col2, quick_col3 = st.columns(3)
    sample_q1 = "Có các điều kiện gì để được cấp giấy phép hành nghề y?"
    sample_q2 = "Tỷ lệ % hưởng bảo hiểm y tế đúng tuyến là bao nhiêu?"
    sample_q3 = "Thủ tục cấp chứng chỉ hành nghề dược ra sao?"

    if quick_col1.button("Điều kiện cấp phép hành nghề y", use_container_width=True):
        st.session_state.quick_question = sample_q1
    if quick_col2.button("Mức hưởng bảo hiểm y tế", use_container_width=True):
        st.session_state.quick_question = sample_q2
    if quick_col3.button("Chứng chỉ hành nghề dược", use_container_width=True):
        st.session_state.quick_question = sample_q3

    st.write("")

    # Nhập câu hỏi
    default_input_text = st.session_state.quick_question if st.session_state.quick_question else ""
    user_query = st.text_input(
        "📝 Đặt câu hỏi pháp lý của bạn:",
        value=default_input_text,
        placeholder="Nhập câu hỏi... (Ví dụ: Thẻ bảo hiểm trái tuyến được thanh toán thế nào?)"
    )

    # Nút gửi câu hỏi
    if st.button("🔮 Truy vấn thông tin luật", type="primary", use_container_width=True) or (user_query and user_query != st.session_state.quick_question):
        if not user_query.strip():
            st.warning("Vui lòng nhập câu hỏi pháp lý!")
        else:
            # Reseting quick question state
            st.session_state.quick_question = ""

            with st.spinner("Đang trích lục dữ liệu & phản hồi..."):
                t_retrieve_start = time.time()

                # Tính vector của câu hỏi
                q_vector = get_embedding(user_query)

                # Đối chiếu tính Cosine similarity
                scored_chunks = []
                for chunk in st.session_state.legal_chunks:
                    score = cosine_similarity(q_vector, chunk["vector"])
                    scored_chunks.append({**chunk, "score": score})

                # Lấy Top 3 chunks tốt nhất
                scored_chunks.sort(key=lambda x: x["score"], reverse=True)
                top_chunks = [sc for sc in scored_chunks if sc["score"] > 0.05][:3]

                t_retrieve_end = time.time()
                retrieve_duration = t_retrieve_end - t_retrieve_start

                # Chuẩn bị bối cảnh (Context)
                context_str = ""
                if top_chunks:
                    context_str = "\n".join([
                        f"Nguồn: {c['source']} | Điều mục: {c['article']}\nNội dung: {c['text']}"
                        for c in top_chunks
                    ])
                else:
                    context_str = "Không tìm thấy điều khoản nào khớp."

                # Gọi AI phản hồi
                ai_model_name = "gemini-2.5-flash"
                system_prompt = (
                    "Bạn là Trợ lý Pháp luật Y tế chính xác và khách quan của Việt Nam.\n"
                    "Dưới đây là các tài liệu điều khoản pháp luật chính thống được tra cứu tự động từ cơ sở dữ liệu quốc gia (Bối cảnh).\n"
                    "Hãy chỉ sử dụng bối cảnh này để trả lời câu hỏi của người dùng. Không bịa đặt, không ngoại suy.\n"
                    "Nếu bối cảnh không chứa đủ thông tin để trả lời, hãy nói rõ 'Tôi không tìm thấy thông tin cụ thể trong tài liệu tham khảo để trả lời câu hỏi này' thay vì tự tạo ý kiến khách quan.\n\n"
                    f"Bối cảnh văn bản luật:\n{context_str}\n"
                )

                t_gen_start = time.time()
                answer_text = ""

                if GEMINI_API_KEY:
                    # Thử qua SDK trước
                    if HAS_GENAI_SDK and ai_client:
                        try:
                            response = ai_client.models.generate_content(
                                model=ai_model_name,
                                contents=user_query,
                                config=types.GenerateContentConfig(
                                    system_instruction=system_prompt,
                                    temperature=0.2
                               )
                            )
                            answer_text = response.text
                        except Exception as sdk_err:
                            # Nếu SDK lỗi (ví dụ không đồng bộ phiên bản), chạy tiếp xuống phương thức REST API
                            ai_client = None

                    # Fallback REST API thuần cực kỳ ổn định, không lo xung đột thư viện
                    if not ai_client:
                        try:
                            url = f"https://generativelanguage.googleapis.com/v1beta/models/{ai_model_name}:generateContent?key={GEMINI_API_KEY}"
                            headers = {"Content-Type": "application/json"}
                            payload = {
                                "contents": [{"parts": [{"text": user_query}]}],
                                "systemInstruction": {"parts": [{"text": system_prompt}]},
                                "generationConfig": {"temperature": 0.2}
                            }
                            req = urllib.request.Request(
                                url,
                                data=json.dumps(payload).encode("utf-8"),
                                headers=headers,
                                method="POST"
                            )
                            with urllib.request.urlopen(req, timeout=30) as responsePost:
                                res_data = json.loads(responsePost.read().decode("utf-8"))
                                answer_text = res_data["candidates"][0]["content"]["parts"][0]["text"]
                        except Exception as rest_err:
                            answer_text = f"Dịch vụ AI phát sinh lỗi: {rest_err}. (Nhưng bạn vẫn có thể xem các điều luật tra cứu ở cột bên phải)."
                else:
                    # Gợi ý thiết lập API key
                    answer_text = (
                        "⚠️ Hệ thống đang chạy ở chế độ KHÔNG CÓ API KEY. "
                        "Do đó ứng dụng không thể sinh phản hồi hoàn thiện bằng Trí tuệ Nhân tạo thông minh.\n\n"
                        "Tuy nhiên, động cơ RAG vẫn hoạt động tốt! "
                        "Hệ thống đã tự động tìm thấy các Điều luật tương đồng nhất với câu hỏi của bạn ở cột kế bên."
                    )

                t_gen_end = time.time()
                generate_duration = t_gen_end - t_gen_start

                # Lưu vào lịch sử
                new_chat = {
                    "question": user_query,
                    "answer": answer_text,
                    "retrieve_time": retrieve_duration,
                    "generate_time": generate_duration,
                    "chunks": top_chunks
                }
                st.session_state.chat_history.insert(0, new_chat)

    # Hiển thị lịch sử hội thoại dạng Bong bóng
    st.write("---")
    st.markdown("### 💬 LỊCH SỬ TRA CỨU KHẢO SÁT")

    if not st.session_state.chat_history:
        st.info("Chưa có phiên hỏi đáp nào. Nhập câu hỏi bên trên để nhận câu trả lời chính xác.")
    else:
        for idx, chat in enumerate(st.session_state.chat_history):
            # Khung câu hỏi
            st.markdown(f"🙋‍♂️ **Bạn hỏi:** *{chat['question']}*")
            # Khung phản hồi
            st.info(chat["answer"])

            # Thống kê hiệu năng
            st.caption(
                f"⏱️ Trích lục RAM: {chat['retrieve_time']*1000:.0f}ms | "
                f"Mô hình AI: {chat['generate_time']*1000:.0f}ms"
            )
            st.write("")


# --- Trực quan hóa RAG Insights Live ở cột bên phải ---
with col2:
    st.markdown("### 🔬 RAG INSIGHTS (LIVE)")
    st.write("Dữ liệu bối cảnh tương ứng của câu hỏi gần nhất:")

    if st.session_state.chat_history:
        last_chat = st.session_state.chat_history[0]
        if last_chat["chunks"]:
            for c_idx, chunk in enumerate(last_chat["chunks"]):
                st.markdown(f"📍 **{chunk['article']}**")
                st.caption(f"Tệp tin: `{chunk['source']}`")
                st.markdown(f'<div class="citation-box">{chunk["text"]}</div>', unsafe_allow_html=True)
                st.markdown(f"💎 *Similarity Score: `{chunk['score']:.4f}`*")
                st.write("---")
        else:
            st.write("Không tìm thấy bối cảnh phù hợp để trích dẫn.")
    else:
        st.write("👉 Bối cảnh thực tế khớp với câu hỏi và điểm số tương quan của mô hình RAG sẽ cập nhật trực tiếp tại đây.")
