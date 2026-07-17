"use client";

import {
  AlertCircle,
  ArrowUp,
  Bot,
  Check,
  CheckCircle2,
  FileText,
  LoaderCircle,
  Send,
  ShieldCheck,
  Sparkles,
  X,
  Compass,
  Zap,
  Activity,
  ChevronDown,
  ChevronRight,
  Eye,
  EyeOff,
  MessageSquare,
  Plus,
  Trash2,
  PanelRight,
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  documentFolders,
  documentRecords,
  qaScenarios,
  selectQaScenario,
  type QaScenario,
} from "./prototype-data";
import { Badge, Button, PageHeading } from "./ui";

type QaMessage = {
  id: number;
  kind: "user" | "answer";
  text: string;
  confidence?: number;
  sources?: string[];
  activeAgents?: string[];
};

const agentNames: Record<string, string> = {
  orchestrator: "Điều phối viên AI",
  credit: "Chuyên gia tín dụng",
  compliance: "Chuyên gia tuân thủ",
  operations: "Chuyên gia vận hành",
};

const scenarioThoughts: Record<string, string> = {
  assessment: "Yêu cầu đánh giá hồ sơ cấp tín dụng trị giá 2,5 tỷ đồng. Tôi sẽ lập kế hoạch phối hợp:\n1. Giao Chuyên gia tín dụng kiểm tra lịch sử CIC (742) và tính tỷ lệ DTI (38.5%).\n2. Giao Chuyên gia tuân thủ đối chiếu quy định KYC/AML và chính sách nội bộ.\n3. Giao Chuyên gia vận hành kiểm tra tính đầy đủ của hồ sơ vay doanh nghiệp.\nSau khi có kết quả độc lập, tôi sẽ kiểm tra chéo độ tin cậy và tổng hợp kết luận phê duyệt có điều kiện.",
  risk: "Yêu cầu rà soát các yếu tố rủi ro chính của hồ sơ vay. Phân công nhiệm vụ:\n1. Chuyên gia tín dụng đánh giá tỷ lệ DTI (38.5% đang gần ngưỡng cảnh báo 40%).\n2. Chuyên gia tuân thủ đối chiếu lịch sử tín dụng xem có nợ xấu tiềm ẩn không.\nTôi sẽ tổng hợp mức độ rủi ro tổng thể và các chênh lệch chính sách để đưa ra cảnh báo cho chuyên viên.",
  missing: "Yêu cầu kiểm tra các tài liệu còn thiếu trong hồ sơ. Phân công nhiệm vụ:\n1. Chuyên gia vận hành kiểm tra danh mục chứng từ bắt buộc cho khách hàng SME.\n2. Chuyên gia tuân thủ kiểm định trạng thái KYC của chủ doanh nghiệp.\nTôi sẽ so sánh với danh mục quy chuẩn để chỉ ra chính xác những chứng từ cần bổ túc trước khi trình ký.",
  sources: "Yêu cầu xác định nguồn căn cứ dùng để ra kết luận. Phân công nhiệm vụ:\n1. Các chuyên gia liệt kê các tài liệu quy trình tín dụng 2026, chính sách chấm điểm và báo cáo CIC đã sử dụng.\nTôi sẽ xuất danh sách tài liệu trích dẫn chi tiết làm cơ sở bằng chứng pháp lý."
};

const agentResults: Record<string, string> = {
  orchestrator: "Đã phân tách yêu cầu và lập kế hoạch phối hợp.",
  credit: "CIC 742, DTI 38.5% (đạt yêu cầu chính sách).",
  compliance: "Đạt chuẩn KYC & AML, không phát hiện rủi ro pháp lý.",
  operations: "Hồ sơ hợp lệ nhưng thiếu tờ khai thuế gần nhất.",
};

const sourceExcerpts: Record<string, string> = {
  "Quy trình cấp tín dụng 2026.pdf": "Khoản cấp tín dụng doanh nghiệp phải được đánh giá đồng thời về năng lực trả nợ, tuân thủ và tính đầy đủ của hồ sơ.",
  "Chính sách chấm điểm tín dụng.pdf": "Khách hàng có điểm CIC từ 720 và không có nợ xấu được xếp vào nhóm rủi ro thấp đến trung bình.",
  "Báo cáo CIC khách hàng.pdf": "Điểm tín dụng 742; nhóm nợ hiện tại: Nhóm 1; không ghi nhận nợ quá hạn.",
  "Danh mục hồ sơ vay doanh nghiệp.docx": "Hồ sơ thẩm định tài chính cần có tờ khai thuế gần nhất và chứng từ đối chiếu dòng tiền.",
  "Danh mục kiểm tra KYC.pdf": "Thông tin định danh doanh nghiệp và người đại diện phải được xác minh trước khi hoàn tất thẩm định.",
};

interface AIQAScreenProps {
  traceExpanded: boolean;
  setTraceExpanded: (val: boolean) => void;
  leftSidebarExpanded: boolean;
  setLeftSidebarExpanded: (val: boolean) => void;
  qaNavTrigger: number;
}

export default function AIQAScreen({ 
  traceExpanded, 
  setTraceExpanded,
  leftSidebarExpanded,
  setLeftSidebarExpanded,
  qaNavTrigger
}: AIQAScreenProps) {
  interface ChatSession {
    id: string;
    title: string;
    messages: QaMessage[];
    runStep: number;
    scenario: QaScenario | null;
  }

  const [sessions, setSessions] = useState<ChatSession[]>([
    {
      id: "session-2",
      title: "Kiểm tra tỷ lệ DTI",
      messages: [
        { id: 1, kind: "user", text: "Tỷ lệ nợ DTI 38.5% có vượt ngưỡng không?" },
        { id: 2, kind: "answer", text: "Tỷ lệ DTI 38.5% nằm trong ngưỡng cho phép (trần 40%), tuy nhiên đang ở mức cảnh báo cần theo dõi dòng tiền.", confidence: 91, activeAgents: ["credit", "compliance"], sources: ["Chính sách chấm điểm tín dụng.pdf"] }
      ],
      runStep: 4,
      scenario: qaScenarios.risk,
    },
    {
      id: "session-3",
      title: "Danh mục hồ sơ còn thiếu",
      messages: [
        { id: 1, kind: "user", text: "Hồ sơ vay doanh nghiệp đang thiếu chứng từ nào?" },
        { id: 2, kind: "answer", text: "Hồ sơ hiện tại đang thiếu tờ khai thuế gần nhất để làm căn cứ thẩm định doanh thu kinh doanh.", confidence: 95, activeAgents: ["operations"], sources: ["Danh mục hồ sơ vay doanh nghiệp.docx"] }
      ],
      runStep: 4,
      scenario: qaScenarios.missing,
    }
  ]);
  const [activeSessionId, setActiveSessionId] = useState("");
  const [question, setQuestion] = useState("");

  const hasAutoCreated = useRef(false);

  const [selectedSource, setSelectedSource] = useState<string | null>(null);
  const [selectedSourceAgents, setSelectedSourceAgents] = useState<string[]>([]);
  const [showThought, setShowThought] = useState(true);
  const [showStepLog, setShowStepLog] = useState(true);
  const [showAgentResults, setShowAgentResults] = useState(true);

  const timeoutIdsRef = useRef<ReturnType<typeof setTimeout>[]>([]);
  const nextMessageIdRef = useRef(0);
  const sourceDialogRef = useRef<HTMLElement>(null);
  const sourceTriggerRef = useRef<HTMLButtonElement | null>(null);
  const chatBottomRef = useRef<HTMLDivElement>(null);
  const questionInputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (questionInputRef.current) {
      questionInputRef.current.style.height = "auto";
      questionInputRef.current.style.height = `${questionInputRef.current.scrollHeight}px`;
    }
  }, [question]);

  const activeSession = useMemo(() => {
    return sessions.find(s => s.id === activeSessionId) || sessions[0];
  }, [sessions, activeSessionId]);

  const messages = activeSession.messages;
  const runStep = activeSession.runStep;
  const scenario = activeSession.scenario;

  useEffect(() => {
    if (chatBottomRef.current) {
      chatBottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [runStep]);

  const setRunStep = useCallback((step: number | ((s: number) => number)) => {
    setSessions(prev => prev.map(s => {
      if (s.id === activeSessionId) {
        const nextStep = typeof step === "function" ? step(s.runStep) : step;
        return { ...s, runStep: nextStep };
      }
      return s;
    }));
  }, [activeSessionId]);

  const setScenario = useCallback((sc: QaScenario | null) => {
    setSessions(prev => prev.map(s => {
      if (s.id === activeSessionId) {
        return { ...s, scenario: sc };
      }
      return s;
    }));
  }, [activeSessionId]);

  const setMessages = useCallback((updater: QaMessage[] | ((m: QaMessage[]) => QaMessage[])) => {
    setSessions(prev => prev.map(s => {
      if (s.id === activeSessionId) {
        const nextMessages = typeof updater === "function" ? updater(s.messages) : updater;
        return { ...s, messages: nextMessages };
      }
      return s;
    }));
  }, [activeSessionId]);

  const isProcessing = runStep > 0 && runStep < 4;
  const sourceDocument = useMemo(
    () => documentRecords.find((document) => document.name === selectedSource),
    [selectedSource],
  );
  const sourceFolder = documentFolders.find((folder) => folder.id === sourceDocument?.folderId);

  const clearScheduledTimeouts = useCallback(() => {
    timeoutIdsRef.current.forEach((timeoutId) => clearTimeout(timeoutId));
    timeoutIdsRef.current = [];
  }, []);

  const createNewSession = useCallback(() => {
    const newId = `session-${Date.now()}`;
    const newSession: ChatSession = {
      id: newId,
      title: `Hội thoại mới #${sessions.length + 1}`,
      messages: [],
      runStep: 0,
      scenario: null,
    };
    setSessions(prev => [newSession, ...prev]);
    setActiveSessionId(newId);
    clearScheduledTimeouts();
  }, [sessions.length, clearScheduledTimeouts]);

  useEffect(() => {
    if (!hasAutoCreated.current) {
      createNewSession();
      hasAutoCreated.current = true;
    }
  }, [createNewSession]);

  useEffect(() => {
    if (qaNavTrigger > 0) {
      createNewSession();
    }
  }, [qaNavTrigger, createNewSession]);

  const deleteSession = useCallback((id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (sessions.length <= 1) return;
    setSessions(prev => prev.filter(s => s.id !== id));
    if (activeSessionId === id) {
      const remaining = sessions.filter(s => s.id !== id);
      setActiveSessionId(remaining[0].id);
    }
    clearScheduledTimeouts();
  }, [sessions, activeSessionId, clearScheduledTimeouts]);

  const appendMessage = useCallback((message: Omit<QaMessage, "id">) => {
    const id = nextMessageIdRef.current;
    nextMessageIdRef.current += 1;
    setMessages((currentMessages) => [...currentMessages, { ...message, id }]);
  }, [setMessages]);

  const schedule = useCallback((delay: number, action: () => void) => {
    const timeoutId = setTimeout(() => {
      timeoutIdsRef.current = timeoutIdsRef.current.filter((currentId) => currentId !== timeoutId);
      action();
    }, delay);
    timeoutIdsRef.current.push(timeoutId);
  }, []);

  function sendQuestion(event?: FormEvent) {
    event?.preventDefault();
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion || isProcessing) return;

    clearScheduledTimeouts();
    const nextScenario = selectQaScenario(trimmedQuestion);
    setScenario(nextScenario);
    setRunStep(1);
    setQuestion("");
    appendMessage({ kind: "user", text: trimmedQuestion });

    schedule(2500, () => {
      setRunStep(2);
    });
    schedule(5500, () => {
      setRunStep(3);
    });
    schedule(8000, () => {
      setRunStep(4);
      appendMessage({
        kind: "answer",
        text: nextScenario.answer,
        confidence: nextScenario.confidence,
        sources: nextScenario.sources,
        activeAgents: nextScenario.activeAgents,
      });
    });
  }

  const closeSourceOverlay = useCallback(() => {
    setSelectedSource(null);
    setSelectedSourceAgents([]);
    window.requestAnimationFrame(() => sourceTriggerRef.current?.focus());
  }, []);

  function openSourceOverlay(source: string, activeAgents: string[], trigger: HTMLButtonElement) {
    sourceTriggerRef.current = trigger;
    setSelectedSource(source);
    setSelectedSourceAgents(activeAgents);
  }

  useEffect(() => clearScheduledTimeouts, [clearScheduledTimeouts]);

  useEffect(() => {
    if (!selectedSource) return;
    const dialog = sourceDialogRef.current;
    if (!dialog) return;

    const focusable = Array.from(dialog.querySelectorAll<HTMLElement>(
      "button:not([disabled]), [href], [tabindex]:not([tabindex=\"-1\"])"
    ));
    const firstFocusable = focusable[0];
    const lastFocusable = focusable.at(-1);
    (firstFocusable ?? dialog).focus();

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        closeSourceOverlay();
        return;
      }
      if (event.key !== "Tab" || !firstFocusable || !lastFocusable) return;
      if (event.shiftKey && document.activeElement === firstFocusable) {
        event.preventDefault();
        lastFocusable.focus();
      } else if (!event.shiftKey && document.activeElement === lastFocusable) {
        event.preventDefault();
        firstFocusable.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [closeSourceOverlay, selectedSource]);

  // Derived current thought for the active scenario
  const currentThought = useMemo(() => {
    if (!runStep || !scenario) return "";
    return scenarioThoughts[scenario.id] || scenarioThoughts.assessment;
  }, [runStep, scenario]);

  const getStepClass = (stepNum: number) => {
    if (runStep === 4 || runStep > stepNum) return "trace-step-item done";
    if (runStep === stepNum) return "trace-step-item active";
    return "trace-step-item waiting";
  };

  const getStepIcon = (stepNum: number) => {
    if (runStep === 4 || runStep > stepNum) {
      return <Check size={11} />;
    }
    if (runStep === stepNum) {
      return <LoaderCircle className="spinning" size={10} />;
    }
    return <span>{stepNum}</span>;
  };

  const getIconClass = (stepNum: number) => {
    if (runStep === 4 || runStep > stepNum) return "step-icon done";
    if (runStep === stepNum) return "step-icon pending";
    return "step-icon waiting";
  };

  const getStepStatusBadge = (stepNum: number) => {
    if (runStep === 4 || runStep > stepNum) {
      return <span style={{ fontSize: "9px", padding: "2px 6px", borderRadius: "4px", background: "rgba(0, 122, 90, 0.08)", color: "var(--green)", border: "1px solid rgba(0, 122, 90, 0.2)", fontWeight: "bold" }}>ĐÃ XONG</span>;
    }
    if (runStep === stepNum) {
      return <span style={{ fontSize: "9px", padding: "2px 6px", borderRadius: "4px", background: "rgba(18, 100, 163, 0.08)", color: "var(--blue)", border: "1px solid rgba(18, 100, 163, 0.2)", fontWeight: "bold", display: "inline-flex", alignItems: "center", gap: "4px" }}><span className="pulse-dot" />ĐANG CHẠY</span>;
    }
    return <span style={{ fontSize: "9px", padding: "2px 6px", borderRadius: "4px", background: "var(--elev)", color: "var(--muted)", border: "1px solid var(--border)", fontWeight: "bold" }}>ĐANG CHỜ</span>;
  };

  // SVG Coordinates for the Agent Interaction flow
  // Orchestrator (Top/Center): X=175, Y=35
  // Credit (Bottom/Left): X=45, Y=115
  // Compliance (Bottom/Center): X=175, Y=115
  // Operations (Bottom/Right): X=305, Y=115
  const getPathClass = (agentId: string) => {
    if (runStep >= 4) return "agent-link-path done";
    if (runStep === 2) return "agent-link-path active";
    if (runStep === 3) return "agent-link-path active-reverse";
    return "agent-link-path";
  };

  return (
    <div className="qa-shell">
      <style>{`
        .qa-workspace-container {
          display: grid;
          grid-template-columns: auto 1fr auto;
          gap: 16px;
          transition: grid-template-columns 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
          height: calc(100vh - 120px);
        }
        
        .qa-sessions-panel {
          display: flex;
          flex-direction: column;
          background: var(--side);
          border: 1px solid var(--border);
          border-radius: 12px;
          padding: 14px;
          gap: 12px;
          overflow: hidden;
          width: 240px;
          opacity: 1;
          transition: width 0.3s cubic-bezier(0.25, 0.8, 0.25, 1), 
                      opacity 0.2s ease, 
                      margin 0.3s cubic-bezier(0.25, 0.8, 0.25, 1),
                      border-color 0.3s ease,
                      padding 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
        }
        .qa-sessions-panel.collapsed {
          width: 0 !important;
          opacity: 0 !important;
          margin: 0 !important;
          border-color: transparent !important;
          padding: 0 !important;
          pointer-events: none;
        }
        .sessions-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 4px;
        }
        .sessions-header h3 {
          margin: 0;
          font-size: 13px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: var(--muted);
        }
        .new-session-btn {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 6px;
          background: rgba(74, 21, 75, 0.06);
          border: 1px dashed rgba(74, 21, 75, 0.25);
          color: var(--purple);
          padding: 8px 12px;
          border-radius: 8px;
          font-size: 13px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s ease;
        }
        .new-session-btn:hover {
          background: rgba(74, 21, 75, 0.12);
          border-color: rgba(74, 21, 75, 0.4);
          color: var(--purple);
        }
        .sessions-list {
          display: flex;
          flex-direction: column;
          gap: 6px;
          overflow-y: auto;
          flex: 1;
        }
        .session-item {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 8px 10px;
          border-radius: 6px;
          cursor: pointer;
          transition: all 0.2s ease;
          color: var(--muted);
          font-size: 14px;
          border: 1px solid transparent;
        }
        .session-item:hover {
          background: var(--elev);
          color: var(--text);
        }
        .session-item.active {
          background: rgba(74, 21, 75, 0.08);
          border-color: rgba(74, 21, 75, 0.15);
          color: var(--purple);
          font-weight: 600;
        }
        .session-title-text {
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          flex: 1;
          margin-right: 8px;
          text-align: left;
        }
        .delete-session-btn {
          border: 0;
          background: transparent;
          color: #64748b;
          cursor: pointer;
          padding: 2px;
          border-radius: 4px;
          opacity: 0;
          transition: opacity 0.2s, color 0.2s;
          display: flex;
          align-items: center;
          justify-content: center;
        }
        .session-item:hover .delete-session-btn {
          opacity: 1;
        }
        .delete-session-btn:hover {
          color: #ef4444;
          background: rgba(239, 68, 68, 0.1);
        }
        .qa-conversation {
          display: flex;
          flex-direction: column;
          border: 1px solid var(--border);
          background: var(--card);
          border-radius: 12px;
          transition: all 0.3s ease;
        }
        .qa-trace-panel {
          display: flex;
          flex-direction: column;
          background-color: var(--side);
          border: 1px solid var(--border);
          border-radius: 12px;
          overflow: hidden;
          width: 370px;
          opacity: 1;
          transition: width 0.3s cubic-bezier(0.25, 0.8, 0.25, 1), 
                      opacity 0.2s ease, 
                      margin 0.3s cubic-bezier(0.25, 0.8, 0.25, 1),
                      border-color 0.3s ease,
                      padding 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
        }
        .qa-trace-panel.collapsed {
          width: 0 !important;
          opacity: 0 !important;
          margin: 0 !important;
          border-color: transparent !important;
          padding: 0 !important;
          pointer-events: none;
        }
        
        /* Agent Visual Flow Diagram */
        .agent-diagram-wrapper {
          position: relative;
          height: 220px;
          background: var(--elev);
          border: 1px solid var(--border);
          border-radius: 8px;
          margin-bottom: 16px;
          overflow: hidden;
        }
        .agent-node {
          position: absolute;
          width: 46px;
          height: 46px;
          border-radius: 50%;
          background: var(--card);
          border: 2px solid var(--border);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 2;
          transition: all 0.3s ease;
          box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        }
        .agent-node strong {
          position: absolute;
          bottom: -18px;
          font-size: 11px;
          white-space: nowrap;
          color: var(--muted);
          font-weight: 600;
          letter-spacing: 0.03em;
        }
        .agent-node.active strong {
          color: var(--text);
        }
        .agent-node.orchestrator {
          top: 15px;
          left: calc(50% - 23px);
          color: #8b5cf6;
          border-color: #8b5cf6;
        }
        .agent-node.orchestrator.active {
          box-shadow: 0 0 20px rgba(139, 92, 246, 0.4);
          background: rgba(139, 92, 246, 0.1);
        }
        .agent-node.credit {
          top: 90px;
          left: calc(50% - 23px);
          color: var(--blue);
          border-color: var(--blue);
        }
        .agent-node.credit.active {
          box-shadow: 0 0 20px rgba(18, 100, 163, 0.4);
          background: rgba(18, 100, 163, 0.1);
        }
        .agent-node.compliance {
          bottom: 15px;
          left: 45px;
          color: var(--amber);
          border-color: var(--amber);
        }
        .agent-node.compliance.active {
          box-shadow: 0 0 20px rgba(236, 178, 46, 0.4);
          background: rgba(236, 178, 46, 0.1);
        }
        .agent-node.operations {
          bottom: 15px;
          right: 45px;
          color: var(--green);
          border-color: var(--green);
        }
        .agent-node.operations.active {
          box-shadow: 0 0 20px rgba(0, 122, 90, 0.4);
          background: rgba(0, 122, 90, 0.1);
        }
        
        .pulse-ring {
          position: absolute;
          top: -4px;
          left: -4px;
          right: -4px;
          bottom: -4px;
          border-radius: 50%;
          border: 2px solid currentColor;
          opacity: 0;
          pointer-events: none;
        }
        .agent-node.active .pulse-ring {
          animation: pulse-ring-animation 1.5s cubic-bezier(0.24, 0, 0.38, 1) infinite;
        }
        @keyframes pulse-ring-animation {
          0% { transform: scale(0.95); opacity: 0.8; }
          100% { transform: scale(1.35); opacity: 0; }
        }

        .agent-link-svg {
          position: absolute;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
          z-index: 1;
          pointer-events: none;
        }
        .agent-link-path {
          fill: none;
          stroke: var(--border);
          stroke-width: 2;
          stroke-dasharray: 4, 4;
          transition: all 0.3s ease;
        }
        .agent-link-path.active {
          stroke: #8b5cf6;
          animation: dash-forward 1.2s linear infinite;
        }
        .agent-link-path.done {
          stroke: var(--green);
          stroke-dasharray: none;
        }
        @keyframes dash-forward {
          to { stroke-dashoffset: -20; }
        }

        .agent-chat-container {
          display: flex;
          flex-direction: column;
          flex: 1;
          overflow: hidden;
        }
        .agent-chat-header {
          display: flex;
          justify-content: space-between;
          font-size: 11px;
          font-weight: 700;
          color: var(--muted);
          text-transform: uppercase;
          letter-spacing: 0.05em;
          padding: 16px 16px 12px 16px;
          border-bottom: 1px solid var(--border);
          flex-shrink: 0;
        }
        .agent-chat-list {
          flex: 1;
          overflow-y: auto;
          padding: 16px;
          display: flex;
          flex-direction: column;
          gap: 12px;
          scrollbar-width: thin;
        }
        .agent-chat-msg {
          display: flex;
          flex-direction: column;
          gap: 6px;
          background: var(--card);
          border: 1px solid var(--border);
          padding: 12px;
          border-radius: 8px;
          font-size: 13px;
        }
        .agent-chat-meta {
          display: flex;
          justify-content: space-between;
          color: var(--muted);
          font-size: 12px;
        }
        .agent-chat-meta strong {
          color: var(--text);
        }
        .agent-chat-text {
          color: var(--text);
          line-height: 1.4;
        }
        .agent-chat-status {
          display: flex;
          align-items: center;
          gap: 4px;
          font-weight: 600;
          font-size: 12px;
        }
        .agent-chat-status.done { color: var(--green); }
        .agent-chat-status.pending { color: var(--blue); }
        .agent-chat-status.warning { color: var(--amber); }

        /* Styling sections */
        .trace-scroll-area {
          flex: 1;
          overflow: hidden;
          display: flex;
          flex-direction: column;
        }
        .trace-collapsible-section {
          border: 1px solid var(--border);
          border-radius: 8px;
          background: var(--card);
          overflow: hidden;
        }
        .trace-collapsible-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 10px 12px;
          background: var(--bg);
          cursor: pointer;
          user-select: none;
          font-size: 13px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: var(--muted);
          border-bottom: 1px solid var(--border);
        }
        .trace-collapsible-header:hover {
          background: var(--elev);
          color: var(--text);
        }
        .trace-collapsible-body {
          padding: 12px;
          display: flex;
          flex-direction: column;
          gap: 12px;
        }
        
        .thought-block {
          margin: 0;
          padding: 10px;
          background-color: var(--elev);
          border-left: 3px solid var(--purple);
          border-radius: 4px;
          font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
          font-size: 14px;
          color: var(--purple);
          white-space: pre-wrap;
          line-height: 1.5;
        }
        
        .trace-steps {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }
        .trace-step-item {
          display: flex;
          gap: 12px;
          align-items: flex-start;
          padding: 12px 14px;
          border-radius: 8px;
          border: 1px solid transparent;
          transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
        }
        .trace-step-item.active {
          background: rgba(74, 21, 75, 0.06);
          border-color: rgba(74, 21, 75, 0.2);
          box-shadow: inset 3px 0 0 var(--purple), 0 4px 12px rgba(74, 21, 75, 0.04);
          transform: translateX(4px) scale(1.01);
        }
        .trace-step-item.waiting {
          opacity: 0.35;
        }
        .trace-step-item.done {
          opacity: 0.95;
          background: rgba(16, 185, 129, 0.02);
          border-color: rgba(16, 185, 129, 0.06);
        }
        .step-icon {
          width: 22px;
          height: 22px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 13px;
          font-weight: bold;
          flex-shrink: 0;
          transition: all 0.3s ease;
        }
        .step-icon.done {
          background-color: rgba(16, 185, 129, 0.15);
          color: #10b981;
          border: 1px solid rgba(16, 185, 129, 0.4);
        }
        .step-icon.pending {
          background-color: rgba(59, 130, 246, 0.15);
          color: #3b82f6;
          border: 1px solid rgba(59, 130, 246, 0.4);
        }
        .step-icon.waiting {
          background-color: rgba(100, 116, 139, 0.1);
          color: #64748b;
          border: 1px solid rgba(100, 116, 139, 0.25);
        }
        .trace-step-item div {
          display: flex;
          flex-direction: column;
          gap: 4px;
          flex: 1;
        }
        .trace-step-item strong {
          font-size: 13px;
          color: var(--text);
          font-weight: 600;
        }
        .trace-step-item.active strong {
          color: var(--purple);
        }
        .trace-step-item p {
          margin: 0;
          font-size: 14px;
          color: var(--muted);
          line-height: 1.4;
        }
        .subagent-badges {
          display: flex;
          flex-wrap: wrap;
          gap: 4px;
          margin-top: 4px;
        }
        .subagent-badge {
          font-size: 13px;
          padding: 1px 6px;
          border-radius: 3px;
          font-weight: 500;
        }
        .subagent-badge.credit {
          background-color: rgba(18, 100, 163, 0.08);
          color: var(--blue);
          border: 1px solid rgba(18, 100, 163, 0.2);
        }
        .subagent-badge.compliance {
          background-color: rgba(236, 178, 46, 0.08);
          color: #b45309;
          border: 1px solid rgba(236, 178, 46, 0.2);
        }
        .subagent-badge.operations {
          background-color: rgba(0, 122, 90, 0.08);
          color: var(--green);
          border: 1px solid rgba(0, 122, 90, 0.2);
        }

        .agent-finding-card {
          background-color: rgba(0,0,0,0.02);
          border: 1px solid var(--border);
          border-radius: 6px;
          padding: 8px 10px;
          display: flex;
          flex-direction: column;
          gap: 4px;
        }
        .agent-finding-card.credit { border-left: 3px solid var(--blue); }
        .agent-finding-card.compliance { border-left: 3px solid var(--amber); }
        .agent-finding-card.operations { border-left: 3px solid var(--green); }
        .agent-finding-card strong { font-size: 14px; color: var(--text); }
        .agent-finding-card p { margin: 0; font-size: 13px; color: var(--muted); line-height: 1.4; }

        .trace-empty-state {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          text-align: center;
          padding: 40px 16px;
          flex: 1;
          color: var(--muted);
          gap: 12px;
        }
        .trace-empty-state strong { color: var(--text); font-size: 14px; }
        .trace-empty-state p { margin: 0; font-size: 12px; line-height: 1.5; }

        .final-answer-loading-container {
          display: flex;
          flex-direction: column;
          gap: 6px;
          padding: 8px 0;
        }
        .skeleton-bar {
          height: 12px;
          background: linear-gradient(90deg, var(--elev) 25%, var(--border) 50%, var(--elev) 75%);
          background-size: 200% 100%;
          animation: loading-skeleton 1.5s infinite;
          border-radius: 3px;
          width: 100%;
        }
        .skeleton-bar.short { width: 60%; }
        @keyframes loading-skeleton {
          0% { background-position: 200% 0; }
          100% { background-position: -200% 0; }
        }
        
        .collapse-toggle-btn:hover {
          background-color: var(--elev) !important;
        }
        .pulse-dot {
          width: 6px;
          height: 6px;
          border-radius: 50%;
          background-color: #3b82f6;
          animation: pulse-dot-animation 0.8s infinite alternate;
          display: inline-block;
          box-shadow: 0 0 6px #3b82f6;
        }
        @keyframes pulse-dot-animation {
          from { opacity: 0.3; transform: scale(0.9); }
          to { opacity: 1; transform: scale(1.25); }
        }
        @media (max-width: 1024px) {
          .qa-workspace-container {
            grid-template-columns: 1fr !important;
          }
          .qa-sessions-panel {
            display: none;
          }
          .qa-trace-panel {
            min-height: auto;
          }
        }
      `}</style>

      <div className="qa-workspace-container">
        {/* Sessions Panel */}
        <section className={`qa-sessions-panel card ${!leftSidebarExpanded ? "collapsed" : ""}`}>
          <div className="sessions-header">
            <h3>Phiên hỏi đáp</h3>
            <Badge tone="info">{sessions.length}</Badge>
          </div>
          <button type="button" className="new-session-btn" onClick={createNewSession}>
            <Plus size={13} /> Tạo phiên mới
          </button>
          <div className="sessions-list">
            {sessions.map((session) => (
              <div
                key={session.id}
                className={`session-item ${session.id === activeSessionId ? "active" : ""}`}
                onClick={() => setActiveSessionId(session.id)}
              >
                <MessageSquare size={13} style={{ marginRight: "8px", flexShrink: 0, opacity: 0.7 }} />
                <span className="session-title-text">{session.title}</span>
                {sessions.length > 1 && (
                  <button
                    type="button"
                    className="delete-session-btn"
                    onClick={(e) => deleteSession(session.id, e)}
                    aria-label="Xóa phiên"
                  >
                    <Trash2 size={11} />
                  </button>
                )}
              </div>
            ))}
          </div>
        </section>

        {/* Center Column: Chat Conversation */}
        <section id="qa-conversation-panel" className="qa-conversation card">
          <div className="sessions-header" style={{ paddingBottom: "12px", borderBottom: "1px solid var(--border)", marginBottom: "16px" }}>
            <h3>Hỏi đáp với chuyên gia</h3>
            <Badge tone={messages.length > 0 ? "neutral" : "success"}>{messages.length > 0 ? `${messages.length} lượt` : "Phiên mới"}</Badge>
          </div>

          <div className="qa-messages" aria-live="polite" aria-label="Lịch sử hội thoại" style={{ flex: 1, minHeight: "360px" }}>
            {messages.length === 0 && (
              <div className="qa-empty">
                <Sparkles size={24} />
                <strong>Bắt đầu cuộc trò chuyện với Đội chuyên gia</strong>
                <p>Nhập câu hỏi tín dụng hoặc sử dụng câu hỏi mẫu bên dưới.</p>
              </div>
            )}

            {messages.map((message) => {
              const isUser = message.kind === "user";
              return (
                <article className={`qa-message ${message.kind}`} key={message.id}>
                  <div className="qa-message-icon">
                    {isUser ? "TA" : <Sparkles size={16} />}
                  </div>
                  <div>
                    <strong>{isUser ? "Bạn" : "Đội chuyên gia AI"}</strong>
                    <p style={{ lineHeight: "1.6", color: "var(--text)" }}>{message.text}</p>
                    {!isUser && (
                      <>
                        <div className="qa-answer-meta">
                          <span>
                            <ShieldCheck size={15} /> Độ tin cậy <b>{message.confidence}%</b>
                          </span>
                          <span>{message.activeAgents?.length ?? 0} chuyên gia tham gia</span>
                        </div>
                        <div className="qa-cited-sources">
                          <span>NGUỒN TRÍCH DẪN</span>
                          {message.sources?.map((source) => (
                            <button
                              type="button"
                              className="qa-source-link"
                              key={source}
                              onClick={(event) =>
                                openSourceOverlay(source, message.activeAgents ?? [], event.currentTarget)
                              }
                            >
                              <FileText size={15} />
                              {source}
                            </button>
                          ))}
                        </div>
                      </>
                    )}
                  </div>
                </article>
              );
            })}

            {isProcessing && (
              <article className="qa-message assistant">
                <div className="qa-message-icon">
                  <LoaderCircle className="spinning" size={16} />
                </div>
                <div style={{ width: "100%" }}>
                  <strong style={{ display: "block", marginBottom: "8px" }}>Đội chuyên gia AI đang phân tích dữ liệu...</strong>
                  <div className="final-answer-loading-container">
                    <div className="skeleton-bar" />
                    <div className="skeleton-bar short" />
                  </div>
                </div>
              </article>
            )}
          </div>

          <form className="qa-composer" onSubmit={sendQuestion}>
            <div className="qa-composer-inner">
              <textarea
                ref={questionInputRef}
                id="qa-question"
                value={question}
                disabled={isProcessing}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder="Nhập câu hỏi nghiệp vụ..."
                rows={1}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    if (question.trim() && !isProcessing) sendQuestion(e);
                  }
                }}
              />
              <button 
                type="submit" 
                className="qa-composer-send" 
                disabled={!question.trim() || isProcessing}
                aria-label="Gửi câu hỏi"
              >
                <ArrowUp size={20} />
              </button>
            </div>
            <div className="qa-composer-footer">
              Đội chuyên gia AI có thể mắc lỗi. Hãy kiểm tra các thông tin quan trọng.
            </div>
          </form>
        </section>

        {/* Right Column: Visual Orchestrator Control Panel */}
        <section 
          id="qa-agent-panel" 
          className={`qa-trace-panel card ${!traceExpanded ? "collapsed" : ""}`}
        >

            {!runStep ? (
              <div className="trace-empty-state">
                <Compass size={28} className="spinning" style={{ animationDuration: "12s" }} />
                <strong>Sẵn sàng phân rã & điều phối</strong>
                <p>Nhập câu hỏi ở khung chat bên trái. Sơ đồ tương tác và nhật ký phân tích nghiệp vụ của từng chuyên gia con sẽ được cập nhật trực quan tại đây.</p>
              </div>
            ) : (
              <div className="trace-scroll-area">
                {/* 2. Agent Inter-Communication Log */}
                <div className="agent-chat-container">
                  <div className="agent-chat-header">
                    <span>Trao đổi giữa các Chuyên gia</span>
                    <span>{runStep === 4 ? "6 lượt" : (runStep === 3 ? "5 lượt" : (runStep === 2 ? "3 lượt" : (runStep === 1 ? "1 lượt" : "0 lượt")))}</span>
                  </div>
                  
                  <div className="agent-chat-list">
                    {runStep >= 1 && (
                    <div className="agent-chat-msg">
                      <div className="agent-chat-meta">
                        <span><strong>RAG / Điều phối</strong> → <strong>Chuyên gia Tín dụng</strong></span>
                        <span>02:14:03</span>
                      </div>
                      <div className="agent-chat-text">
                        Hãy đánh giá khả năng cấp khoản vay 2,5 tỷ dựa trên hồ sơ khách hàng, CIC và tỷ lệ DTI.
                      </div>
                      <div className="agent-chat-status done">
                        <Check size={14} /> Đã chuyển yêu cầu
                      </div>
                    </div>
                  )}

                  {runStep >= 2 && (
                    <div className="agent-chat-msg">
                      <div className="agent-chat-meta">
                        <span><strong>Chuyên gia Tín dụng</strong> → <strong>Chuyên gia Tuân thủ</strong></span>
                        <span>02:14:05</span>
                      </div>
                      <div className="agent-chat-text">
                        Kiểm tra trạng thái KYC/AML và các điều kiện hạn chế cấp tín dụng.
                      </div>
                      <div className={runStep >= 3 ? "agent-chat-status done" : "agent-chat-status pending"}>
                        {runStep >= 3 ? <><Check size={14} /> Hoàn thành</> : <><LoaderCircle size={14} className="spinning"/> Đang xử lý</>}
                      </div>
                    </div>
                  )}

                  {runStep >= 2 && (
                    <div className="agent-chat-msg">
                      <div className="agent-chat-meta">
                        <span><strong>Chuyên gia Tín dụng</strong> → <strong>Chuyên gia Vận hành</strong></span>
                        <span>02:14:05</span>
                      </div>
                      <div className="agent-chat-text">
                        Kiểm tra tính đầy đủ của hồ sơ và đối chiếu báo cáo tài chính.
                      </div>
                      <div className={runStep >= 3 ? "agent-chat-status done" : "agent-chat-status pending"}>
                        {runStep >= 3 ? <><Check size={14} /> Hoàn thành</> : <><LoaderCircle size={14} className="spinning"/> Đang xử lý</>}
                      </div>
                    </div>
                  )}

                  {runStep >= 3 && (
                    <div className="agent-chat-msg">
                      <div className="agent-chat-meta">
                        <span><strong>Chuyên gia Tuân thủ</strong> → <strong>Chuyên gia Tín dụng</strong></span>
                        <span>02:14:07</span>
                      </div>
                      <div className="agent-chat-text">
                        Không phát hiện cảnh báo KYC/AML. Khách hàng đáp ứng điều kiện tuân thủ.
                      </div>
                      <div className="agent-chat-status done">
                        <Check size={14} /> Đã phản hồi
                      </div>
                    </div>
                  )}

                  {runStep >= 3 && (
                    <div className="agent-chat-msg">
                      <div className="agent-chat-meta">
                        <span><strong>Chuyên gia Vận hành</strong> → <strong>Chuyên gia Tín dụng</strong></span>
                        <span>02:14:08</span>
                      </div>
                      <div className="agent-chat-text">
                        Hồ sơ cơ bản đầy đủ. Cần bổ sung sao kê tài khoản trong 3 tháng gần nhất.
                      </div>
                      <div className="agent-chat-status warning">
                        <AlertCircle size={14} /> Cần bổ sung
                      </div>
                    </div>
                  )}

                  {runStep >= 4 && (
                    <div className="agent-chat-msg">
                      <div className="agent-chat-meta">
                        <span><strong>Chuyên gia Tín dụng</strong> → <strong>RAG / Điều phối</strong></span>
                        <span>02:14:10</span>
                      </div>
                      <div className="agent-chat-text">
                        CIC 742 và DTI 38,5% nằm trong ngưỡng cho phép. Đề xuất phê duyệt có điều kiện.
                      </div>
                      <div className="agent-chat-status done">
                        <Check size={14} /> Đã tổng hợp
                      </div>
                    </div>
                  )}
                  <div ref={chatBottomRef} />
                </div>
              </div>
            </div>
            )}
          </section>
      </div>

      {selectedSource && (
        <div className="qa-source-overlay">
          <button type="button" className="overlay" aria-label="Đóng chi tiết nguồn" onClick={closeSourceOverlay} />
          <section ref={sourceDialogRef} className="qa-source-panel card" tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby="qa-source-title">
            <div className="qa-source-header">
              <div>
                <span>CHI TIẾT NGUỒN</span>
                <h2 id="qa-source-title">{selectedSource}</h2>
              </div>
              <button type="button" aria-label="Đóng chi tiết nguồn" onClick={closeSourceOverlay}>
                <X />
              </button>
            </div>
            <dl>
              <div>
                <dt>Danh mục</dt>
                <dd>{sourceDocument?.type ?? "Tài liệu nghiệp vụ"}</dd>
              </div>
              <div>
                <dt>Thư mục</dt>
                <dd>{sourceFolder?.name ?? "Kho tài liệu"}</dd>
              </div>
              <div>
                <dt>Cập nhật</dt>
                <dd>{sourceDocument?.updatedAt ?? "15/07/2026"}</dd>
              </div>
            </dl>
            <div className="qa-source-excerpt">
              <span>ĐOẠN TRÍCH</span>
              <blockquote>
                {sourceExcerpts[selectedSource] ?? "Nguồn được đội chuyên gia sử dụng để đối chiếu và hoàn thiện kết luận."}
              </blockquote>
            </div>
            <div className="qa-source-agents">
              <span>Được sử dụng bởi</span>
              {selectedSourceAgents
                .filter((agent) => sourceDocument?.allowedAgents.includes(agent) ?? true)
                .map((agent) => (
                  <p key={agent}>
                    <CheckCircle2 size={15} />
                    {agentNames[agent]}
                  </p>
                ))}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
