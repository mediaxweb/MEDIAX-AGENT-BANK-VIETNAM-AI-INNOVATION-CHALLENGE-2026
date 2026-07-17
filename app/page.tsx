"use client";

import {
  ChevronLeft, ChevronRight, LibraryBig, Menu, MessagesSquare, MoreHorizontal, Sparkles
} from "lucide-react";
import { lazy, Suspense, useEffect, useState } from "react";
import DocumentsScreen from "./DocumentsScreen";

const AIQAScreen = lazy(() => import("./AIQAScreen"));

type Screen = "documents" | "qa";

const nav = [
  { label: "Hỏi đáp AI", icon: MessagesSquare, screen: "qa" as Screen },
  { label: "Kho tri thức", icon: LibraryBig, screen: "documents" as Screen },
];


export default function Home() {
  const [screen, setScreen] = useState<Screen>("qa");
  const [mobileNav, setMobileNav] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [traceExpanded, setTraceExpanded] = useState(true);
  const [leftSidebarExpanded, setLeftSidebarExpanded] = useState(true);

  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash.replace("#", "") as Screen;
      const validScreens: Screen[] = ["qa", "documents"];
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

  const pageTitles: Record<Screen, { title: string; subtitle: string }> = {
    documents: { title: "Kho tài liệu", subtitle: "Quản lý dữ liệu và tri thức nghiệp vụ của hệ thống" },
    qa: { title: "Hỏi đáp AI", subtitle: "Truy vấn dữ liệu và phân tích nghiệp vụ với sự trợ giúp từ Đội chuyên gia AI" },
  };
  const { title: pageTitle, subtitle: pageSubtitle } = pageTitles[screen];

  function navigate(next: Screen) {
    window.location.hash = next;
    setMobileNav(false);
  }

  const handleMenuClick = (itemScreen: Screen) => {
    navigate(itemScreen);
  };

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
          {nav.map((item) => (
            <button 
              key={item.label} 
              className={screen === item.screen ? "active" : ""} 
              onClick={() => handleMenuClick(item.screen)}
            >
              <item.icon size={18} />
              {!sidebarCollapsed && <span>{item.label}</span>}
            </button>
          ))}
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
          <div className="topbar-title">
            <h1>{pageTitle}</h1>
            <p>{pageSubtitle}</p>
          </div>
          <div id="top-actions-portal" className="top-actions"></div>
        </header>

        <div className="content">
          {screen === "documents" && <DocumentsScreen />}
          {screen === "qa" && (
            <Suspense fallback={<div className="agent-stage-fallback">Đang chuẩn bị hỏi đáp AI...</div>}>
              <AIQAScreen 
                traceExpanded={traceExpanded} 
                setTraceExpanded={setTraceExpanded} 
                leftSidebarExpanded={leftSidebarExpanded} 
                setLeftSidebarExpanded={setLeftSidebarExpanded} 
              />
            </Suspense>
          )}
        </div>
      </section>
    </main>
  );
}
