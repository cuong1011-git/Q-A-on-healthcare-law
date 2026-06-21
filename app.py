import streamlit as st
import re
import math
import time
import os
from google import genai
from google.genai import types

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

# Khởi tạo Gemini Client từ khóa môi trường
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")


@st.cache_resource
def get_gemini_client(api_key):
    if api_key:
        try:
            return genai.Client(api_key=api_key)
        except Exception as e:
            st.error(f"Lỗi khởi tạo Gemini SDK: {e}")
    return None


ai_client = get_gemini_client(GEMINI_API_KEY)


# --- Khởi tạo dữ liệu cơ bản (Session State) ---
if "legal_chunks" not in st.session_state:
    st.session_state.legal_chunks = [
        {
            "id": 1,
            "text": "Điều 3. Nguyên tắc trong khám bệnh, chữa bệnh: 1. Tôn trọng, bảo vệ, đối xử bình đẳng và không kỳ thị, phân biệt đối xử đối với người bệnh. 2. Ưu tiên khám bệnh, chữa bệnh đối với người bệnh trong tình trạng cấp cứu, trẻ em dưới 06 tuổi, phụ nữ có thai, người khuyết tật nặng, người từ đủ 75 tuổi trở lên, người có công với cách mạng. 3. Bảo đảm đạo đức nghề nghiệp của người hành nghề. 4. Tôn trọng quyền của người bệnh; cung cấp thông tin đầy đủ, trung thực về tình trạng bệnh, phương pháp và chi phí.",
            "source": "luat_kham_chua_benh.txt",
            "article": "Điều 3 (Nguyên tắc khám chữa bệnh)",
            "char_length": 535
        },
        {
            "id": 2,
            "text": "Điều 45. Điều kiện được cấp giấy phép hành nghề khám bệnh, chữa bệnh đối với chức danh bác sĩ, y sỹ, điều dưỡng, hộ sinh: 1. Phải tốt nghiệp văn bằng y khoa chuyên ngành phù hợp. 2. Có đủ sức khỏe để hành nghề. 3. Không thuộc trường hợp đang bị cấm hành nghề hoặc bị kỷ luật theo quy định pháp luật. 4. Đạt yêu cầu kiểm tra đánh giá năng lực hành nghề khám bệnh, chữa bệnh do Hội đồng Y khoa Quốc gia tổ chức.",
            "source": "luat_kham_chua_benh.txt",
            "article": "Điều 45 (Điều kiện cấp giấy phép hành nghề)",
            "char_length": 440
        },
        {
            "id": 3,
            "text": "Điều 22. Mức hưởng bảo hiểm y tế: 1. Người tham gia bảo hiểm y tế khi đi khám bệnh, chữa bệnh theo quy định thì được quỹ bảo hiểm y tế thanh toán chi phí khám bệnh, chữa bệnh trong phạm vi quyền lợi với mức hưởng như sau: a) 100% chi phí đối với đối tượng là sĩ quan quân đội, công an, người có công với cách mạng, trẻ em dưới 6 tuổi; b) 100% chi phí đối với trường hợp chi phí cho một lần khám bệnh, chữa bệnh thấp hơn mức quy định của Chính phủ; c) 80% chi phí đối với các đối tượng khác.",
            "source": "luat_bao_hiem_y_te.txt",
            "article": "Điều 22 (Mức hưởng bảo hiểm y tế đúng tuyến)",
            "char_length": 533
        },
        {
            "id": 4,
            "text": "Điều 22. Mức hưởng bảo hiểm y tế trái tuyến (không đúng tuyến): Trường hợp người có thẻ bảo hiểm y tế tự đi khám bệnh, chữa bệnh không đúng tuyến được quỹ bảo hiểm y tế thanh toán theo tỷ lệ sau: a) Tại bệnh viện tuyến trung ương là 40% chi phí điều trị nội trú; b) Tại bệnh viện tuyến tỉnh là 100% chi phí điều trị nội trú; c) Tại bệnh viện tuyến huyện là 100% chi phí khám bệnh, chữa bệnh ngoại trú và nội trú.",
            "source": "luat_bao_hiem_y_te.txt",
            "article": "Điều 22 (Mức hưởng bảo hiểm y tế trái tuyến)",
            "char_length": 445
        },
        {
            "id": 5,
            "text": "Điều 54. Điều kiện cấp Chứng chỉ hành nghề dược: 1. Có văn bằng chuyên môn phù hợp như Bằng tốt nghiệp đại học ngành dược, y đa khoa hoặc y học cổ truyền. 2. Có thời gian thực hành tại cơ sở dược phù hợp đối với từng loại hình hành nghề (thường là từ 1 đến 2 năm tùy thuộc chức danh). 3. Có đủ sức khỏe hành nghề dược. 4. Không trong thời gian bị truy cứu trách nhiệm hình sự hoặc bị hạn chế năng lực hành vi dân sự.",
            "source": "luat_duoc.txt",
            "article": "Điều 54 (Chứng chỉ hành nghề dược)",
            "char_length": 441
        },
        {
            "id": 6,
            "text": "Điều 58. Điều kiện kinh doanh dược: Cơ sở bán lẻ thuốc (Nhà thuốc, Quầy thuốc) phải có Giấy chứng nhận đủ điều kiện kinh doanh dược. Yêu cầu: a) Người chịu trách nhiệm chuyên môn về dược phải có Chứng chỉ hành nghề dược phù hợp; b) Cơ sở vật chất, kỹ thuật và nhân sự phải đáp ứng tiêu chuẩn Thực hành tốt cơ sở bán lẻ thuốc (GPP: Good Pharmacy Practice).",
            "source": "luat_duoc.txt",
            "article": "Điều 58 (Điều kiện kinh doanh dược)",
            "char_length": 373
        },
        {
            "id": 7,
            "text": "Điều 15. Quy định về cấp cứu ngoại viện: 1. Hoạt động cấp cứu ngoại viện phải bảo đảm nhanh chóng, kịp thời, an toàn cho người bệnh. 2. Cơ sở cấp cứu ngoại viện phải trang bị đủ xe cứu thương, trang bị thiết bị y tế chuyên dụng và có nhân sự trực cấp cứu 24/24 giờ. 3. Nghiêm cấm mọi hành vi gây cản trước, trì hoãn xe cấp cứu ngoại viện khi đang thực hiện nhiệm vụ vận chuyển người bệnh cấp cứu.",
            "source": "nghi_dinh_96_huong_dan_luat.txt",
            "article": "Điều 15 (Cấp cứu ngoại viện)",
            "char_length": 419
        },
        {
            "id": 8,
            "text": "Điều 2. Quy định Danh mục thuốc thuộc phạm vi được hưởng của người tham gia bảo hiểm y tế: Thuốc được quỹ bảo hiểm y tế thanh toán phải có tên trong danh mục được Bộ Y tế ban hành, bao gồm thuốc hóa dược, sinh phẩm, thuốc cổ truyền. Tỷ lệ và điều kiện thanh toán áp dụng cho từng hoạt chất cụ thể nhằm bảo đảm an toàn, hiệu quả điều trị và cân đối quỹ BHYT.",
            "source": "thong_tu_01_danh_muc_thuoc_byt.txt",
            "article": "Điều 2 (Danh mục thuốc thanh toán BHYT)",
            "char_length": 395
        }
    ]

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "quick_question" not in st.session_state:
    st.session_state.quick_question = ""


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


# Điền vector băm vào tất cả các mảnh luật chưa có vector
for chunk in st.session_state.legal_chunks:
    if "vector" not in chunk:
        chunk["vector"] = get_embedding(chunk["text"])


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

                if GEMINI_API_KEY and ai_client:
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
                    except Exception as e:
                        answer_text = f"Dịch vụ AI phát sinh lỗi: {e}. (Nhưng bạn vẫn có thể xem các điều luật tra cứu ở cột bên phải)."
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
