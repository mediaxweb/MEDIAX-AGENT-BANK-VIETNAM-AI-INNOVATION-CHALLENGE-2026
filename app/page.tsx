"use client";

import {
  Activity, AlertTriangle, ArrowLeft, Bell, BookOpen, Bot, Box, Building2,
  Check, CheckCircle2, ChevronDown, ChevronRight, CircleDollarSign, Clock3,
  Database, FileCheck2, FileText, Filter, GitBranch, KeyRound, LayoutDashboard,
  Link2, ListChecks, LockKeyhole, Maximize2, Menu, MessageSquareText, MoreHorizontal,
  Network, PanelLeftClose, Play, Plus, RefreshCw, Search, Settings2, ShieldCheck,
  SlidersHorizontal, Sparkles, TestTube2, Upload, UserCheck, Users, Wrench, X,
  ZoomIn, ZoomOut
} from "lucide-react";
import { useEffect, useState } from "react";

type Screen = "agents" | "detail" | "team" | "run";
type DetailTab = "overview" | "knowledge" | "tools" | "playground";

const agents = [
  { name: "Chuyên gia tín dụng", role: "Chuyên gia thẩm định tín dụng", docs: 682, tools: 8, color: "blue", icon: CircleDollarSign, updated: "12 phút trước" },
  { name: "Chuyên gia tuân thủ", role: "Chuyên gia KYC, AML và pháp lý", docs: 945, tools: 6, color: "amber", icon: ShieldCheck, updated: "28 phút trước" },
  { name: "Chuyên gia vận hành", role: "Chuyên gia vận hành hồ sơ", docs: 310, tools: 10, color: "green", icon: FileCheck2, updated: "1 giờ trước" },
  { name: "Điều phối viên AI", role: "Điều phối và tổng hợp quyết định", docs: 120, tools: 5, color: "purple", icon: Network, updated: "2 giờ trước" },
];

const nav = [
  { label: "Tổng quan", icon: LayoutDashboard, screen: "agents" as Screen },
  { label: "Chuyên gia AI", icon: Bot, screen: "agents" as Screen },
  { label: "Đội chuyên gia AI", icon: Users, screen: "team" as Screen },
  { label: "Nghiệp vụ", icon: Building2, screen: "run" as Screen },
  { label: "Lịch sử xử lý", icon: Clock3 },
  { label: "Kho tri thức", icon: BookOpen },
  { label: "Nguồn dữ liệu", icon: Database },
  { label: "Thiết lập nghiệp vụ", icon: Settings2 },
];

function Badge({ children, tone = "neutral" }: { children: React.ReactNode; tone?: string }) {
  return <span className={`badge ${tone}`}><span className="badge-dot" />{children}</span>;
}

function Button({ children, variant = "primary", onClick, disabled = false, className = "" }: { children: React.ReactNode; variant?: string; onClick?: () => void; disabled?: boolean; className?: string }) {
  return <button className={`button ${variant} ${className}`} onClick={onClick} disabled={disabled}>{children}</button>;
}

export default function Home() {
  const [screen, setScreen] = useState<Screen>("agents");
  const [tab, setTab] = useState<DetailTab>("overview");
  const [selectedNode, setSelectedNode] = useState("credit");
  const [toolDrawer, setToolDrawer] = useState(false);
  const [traceDrawer, setTraceDrawer] = useState(false);
  const [approval, setApproval] = useState(false);
  const [acknowledged, setAcknowledged] = useState(false);
  const [approved, setApproved] = useState(false);
  const [workflowRun, setWorkflowRun] = useState(0);
  const [mobileNav, setMobileNav] = useState(false);

  const pageTitle = screen === "agents" ? "Chuyên gia AI" : screen === "detail" ? "Chuyên gia tín dụng" : screen === "team" ? "Thiết lập đội chuyên gia" : "Không gian xử lý";

  function navigate(next: Screen) {
    setScreen(next); setMobileNav(false);
    if (next === "detail") setTab("overview");
  }

  function runWorkflow() {
    setWorkflowRun(1);
    setTimeout(() => setWorkflowRun(2), 700);
    setTimeout(() => setWorkflowRun(3), 1500);
    setTimeout(() => setWorkflowRun(4), 2300);
  }

  return (
    <main className="app-shell">
      <aside className={`sidebar ${mobileNav ? "open" : ""}`}>
        <div className="brand"><div className="brand-mark"><Sparkles size={18} /></div><div><strong>MediaX</strong><span>Agent Bank</span></div></div>
        <nav>
          <p className="nav-label">KHÔNG GIAN LÀM VIỆC</p>
          {nav.slice(0, 5).map((item) => <button key={item.label} className={(screen === item.screen || (item.label === "Chuyên gia AI" && screen === "detail")) ? "active" : ""} onClick={() => item.screen && navigate(item.screen)}><item.icon size={18} /><span>{item.label}</span>{item.label === "Nghiệp vụ" && <b>3</b>}</button>)}
          <p className="nav-label second">HỆ THỐNG</p>
          {nav.slice(5).map((item) => <button key={item.label}><item.icon size={18} /><span>{item.label}</span></button>)}
        </nav>
        <div className="sidebar-bottom">
          <div className="system-health"><span className="pulse" /><div><strong>Hệ thống ổn định</strong><small>8 chuyên gia sẵn sàng</small></div></div>
          <div className="profile"><div className="avatar">TA</div><div><strong>Trần Minh Anh</strong><small>Chuyên viên tín dụng</small></div><MoreHorizontal size={18} /></div>
        </div>
      </aside>

      <section className="app-main">
        <header className="topbar">
          <button className="mobile-menu" onClick={() => setMobileNav(!mobileNav)}><Menu size={20} /></button>
          <div className="breadcrumb"><span>MediaX Agent Bank</span><ChevronRight size={14} /><strong>{pageTitle}</strong></div>
          <div className="top-actions">
            <label className="global-search"><Search size={17} /><input placeholder="Tìm kiếm hồ sơ, chuyên gia..." /><kbd>⌘ K</kbd></label>
            <div className="factory-status"><span /><strong>Hệ thống AI</strong><em>Sẵn sàng</em></div>
            <button className="icon-button"><Bell size={19} /><i /></button>
            <div className="avatar small">TA</div>
          </div>
        </header>

        <div className="content">
          {screen === "agents" && <AgentsScreen onOpen={() => navigate("detail")} />}
          {screen === "detail" && <DetailScreen tab={tab} setTab={setTab} onBack={() => navigate("agents")} openTool={() => setToolDrawer(true)} />}
          {screen === "team" && <TeamScreen selected={selectedNode} setSelected={setSelectedNode} run={workflowRun} onRun={runWorkflow} onOpenRun={() => navigate("run")} />}
          {screen === "run" && <RunScreen openTrace={() => setTraceDrawer(true)} openApproval={() => { setApproval(true); setApproved(false); setAcknowledged(false); }} />}
        </div>
      </section>

      {toolDrawer && <ToolDrawer onClose={() => setToolDrawer(false)} />}
      {traceDrawer && <TraceDrawer onClose={() => setTraceDrawer(false)} />}
      {approval && <ApprovalModal acknowledged={acknowledged} setAcknowledged={setAcknowledged} approved={approved} onApprove={() => setApproved(true)} onClose={() => setApproval(false)} />}
    </main>
  );
}

function PageHeading({ title, subtitle, children }: { title: string; subtitle: string; children?: React.ReactNode }) {
  return <div className="page-heading"><div><h1>{title}</h1><p>{subtitle}</p></div>{children && <div className="heading-actions">{children}</div>}</div>;
}

function AgentsScreen({ onOpen }: { onOpen: () => void }) {
  const [filter, setFilter] = useState("Tất cả");
  return <>
    <PageHeading title="Chuyên gia AI" subtitle="Xây dựng và quản lý các chuyên gia AI cho nghiệp vụ ngân hàng">
      <Button><Plus size={17} /> Tạo chuyên gia AI</Button>
    </PageHeading>
    <section className="stats-row">
      <div><span className="stat-icon blue"><Bot /></span><p><strong>12</strong><small>Tổng chuyên gia AI</small></p><em>+2 tháng này</em></div>
      <div><span className="stat-icon green"><CheckCircle2 /></span><p><strong>8</strong><small>Đang sẵn sàng</small></p><em>Hoạt động ổn định</em></div>
      <div><span className="stat-icon cyan"><Activity /></span><p><strong>1.248</strong><small>Lượt xử lý tháng này</small></p><em>+18,5%</em></div>
      <div><span className="stat-icon amber"><Clock3 /></span><p><strong>4,2 giây</strong><small>Thời gian phản hồi TB</small></p><em>−0,8 giây</em></div>
    </section>
    <section className="toolbar card">
      <label className="search-box"><Search size={18} /><input placeholder="Tìm theo tên hoặc vai trò..." /></label>
      <div className="filter-chips">{["Tất cả", "Tín dụng", "Tuân thủ", "Vận hành"].map((f) => <button className={filter === f ? "selected" : ""} onClick={() => setFilter(f)} key={f}>{f}</button>)}</div>
      <Button variant="ghost"><Filter size={17} /> Lĩnh vực <ChevronDown size={15} /></Button>
      <Button variant="ghost"><SlidersHorizontal size={17} /> Trạng thái <ChevronDown size={15} /></Button>
    </section>
    <div className="section-title"><div><h2>Danh sách chuyên gia</h2><span>12 chuyên gia</span></div><button>Hoạt động gần đây <ChevronDown size={15} /></button></div>
    <section className="agent-grid">
      {agents.map((agent, index) => <article className="agent-card card" key={agent.name}>
        <div className="agent-card-top"><span className={`agent-icon ${agent.color}`}><agent.icon size={22} /></span><Badge tone="success">Sẵn sàng</Badge><button><MoreHorizontal size={18} /></button></div>
        <h3>{agent.name}</h3><p>{agent.role}</p>
        <div className="provider"><span>AI</span><div><small>Phạm vi nghiệp vụ</small><strong>{index === 0 ? "Tín dụng doanh nghiệp" : index === 1 ? "KYC và AML" : index === 2 ? "Vận hành hồ sơ" : "Điều phối nghiệp vụ"}</strong></div><CheckCircle2 size={16} /></div>
        <div className="agent-metrics"><div><BookOpen size={16} /><strong>{agent.docs}</strong><small>Tài liệu</small></div><div><Database size={16} /><strong>{agent.tools}</strong><small>Nguồn dữ liệu</small></div><div><Clock3 size={16} /><strong>{index === 0 ? "4,1 giây" : "3,8 giây"}</strong><small>Phản hồi TB</small></div></div>
        <div className="updated"><RefreshCw size={13} /> Cập nhật {agent.updated}</div>
        <div className="card-actions"><Button onClick={index === 0 ? onOpen : undefined}>Mở chuyên gia <ChevronRight size={16} /></Button><Button variant="secondary"><FileCheck2 size={16} /> Xem mẫu đánh giá</Button></div>
      </article>)}
    </section>
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
  return <><PageHeading title="Thiết lập đội chuyên gia" subtitle="Đội chuyên gia thẩm định hồ sơ vay doanh nghiệp"><Button variant="secondary"><Check size={16} /> Lưu đội chuyên gia</Button><Button onClick={onRun}><Play size={16} /> Mô phỏng quy trình</Button></PageHeading>
    <div className="team-layout"><section className="card agent-library"><div className="panel-heading"><div><h3>Thư viện chuyên gia</h3><span>4 chuyên gia</span></div></div><label className="search-box"><Search size={17} /><input placeholder="Tìm chuyên gia..." /></label><select><option>Tất cả lĩnh vực</option></select>{agents.map((a, i) => <button key={a.name} onClick={() => setSelected(["credit", "compliance", "operations", "orchestrator"][i])}><span className={`agent-icon ${a.color}`}><a.icon size={18} /></span><div><strong>{a.name}</strong><small>{a.role}</small></div><span className="drag">⠿</span></button>)}</section>
      <section className="workflow-card card"><div className="workflow-toolbar"><div><h3>Quy trình phối hợp</h3><Badge tone={run ? "info" : "success"}>{run ? "Đang mô phỏng" : "Đã lưu"}</Badge></div><div><button aria-label="Thu nhỏ"><ZoomOut size={17} /></button><span>100%</span><button aria-label="Phóng to"><ZoomIn size={17} /></button><button aria-label="Xem toàn bộ"><Maximize2 size={17} /></button></div></div><div className="canvas-grid"><div className="flow-line vertical top" /><FlowNode id="orchestrator" selected={selected} setSelected={setSelected} run={run} step={1} color="purple" icon={Network} title="Điều phối viên AI" status="Điều phối" /><div className="branch-lines" /><div className="flow-row"><FlowNode id="credit" selected={selected} setSelected={setSelected} run={run} step={2} color="blue" icon={CircleDollarSign} title="Chuyên gia tín dụng" status="Thẩm định" /><FlowNode id="compliance" selected={selected} setSelected={setSelected} run={run} step={2} color="amber" icon={ShieldCheck} title="Chuyên gia tuân thủ" status="KYC & AML" /></div><div className="merge-lines" /><FlowNode id="operations" selected={selected} setSelected={setSelected} run={run} step={3} color="green" icon={FileCheck2} title="Chuyên gia vận hành" status="Kiểm tra hồ sơ" /><div className="flow-line vertical" /><FlowNode id="approval" selected={selected} setSelected={setSelected} run={run} step={4} color="neutral" icon={UserCheck} title="Phê duyệt của chuyên viên" status="Kiểm soát cuối" /></div><div className="canvas-footer"><span><ListChecks size={14} /> Quy trình gồm 5 bước</span>{run === 4 ? <Button onClick={onOpenRun}>Mở không gian xử lý <ChevronRight size={15} /></Button> : <span>Tự động lưu lúc 14:03</span>}</div></section>
      <PropertiesPanel selected={selected} /></div></>;
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
      <section className="execution card"><div className="panel-heading"><div><h3>Tiến trình xử lý</h3><span>Cập nhật theo thời gian thực</span></div><span className="live-dot">TRỰC TIẾP</span></div><div className="execution-agents">{[["Điều phối viên AI", "Hoàn thành", "purple", Network], ["Chuyên gia tín dụng", "Hoàn thành", "blue", CircleDollarSign], ["Chuyên gia tuân thủ", "Đang xử lý", "amber", ShieldCheck], ["Chuyên gia vận hành", "Đang chờ", "green", FileCheck2]].map(([n, s, c, I]: any) => <div key={n}><span className={`agent-icon ${c}`}><I size={17} /></span><p><strong>{n}</strong><small>{s === "Đang xử lý" ? "Kiểm tra KYC và AML" : s === "Đang chờ" ? "Chờ kết quả tuân thủ" : "Đã trả kết quả"}</small></p><Badge tone={s === "Hoàn thành" ? "success" : s === "Đang xử lý" ? "info" : "neutral"}>{s}</Badge></div>)}</div><div className="timeline-title"><h4>Nhật ký hoạt động</h4><button>Lọc <Filter size={14} /></button></div><div className="timeline">{[["14:02", "Điều phối viên AI phân công đánh giá", "Đã phân công"], ["14:03", "Chuyên gia tín dụng kiểm tra thông tin CIC", "Đã kiểm tra"], ["14:04", "Đối chiếu Chính sách chấm điểm tín dụng", "Đã đối chiếu"], ["14:05", "Chuyên gia tuân thủ kiểm tra AML", "Đang xử lý"], ["14:06", "Chuyên gia vận hành kiểm tra tài liệu", "Đang chờ"]].map((a, i) => <button key={a[0]} className={i === 3 ? "active" : ""} onClick={openTrace}><span className="time">{a[0]}</span><i /><div><strong>{a[1]}</strong><small>{a[2]}</small></div><ChevronRight size={15} /></button>)}</div></section></div></>;
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
