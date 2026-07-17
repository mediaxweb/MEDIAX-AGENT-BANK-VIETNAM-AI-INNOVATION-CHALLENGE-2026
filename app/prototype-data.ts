export interface DocumentFolder {
  id: string;
  name: string;
  count: number;
}

export interface DocumentRecord {
  id: string;
  name: string;
  folderId: string;
  type: string;
  updatedAt: string;
  size: string;
  status: string;
  allowedAgents: string[];
}

export type UploadStage = "Đang tải" | "Đang phân loại" | "Đang lập chỉ mục" | "Sẵn sàng";

export interface QaScenario {
  id: "assessment" | "risk" | "missing" | "sources";
  question: string;
  answer: string;
  confidence: number;
  activeAgents: string[];
  sources: string[];
}

export const documentFolders: DocumentFolder[] = [
  { id: "all", name: "Tất cả tài liệu", count: 8 },
  { id: "credit", name: "Tín dụng doanh nghiệp", count: 3 },
  { id: "compliance", name: "Tuân thủ và pháp lý", count: 2 },
  { id: "operations", name: "Vận hành hồ sơ", count: 1 },
  { id: "forms", name: "Biểu mẫu nghiệp vụ", count: 1 },
  { id: "archive", name: "Tài liệu lưu trữ", count: 1 },
];

export const documentRecords: DocumentRecord[] = [
  {
    id: "credit-process-2026",
    name: "Quy trình cấp tín dụng 2026.pdf",
    folderId: "credit",
    type: "Quy trình",
    updatedAt: "15/07/2026",
    size: "4,8 MB",
    status: "Sẵn sàng",
    allowedAgents: ["orchestrator", "credit", "compliance", "operations"],
  },
  {
    id: "credit-scoring-policy",
    name: "Chính sách chấm điểm tín dụng.pdf",
    folderId: "credit",
    type: "Chính sách",
    updatedAt: "08/07/2026",
    size: "3,6 MB",
    status: "Sẵn sàng",
    allowedAgents: ["orchestrator", "credit", "compliance"],
  },
  {
    id: "cic-report",
    name: "Báo cáo CIC khách hàng.pdf",
    folderId: "credit",
    type: "Báo cáo",
    updatedAt: "14/07/2026",
    size: "1,7 MB",
    status: "Sẵn sàng",
    allowedAgents: ["orchestrator", "credit"],
  },
  {
    id: "collateral-policy",
    name: "Quy định tài sản bảo đảm.pdf",
    folderId: "compliance",
    type: "Chính sách",
    updatedAt: "12/07/2026",
    size: "2,1 MB",
    status: "Sẵn sàng",
    allowedAgents: ["orchestrator", "credit", "compliance"],
  },
  {
    id: "kyc-checklist",
    name: "Danh mục kiểm tra KYC.pdf",
    folderId: "compliance",
    type: "Biểu mẫu",
    updatedAt: "10/07/2026",
    size: "860 KB",
    status: "Sẵn sàng",
    allowedAgents: ["orchestrator", "compliance", "operations"],
  },
  {
    id: "application-checklist",
    name: "Danh mục hồ sơ vay doanh nghiệp.docx",
    folderId: "operations",
    type: "Biểu mẫu",
    updatedAt: "09/07/2026",
    size: "540 KB",
    status: "Đang xử lý",
    allowedAgents: ["orchestrator", "operations"],
  },
  {
    id: "loan-fees",
    name: "Biểu phí tín dụng doanh nghiệp.pdf",
    folderId: "forms",
    type: "Dữ liệu tham chiếu",
    updatedAt: "01/07/2026",
    size: "1,2 MB",
    status: "Sẵn sàng",
    allowedAgents: ["orchestrator", "credit", "operations"],
  },
  {
    id: "credit-policy-2024",
    name: "Chính sách tín dụng 2024.pdf",
    folderId: "archive",
    type: "Chính sách",
    updatedAt: "22/12/2024",
    size: "5,4 MB",
    status: "Hết hiệu lực",
    allowedAgents: ["orchestrator"],
  },
];

export const uploadStages: UploadStage[] = ["Đang tải", "Đang phân loại", "Đang lập chỉ mục", "Sẵn sàng"];

export const qaScenarios: Record<QaScenario["id"], QaScenario> = {
  assessment: {
    id: "assessment",
    question: "Đánh giá khả năng vay 2,5 tỷ đồng của khách hàng doanh nghiệp này.",
    answer: "Đội chuyên gia đề xuất phê duyệt có điều kiện. Điểm CIC 742 và DTI 38,5% nằm trong ngưỡng cho phép, nhưng hồ sơ cần bổ sung tờ khai thuế gần nhất trước khi ra quyết định.",
    confidence: 87,
    activeAgents: ["orchestrator", "credit", "compliance", "operations"],
    sources: ["Quy trình cấp tín dụng 2026.pdf", "Chính sách chấm điểm tín dụng.pdf", "Báo cáo CIC khách hàng.pdf"],
  },
  risk: {
    id: "risk",
    question: "Điểm rủi ro chính của hồ sơ là gì?",
    answer: "DTI 38,5% đang gần ngưỡng kiểm soát và cần đối chiếu thêm dòng tiền trước khi phê duyệt.",
    confidence: 84,
    activeAgents: ["orchestrator", "credit", "compliance"],
    sources: ["Báo cáo CIC khách hàng.pdf", "Chính sách chấm điểm tín dụng.pdf"],
  },
  missing: {
    id: "missing",
    question: "Hồ sơ đang thiếu tài liệu nào?",
    answer: "Hồ sơ cần bổ sung tờ khai thuế gần nhất để hoàn tất kiểm tra năng lực tài chính.",
    confidence: 92,
    activeAgents: ["orchestrator", "operations", "compliance"],
    sources: ["Danh mục hồ sơ vay doanh nghiệp.docx", "Danh mục kiểm tra KYC.pdf"],
  },
  sources: {
    id: "sources",
    question: "Chính sách nào được dùng để đưa ra kết luận?",
    answer: "Kết luận sử dụng quy trình cấp tín dụng 2026, chính sách chấm điểm tín dụng và báo cáo CIC khách hàng.",
    confidence: 89,
    activeAgents: ["orchestrator", "credit", "compliance"],
    sources: ["Quy trình cấp tín dụng 2026.pdf", "Chính sách chấm điểm tín dụng.pdf", "Báo cáo CIC khách hàng.pdf"],
  },
};

export function filterDocuments(
  records: DocumentRecord[],
  folderId: string,
  type: string,
  query: string,
): DocumentRecord[] {
  const normalizedQuery = query.trim().toLocaleLowerCase("vi");

  return records.filter((record) => {
    const matchesFolder = folderId === "all" || record.folderId === folderId;
    const matchesType = type === "Tất cả" || record.type === type;
    const searchableText = `${record.name} ${record.type}`.toLocaleLowerCase("vi");
    const matchesQuery = !normalizedQuery || searchableText.includes(normalizedQuery);
    return matchesFolder && matchesType && matchesQuery;
  });
}

export function selectQaScenario(question: string): QaScenario {
  const normalizedQuestion = question.toLocaleLowerCase("vi");

  if (normalizedQuestion.includes("rủi ro")) return qaScenarios.risk;
  if (normalizedQuestion.includes("thiếu")) return qaScenarios.missing;
  if (/chính sách|nguồn/u.test(normalizedQuestion)) return qaScenarios.sources;
  return qaScenarios.assessment;
}
