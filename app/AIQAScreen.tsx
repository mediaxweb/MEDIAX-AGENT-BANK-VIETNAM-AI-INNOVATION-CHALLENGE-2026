"use client";

import {
  Bot,
  Check,
  CheckCircle2,
  CircleStop,
  FileText,
  Network,
  RefreshCw,
  Send,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import AgentStage3D from "./AgentStage3D";
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
  kind: "user" | "progress" | "answer";
  text: string;
  confidence?: number;
  sources?: string[];
  activeAgents?: string[];
};

type MobileTab = "conversation" | "agents";

const agentNames: Record<string, string> = {
  orchestrator: "Điều phối viên AI",
  credit: "Chuyên gia tín dụng",
  compliance: "Chuyên gia tuân thủ",
  operations: "Chuyên gia vận hành",
};

const progressStages = [
  { title: "Phân rã yêu cầu", detail: "Điều phối viên xác định chuyên môn cần thiết" },
  { title: "Phân tích song song", detail: "Các chuyên gia tra cứu và đánh giá độc lập" },
  { title: "Kiểm tra chéo", detail: "Đội agent đối chiếu kết quả và bằng chứng" },
  { title: "Tổng hợp câu trả lời", detail: "Điều phối viên hoàn thiện kết luận có nguồn" },
];

const sourceExcerpts: Record<string, string> = {
  "Quy trình cấp tín dụng 2026.pdf": "Khoản cấp tín dụng doanh nghiệp phải được đánh giá đồng thời về năng lực trả nợ, tuân thủ và tính đầy đủ của hồ sơ.",
  "Chính sách chấm điểm tín dụng.pdf": "Khách hàng có điểm CIC từ 720 và không có nợ xấu được xếp vào nhóm rủi ro thấp đến trung bình.",
  "Báo cáo CIC khách hàng.pdf": "Điểm tín dụng 742; nhóm nợ hiện tại: Nhóm 1; không ghi nhận nợ quá hạn.",
  "Danh mục hồ sơ vay doanh nghiệp.docx": "Hồ sơ thẩm định tài chính cần có tờ khai thuế gần nhất và chứng từ đối chiếu dòng tiền.",
  "Danh mục kiểm tra KYC.pdf": "Thông tin định danh doanh nghiệp và người đại diện phải được xác minh trước khi hoàn tất thẩm định.",
};

const agentResults: Record<string, string> = {
  orchestrator: "Đã phân rã yêu cầu và giao việc theo chuyên môn.",
  credit: "CIC 742 và DTI 38,5% nằm trong ngưỡng kiểm soát.",
  compliance: "Không phát hiện cảnh báo KYC hoặc AML trọng yếu.",
  operations: "Cần bổ sung tờ khai thuế gần nhất.",
};

export default function AIQAScreen() {
  const [question, setQuestion] = useState(qaScenarios.assessment.question);
  const [messages, setMessages] = useState<QaMessage[]>([]);
  const [runStep, setRunStep] = useState(0);
  const [scenario, setScenario] = useState<QaScenario | null>(null);
  const [running, setRunning] = useState(false);
  const [stopped, setStopped] = useState(false);
  const [activeMobileTab, setActiveMobileTab] = useState<MobileTab>("conversation");
  const [selectedSource, setSelectedSource] = useState<string | null>(null);
  const [selectedSourceAgents, setSelectedSourceAgents] = useState<string[]>([]);
  const timeoutIdsRef = useRef<ReturnType<typeof setTimeout>[]>([]);
  const nextMessageIdRef = useRef(0);
  const sourceDialogRef = useRef<HTMLElement>(null);
  const sourceTriggerRef = useRef<HTMLButtonElement | null>(null);

  const isRunning = running && !stopped;
  const selectedAgent = runStep <= 1 ? "orchestrator" : runStep === 2 ? "credit" : runStep === 3 ? "compliance" : "operations";
  const sourceDocument = useMemo(
    () => documentRecords.find((document) => document.name === selectedSource),
    [selectedSource],
  );
  const sourceFolder = documentFolders.find((folder) => folder.id === sourceDocument?.folderId);

  const clearScheduledTimeouts = useCallback(() => {
    timeoutIdsRef.current.forEach((timeoutId) => clearTimeout(timeoutId));
    timeoutIdsRef.current = [];
  }, []);

  const appendMessage = useCallback((message: Omit<QaMessage, "id">) => {
    const id = nextMessageIdRef.current;
    nextMessageIdRef.current += 1;
    setMessages((currentMessages) => [...currentMessages, { ...message, id }]);
  }, []);

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
    if (!trimmedQuestion || isRunning) return;

    clearScheduledTimeouts();
    const nextScenario = selectQaScenario(trimmedQuestion);
    setScenario(nextScenario);
    setRunning(true);
    setStopped(false);
    setQuestion("");
    appendMessage({ kind: "user", text: trimmedQuestion });

    schedule(0, () => setRunStep(0));
    schedule(700, () => {
      setRunStep(1);
      appendMessage({ kind: "progress", text: "Điều phối viên đã phân rã yêu cầu và phân công cho các chuyên gia phù hợp." });
    });
    schedule(1500, () => {
      setRunStep(2);
      appendMessage({ kind: "progress", text: "Các chuyên gia đang phân tích song song dữ liệu tín dụng, tuân thủ và vận hành." });
    });
    schedule(2300, () => {
      setRunStep(3);
      appendMessage({ kind: "progress", text: "Đội agent đang kiểm tra chéo kết quả và đối chiếu nguồn bằng chứng." });
    });
    schedule(3100, () => {
      setRunStep(4);
      setRunning(false);
      appendMessage({
        kind: "answer",
        text: nextScenario.answer,
        confidence: nextScenario.confidence,
        sources: nextScenario.sources,
        activeAgents: nextScenario.activeAgents,
      });
    });
  }

  function stopRun() {
    if (!isRunning) return;
    clearScheduledTimeouts();
    setRunning(false);
    setStopped(true);
    appendMessage({ kind: "progress", text: "Tác vụ đã dừng theo yêu cầu. Tiến độ hiện tại được giữ lại." });
  }

  function resetConversation() {
    clearScheduledTimeouts();
    setQuestion(qaScenarios.assessment.question);
    setMessages([]);
    setRunStep(0);
    setScenario(null);
    setRunning(false);
    setStopped(false);
    setSelectedSource(null);
    setSelectedSourceAgents([]);
    setActiveMobileTab("conversation");
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
      "button:not([disabled]), [href], [tabindex]:not([tabindex=\"-1\"])",
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

  return <div className="qa-shell">
    <PageHeading title="Hỏi đáp AI đa-agent" subtitle="Đặt câu hỏi nghiệp vụ và theo dõi đội chuyên gia tự phối hợp xử lý">
      <Badge tone={stopped ? "warning" : isRunning ? "info" : "success"}>{stopped ? "Đã dừng" : isRunning ? "Đang xử lý" : "Sẵn sàng"}</Badge>
    </PageHeading>

    <div className="qa-mobile-tabs" role="tablist" aria-label="Khu vực hỏi đáp">
      <button type="button" role="tab" aria-controls="qa-conversation-panel" aria-selected={activeMobileTab === "conversation"} onClick={() => setActiveMobileTab("conversation")}>Hội thoại</button>
      <button type="button" role="tab" aria-controls="qa-agents-panel" aria-selected={activeMobileTab === "agents"} onClick={() => setActiveMobileTab("agents")}>Agent 3D</button>
    </div>

    <div className="qa-workspace">
      <section id="qa-conversation-panel" role="tabpanel" className={`qa-conversation card ${activeMobileTab === "conversation" ? "mobile-active" : ""}`} aria-label="Cuộc hội thoại">
        <div className="card-heading">
          <div><h2>Cuộc hội thoại</h2><p>Hỏi trên toàn bộ nguồn tri thức đã được cấp quyền</p></div>
          <Badge tone="success">Có trích dẫn nguồn</Badge>
        </div>

        <div className="qa-suggestions" aria-label="Câu hỏi gợi ý">
          <span>CÂU HỎI GỢI Ý</span>
          {Object.values(qaScenarios).map((item) => <button type="button" key={item.id} disabled={isRunning} onClick={() => setQuestion(item.question)}>{item.question}</button>)}
        </div>

        <div className="qa-messages" aria-live="polite" aria-label="Lịch sử hội thoại">
          {messages.length === 0 && <div className="qa-empty"><Sparkles size={24} /><strong>Bắt đầu hỏi đội chuyên gia AI</strong><p>Chọn một câu hỏi gợi ý hoặc nhập câu hỏi nghiệp vụ của bạn.</p></div>}
          {messages.map((message) => <article className={`qa-message ${message.kind}`} key={message.id}>
            <div className="qa-message-icon">{message.kind === "user" ? "TA" : message.kind === "answer" ? <Sparkles size={16} /> : <Network size={16} />}</div>
            <div>
              <strong>{message.kind === "user" ? "Bạn" : message.kind === "answer" ? "Đội chuyên gia AI" : "Cập nhật điều phối"}</strong>
              <p>{message.text}</p>
              {message.kind === "answer" && <>
                <div className="qa-answer-meta"><span><ShieldCheck size={15} /> Độ tin cậy <b>{message.confidence}%</b></span><span>{message.activeAgents?.length ?? 0} agent tham gia</span></div>
                <div className="qa-cited-sources"><span>NGUỒN TRÍCH DẪN</span>{message.sources?.map((source) => <button
                  type="button"
                  className="qa-source-link"
                  key={source}
                  onClick={(event) => openSourceOverlay(source, message.activeAgents ?? [], event.currentTarget)}
                ><FileText size={15} />{source}</button>)}</div>
              </>}
            </div>
          </article>)}
        </div>

        <form className="qa-composer" onSubmit={sendQuestion}>
          <label htmlFor="qa-question">Nhập câu hỏi nghiệp vụ</label>
          <textarea id="qa-question" value={question} disabled={isRunning} onChange={(event) => setQuestion(event.target.value)} placeholder="Ví dụ: Hồ sơ này có điểm rủi ro nào cần lưu ý?" />
          <div>
            <button type="button" className="button secondary" onClick={resetConversation}><RefreshCw size={16} /> Đặt lại</button>
            <button type="button" className="button danger" onClick={stopRun} disabled={!isRunning}><CircleStop size={16} /> Dừng</button>
            <Button disabled={!question.trim() || isRunning}><Send size={16} /> Gửi câu hỏi</Button>
          </div>
        </form>
      </section>

      <section id="qa-agents-panel" role="tabpanel" className={`qa-stage-panel card ${activeMobileTab === "agents" ? "mobile-active" : ""}`} aria-label="Trạng thái đội agent">
        <div className="card-heading">
          <div><h2>Đội agent đang phối hợp</h2><p aria-live="polite">{stopped ? `Đã dừng tại bước ${runStep}/4` : runStep === 4 ? "Đã hoàn thành câu trả lời" : runStep ? `Đang thực hiện bước ${runStep}/4` : "Sẵn sàng nhận yêu cầu"}</p></div>
          <Badge tone={stopped ? "warning" : runStep === 4 ? "success" : runStep ? "info" : "neutral"}>{stopped ? "Đã dừng" : runStep === 4 ? "Hoàn thành" : runStep ? "Đang chạy" : "Chờ"}</Badge>
        </div>

        <div className="qa-stage-visual">
          {/* Task 5 will switch this localized compatibility mode to `qa` and add Q&A-specific stage state. */}
          <AgentStage3D mode="builder" selected={selectedAgent} runStep={runStep} compact />
        </div>

        <ol className="qa-progress" aria-label="Bốn giai đoạn xử lý">
          {progressStages.map((stage, index) => {
            const step = index + 1;
            const state = runStep === 4 || runStep > step ? "done" : runStep === step ? stopped ? "stopped" : "active" : "waiting";
            return <li className={state} key={stage.title}><span>{runStep > step || runStep === 4 ? <Check size={14} /> : step}</span><div><strong>{stage.title}</strong><small>{state === "done" ? "Đã hoàn thành" : state === "active" ? "Đang xử lý" : state === "stopped" ? "Đã dừng tại đây" : stage.detail}</small></div></li>;
          })}
        </ol>

        <div className="qa-agent-results" aria-label="Kết quả theo agent">
          {(scenario?.activeAgents ?? ["orchestrator", "credit", "compliance", "operations"]).map((agent, index) => {
            const completed = runStep === 4 || runStep > Math.min(index + 1, 3);
            return <article key={agent}><span>{completed ? <CheckCircle2 size={16} /> : <Bot size={16} />}</span><div><strong>{agentNames[agent]}</strong><p>{completed ? agentResults[agent] : "Đang chờ kết quả phân tích"}</p></div></article>;
          })}
        </div>
      </section>
    </div>

    {selectedSource && <div className="qa-source-overlay">
      <button type="button" className="overlay" aria-label="Đóng chi tiết nguồn" onClick={closeSourceOverlay} />
      <section ref={sourceDialogRef} className="qa-source-panel card" tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby="qa-source-title">
        <div className="qa-source-header"><div><span>CHI TIẾT NGUỒN</span><h2 id="qa-source-title">{selectedSource}</h2></div><button type="button" aria-label="Đóng chi tiết nguồn" onClick={closeSourceOverlay}><X /></button></div>
        <dl>
          <div><dt>Danh mục</dt><dd>{sourceDocument?.type ?? "Tài liệu nghiệp vụ"}</dd></div>
          <div><dt>Thư mục</dt><dd>{sourceFolder?.name ?? "Kho tài liệu"}</dd></div>
          <div><dt>Cập nhật</dt><dd>{sourceDocument?.updatedAt ?? "15/07/2026"}</dd></div>
        </dl>
        <div className="qa-source-excerpt"><span>ĐOẠN TRÍCH</span><blockquote>{sourceExcerpts[selectedSource] ?? "Nguồn được đội chuyên gia sử dụng để đối chiếu và hoàn thiện kết luận."}</blockquote></div>
        <div className="qa-source-agents"><span>Được sử dụng bởi</span>{selectedSourceAgents.filter((agent) => sourceDocument?.allowedAgents.includes(agent) ?? true).map((agent) => <p key={agent}><CheckCircle2 size={15} />{agentNames[agent]}</p>)}</div>
      </section>
    </div>}
  </div>;
}
