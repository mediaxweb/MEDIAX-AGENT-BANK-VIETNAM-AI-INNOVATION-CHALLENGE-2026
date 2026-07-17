"use client";

import {
  Activity, AlertTriangle, ArrowLeft, Bell, BookOpen, Bot, Box, Building2,
  Check, CheckCircle2, ChevronDown, ChevronLeft, ChevronRight, CircleDollarSign, Clock3,
  Database, FileCheck2, FileText, Filter, GitBranch, KeyRound, LayoutDashboard, LibraryBig,
  Link2, ListChecks, LockKeyhole, Maximize2, Menu, MessagesSquare, MessageSquareText, MoreHorizontal,
  Network, PanelLeft, PanelLeftClose, PanelRight, Play, Plus, RefreshCw, Search, Settings2, ShieldCheck,
  SlidersHorizontal, Sparkles, TestTube2, Upload, UserCheck, Users, Wrench, X,
  ZoomIn, ZoomOut
} from "lucide-react";
import { lazy, Suspense, useEffect, useState } from "react";
import DocumentsScreen from "./DocumentsScreen";
import { Badge, Button, PageHeading } from "./ui";

const AgentStage3D = lazy(() => import("./AgentStage3D"));
const AIQAScreen = lazy(() => import("./AIQAScreen"));

type Screen = "agents" | "documents" | "qa" | "team" | "run" | "comparison";
type DetailTab = "overview" | "knowledge" | "tools" | "playground";

const agents = [
  { name: "Chuyên gia tín dụng", role: "Thẩm định năng lực tài chính và điểm tín dụng", docs: 682, tools: 8, color: "blue", icon: CircleDollarSign, updated: "12 phút trước" },
  { name: "Chuyên gia tuân thủ", role: "Kiểm soát tuân thủ pháp lý KYC & AML", docs: 945, tools: 6, color: "amber", icon: ShieldCheck, updated: "28 phút trước" },
  { name: "Chuyên gia vận hành", role: "Kiểm tra hồ sơ và đề xuất luồng nghiệp vụ", docs: 310, tools: 10, color: "green", icon: FileCheck2, updated: "1 giờ trước" },
  { name: "Điều phối viên AI", role: "Phân rã yêu cầu và lập kế hoạch phối hợp", docs: 120, tools: 5, color: "purple", icon: Network, updated: "2 giờ trước" },
];

const nav = [
  { label: "Hỏi đáp AI", icon: MessagesSquare, screen: "qa" as Screen },
  { label: "Kho tri thức", icon: LibraryBig, screen: "documents" as Screen },
  { label: "Đội chuyên gia AI", icon: Users, screen: "team" as Screen },
];


export default function Home() {
  const [screen, setScreen] = useState<Screen>("qa");
  const [selectedNode, setSelectedNode] = useState("credit");
  const [traceDrawer, setTraceDrawer] = useState(false);
  const [approval, setApproval] = useState(false);
  const [acknowledged, setAcknowledged] = useState(false);
  const [approved, setApproved] = useState(false);
  const [workflowRun, setWorkflowRun] = useState(0);
  const [mobileNav, setMobileNav] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [traceExpanded, setTraceExpanded] = useState(true);
  const [leftSidebarExpanded, setLeftSidebarExpanded] = useState(true);
  const [qaNavTrigger, setQaNavTrigger] = useState(0);


  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash.replace("#", "") as Screen;
      const validScreens: Screen[] = ["qa", "documents", "team", "run", "comparison", "agents"];
      if (validScreens.includes(hash)) {
        setScreen(hash);
      } else {
        window.location.hash = "qa";
      }
    };

    handleHashChange();

    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  const pageTitles: Record<Screen, string> = {
    agents: "Tổng quan",
    documents: "Kho tri thức",
    qa: "Hỏi đáp AI",
    team: "Đội chuyên gia AI",
    run: "Hồ sơ trình diễn",
    comparison: "So sánh hiệu quả",
  };
  const pageTitle = pageTitles[screen];

  function navigate(next: Screen) {
    window.location.hash = next;
    setMobileNav(false);
  }

  const handleMenuClick = (itemScreen: Screen) => {
    if (itemScreen === "qa") {
      setQaNavTrigger((prev) => prev + 1);
    }
    navigate(itemScreen);
  };

  function runWorkflow() {
    setWorkflowRun(1);
    setTimeout(() => setWorkflowRun(2), 700);
    setTimeout(() => setWorkflowRun(3), 1500);
    setTimeout(() => setWorkflowRun(4), 2300);
  }

  return (
    <main className="app-shell">
      <aside className={`sidebar ${sidebarCollapsed ? "collapsed" : ""} ${mobileNav ? "open" : ""}`}>
        <div className="brand" style={{ position: "relative" }}>
          <div className="brand-mark"><Sparkles size={18} /></div>
          {!sidebarCollapsed && <div><strong>MediaX</strong><span>Agent Bank</span></div>}
          <button 
            type="button" 
            className="sidebar-toggle-btn" 
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            aria-label={sidebarCollapsed ? "Mở rộng thanh menu" : "Thu gọn thanh menu"}
          >
            {sidebarCollapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
          </button>
        </div>
        <nav>
          {nav.map((item) => <button key={item.label} className={screen === item.screen ? "active" : ""} onClick={() => handleMenuClick(item.screen)}><item.icon size={18} />{!sidebarCollapsed && <span>{item.label}</span>}{item.label === "Hồ sơ trình diễn" && !sidebarCollapsed && <b>1</b>}</button>)}
        </nav>
        <div className="sidebar-bottom">
          <div className="profile">
            <div className="avatar">TA</div>
            {!sidebarCollapsed && <div><strong>Trần Minh Anh</strong><small>Chuyên viên tín dụng</small></div>}
            {!sidebarCollapsed && <MoreHorizontal size={18} />}
          </div>
        </div>
      </aside>

      <section className={`app-main ${sidebarCollapsed ? "collapsed" : ""}`}>
        <header className="topbar">
          <button className="mobile-menu" onClick={() => setMobileNav(!mobileNav)}><Menu size={20} /></button>
          <div className="breadcrumb"><span>MediaX Agent Bank</span><ChevronRight size={14} /><strong>{pageTitle}</strong></div>
          <div className="top-actions">
          </div>
        </header>

        <div className="content">
          {screen === "agents" && <AgentsScreen onStart={() => navigate("team")} onOpenCase={() => navigate("run")} />}
          {screen === "documents" && <DocumentsScreen />}
          {screen === "qa" && <Suspense fallback={<div className="agent-stage-fallback">Đang chuẩn bị hỏi đáp AI...</div>}><AIQAScreen traceExpanded={traceExpanded} setTraceExpanded={setTraceExpanded} leftSidebarExpanded={leftSidebarExpanded} setLeftSidebarExpanded={setLeftSidebarExpanded} /></Suspense>}
          {screen === "team" && <TeamScreen selected={selectedNode} setSelected={setSelectedNode} run={workflowRun} onRun={runWorkflow} onOpenRun={() => navigate("run")} />}
          {screen === "run" && <RunScreen openTrace={() => setTraceDrawer(true)} openApproval={() => { setApproval(true); setApproved(false); setAcknowledged(false); }} />}
          {screen === "comparison" && <ComparisonScreen onRun={() => navigate("run")} />}
        </div>
      </section>

      {traceDrawer && <TraceDrawer onClose={() => setTraceDrawer(false)} />}
      {approval && <ApprovalModal acknowledged={acknowledged} setAcknowledged={setAcknowledged} approved={approved} onApprove={() => setApproved(true)} onClose={() => setApproval(false)} />}
    </main>
  );
}

function AgentsScreen({ onStart, onOpenCase }: { onStart: () => void; onOpenCase: () => void }) {
  const responsibilities = [
    ["Phân rã yêu cầu", "Phân công và tổng hợp kết quả"],
    ["Thẩm định tín dụng", "Tra cứu CIC và tính DTI"],
    ["Kiểm soát tuân thủ", "Đối chiếu KYC, AML và quy định"],
    ["Kiểm tra vận hành", "Xác minh hồ sơ và đề xuất hành động"],
  ];
  const orderedAgents = [agents[3], agents[0], agents[1], agents[2]];
  return <>
    <PageHeading title="Đội chuyên gia AI nghiệp vụ" subtitle="Thẩm định hồ sơ tín dụng tự động qua hệ thống đa tác nhân">
      <Button onClick={onStart}><Play size={16} /> Bắt đầu trình diễn</Button>
    </PageHeading>
    <section className="problem-banner card">
      <div className="problem-badge"><Sparkles /></div>
      <div><span>BÀI TOÁN TRÌNH DIỄN</span><h2>Đánh giá hồ sơ vay doanh nghiệp 2,5 tỷ đồng</h2><p>Tự động phân rã nhiệm vụ, truy xuất dữ liệu độc lập và đối chiếu chéo chính sách cấp tín dụng.</p></div>
      <div className="problem-outcome"><small>KẾT QUẢ MONG ĐỢI</small><strong>Phê duyệt có điều kiện</strong><span>Chuyên viên quyết định cuối cùng</span></div>
    </section>
    <div className="section-title"><div><h2>Đội chuyên gia tham gia</h2><span>4 vai trò phối hợp</span></div><Badge tone="success">Sẵn sàng</Badge></div>
    <section className="agent-grid focused">
      {orderedAgents.map((agent, index) => <article className="agent-card card" key={agent.name}>
        <div className="agent-card-top"><span className={`agent-icon ${agent.color}`}><agent.icon size={22} /></span><Badge tone="success">Sẵn sàng</Badge><span className="agent-order">0{index + 1}</span></div>
        <h3>{agent.name}</h3><p>{agent.role}</p>
        <div className="responsibility"><small>NHIỆM VỤ CHÍNH</small><strong>{responsibilities[index][0]}</strong><span>{responsibilities[index][1]}</span></div>
        <div className="agent-evidence"><CheckCircle2 /> Mọi kết luận đều kèm nguồn đối chiếu</div>
      </article>)}
    </section>
    <section className="demo-flow card">
      {["Tiếp nhận hồ sơ", "Điều phối phân rã", "3 chuyên gia xử lý song song", "Kiểm tra chéo", "Chuyên viên phê duyệt"].map((step, index) => <div key={step}><span>{index + 1}</span><strong>{step}</strong>{index < 4 && <ChevronRight />}</div>)}
    </section>
  </>;
}

function ComparisonScreen({ onRun }: { onRun: () => void }) {
  const rows = [
    ["Khả năng phân rã nhiệm vụ", "Một luồng trả lời", "Điều phối theo chuyên môn", 35, 92],
    ["Kiểm tra chéo kết quả", "Không có", "Ba chuyên gia đối chiếu", 18, 88],
    ["Bằng chứng nghiệp vụ", "Nguồn tổng quát", "Nguồn riêng theo lĩnh vực", 42, 94],
    ["Khả năng thực hiện hành động", "Chỉ đề xuất", "Tra cứu và tạo yêu cầu", 30, 86],
  ];
  return <>
    <PageHeading title="So sánh hiệu quả xử lý" subtitle="Kết quả mô phỏng trên cùng hồ sơ HS-2026-0182"><Button onClick={onRun}><Play size={16} /> Xem đội AI xử lý</Button></PageHeading>
    <section className="comparison-summary">
      <div className="card"><span>AI đơn lẻ</span><strong>58%</strong><small>Mức độ hoàn chỉnh</small></div>
      <div className="versus">SO VỚI</div>
      <div className="card highlighted"><span>Đội chuyên gia AI</span><strong>91%</strong><small>Mức độ hoàn chỉnh</small></div>
      <div className="card improvement"><Activity /><strong>+33 điểm</strong><small>Nhờ phân công và kiểm tra chéo</small></div>
    </section>
    <section className="comparison-table card"><div className="comparison-head"><span>TIÊU CHÍ</span><span>AI ĐƠN LẺ</span><span>ĐỘI CHUYÊN GIA AI</span><span>SO SÁNH</span></div>{rows.map((row) => <div className="comparison-row" key={String(row[0])}><strong>{row[0]}</strong><span>{row[1]}</span><span className="team-value"><CheckCircle2 /> {row[2]}</span><div className="compare-bars"><i className="single" style={{ width: `${row[3]}%` }} /><i className="multi" style={{ width: `${row[4]}%` }} /></div></div>)}</section>
    <div className="comparison-note"><ShieldCheck /><p><strong>Ý nghĩa đối với SHB</strong><span>Chuyển từ AI chỉ trả lời câu hỏi sang đội chuyên gia có thể lập kế hoạch, phối hợp, sử dụng dữ liệu nghiệp vụ và hỗ trợ thực hiện hành động có kiểm soát.</span></p></div>
  </>;
}

function DetailScreen({ tab, setTab, onBack, openTool }: { tab: DetailTab; setTab: (t: DetailTab) => void; onBack: () => void; openTool: () => void }) {
  return <>
    <button className="back-link" onClick={onBack}><ArrowLeft size={16} /> Quay lại danh sách chuyên gia</button>
    <div className="detail-hero">
      <span className="agent-icon blue large"><CircleDollarSign /></span><div className="detail-title"><div><h1>Chuyên gia tín dụng</h1><Badge tone="success">Sẵn sàng</Badge></div><p>Chuyên gia thẩm định tín dụng</p></div>
      <div className="detail-actions"><label>Bộ quy tắc <select><option>Chính sách 07/2026</option><option>Chính sách 01/2026</option></select></label><Button variant="secondary"><Settings2 size={16} /> Điều chỉnh</Button><Button><FileCheck2 size={16} /> Xem mẫu đánh giá</Button></div>
    </div>
    <div className="tabs">{(["overview", "knowledge", "tools", "playground"] as DetailTab[]).map((t, i) => <button className={tab === t ? "active" : ""} onClick={() => setTab(t)} key={t}>{["Tổng quan", "Tài liệu nghiệp vụ", "Nguồn dữ liệu", "Chạy thử tình huống"][i]}{t === "knowledge" && <span>682</span>}</button>)}</div>
    {tab === "overview" && <OverviewTab />}
    {tab === "knowledge" && <KnowledgeTab />}
    {tab === "tools" && <ToolsTab openTool={openTool} />}
    {tab === "playground" && <PlaygroundTab />}
  </>;
}

function OverviewTab() {
  return <div className="two-col detail-content">
    <section className="card form-card"><div className="card-heading"><div><h3>Thông tin chuyên gia</h3><p>Vai trò, mục tiêu và chỉ dẫn vận hành</p></div><button><Settings2 size={17} /></button></div>
      <div className="field-grid"><label>Tên chuyên gia<input value="Chuyên gia tín dụng" readOnly /></label><label>Vai trò<input value="Chuyên gia thẩm định tín dụng" readOnly /></label></div>
      <label>Mục tiêu<textarea value="Đánh giá chính xác khả năng trả nợ và mức độ rủi ro của khách hàng theo chính sách tín dụng hiện hành." readOnly /></label>
      <label>Chỉ dẫn<textarea className="tall" value={'1. Kiểm tra tính đầy đủ của hồ sơ khách hàng.\n2. Truy xuất CIC và phân tích lịch sử tín dụng.\n3. Tính DTI và đánh giá dòng tiền.\n4. Trích dẫn bằng chứng cho mọi kết luận.'} readOnly /></label>
      <label>Hàng rào an toàn<div className="guardrails"><span><Check size={14} /> Không tự phê duyệt khoản vay</span><span><Check size={14} /> Luôn trích dẫn nguồn</span><span><Check size={14} /> Ẩn dữ liệu nhạy cảm</span></div></label>
    </section>
    <section className="card model-card"><div className="card-heading"><div><h3>Thiết lập phân tích</h3><p>Quy tắc áp dụng khi đánh giá hồ sơ</p></div><Badge tone="success">Đang áp dụng</Badge></div>
      <div className="factory-panel"><span>AI</span><div><small>Chế độ xử lý</small><strong>Ưu tiên độ chính xác</strong><em>Mọi kết luận phải kèm bằng chứng</em></div><CheckCircle2 size={18} /></div>
      <label>Phạm vi áp dụng<select><option>Thẩm định tín dụng doanh nghiệp</option><option>Thẩm định tín dụng cá nhân</option></select></label>
      <div className="slider-label"><span>Mức độ thận trọng</span><strong>Cao</strong></div><input className="range" type="range" min="0" max="10" value="8" readOnly /><div className="range-notes"><span>Linh hoạt</span><span>Thận trọng</span></div>
      <div className="field-grid"><label>Thời hạn tài liệu<input value="Không quá 12 tháng" readOnly /></label><label>Mức tin cậy tối thiểu<input value="80%" readOnly /></label></div>
      <div className="connection-row"><div><span className="pulse" /><p><strong>Sẵn sàng xử lý</strong><small>Kiểm tra lúc 14:02 hôm nay</small></p></div><strong>Ổn định</strong></div>
      <Button variant="secondary" className="full"><FileCheck2 size={16} /> Xem quy tắc đánh giá</Button>
    </section>
  </div>;
}

const documents = [
  ["Quy trình cấp tín dụng 2026.pdf", "Quy trình", "4,8 MB", "15/07/2026", "Sẵn sàng"],
  ["Quy định tài sản bảo đảm.pdf", "Chính sách", "2,1 MB", "12/07/2026", "Sẵn sàng"],
  ["Chính sách chấm điểm tín dụng.pdf", "Chấm điểm", "3,6 MB", "08/07/2026", "Sẵn sàng"],
  ["Biểu phí tín dụng doanh nghiệp.pdf", "Biểu phí", "1,2 MB", "01/07/2026", "Đang cập nhật"],
  ["Chính sách tín dụng 2024.pdf", "Chính sách", "5,4 MB", "22/12/2024", "Hết hiệu lực"],
];

function KnowledgeTab() {
  return <div className="detail-content"><div className="mini-stats"><div><BookOpen /><p><strong>682</strong><small>Tổng tài liệu</small></p></div><div><CheckCircle2 /><p><strong>658</strong><small>Sẵn sàng sử dụng</small></p></div><div><Clock3 /><p><strong>14</strong><small>Đang cập nhật</small></p></div><div><AlertTriangle /><p><strong>10</strong><small>Cần kiểm tra lại</small></p></div></div>
    <section className="card table-card"><div className="table-toolbar"><div><h3>Tài liệu nghiệp vụ</h3><p>Nguồn tri thức được sử dụng khi phân tích hồ sơ</p></div><label className="search-box"><Search size={17} /><input placeholder="Tìm tài liệu..." /></label><Button variant="ghost"><Filter size={16} /> Danh mục</Button><Button variant="secondary"><Box size={16} /> Nhập thư mục</Button><Button><Upload size={16} /> Tải tài liệu lên</Button></div>
      <div className="data-table"><div className="tr th"><span>TÊN TÀI LIỆU</span><span>DANH MỤC</span><span>DUNG LƯỢNG</span><span>CẬP NHẬT</span><span>TRẠNG THÁI</span><span /></div>{documents.map((d) => <div className="tr" key={d[0]}><span className="doc-name"><FileText size={18} /><strong>{d[0]}</strong></span><span>{d[1]}</span><span>{d[2]}</span><span>{d[3]}</span><span><Badge tone={d[4] === "Sẵn sàng" ? "success" : d[4] === "Đang cập nhật" ? "info" : "warning"}>{d[4]}</Badge></span><button><MoreHorizontal size={17} /></button></div>)}</div>
    </section></div>;
}

const tools = ["Thông tin tín dụng CIC", "Hệ thống ngân hàng lõi", "Tính tỷ lệ DTI", "Định giá tài sản bảo đảm", "Lịch sử giao dịch khách hàng", "Xuất báo cáo tín dụng", "Hồ sơ khách hàng", "Yêu cầu bổ sung tài liệu"];
function ToolsTab({ openTool }: { openTool: () => void }) {
  return <div className="detail-content"><div className="tool-summary"><div><h3>Nguồn dữ liệu nghiệp vụ</h3><p>Các nguồn thông tin được chuyên gia sử dụng khi đánh giá hồ sơ</p></div><strong>8 <span>/ 10 nguồn sẵn sàng</span></strong><Button><Plus size={16} /> Đề nghị bổ sung nguồn</Button></div>
    <div className="tools-grid">{tools.map((tool, i) => <button className="tool-card card" key={tool} onClick={openTool}><span className={`tool-icon ${i % 4 === 0 ? "blue" : i % 4 === 1 ? "purple" : i % 4 === 2 ? "cyan" : "green"}`}><Database size={19} /></span><div><h4>{tool}</h4><p>{i < 4 ? "Nguồn xác thực" : "Nguồn nội bộ"} · Cập nhật {i % 2 ? "hôm qua" : "lúc 14:01"}</p><div><Badge tone="success">Sẵn sàng</Badge>{i % 3 === 0 && <Badge tone="warning">Cần phê duyệt</Badge>}</div></div><ChevronRight size={18} /></button>)}</div>
  </div>;
}

function PlaygroundTab() {
  const [ran, setRan] = useState(false);
  return <div className="playground detail-content"><section className="card chat-panel"><div className="card-heading"><div><h3>Chạy thử tình huống</h3><p>Xem trước cách chuyên gia đánh giá một hồ sơ mẫu</p></div><Badge tone="success">Sẵn sàng</Badge></div><div className="suggestions"><span>Tình huống gợi ý</span><button>Đánh giá sơ bộ khoản vay</button><button>Kiểm tra điều kiện DTI</button></div><div className="chat-space">{ran ? <><div className="chat user">Đánh giá sơ bộ khả năng vay 2,5 tỷ của khách hàng này.</div><div className="chat ai"><strong><Sparkles size={15} /> Chuyên gia tín dụng</strong><p>Khách hàng có khả năng đáp ứng điều kiện vay ở mức trung bình–tốt. Điểm CIC 742 và DTI 38,5% nằm trong ngưỡng cho phép. Cần bổ sung tờ khai thuế gần nhất trước khi đưa ra quyết định.</p><span>Độ tin cậy 87% · Hoàn thành trong 3,8 giây</span></div></> : <div className="empty-chat"><MessageSquareText /><strong>Bắt đầu một lượt chạy thử</strong><p>Nhập tình huống nghiệp vụ để xem cách chuyên gia phân tích.</p></div>}</div><div className="chat-input"><textarea defaultValue="Đánh giá sơ bộ khả năng vay 2,5 tỷ của khách hàng này." /><Button onClick={() => setRan(true)}><Play size={16} /> Phân tích hồ sơ mẫu</Button></div></section>
    <section className="card inspector"><div className="card-heading"><div><h3>Các bước đánh giá</h3><p>Thông tin nào đã được kiểm tra</p></div><ListChecks size={19} /></div>{["Kiểm tra thông tin hồ sơ", "Đối chiếu 5 nội dung chính sách", "Kiểm tra lịch sử tín dụng CIC", "Tính tỷ lệ DTI", "Tổng hợp đề xuất"].map((s, i) => <div className={`inspect-step ${ran ? "done" : i === 0 ? "active" : ""}`} key={s}><span>{ran ? <Check size={13} /> : i + 1}</span><div><strong>{s}</strong><small>{ran ? "Đã hoàn thành" : i === 0 ? "Sẵn sàng" : "Đang chờ"}</small></div></div>)}<div className="inspect-meta"><div><span>Kết quả</span><strong>{ran ? "Có điều kiện" : "—"}</strong></div><div><span>Độ tin cậy</span><strong>{ran ? "87%" : "—"}</strong></div><div><span>Bằng chứng</span><strong>{ran ? "5 nguồn" : "—"}</strong></div></div></section>
  </div>;
}

function TeamScreen({ selected, setSelected, run, onRun, onOpenRun }: { selected: string; setSelected: (s: string) => void; run: number; onRun: () => void; onOpenRun: () => void }) {
  const details: Record<string, { name: string; task: string; sources: string; result: string; icon: any; color: string }> = {
    orchestrator: { name: "Điều phối viên AI", task: "Phân rã yêu cầu và phân công nhiệm vụ chuyên môn", sources: "Quy trình tín dụng & Hồ sơ đầu vào", result: "Kế hoạch thực thi phối hợp", icon: Network, color: "purple" },
    credit: { name: "Chuyên gia tín dụng", task: "Thẩm định năng lực tài chính và điểm tín dụng", sources: "CIC, tỷ lệ DTI & Sao kê tài khoản", result: "Báo cáo phân tích tài chính", icon: CircleDollarSign, color: "blue" },
    compliance: { name: "Chuyên gia tuân thủ", task: "Kiểm soát tuân thủ pháp lý KYC & AML", sources: "Dữ liệu định danh, danh sách đen AML & Quy định", result: "Chứng nhận tuân thủ pháp lý", icon: ShieldCheck, color: "amber" },
    operations: { name: "Chuyên gia vận hành", task: "Kiểm tra tính đầy đủ và hợp lệ của chứng từ", sources: "Danh mục hồ sơ vay & Checklists nghiệp vụ", result: "Đề xuất danh mục hồ sơ cần bổ túc", icon: FileCheck2, color: "green" },
  };
  const detail = details[selected] || details.orchestrator;
  const steps = [
    ["Tiếp nhận hồ sơ", "Hoàn thành"],
    ["Phân rã và giao nhiệm vụ", run >= 1 ? "Hoàn thành" : "Sẵn sàng"],
    ["Ba chuyên gia xử lý song song", run >= 2 ? "Hoàn thành" : run === 1 ? "Đang xử lý" : "Đang chờ"],
    ["Kiểm tra chéo và tổng hợp", run >= 3 ? "Hoàn thành" : run === 2 ? "Đang xử lý" : "Đang chờ"],
    ["Chuyên viên xem xét", run >= 4 ? "Sẵn sàng" : "Đang chờ"],
  ];
  return <><PageHeading title="Quy trình phối hợp đa chuyên gia" subtitle="Quy trình tự động thẩm định hồ sơ HS-2026-0182"><Button onClick={onRun}><Play size={16} /> Mô phỏng quy trình</Button></PageHeading>
    <div className="demo-team-layout">
      <section className="workflow-card card"><div className="workflow-toolbar"><div><h3>Đội chuyên gia AI trong không gian 3D</h3><Badge tone={run && run < 4 ? "info" : "success"}>{run && run < 4 ? "Đang xử lý" : run === 4 ? "Hoàn thành" : "Sẵn sàng"}</Badge></div><div><span>Chọn một chuyên gia để xem nhiệm vụ</span></div></div><Suspense fallback={<div className="agent-stage-fallback">Đang chuẩn bị đội chuyên gia 3D...</div>}><AgentStage3D mode="builder" selected={selected} onSelect={setSelected} runStep={run} /></Suspense><div className="canvas-footer"><span><ListChecks size={14} /> 4 chuyên gia · 1 bước phê duyệt</span><span>Mọi kết luận đều có bằng chứng</span></div></section>
      <section className="demo-task-panel card">
        <div className="case-brief"><small>HỒ SƠ ĐANG XỬ LÝ</small><strong>HS-2026-0182</strong><span>Nguyễn Văn An · 2,5 tỷ đồng</span></div>
        <div className="selected-expert"><span className={`agent-icon ${detail.color}`}><detail.icon size={19} /></span><div><small>CHUYÊN GIA ĐÃ CHỌN</small><strong>{detail.name}</strong></div></div>
        <div className="task-detail"><div><span>Nhiệm vụ</span><strong>{detail.task}</strong></div><div><span>Nguồn đối chiếu</span><strong>{detail.sources}</strong></div><div><span>Kết quả bàn giao</span><strong>{detail.result}</strong></div></div>
        <div className="coordination-steps"><h3>Tiến trình phối hợp</h3>{steps.map(([name, status], index) => <div key={name} className={status === "Đang xử lý" ? "active" : status === "Hoàn thành" ? "done" : ""}><i>{status === "Hoàn thành" ? <Check size={12} /> : index + 1}</i><p><strong>{name}</strong><small>{status}</small></p></div>)}</div>
        <div className="human-control"><UserCheck size={18} /><p><strong>Chuyên viên kiểm soát quyết định</strong><span>AI không tự phê duyệt hoặc thay đổi hồ sơ.</span></p></div>
      </section>
    </div></>;
}

function FlowNode({ id, selected, setSelected, run, step, color, icon: Icon, title, status }: any) {
  const done = run > step; const active = run === step;
  return <button className={`flow-node ${selected === id ? "selected" : ""} ${active ? "running" : ""}`} onClick={() => setSelected(id)}><span className={`agent-icon ${color}`}><Icon size={18} /></span><div><strong>{title}</strong><small>{status}</small></div>{done ? <CheckCircle2 className="node-state complete" /> : active ? <RefreshCw className="node-state spinning" /> : <span className="node-ready" />}</button>;
}

function PropertiesPanel({ selected }: { selected: string }) {
  const name: Record<string, string> = { credit: "Chuyên gia tín dụng", compliance: "Chuyên gia tuân thủ", operations: "Chuyên gia vận hành", orchestrator: "Điều phối viên AI", approval: "Phê duyệt của chuyên viên" };
  return <section className="card properties"><div className="panel-heading"><div><h3>Phân công nhiệm vụ</h3><span>Vai trò trong quy trình</span></div><button><PanelLeftClose size={17} /></button></div><div className="selected-agent"><span className="agent-icon blue"><CircleDollarSign size={18} /></span><div><small>CHUYÊN GIA ĐÃ CHỌN</small><strong>{name[selected]}</strong></div></div><label>Chuyên gia phụ trách<input value={name[selected]} readOnly /></label><label>Nhiệm vụ được giao<textarea value="Phân tích năng lực tài chính, lịch sử tín dụng và đề xuất hạn mức phù hợp." readOnly /></label><label>Kết quả cần bàn giao<textarea value="Báo cáo đánh giá tín dụng có trích dẫn bằng chứng và mức độ tin cậy." readOnly /></label><label>Kho tài liệu sử dụng<select><option>Kho tín dụng doanh nghiệp</option></select></label><label>Nguồn thông tin được phép dùng<div className="guardrails"><span><Check size={14} /> Thông tin CIC</span><span><Check size={14} /> Tỷ lệ DTI</span><span><Check size={14} /> Hệ thống ngân hàng lõi</span></div></label><div className="field-grid"><label>Thời hạn hoàn thành<input value="Trong 1 phút" readOnly /></label><label>Khi thiếu dữ liệu<input value="Yêu cầu bổ sung" readOnly /></label></div><label className="toggle-row"><span><strong>Yêu cầu phê duyệt</strong><small>Trước mọi hành động ảnh hưởng hồ sơ</small></span><input type="checkbox" defaultChecked /></label></section>;
}

function RunScreen({ openTrace, openApproval }: { openTrace: () => void; openApproval: () => void }) {
  const [progress, setProgress] = useState(72);
  useEffect(() => { const t = setTimeout(() => setProgress(78), 1800); return () => clearTimeout(t); }, []);
  return <><PageHeading title="Hồ sơ vay HS-2026-0182" subtitle="Nguyễn Văn An · Vay kinh doanh · 2,5 tỷ đồng"><Badge tone="info"><RefreshCw className="spinning" size={13} /> AI đang xử lý</Badge><Button variant="secondary"><MoreHorizontal size={17} /></Button></PageHeading>
    <div className="run-layout"><section className="case-panel card"><div className="panel-heading"><div><h3>Thông tin hồ sơ</h3><span>Cập nhật lúc 14:05</span></div><button><Settings2 size={17} /></button></div><div className="customer"><div className="avatar customer-avatar">NA</div><div><strong>Nguyễn Văn An</strong><small>KH-0018293</small></div><Badge tone="success">Đã xác minh</Badge></div><div className="case-fields"><div><span>Số tiền đề nghị</span><strong>2,5 tỷ đồng</strong></div><div><span>Mục đích vay</span><strong>Bổ sung vốn kinh doanh</strong></div><div><span>Sản phẩm</span><strong>Vay doanh nghiệp SME</strong></div><div><span>Thời điểm gửi</span><strong>17/07/2026 · 13:58</strong></div></div><div className="document-check"><div><h4>Hồ sơ đính kèm</h4><span>4/5 đầy đủ</span></div>{[["CCCD", "Đã xác minh", true], ["Đăng ký kinh doanh", "Hợp lệ", true], ["Sao kê 6 tháng", "Đã nhận", true], ["Tờ khai thuế gần nhất", "Còn thiếu", false], ["Hồ sơ tài sản bảo đảm", "Đã nhận", true]].map(([n, s, ok]) => <div className="check-item" key={String(n)}><span className={ok ? "ok" : "missing"}>{ok ? <Check size={13} /> : <AlertTriangle size={13} />}</span><p><strong>{n}</strong><small>{s}</small></p>{!ok && <button>Yêu cầu</button>}</div>)}</div><Button variant="secondary" className="full"><Upload size={16} /> Tải thêm tài liệu</Button></section>
      <section className="assessment"><div className="progress-card card"><div><span>TIẾN ĐỘ PHÂN TÍCH</span><strong>{progress}%</strong></div><div className="progress-track"><i style={{ width: `${progress}%` }} /></div><p><RefreshCw className="spinning" size={13} /> Chuyên gia tuân thủ đang kiểm tra AML...</p></div><div className="recommendation card"><div className="rec-top"><div><span className="eyebrow"><Sparkles size={14} /> ĐỀ XUẤT CỦA ĐỘI CHUYÊN GIA AI</span><h2>PHÊ DUYỆT CÓ ĐIỀU KIỆN</h2></div><span className="rec-icon"><ShieldCheck /></span></div><div className="rec-metrics"><div><span>Mức độ rủi ro</span><strong className="amber-text"><span />Trung bình</strong></div><div><span>Độ tin cậy</span><strong>87%</strong></div><div><span>Thời gian phân tích</span><strong>6 phút 12 giây</strong></div></div><div className="human-note"><UserCheck size={18} /><p><strong>Cần quyết định của chuyên viên</strong><span>Hệ thống chỉ đưa ra đề xuất. Mọi hành động đều cần được bạn xem xét và phê duyệt.</span></p></div></div>
        <div className="metric-grid"><div className="card"><span>Điểm tín dụng</span><strong>742</strong><small className="good">Tốt</small><div className="meter"><i style={{ width: "74%" }} /></div></div><div className="card"><span>DTI</span><strong>38,5%</strong><small className="good">Đạt</small><div className="meter"><i style={{ width: "38.5%" }} /></div></div><div className="card"><span>Ổn định dòng tiền</span><strong>Tốt</strong><small>6 tháng</small></div><div className="card"><span>Trạng thái AML</span><strong>Không cảnh báo</strong><small className="good">An toàn</small></div></div>
        <div className="findings card"><div className="card-heading"><div><h3>Phát hiện chính</h3><p>Tổng hợp từ 3 chuyên gia AI</p></div><button onClick={openTrace}>Xem bằng chứng <ChevronRight size={15} /></button></div><div className="finding-list"><span className="positive"><Check size={14} /> Dòng tiền kinh doanh ổn định</span><span className="positive"><Check size={14} /> Không có nợ nhóm 3–5</span><span className="warning"><AlertTriangle size={14} /> Thiếu tờ khai thuế gần nhất</span><span className="warning"><AlertTriangle size={14} /> Tài sản bảo đảm cần xác minh lại</span></div></div><div className="assessment-actions"><Button variant="secondary" onClick={openTrace}>Xem bằng chứng</Button><Button variant="secondary"><RefreshCw size={15} /> Yêu cầu phân tích lại</Button><Button variant="secondary">Xem đề xuất hành động</Button><Button onClick={openApproval}><UserCheck size={16} /> Phê duyệt</Button></div></section>
      <section className="execution card"><div className="panel-heading"><div><h3>Tiến trình xử lý</h3><span>Cập nhật theo thời gian thực</span></div><span className="live-dot">TRỰC TIẾP</span></div><Suspense fallback={<div className="agent-stage-fallback compact">Đang chuẩn bị đội chuyên gia 3D...</div>}><AgentStage3D mode="run" compact /></Suspense><div className="execution-agents">{[["Điều phối viên AI", "Hoàn thành", "purple", Network], ["Chuyên gia tín dụng", "Hoàn thành", "blue", CircleDollarSign], ["Chuyên gia tuân thủ", "Đang xử lý", "amber", ShieldCheck], ["Chuyên gia vận hành", "Đang chờ", "green", FileCheck2]].map(([n, s, c, I]: any) => <div key={n}><span className={`agent-icon ${c}`}><I size={17} /></span><p><strong>{n}</strong><small>{s === "Đang xử lý" ? "Kiểm tra KYC và AML" : s === "Đang chờ" ? "Chờ kết quả tuân thủ" : "Đã trả kết quả"}</small></p><Badge tone={s === "Hoàn thành" ? "success" : s === "Đang xử lý" ? "info" : "neutral"}>{s}</Badge></div>)}</div><div className="timeline-title"><h4>Nhật ký hoạt động</h4><button>Lọc <Filter size={14} /></button></div><div className="timeline">{[["14:02", "Điều phối viên AI phân công đánh giá", "Đã phân công"], ["14:03", "Chuyên gia tín dụng kiểm tra thông tin CIC", "Đã kiểm tra"], ["14:04", "Đối chiếu Chính sách chấm điểm tín dụng", "Đã đối chiếu"], ["14:05", "Chuyên gia tuân thủ kiểm tra AML", "Đang xử lý"], ["14:06", "Chuyên gia vận hành kiểm tra tài liệu", "Đang chờ"]].map((a, i) => <button key={a[0]} className={i === 3 ? "active" : ""} onClick={openTrace}><span className="time">{a[0]}</span><i /><div><strong>{a[1]}</strong><small>{a[2]}</small></div><ChevronRight size={15} /></button>)}</div></section></div></>;
}

function DrawerShell({ title, subtitle, onClose, children }: { title: string; subtitle: string; onClose: () => void; children: React.ReactNode }) {
  return <><div className="overlay" onClick={onClose} /><aside className="drawer"><div className="drawer-head"><div><h2>{title}</h2><p>{subtitle}</p></div><button onClick={onClose}><X /></button></div><div className="drawer-body">{children}</div></aside></>;
}

function ToolDrawer({ onClose }: { onClose: () => void }) {
  const [approval, setApproval] = useState(true);
  const [tested, setTested] = useState(false);
  return <DrawerShell title="Thông tin nguồn dữ liệu" subtitle="Thông tin tín dụng CIC" onClose={onClose}><div className="drawer-tool"><span className="tool-icon blue"><Database /></span><div><h3>Thông tin tín dụng CIC</h3><p>Cung cấp lịch sử tín dụng, dư nợ hiện tại và tình trạng nợ quá hạn của khách hàng.</p></div></div><div className="drawer-section"><h4>PHẠM VI THÔNG TIN</h4><div className="trace-grid"><div><span>Dữ liệu cung cấp</span><strong>Điểm tín dụng, dư nợ</strong></div><div><span>Đơn vị quản lý</span><strong>Trung tâm CIC</strong></div><div><span>Tần suất cập nhật</span><strong>Hằng ngày</strong></div><div><span>Trạng thái</span><strong>Sẵn sàng</strong></div></div></div><div className="drawer-section"><h4>QUY TẮC SỬ DỤNG</h4><div className="guardrails"><span><Check size={14} /> Chỉ dùng cho hồ sơ đang thẩm định</span><span><Check size={14} /> Ghi nhận lịch sử tra cứu</span><span><Check size={14} /> Bảo vệ thông tin khách hàng</span></div><label>Mục đích được phép<select><option>Thẩm định hồ sơ tín dụng</option></select></label></div><label className="toggle-row"><span><strong>Yêu cầu phê duyệt</strong><small>Chuyên viên xác nhận trước khi tra cứu</small></span><input type="checkbox" checked={approval} onChange={() => setApproval(!approval)} /></label>{tested && <div className="test-success"><CheckCircle2 /> Nguồn dữ liệu đang sẵn sàng</div>}<div className="drawer-actions"><Button variant="secondary" onClick={onClose}>Đóng</Button><Button onClick={() => setTested(true)}><FileCheck2 size={16} /> Kiểm tra trạng thái</Button></div></DrawerShell>;
}

function TraceDrawer({ onClose }: { onClose: () => void }) {
  return <DrawerShell title="Bằng chứng đánh giá" subtitle="14:03 · Kiểm tra thông tin tín dụng" onClose={onClose}><div className="trace-summary"><span className="agent-icon blue"><CircleDollarSign /></span><div><span>CHUYÊN GIA AI</span><strong>Chuyên gia tín dụng</strong><small>Đánh giá lịch sử tín dụng khách hàng</small></div><Badge tone="success">Hoàn thành</Badge></div><div className="trace-grid"><div><span>Nội dung kiểm tra</span><strong>Lịch sử tín dụng CIC</strong></div><div><span>Thời điểm</span><strong>17/07/2026 · 14:03</strong></div><div><span>Kết quả</span><strong>Đạt yêu cầu</strong></div><div><span>Độ tin cậy</span><strong>94%</strong></div></div><div className="drawer-section"><h4>KẾT QUẢ ĐỐI CHIẾU</h4><div className="evidence-head"><Database /><div><strong>Thông tin tín dụng CIC</strong><small>Cập nhật ngày 17/07/2026</small></div><Badge tone="success">Đã xác minh</Badge></div><div className="case-fields"><div><span>Điểm tín dụng</span><strong>742 điểm</strong></div><div><span>Nhóm nợ hiện tại</span><strong>Nhóm 1 — Đủ tiêu chuẩn</strong></div><div><span>Nợ quá hạn</span><strong>Không ghi nhận</strong></div><div><span>Nợ nhóm 3–5 trong 24 tháng</span><strong>Không ghi nhận</strong></div></div></div><div className="drawer-section"><h4>CHÍNH SÁCH ÁP DỤNG</h4><div className="evidence"><div><FileText /><p><strong>Chính sách chấm điểm tín dụng.pdf</strong><small>Trang 18 · Mức phù hợp 94%</small></p></div><blockquote>“Khách hàng có điểm tín dụng từ 720 và không phát sinh nợ nhóm 3–5 trong 24 tháng gần nhất được xếp nhóm rủi ro thấp đến trung bình.”</blockquote></div></div><div className="human-note"><UserCheck size={18} /><p><strong>Kết quả hỗ trợ quyết định</strong><span>Chuyên viên cần xem xét cùng các thông tin khác trước khi phê duyệt.</span></p></div></DrawerShell>;
}

function ApprovalModal({ acknowledged, setAcknowledged, approved, onApprove, onClose }: { acknowledged: boolean; setAcknowledged: (v: boolean) => void; approved: boolean; onApprove: () => void; onClose: () => void }) {
  return <div className="modal-layer"><div className="overlay" onClick={onClose} /><div className="modal">{approved ? <div className="approval-success"><span><Check /></span><h2>Phê duyệt thành công</h2><p>Các hành động đã được thực hiện theo quyết định của bạn.</p><div><strong><CheckCircle2 /> Đã cập nhật trạng thái hồ sơ</strong><strong><CheckCircle2 /> Đã gửi yêu cầu bổ sung tài liệu</strong><strong><CheckCircle2 /> Đã chuyển hồ sơ sang bộ phận thẩm định tài sản</strong></div><Button onClick={onClose}>Hoàn tất</Button></div> : <><div className="modal-head"><div><span className="modal-icon"><UserCheck /></span><div><h2>Xem xét hành động được đề xuất</h2><p>Quyết định của bạn sẽ được ghi vào nhật ký kiểm toán.</p></div></div><button onClick={onClose}><X /></button></div><div className="modal-body"><div className="approval-rec"><span>ĐỀ XUẤT CỦA HỆ THỐNG</span><strong>PHÊ DUYỆT CÓ ĐIỀU KIỆN</strong><div><p>Mức độ rủi ro <b>Trung bình</b></p><p>Độ tin cậy <b>87%</b></p></div></div><div className="approval-columns"><div><h4>ĐIỀU KIỆN BẮT BUỘC</h4><p><AlertTriangle /> Bổ sung tờ khai thuế gần nhất</p><p><AlertTriangle /> Xác minh lại giá trị tài sản bảo đảm</p></div><div><h4>HÀNH ĐỘNG SẼ THỰC HIỆN</h4><p><CheckCircle2 /> Cập nhật trạng thái hồ sơ</p><p><CheckCircle2 /> Gửi yêu cầu bổ sung tài liệu</p><p><CheckCircle2 /> Chuyển hồ sơ sang bộ phận thẩm định tài sản</p></div></div><label className="acknowledge"><input type="checkbox" checked={acknowledged} onChange={(e) => setAcknowledged(e.target.checked)} /><span>Tôi đã xem kết quả, bằng chứng và các cảnh báo của hệ thống.</span></label></div><div className="modal-actions"><Button variant="danger">Từ chối</Button><Button variant="secondary">Yêu cầu phân tích lại</Button><Button onClick={onApprove} disabled={!acknowledged}><LockKeyhole size={16} /> Phê duyệt và thực hiện</Button></div></>}</div></div>;
}
