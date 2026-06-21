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


# --- Khởi tạo dữ liệu cơ bản (Session State) ---
if "legal_chunks" not in st.session_state:
    st.session_state.legal_chunks = [
        {
            "id": 1,
            "text": "Điều 1. Phạm vi điều chỉnh: Luật này quy định về quyền, nghĩa vụ của người bệnh; người hành nghề khám bệnh, chữa bệnh; cơ sở khám bệnh, chữa bệnh; chuyên môn kỹ thuật trong khám bệnh, chữa bệnh; khám bệnh, chữa bệnh bằng y học cổ truyền và kết hợp y học cổ truyền với y học hiện đại; khám bệnh, chữa bệnh nhân đạo, không vì mục đích lợi nhuận; chuyển giao kỹ thuật chuyên môn về khám bệnh, chữa bệnh; áp dụng kỹ thuật mới, phương pháp mới và thử nghiệm lâm sàng; sai sót chuyên môn kỹ thuật; điều kiện bảo đảm hoạt động khám bệnh, chữa bệnh; huy động, điều động nguồn lực phục vụ công tác khám bệnh, chữa bệnh trong trường hợp xảy ra thiên tai, thảm họa, dịch bệnh truyền nhiễm thuộc nhóm A hoặc tình trạng khẩn cấp.",
            "source": "luat_kham_chua_benh_2023.txt",
            "article": "Điều 1 (Phạm vi điều chỉnh)",
            "char_length": 765
        },
        {
            "id": 2,
            "text": "Điều 2. Giải thích từ ngữ (Phần 1): Trong Luật này, các từ ngữ dưới đây được hiểu như sau:\n1. Khám bệnh là việc người hành nghề sử dụng kiến thức, phương pháp, kỹ thuật chuyên môn để đánh giá tình trạng sức khỏe, nguy cơ đối với sức khỏe và nhu cầu chăm sóc sức khỏe của người bệnh.\n2. Chữa bệnh là việc người hành nghề sử dụng kiến thức, phương pháp, kỹ thuật chuyên môn để giải quyết tình trạng bệnh, ngăn ngừa sự xuất hiện, tiến triển của bệnh hoặc đáp ứng nhu cầu chăm sóc sức khỏe trên cơ sở kết quả khám bệnh.\n3. Người bệnh là người sử dụng dịch vụ khám bệnh, chữa bệnh.\n4. Người hành nghề khám bệnh, chữa bệnh là người đã được cơ quan có thẩm quyền của Việt Nam cấp giấy phép hành nghề khám bệnh, chữa bệnh.\n5. Giấy phép hành nghề khám bệnh, chữa bệnh là văn bản do cơ quan có thẩm quyền cấp cho người có đủ điều kiện hành nghề.\n6. Cơ sở khám bệnh, chữa bệnh là cơ sở đã được cấp giấy phép hoạt động khám chữa bệnh.\n7. Giấy phép hoạt động khám chữa bệnh là văn bản do cơ quan có thẩm quyền cấp cho cơ sở có đủ điều kiện hoạt động.",
            "source": "luat_kham_chua_benh_2023.txt",
            "article": "Điều 2 (Giải thích thuật ngữ cơ bản)",
            "char_length": 1050
        },
        {
            "id": 3,
            "text": "Điều 2. Giải thích từ ngữ (Phần 2):\n8. Bài thuốc gia truyền hoặc phương pháp chữa bệnh gia truyền là bài thuốc hoặc phương pháp theo kinh nghiệm do dòng tộc/gia đình truyền lại, điều trị có hiệu quả, được cơ quan chuyên môn y tế cấp tỉnh công nhận.\n9. Người có bài thuốc/phương pháp gia truyền là người giữ quyền sở hữu bài thuốc/phương pháp gia truyền hợp pháp.\n10. Người bệnh không có thân nhân: gồm người đang cấp cứu không giấy tờ tùy thân/không thân nhân; người lúc vào viện không có khả năng nhận thức/không giấy tờ/không thân nhân; trẻ em dưới 06 tháng tuổi bị bỏ rơi tại cơ sở khám chữa bệnh.\n11. Thân nhân của người bệnh: vợ hoặc chồng; cha mẹ đẻ, cha mẹ nuôi, cha mẹ vợ, cha mẹ chồng; con đẻ, con nuôi, con dâu, con rể; người đại diện; người trực tiếp chăm sóc.\n12. Người đại diện của người bệnh là người thay thế thực hiện quyền và nghĩa vụ trong phạm vi đại diện.\n13. Người chịu trách nhiệm chuyên môn của cơ sở khám chữa bệnh là người đại diện theo pháp luật của cơ sở về toàn bộ hoạt động chuyên môn.",
            "source": "luat_kham_chua_benh_2023.txt",
            "article": "Điều 2 (Về Thân nhân và Người đại diện)",
            "char_length": 1080
        },
        {
            "id": 4,
            "text": "Điều 2. Giải thích từ ngữ (Phần 3):\n14. Cập nhật kiến thức y khoa liên tục là việc bổ sung kiến thức, kỹ năng y khoa theo quy định của Bộ trưởng Bộ Y tế.\n15. Tình trạng cấp cứu là tình trạng sức khỏe/hành vi xuất hiện đột ngột mà nếu không can thiệp kịp thời có thể dẫn đến suy giảm chức năng, tổn thương nghiêm trọng bộ phận cơ thể hoặc tử vong hoặc đe dọa tính mạng người khác.\n16. Hội chẩn là thảo luận giữa nhóm người hành nghề về tình trạng bệnh để đưa ra chẩn đoán, điều trị kịp thời.\n17. Hồ sơ bệnh án là tập hợp dữ liệu hành chính, lâm sàng, cận lâm sàng, quá trình điều trị của người bệnh.\n18. Phục hồi chức năng là tập hợp can thiệp y đức, kỹ thuật, xã hội giúp người khuyết tật phát triển tối đa hoạt động chức năng.\n19. Khám bệnh, chữa bệnh từ xa là hình thức không trực tiếp tiếp xúc mà thông qua thiết bị công nghệ thông tin.\n20. Khám sức khỏe là khám để xác định, phân loại sức khỏe hoặc phát hiện bệnh.\n21. Giám định y khoa là khám để xác định sức khỏe, mức độ thương tật tổn thương cơ thể.\n22. Sự cố y khoa là tình huống không mong muốn xảy ra do yếu tố khách quan, chủ quan.\n23. Tai biến y khoa là sự cố y khoa gây tổn hại sức khỏe, tính mạng do rủi ro ngoài ý muốn mặc dù tuân thủ kỹ thuật học hoặc do sai sót chuyên môn.",
            "source": "luat_kham_chua_benh_2023.txt",
            "article": "Điều 2 (Định nghĩa chuyên môn kỹ thuật)",
            "char_length": 1250
        },
        {
            "id": 5,
            "text": "Điều 3. Nguyên tắc trong khám bệnh, chữa bệnh:\n1. Tôn trọng, bảo vệ, đối xử bình đẳng và không kỳ thị, phân biệt đối xử đối với người bệnh.\n2. Ưu tiên khám bệnh, chữa bệnh đối với trường hợp người bệnh trong tình trạng cấp cứu, trẻ em dưới 06 tuổi, phụ nữ có thai, người khuyết tật đặc biệt nặng, người khuyết tật nặng, người từ đủ 75 tuổi trở lên, người có công với cách mạng phù hợp với đặc thù của cơ sở.\n3. Tôn trọng, hợp tác, bảo vệ người hành nghề, người khác đang thực hiện nhiệm vụ tại cơ sở khám bệnh, chữa bệnh.\n4. Thực hiện kịp thời và tuân thủ quy định về chuyên môn kỹ thuật.\n5. Tuân thủ quy tắc đạo đức nghề nghiệp trong hành nghề khám bệnh, chữa bệnh do Bộ trưởng Bộ Y tế ban hành.\n6. Bình đẳng, công bằng giữa các cơ sở khám bệnh, chữa bệnh.",
            "source": "luat_kham_chua_benh_2023.txt",
            "article": "Điều 3 (Nguyên tắc khám chữa bệnh mới)",
            "char_length": 810
        },
        {
            "id": 6,
            "text": "Điều 4. Chính sách của Nhà nước về khám bệnh, chữa bệnh (Phần 1 - Phát triển và Ngân sách):\n1. Nhà nước giữ vai trò chủ đạo trong phát triển hoạt động khám bệnh, chữa bệnh; huy động các nguồn lực xã hội cho hoạt động khám bệnh, chữa bệnh.\n2. Ưu tiên bố trí ngân sách nhà nước cho các hoạt động:\na) Phát triển cơ sở khám bệnh, chữa bệnh thuộc y tế cơ sở, hệ thống cấp cứu ngoại viện; tập trung đầu tư cho biên giới, hải đảo, vùng dân tộc thiểu số, khó khăn;\nb) Khám chữa bệnh đối với người có công, trẻ em, người cao tuổi, người khuyết tật, hộ nghèo, cận nghèo, người dân tộc miền núi, người mắc bệnh tâm thần, phong, truyền nhiễm nhóm A, truyền nhiễm nhóm B cần ưu tiên;\nc) Phát triển nguồn nhân lực y tế, đặc biệt là truyền nhiễm, tâm thần, giải phẫu bệnh, pháp y, pháp y tâm thần, hồi sức cấp cứu;\nd) Nghiên cứu, ứng dụng khoa học, công nghệ, chuyển đổi số trong khám bệnh, chữa bệnh.",
            "source": "luat_kham_chua_benh_2023.txt",
            "article": "Điều 4 (Ưu tiên bố trí ngân sách)",
            "char_length": 920
        },
        {
            "id": 7,
            "text": "Điều 4. Chính sách của Nhà nước về khám bệnh, chữa bệnh (Phần 2 - Đầu tư, đãi ngộ và Y học cổ truyền):\n3. Khuyến khích thực hiện hợp tác công tư; ưu đãi đầu tư; cơ sở khám chữa bệnh được ưu đãi về tín dụng, miễn thuế thu nhập doanh nghiệp với phần thu nhập không chia dùng để phát triển cơ sở.\n4. Đầu tư cơ sở khám chữa bệnh tại vùng điều kiện kinh tế khó khăn hoặc cơ sở hoạt động không vì mục đích lợi nhuận được xác định là ngành nghề đặc biệt ưu đãi đầu tư.\n5. Thực hiện chế độ luân phiên có thời hạn đối với người hành nghề giữa các cơ sở của Nhà nước.\n6. Có chính sách đãi ngộ đặc biệt đối với người hành nghề.\n7. Có chính sách phát triển nguồn nhân lực quản lý, quản trị bệnh viện.\n8. Phát huy vai trò tổ chức xã hội - nghề nghiệp khám bệnh, chữa bệnh.\n9. Kế thừa và phát huy y học cổ truyền; kết hợp y học cổ truyền với y học hiện đại.\n10. Kết hợp quân y và dân y trong khám bệnh, chữa bệnh.",
            "source": "luat_kham_chua_benh_2023.txt",
            "article": "Điều 4 (Khuyến khích đầu tư & Đãi ngộ)",
            "char_length": 950
        },
        {
            "id": 8,
            "text": "Điều 5. Quản lý nhà nước về khám bệnh, chữa bệnh (Nội dung quản lý):\n1. Nội dung quản lý nhà nước bao gồm:\na) Ban hành và thực hiện văn bản quy phạm pháp luật, hệ thống tiêu chuẩn, quy chuẩn kỹ thuật khám chữa bệnh;\nb) Xây dựng chính sách, quy hoạch hệ thống cơ sở khám chữa bệnh;\nc) Quy định về chuyên môn kỹ thuật, tiêu chí, tiêu chuẩn;\nd) Tổ chức hệ thống cơ sở, đánh giá chất lượng;\nđ) Cấp, đình chỉ, thu hồi giấy phép hành nghề, giấy phép hoạt động;\ne) Đào tạo phát triển nguồn nhân lực, luân phiên người hành nghề;\ng) Nghiên cứu khoa học, chuyển giao công nghệ;\nh) Vận hành Hệ sinh thái thông tin y tế, quản lý giá dịch vụ, hợp tác quốc tế;\ni) Thanh tra, kiểm tra, giải quyết khiếu nại, xử lý vi phạm.",
            "source": "luat_kham_chua_benh_2023.txt",
            "article": "Điều 5 (Nội dung quản lý nhà nước)",
            "char_length": 760
        },
        {
            "id": 9,
            "text": "Điều 5. Quản lý nhà nước về khám bệnh, chữa bệnh (Trách nhiệm quản lý):\n2. Trách nhiệm quản lý nhà nước về khám bệnh, chữa bệnh được quy định như sau:\na) Chính phủ thống nhất quản lý nhà nước về khám bệnh, chữa bệnh;\nb) Bộ Y tế chịu trách nhiệm trước Chính phủ thực hiện quản lý nhà nước về khám bệnh, chữa bệnh;\nc) Bộ Quốc phòng, Bộ Công an thực hiện quản lý nhà nước về khám chữa bệnh và tổ chức hoạt động thuộc thẩm quyền quản lý;\nd) Các Bộ, cơ quan ngang Bộ phối hợp thực hiện;\nđ) Ủy ban nhân dân các cấp thực hiện quản lý trên địa bàn thuộc thẩm quyền.",
            "source": "luat_kham_chua_benh_2023.txt",
            "article": "Điều 5 (Trách nhiệm quản lý nhà nước)",
            "char_length": 580
        },
        {
            "id": 10,
            "text": "Điều 6. Tổ chức xã hội - nghề nghiệp về khám bệnh, chữa bệnh: Có trách nhiệm:\n1. Bảo vệ quyền, lợi ích hợp pháp của hội viên.\n2. Tham gia xây dựng chính sách, pháp luật.\n3. Tham gia hội đồng chuyên môn, biên soạn giáo trình, tài liệu giáo dục kỹ thuật y khoa và kiểm tra đánh giá năng lực, cập nhật kiến thức liên tục.\n4. Phổ biến, bồi dưỡng kiến thức pháp luật, chuyên môn cho hội viên.\n5. Thực hiện dự án, đề tài nghiên cứu, tư vấn phản biện xã hội.\n6. Xây dựng và tổ chức thực hiện quy tắc đạo đức nghề nghiệp; vận động tuân thủ pháp luật.\n7. Huy động nguồn lực xã hội triển khai hoạt động.\n8. Kiến nghị xử lý vi phạm pháp luật về khám chữa bệnh.",
            "source": "luat_kham_chua_benh_2023.txt",
            "article": "Điều 6 (Tổ chức xã hội - nghề nghiệp)",
            "char_length": 690
        },
        {
            "id": 11,
            "text": "Điều 7. Các hành vi bị nghiêm cấm trong khám bệnh, chữa bệnh (Phần 1):\n1. Xâm phạm quyền của người bệnh.\n2. Từ chối hoặc cố ý chậm cấp cứu người bệnh.\n3. Khám chữa bệnh không đáp ứng điều kiện quy định.\n4. Khám chữa bệnh không đúng phạm vi hành nghề/hoạt động cho phép (trừ cấp cứu hoặc huy động thiên tai, dịch bệnh nhóm A, tình trạng khẩn cấp).\n5. Hành nghề ngoài thời gian, địa điểm đăng ký.\n6. Không tuân thủ quy định chuyên môn kỹ thuật; áp dụng phương pháp, thiết bị chưa được phép.\n7. Kê đơn, chỉ định sử dụng thuốc chưa được cấp phép lưu hành.\n8. Có hành vi nhũng nhiễu trong khám chữa bệnh.\n9. Kê đơn thuốc, chỉ định dịch vụ kỹ thuật, gợi ý chuyển người bệnh để trục lợi.\n10. Tẩy xóa, sửa hồ sơ bệnh án làm sai thông tin hoặc lập hồ sơ khống, bệnh án giả.",
            "source": "luat_kham_chua_benh_2023.txt",
            "article": "Điều 7 (Hành vi nghiêm cấm y đức)",
            "char_length": 780
        },
        {
            "id": 12,
            "text": "Điều 7. Các hành vi bị nghiêm cấm trong khám bệnh, chữa bệnh (Phần 2):\n11. Người hành nghề bán thuốc dưới mọi hình thức (trừ bán thuốc cổ truyền của bác sĩ/y sĩ y học cổ truyền/lương y hoặc thuốc gia truyền đã đăng ký).\n12. Sử dụng rượu, bia, ma túy, thuốc lá tại cơ sở hoặc trong khi khám bệnh, chữa bệnh.\n13. Sử dụng hình thức mê tín, dị đoan.\n14. Từ chối tham gia hoạt động khi có thiên tai, dịch bệnh nhóm A, khẩn cấp theo điều động.\n15. Cung cấp dịch vụ không giấy phép, đang bị đình chỉ hoặc không đúng phạm vi hoạt động.\n16. Thuê, mượn, cho thuê, cho mượn giấy phép hành nghề/hoạt động.\n17. Lợi dụng hình ảnh người hành nghề tuyên truyền thuốc/phương pháp chưa công nhận.\n18. Xâm phạm tính mạng, sức khỏe, xúc phạm danh dự y bác sĩ/người làm việc ở cơ sở, phá hoại tài sản.\n19. Ngăn cản người bắt buộc chữa bệnh vào viện hoặc bắt buộc chữa bệnh trái phép.\n20. Quảng cáo vượt quá phạm vi hành nghề/hoạt động; quảng cáo gian dối.\n21. Đăng tải thông tin quy kết trách nhiệm sự cố y khoa khi chưa có kết luận.",
            "source": "luat_kham_chua_benh_2023.txt",
            "article": "Điều 7 (Hành vi cấm hành nghề & bạo lực)",
            "char_length": 1050
        },
        {
            "id": 13,
            "text": "Điều 8. Người đại diện của người bệnh:\n1. Một người bệnh chỉ có một người đại diện tại một thời điểm.\n2. Người đại diện phải có năng lực hành vi dân sự đầy đủ, bao gồm:\na) Do người bệnh thành niên tự chọn;\nb) Do thành viên gia đình chọn nếu người bệnh không thể tự chọn và không có ủy quyền trước;\nc) Đại diện theo ủy quyền, theo pháp luật;\nd) Do pháp nhân quản lý/chăm sóc cử ra;\nđ) Người tự nguyện thực hiện nghĩa vụ.\n3. Thay thế người đại diện: Phải có xác nhận của người bệnh hoặc gia đình (trong từng trường hợp cụ thể); trường hợp là cha mẹ đối với con chưa thành niên không cần xác nhận; trường hợp là người giám hộ/pháp nhân thay thế bằng quyết định/ủy quyền văn bản.\n4. Quyền và nghĩa vụ thực hiện theo Bộ luật Dân sự.",
            "source": "luat_kham_chua_benh_2023.txt",
            "article": "Điều 8 (Người đại diện pháp lý bệnh nhân)",
            "char_length": 810
        },
        {
            "id": 14,
            "text": "Điều 22. Mức hưởng bảo hiểm y tế: 1. Người tham gia bảo hiểm y tế khi đi khám bệnh, chữa bệnh theo quy định thì được quỹ bảo hiểm y tế thanh toán chi phí khám bệnh, chữa bệnh trong phạm vi quyền lợi với mức hưởng như sau: a) 100% chi phí đối với đối tượng là sĩ quan quân đội, công an, người có công với cách mạng, trẻ em dưới 6 tuổi; b) 100% chi phí đối với trường hợp chi phí cho một lần khám bệnh, chữa bệnh thấp hơn mức quy định của Chính phủ; c) 80% chi phí đối với các đối tượng khác.",
            "source": "luat_bao_hiem_y_te.txt",
            "article": "Điều 22 (Mức hưởng bảo hiểm y tế đúng tuyến)",
            "char_length": 533
        },
        {
            "id": 15,
            "text": "Điều 22. Mức hưởng bảo hiểm y tế trái tuyến (không đúng tuyến): Trường hợp người có thẻ bảo hiểm y tế tự đi khám bệnh, chữa bệnh không đúng tuyến được quỹ bảo hiểm y tế thanh toán theo tỷ lệ sau: a) Tại bệnh viện tuyến trung ương là 40% chi phí điều trị nội trú; b) Tại bệnh viện tuyến tỉnh là 100% chi phí điều trị nội trú; c) Tại bệnh viện tuyến huyện là 100% chi phí khám bệnh, chữa bệnh ngoại trú và nội trú.",
            "source": "luat_bao_hiem_y_te.txt",
            "article": "Điều 22 (Mức hưởng bảo hiểm y tế trái tuyến)",
            "char_length": 445
        },
        {
            "id": 16,
            "text": "Điều 54. Điều kiện cấp Chứng chỉ hành nghề dược: 1. Có văn bằng chuyên môn phù hợp như Bằng tốt nghiệp đại học ngành dược, y đa khoa hoặc y học cổ truyền. 2. Có thời gian thực hành tại cơ sở dược phù hợp đối với từng loại hình hành nghề (thường là từ 1 đến 2 năm tùy thuộc chức danh). 3. Có đủ sức khỏe hành nghề dược. 4. Không trong thời gian bị truy cứu trách nhiệm hình sự hoặc bị hạn chế năng lực hành vi dân sự.",
            "source": "luat_duoc.txt",
            "article": "Điều 54 (Chứng chỉ hành nghề dược)",
            "char_length": 441
        },
        {
            "id": 17,
            "text": "Điều 58. Điều kiện kinh doanh dược: Cơ sở bán lẻ thuốc (Nhà thuốc, Quầy thuốc) phải có Giấy chứng nhận đủ điều kiện kinh doanh dược. Yêu cầu: a) Người chịu trách nhiệm chuyên môn về dược phải có Chứng chỉ hành nghề dược phù hợp; b) Cơ sở vật chất, kỹ thuật và nhân sự phải đáp ứng tiêu chuẩn Thực hành tốt cơ sở bán lẻ thuốc (GPP: Good Pharmacy Practice).",
            "source": "luat_duoc.txt",
            "article": "Điều 58 (Điều kiện kinh doanh dược)",
            "char_length": 373
        },
        {
            "id": 18,
            "text": "Điều 15. Quy định về cấp cứu ngoại viện: 1. Hoạt động cấp cứu ngoại viện phải bảo đảm nhanh chóng, kịp thời, an toàn cho người bệnh. 2. Cơ sở cấp cứu ngoại viện phải trang bị đủ xe cứu thương, trang bị thiết bị y tế chuyên dụng và có nhân sự trực cấp cứu 24/24 giờ. 3. Nghiêm cấm mọi hành vi gây cản trước, trì hoãn xe cấp cứu ngoại viện khi đang thực hiện nhiệm vụ vận chuyển người bệnh cấp cứu.",
            "source": "nghi_dinh_96_huong_dan_luat.txt",
            "article": "Điều 15 (Cấp cứu ngoại viện)",
            "char_length": 419
        },
        {
            "id": 19,
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
