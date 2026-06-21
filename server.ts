import express from "express";
import path from "path";
import { createServer as createViteServer } from "vite";
import { GoogleGenAI } from "@google/genai";
import dotenv from "dotenv";

dotenv.config();

const app = express();
const PORT = 3000;

app.use(express.json({ limit: "50mb" }));
app.use(express.urlencoded({ limit: "50mb", extended: true }));

// Khởi tạo Gemini SDK
let ai: GoogleGenAI | null = null;
const apiKey = process.env.GEMINI_API_KEY;

if (apiKey && apiKey !== "MY_GEMINI_API_KEY") {
  try {
    ai = new GoogleGenAI({
      apiKey: apiKey,
      httpOptions: {
        headers: {
          "User-Agent": "aistudio-build",
        },
      },
    });
    console.log("Đã khởi tạo Gemini SDK server-side thành công.");
  } catch (error) {
    console.error("Lỗi khi khởi tạo Gemini SDK:", error);
  }
}

// Kiểu dữ liệu Chunk pháp lý
interface LegalChunk {
  id: number;
  text: string;
  metadata: {
    source: string;
    article: string;
    char_length: number;
  };
  vector?: number[];
}

// Tập hợp tài liệu luật ban đầu (mô phỏng dữ liệu thô chất lượng cao)
let legalChunks: LegalChunk[] = [
  {
    id: 1,
    text: "Điều 3. Nguyên tắc trong khám bệnh, chữa bệnh: 1. Tôn trọng, bảo vệ, đối xử bình đẳng và không kỳ thị, phân biệt đối xử đối với người bệnh. 2. Ưu tiên khám bệnh, chữa bệnh đối với người bệnh trong tình trạng cấp cứu, trẻ em dưới 06 tuổi, phụ nữ có thai, người khuyết tật nặng, người từ đủ 75 tuổi trở lên, người có công với cách mạng. 3. Bảo đảm đạo đức nghề nghiệp của người hành nghề. 4. Tôn trọng quyền của người bệnh; cung cấp thông tin đầy đủ, trung thực về tình trạng bệnh, phương pháp và chi phí.",
    metadata: { source: "luat_kham_chua_benh.pdf", article: "Điều 3 (Nguyên tắc khám chữa bệnh)", char_length: 535 }
  },
  {
    id: 2,
    text: "Điều 45. Điều kiện được cấp giấy phép hành nghề khám bệnh, chữa bệnh đối với chức danh bác sĩ, y sỹ, điều dưỡng, hộ sinh: 1. Phải tốt nghiệp văn bằng y khoa chuyên ngành phù hợp. 2. Có đủ sức khỏe để hành nghề. 3. Không thuộc trường hợp đang bị cấm hành nghề hoặc bị kỷ luật theo quy định pháp luật. 4. Đạt yêu cầu kiểm tra đánh giá năng lực hành nghề khám bệnh, chữa bệnh do Hội đồng Y khoa Quốc gia tổ chức.",
    metadata: { source: "luat_kham_chua_benh.pdf", article: "Điều 45 (Điều kiện cấp giấy phép hành nghề)", char_length: 440 }
  },
  {
    id: 3,
    text: "Điều 22. Mức hưởng bảo hiểm y tế: 1. Người tham gia bảo hiểm y tế khi đi khám bệnh, chữa bệnh theo quy định thì được quỹ bảo hiểm y tế thanh toán chi phí khám bệnh, chữa bệnh trong phạm vi quyền lợi với mức hưởng như sau: a) 100% chi phí đối với đối tượng là sĩ quan quân đội, công an, người có công với cách mạng, trẻ em dưới 6 tuổi; b) 100% chi phí đối với trường hợp chi phí cho một lần khám bệnh, chữa bệnh thấp hơn mức quy định của Chính phủ; c) 80% chi phí đối với các đối tượng khác.",
    metadata: { source: "luat_bao_hiem_y_te.pdf", article: "Điều 22 (Mức hưởng bảo hiểm y tế đúng tuyến)", char_length: 533 }
  },
  {
    id: 4,
    text: "Điều 22. Mức hưởng bảo hiểm y tế trái tuyến (không đúng tuyến): Trường hợp người có thẻ bảo hiểm y tế tự đi khám bệnh, chữa bệnh không đúng tuyến được quỹ bảo hiểm y tế thanh toán theo tỷ lệ sau: a) Tại bệnh viện tuyến trung ương là 40% chi phí điều trị nội trú; b) Tại bệnh viện tuyến tỉnh là 100% chi phí điều trị nội trú; c) Tại bệnh viện tuyến huyện là 100% chi phí khám bệnh, chữa bệnh ngoại trú và nội trú.",
    metadata: { source: "luat_bao_hiem_y_te.pdf", article: "Điều 22 (Mức hưởng bảo hiểm y tế trái tuyến)", char_length: 445 }
  },
  {
    id: 5,
    text: "Điều 54. Điều kiện cấp Chứng chỉ hành nghề dược: 1. Có văn bằng chuyên môn phù hợp như Bằng tốt nghiệp đại học ngành dược, y đa khoa hoặc y học cổ truyền. 2. Có thời gian thực hành tại cơ sở dược phù hợp đối với từng loại hình hành nghề (thường là từ 1 đến 2 năm tùy thuộc chức danh). 3. Có đủ sức khỏe hành nghề dược. 4. Không trong thời gian bị truy cứu trách nhiệm hình sự hoặc bị hạn chế năng lực hành vi dân sự.",
    metadata: { source: "luat_duoc.pdf", article: "Điều 54 (Chứng chỉ hành nghề dược)", char_length: 441 }
  },
  {
    id: 6,
    text: "Điều 58. Điều kiện kinh doanh dược: Cơ sở bán lẻ thuốc (Nhà thuốc, Quầy thuốc) phải có Giấy chứng nhận đủ điều kiện kinh doanh dược. Yêu cầu: a) Người chịu trách nhiệm chuyên môn về dược phải có Chứng chỉ hành nghề dược phù hợp; b) Cơ sở vật chất, kỹ thuật và nhân sự phải đáp ứng tiêu chuẩn Thực hành tốt cơ sở bán lẻ thuốc (GPP: Good Pharmacy Practice).",
    metadata: { source: "luat_duoc.pdf", article: "Điều 58 (Điều kiện kinh doanh dược)", char_length: 373 }
  },
  {
    id: 7,
    text: "Điều 15. Quy định về cấp cứu ngoại viện: 1. Hoạt động cấp cứu ngoại viện phải bảo đảm nhanh chóng, kịp thời, an toàn cho người bệnh. 2. Cơ sở cấp cứu ngoại viện phải trang bị đủ xe cứu thương, trang bị thiết bị y tế chuyên dụng và có nhân sự trực cấp cứu 24/24 giờ. 3. Nghiêm cấm mọi hành vi gây cản trước, trì hoãn xe cấp cứu ngoại viện khi đang thực hiện nhiệm vụ vận chuyển người bệnh cấp cứu.",
    metadata: { source: "nghi_dinh_96_huong_dan_luat.pdf", article: "Điều 15 (Cấp cứu ngoại viện)", char_length: 419 }
  },
  {
    id: 8,
    text: "Điều 2. Quy định Danh mục thuốc thuộc phạm vi được hưởng của người tham gia bảo hiểm y tế: Thuốc được quỹ bảo hiểm y tế thanh toán phải có tên trong danh mục được Bộ Y tế ban hành, bao gồm thuốc hóa dược, sinh phẩm, thuốc cổ truyền. Tỷ lệ và điều kiện thanh toán áp dụng cho từng hoạt chất cụ thể nhằm bảo đảm an toàn, hiệu quả điều trị và cân đối quỹ BHYT.",
    metadata: { source: "thong_tu_01_danh_muc_thuoc_byt.pdf", article: "Điều 2 (Danh mục thuốc thanh toán BHYT)", char_length: 395 }
  }
];

// Hàm phụ trợ tính Cosine Similarity toán học giữa 2 vector số
function cosineSimilarity(vecA: number[], vecB: number[]): number {
  let dotProduct = 0.0;
  let normA = 0.0;
  let normB = 0.0;
  for (let i = 0; i < vecA.length; i++) {
    dotProduct += vecA[i] * vecB[i];
    normA += vecA[i] * vecA[i];
    normB += vecB[i] * vecB[i];
  }
  if (normA === 0 || normB === 0) return 0;
  return dotProduct / (Math.sqrt(normA) * Math.sqrt(normB));
}

// Hàm phụ trợ tự động sinh vector embedding thô bằng Gemini hoặc thuật toán đếm tần suất Overlap dự phòng (fallback)
async function getEmbedding(text: string): Promise<number[]> {
  if (ai) {
    try {
      const response = await ai.models.embedContent({
        model: "gemini-embedding-2-preview",
        contents: text,
      }) as any;
      if (response.embedding?.values) {
        return response.embedding.values;
      } else if (response.embeddings?.[0]?.values) {
        return response.embeddings[0].values;
      }
    } catch (e) {
      console.warn("Lỗi sinh embedding bằng Gemini, chuyển sang dùng thuật toán tần suất:", e);
    }
  }

  // Thuật toán băm tần suất từ (Fallback Vector) đạt hiệu suất cao với 300 chiều số
  const hashSize = 300;
  const vector = new Array(hashSize).fill(0);
  const cleanText = text.toLowerCase().replace(/[.,\/#!$%\^&\*;:{}=\-_`~()]/g, "");
  const words = cleanText.split(/\s+/);
  words.forEach(word => {
    let hash = 0;
    for (let i = 0; i < word.length; i++) {
      hash = (hash << 5) - hash + word.charCodeAt(i);
      hash |= 0;
    }
    const index = Math.abs(hash) % hashSize;
    vector[index] += 1;
  });
  return vector;
}

// Khởi chạy tiến trình mã hóa (embed) trước các khối luật khi server khởi động
async function preIndexChunks() {
  console.log("Đang tiến hành lập chỉ mục (Embedding) văn bản pháp luật...");
  for (const chunk of legalChunks) {
    chunk.vector = await getEmbedding(chunk.text);
  }
  console.log("Hoàn tất lập chỉ mục cho", legalChunks.length, "khối luật.");
}

preIndexChunks();

// --- ĐĂNG KÝ CÁC API ENDPOINTS ---

// API Health Check
app.get("/api/health", (req, res) => {
  res.json({ status: "ok", chunksLoaded: legalChunks.length });
});

// API Get Documents list
app.get("/api/documents", (req, res) => {
  const docsMap = new Map<string, { source: string; chunks: number; char_length: number }>();
  legalChunks.forEach(chunk => {
    const s = chunk.metadata.source;
    const current = docsMap.get(s) || { source: s, chunks: 0, char_length: 0 };
    current.chunks += 1;
    current.char_length += chunk.metadata.char_length;
    docsMap.set(s, current);
  });
  res.json(Array.from(docsMap.values()));
});

// API Upload Document động
app.post("/api/documents/upload", async (req, res) => {
  const { name, text } = req.body;
  if (!name || !text) {
    return res.status(400).json({ error: "Thiếu dữ liệu tệp tin" });
  }

  try {
    const cleanTxt = text.trim();
    
    // Tách văn bản tự động dựa trên từ khóa "Điều"
    // Sử dụng Regex lookahead để giữ lại nhãn "Điều ..." ở đầu mỗi phần tử
    const segments = cleanTxt.split(/(?=Điều\s+\d+)/gi).map((s: string) => s.trim()).filter((s: string) => s.length > 5);
    
    const partsToEmbed: { text: string; article: string }[] = [];
    
    if (segments.length > 1) {
      // Tự động phân tích từng Điều để làm metadata
      segments.forEach((seg, index) => {
        // Tìm tiêu đề Điều, e.g., "Điều 5. Quyền lợi người bệnh" hoặc "Điều 12: ..."
        const match = seg.match(/^(Điều\s+\d+[^.\n:]*)/i);
        const articleHeader = match ? match[1].trim() : `Điều bổ sung ${index + 1}`;
        partsToEmbed.push({
          text: seg,
          article: articleHeader,
        });
      });
    } else {
      // Nếu không có nhiều "Điều", thử tách theo đoạn văn (Double newline)
      const paragraphs = cleanTxt.split(/\n\s*\n/).map((p: string) => p.trim()).filter((p: string) => p.length > 10);
      if (paragraphs.length > 1) {
        paragraphs.forEach((p, index) => {
          partsToEmbed.push({
            text: p,
            article: `Đoạn thứ ${index + 1}`
          });
        });
      } else {
        // Tách theo sliding-window kích thước 600 ký tự
        if (cleanTxt.length > 600) {
          let currentIdx = 0;
          let partCount = 1;
          while (currentIdx < cleanTxt.length) {
            const chunkText = cleanTxt.substring(currentIdx, currentIdx + 600);
            partsToEmbed.push({
              text: chunkText,
              article: `Phân đoạn ${partCount++}`
            });
            currentIdx += 450;
          }
        } else {
          partsToEmbed.push({
            text: cleanTxt,
            article: "Văn bản bổ sung"
          });
        }
      }
    }

    const newCreatedChunks: LegalChunk[] = [];
    for (let i = 0; i < partsToEmbed.length; i++) {
      const part = partsToEmbed[i];
      const chunkId = legalChunks.length + 1;
      const embeddingVector = await getEmbedding(part.text);
      const newChunk: LegalChunk = {
        id: chunkId,
        text: part.text,
        metadata: {
          source: name,
          article: part.article,
          char_length: part.text.length
        },
        vector: embeddingVector
      };
      legalChunks.push(newChunk);
      newCreatedChunks.push(newChunk);
    }

    res.json({ success: true, addedChunksCount: newCreatedChunks.length });
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

// API chat RAG
app.post("/api/chat", async (req, res) => {
  const { question } = req.body;
  if (!question || typeof question !== "string") {
    return res.status(400).json({ error: "Cần cung cấp câu hỏi hợp lệ" });
  }

  const startTime = Date.now();
  try {
    // 1. Sinh vector cho câu hỏi người dùng
    const queryVector = await getEmbedding(question);

    // 2. Tính Cosine Similarity thô với toàn bộ kho lưu trữ
    const scoredChunks = legalChunks.map(chunk => {
      let score = 0;
      if (chunk.vector) {
        score = cosineSimilarity(queryVector, chunk.vector);
      }
      return { chunk, score };
    });

    // Sắp xếp giảm dần theo điểm tương đồng ngữ nghĩa
    scoredChunks.sort((a, b) => b.score - a.score);

    // Lọc lấy Top-5 tài liệu tốt nhất có score tối thiểu > 0.15
    const topK = 5;
    const retrieved = scoredChunks
      .slice(0, topK)
      .filter(item => item.score >= 0.15)
      .map(item => ({
        text: item.chunk.text,
        score: item.score,
        metadata: item.chunk.metadata
      }));

    const retrieveTime = (Date.now() - startTime) / 1000;

    // 3. Phối hợp Prompt và sinh câu trả lời bằng Gemini
    let answerText = "";
    const genStartTime = Date.now();

    if (retrieved.length === 0) {
      answerText = "Tôi không tìm thấy căn cứ pháp luật phù hợp trong cơ sở dữ liệu hiện có.";
    } else {
      // Tập hợp dữ liệu Luật làm bối cảnh
      let contextString = "";
      retrieved.forEach((item, index) => {
        contextString += `[${index + 1}] Nguồn: ${item.metadata.source} | ${item.metadata.article}\nNội dung: ${item.text}\n\n`;
      });

      const systemInstruction = 
        "Bạn là chuyên gia tư vấn pháp luật khám chữa bệnh chuyên nghiệp.\n" +
        "Chỉ được trả lời câu hỏi dựa trên các đoạn văn bản luật được truy xuất từ hệ thống RAG dưới đây.\n" +
        "Tuyệt đối không được tự suy diễn ngoài phạm vi tài liệu được cấp.\n" +
        "Nếu dữ liệu tài liệu truy xuất không chứa đựng hoặc không đủ căn cứ pháp lý thích hợp để trả lời câu hỏi, bạn PHẢI trả lời chính xác từ ngữ sau:\n" +
        "'Tôi không tìm thấy căn cứ pháp luật phù hợp trong cơ sở dữ liệu hiện có.'\n" +
        "Khi trả lời câu hỏi, mỗi câu trả lời phải nêu rõ:\n" +
        "- Tên Điều luật\n" +
        "- Khoản, Điểm\n" +
        "- Tên Văn bản pháp luật gốc\n" +
        "- Trích dẫn nội dung chính làm căn cứ pháp lý rõ ràng.";

      const finalPrompt = `Ngữ cảnh các tài liệu luật liên quan:\n${contextString}\n\nCâu hỏi: ${question}\n\nHãy phân tích và trả lời theo hướng dẫn hệ thống một cách chuẩn chỉ nhất.`;

      if (ai) {
        try {
          const geminiResponse = await ai.models.generateContent({
            model: "gemini-3.5-flash",
            contents: finalPrompt,
            config: {
              systemInstruction: systemInstruction,
              temperature: 0.1,
            }
          });
          answerText = geminiResponse.text || "Xin lỗi, tôi gặp lỗi khi sinh câu trả lời.";
        } catch (genErr) {
          console.error("Lỗi khi gọi Gemini Generate:", genErr);
          answerText = `Dựa trên tài liệu luật: ${retrieved[0].metadata.article} thuộc ${retrieved[0].metadata.source}:\n\n${retrieved[0].text}`;
        }
      } else {
        // Fallback Extractive RAG: Trích xuất điều luật tốt nhất trực tiếp nếu không cấu hình Gemini API Key
        answerText = `Dựa trên cơ sở dữ liệu pháp luật hiện có, tôi xin tư vấn về câu hỏi của bạn như sau:\n\n` +
          `**Căn cứ pháp lý:**\n` +
          `- **${retrieved[0].metadata.article}** thuộc **${retrieved[0].metadata.source}**\n\n` +
          `**Nội dung cụ thể:**\n` +
          `${retrieved[0].text.trim()}\n\n` +
          `--- \n` +
          `*Khuyến cáo: Bản tin được trích xuất hoàn toàn tự động trực tiếp trên căn cứ pháp lý thô có trong hệ sinh thái dữ liệu.*`;
      }
    }

    const generateTime = (Date.now() - genStartTime) / 1000;

    res.json({
      answer: answerText,
      chunks: retrieved,
      retrieve_time: retrieveTime,
      generate_time: generateTime
    });

  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

// Khởi tạo máy chủ Vite Middleware phục vụ giao diện React tuyệt đẹp
async function startViteServer() {
  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), "dist");
    app.use(express.static(distPath));
    app.get("*", (req, res) => {
      res.sendFile(path.join(distPath, "index.html"));
    });
  }

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`Ứng dụng đang phục vụ trực tiếp tại: http://localhost:${PORT}`);
  });
}

startViteServer();
