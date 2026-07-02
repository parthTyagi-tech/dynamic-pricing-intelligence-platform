import { useState, useEffect, useRef } from "react";

import {
  Outlet,
  useLocation,
  useNavigate,
} from "react-router-dom";

import {
  motion,
  AnimatePresence
} from "framer-motion";

import {
  Bell,
  Search,
  ChevronDown,
  LogOut,
  Menu,
  Zap,
  MessageSquare,
  Paperclip,
  Send,
  Bot,
  X,
} from "lucide-react";

import Sidebar from "../components/Sidebar";

import { useAuth } from "../context/AuthContext";

import apiClient from "../services/api";

const pageTransition = {
  initial: {
    opacity: 0,
    y: 12,
  },

  animate: {
    opacity: 1,
    y: 0,
  },

  exit: {
    opacity: 0,
    y: -8,
  },
};

// Simple custom component to parse basic Markdown formatting (bold, headers, bullets, inline code, links, tables)
function MessageFormatter({ content }) {
  if (!content) return null;

  const lines = content.split("\n");
  const parsedElements = [];
  let currentTable = null;

  const parseInline = (text) => {
    const formatBoldAndCode = (str) => {
      const boldParts = str.split(/\*\*(.*?)\*\*/g);
      return boldParts.map((bPart, idx) => {
        if (idx % 2 === 1) {
          return <strong key={`bold-${idx}`} className="text-white font-bold">{bPart}</strong>;
        }
        
        const codeParts = bPart.split(/`(.*?)`/g);
        return codeParts.map((cPart, cIdx) => {
          if (cIdx % 2 === 1) {
            return (
              <code key={`code-${cIdx}`} className="bg-white/10 text-teal-300 font-mono text-xs px-1.5 py-0.5 rounded border border-white/5">
                {cPart}
              </code>
            );
          }
          
          const linkParts = cPart.split(/\[(.*?)\]\((.*?)\)/g);
          if (linkParts.length > 1) {
            return linkParts.map((lPart, lIdx) => {
              if (lIdx % 3 === 1) {
                const label = lPart;
                const url = linkParts[lIdx + 1];
                return (
                  <a
                    key={`link-${lIdx}`}
                    href={url}
                    className="text-[#00A19B] hover:text-[#2dd4bf] hover:underline font-semibold transition-all inline-flex items-center gap-1"
                  >
                    {label}
                  </a>
                );
              } else if (lIdx % 3 === 2) {
                return null;
              }
              return lPart;
            });
          }
          
          return cPart;
        });
      });
    };

    return formatBoldAndCode(text);
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();

    if (line.startsWith("|")) {
      const cells = line.split("|").map(c => c.trim()).filter((_, idx, arr) => idx > 0 && idx < arr.length - 1);
      
      if (line.includes("---")) {
        continue;
      }

      if (!currentTable) {
        currentTable = { headers: cells, rows: [] };
      } else {
        currentTable.rows.push(cells);
      }
      continue;
    } else if (currentTable) {
      const table = currentTable;
      parsedElements.push(
        <div key={`table-${i}`} className="my-2 overflow-x-auto rounded-lg border border-white/10 bg-white/5 text-[11px]">
          <table className="min-w-full divide-y divide-white/10">
            <thead className="bg-white/10">
              <tr>
                {table.headers.map((h, hIdx) => (
                  <th key={hIdx} className="px-2 py-1.5 text-left font-semibold text-white">
                    {parseInline(h)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {table.rows.map((row, rIdx) => (
                <tr key={rIdx} className="hover:bg-white/5">
                  {row.map((cell, cIdx) => (
                    <td key={cIdx} className="px-2 py-1 text-slate-300">
                      {parseInline(cell)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      currentTable = null;
    }

    if (line.startsWith("###")) {
      parsedElements.push(
        <h3 key={i} className="text-sm font-bold text-white mt-2 mb-1">
          {parseInline(line.substring(3).trim())}
        </h3>
      );
    } else if (line.startsWith("####")) {
      parsedElements.push(
        <h4 key={i} className="text-xs font-semibold text-white mt-1.5 mb-0.5">
          {parseInline(line.substring(4).trim())}
        </h4>
      );
    } else if (line.startsWith("-") || line.startsWith("*")) {
      parsedElements.push(
        <li key={i} className="ml-3 list-disc text-xs text-slate-300 py-0.5">
          {parseInline(line.substring(1).trim())}
        </li>
      );
    } else if (line === "") {
      parsedElements.push(<div key={i} className="h-1" />);
    } else {
      parsedElements.push(
        <p key={i} className="text-xs text-slate-300 leading-relaxed my-0.5">
          {parseInline(line)}
        </p>
      );
    }
  }

  if (currentTable) {
    const table = currentTable;
    parsedElements.push(
      <div key="table-end" className="my-2 overflow-x-auto rounded-lg border border-white/10 bg-white/5 text-[11px]">
        <table className="min-w-full divide-y divide-white/10">
          <thead className="bg-white/10">
            <tr>
              {table.headers.map((h, hIdx) => (
                <th key={hIdx} className="px-2 py-1.5 text-left font-semibold text-white">
                  {parseInline(h)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {table.rows.map((row, rIdx) => (
              <tr key={rIdx} className="hover:bg-white/5">
                {row.map((cell, cIdx) => (
                  <td key={cIdx} className="px-2 py-1 text-slate-300">
                    {parseInline(cell)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return <div className="space-y-0.5">{parsedElements}</div>;
}

export default function DashboardLayout() {
  const { user, logout } = useAuth();

  const location = useLocation();

  const navigate = useNavigate();

  const [sidebarOpen,
    setSidebarOpen] = useState(true);

  const [mobileSidebarOpen,
    setMobileSidebarOpen] = useState(false);

  const [profileOpen,
    setProfileOpen] = useState(false);

  const [notifOpen,
    setNotifOpen] = useState(false);

  const [notifications,
    setNotifications] = useState([]);

  const [chatOpen, setChatOpen] = useState(false);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [chatMessages, setChatMessages] = useState([
    {
      sender: "ai",
      text: `Welcome to Klypup AI. How can I help you today?`
    }
  ]);
  const chatMessagesEndRef = useRef(null);

  useEffect(() => {
    if (chatOpen) {
      chatMessagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [chatMessages, chatOpen]);

  const handleSendChatMessage = async (textToSend) => {
    const text = (typeof textToSend === "string" ? textToSend : chatInput).trim();
    if (!text) return;

    if (typeof textToSend !== "string") {
      setChatInput("");
    }

    setChatMessages((prev) => [...prev, { sender: "user", text }]);
    setChatLoading(true);

    try {
      const historyFormatted = chatMessages.map((m) => ({
        role: m.sender === "user" ? "user" : "assistant",
        content: m.text,
      }));

      const response = await apiClient.post("/chatbot/chat", {
        message: text,
        history: historyFormatted,
      });

      setChatMessages((prev) => [
        ...prev,
        { sender: "ai", text: response.data.response || "No response received." },
      ]);
    } catch (error) {
      console.error(error);
      setChatMessages((prev) => [
        ...prev,
        {
          sender: "ai",
          text: "⚠️ Sorry, I encountered an error communicating with the coordinator backend. Make sure the Flask server is running."
        },
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  /* ======================================
     UNREAD COUNT
  ====================================== */

  const unreadCount =
    notifications.filter(
      (n) => n.unread
    ).length;

  /* ======================================
     PAGE TITLES
  ====================================== */

  const pageTitles = {
    "/dashboard": "Dashboard",

    "/recommendations":
      "AI Recommendations",

    "/approvals":
      "Approval Queue",

    "/audit-history":
      "Audit History",

    "/products":
      "Products",
  };

  const currentTitle =
    pageTitles[location.pathname]
    || "Klypup";

  /* ======================================
     FETCH REAL NOTIFICATIONS
  ====================================== */

  const fetchNotifications = async () => {
    try {
      const [
        recsRes,
        historyRes,
        productsRes,
      ] = await Promise.all([
        apiClient.get("/recommendations"),

        apiClient.get("/approvals/history"),

        apiClient.get("/products"),
      ]);

      const recs =
        recsRes.data.recommendations || [];

      const history =
        historyRes.data.history || [];

      const products =
        productsRes.data.products || [];

      /* ======================================
         RECOMMENDATION EVENTS
      ====================================== */

      const recommendationNotifications =
        recs.map((rec) => ({
          id: `rec-${rec.id}`,

          text:
            `${rec.product?.name || "Product"} AI recommendation generated`,

          time:
            rec.created_at,

          unread: true,

          type: "ai",

          route:
            "/recommendations",
        }));

      /* ======================================
         APPROVAL EVENTS
      ====================================== */

      const historyNotifications =
        history.map((item) => ({
          id: `history-${item.id}`,

          text:
            item.action_type === "approve"

              ? `${item.product?.name || "Product"} recommendation approved`

              : `${item.product?.name || "Product"} recommendation rejected`,

          time:
            item.timestamp,

          unread: false,

          type:
            item.action_type === "approve"
              ? "success"
              : "alert",

          route:
            "/audit-history",
        }));

      /* ======================================
         LOW STOCK EVENTS
      ====================================== */

      const stockNotifications =
        products

          .filter(
            (p) =>
              p.inventory_quantity < 10
          )

          .map((p) => ({
            id: `stock-${p.id}`,

            text:
              `${p.name} inventory running low`,

            time:
              new Date(),

            unread: true,

            type: "alert",

            route:
              "/products",
          }));

      /* ======================================
         HIGH CONFIDENCE EVENTS
      ====================================== */

      const confidenceNotifications =
        recs

          .filter(
            (r) =>
              Number(r.confidence_score) >= 90
          )

          .map((r) => ({
            id:
              `confidence-${r.id}`,

            text:
              `${r.product?.name || "Product"} AI confidence reached ${r.confidence_score}%`,

            time:
              r.created_at,

            unread: true,

            type: "info",

            route:
              "/approvals",
          }));

      /* ======================================
         MERGE EVERYTHING
      ====================================== */

      const allNotifications = [
        ...recommendationNotifications,

        ...historyNotifications,

        ...stockNotifications,

        ...confidenceNotifications,
      ];

      /* ======================================
         SORT LATEST FIRST
      ====================================== */

      allNotifications.sort(
        (a, b) =>
          new Date(b.time)
          - new Date(a.time)
      );

      setNotifications(
        allNotifications.slice(0, 8)
      );

    } catch (error) {
      console.error(
        "Notification fetch error:",
        error
      );
    }
  };

  /* ======================================
     EFFECTS
  ====================================== */

  useEffect(() => {
    if (user) {
      fetchNotifications();
    }

    const handleKey = (e) => {
      if (e.key === "Escape") {
        setProfileOpen(false);

        setNotifOpen(false);

        setMobileSidebarOpen(false);
      }
    };

    window.addEventListener(
      "keydown",
      handleKey
    );

    return () =>
      window.removeEventListener(
        "keydown",
        handleKey
      );

  }, [user]);

  /* ======================================
     NOTIFICATION COLORS
  ====================================== */

  const notifColors = {
    ai:
      "from-[#00A19B] to-[#6366f1]",

    alert:
      "from-amber-500 to-orange-600",

    success:
      "from-emerald-500 to-teal-600",

    info:
      "from-sky-500 to-blue-600",
  };

  /* ======================================
     SIGN OUT HANDLER
  ====================================== */

  const handleSignOut = () => {
    logout();
    navigate("/login");
  };

  return (

    <div
      className="
        flex
        h-screen
        overflow-hidden
        font-sans
        relative
      "
      style={{
        background:
          "linear-gradient(135deg,#080b14 0%,#0f172a 45%,#0f766e 100%)",
      }}
    >

      {/* BACKGROUND GLOWS */}

      <div
        style={{
          position: "absolute",
          width: 420,
          height: 420,
          borderRadius: "50%",
          background:
            "rgba(0,161,155,0.12)",
          filter: "blur(120px)",
          top: -120,
          right: -100,
          pointerEvents: "none",
        }}
      />

      <div
        style={{
          position: "absolute",
          width: 340,
          height: 340,
          borderRadius: "50%",
          background:
            "rgba(99,102,241,0.14)",
          filter: "blur(120px)",
          bottom: -100,
          left: -80,
          pointerEvents: "none",
        }}
      />

      {/* DESKTOP SIDEBAR */}

      <div
        className={`hidden lg:flex transition-all duration-300 ease-in-out ${
          sidebarOpen ? "w-64" : "w-16"
        } flex-shrink-0 relative z-20`}
      >

        <Sidebar
          collapsed={!sidebarOpen}
          onToggle={() =>
            setSidebarOpen(
              !sidebarOpen
            )
          }
        />

      </div>

      {/* MOBILE SIDEBAR */}

      <AnimatePresence>

        {mobileSidebarOpen && (

          <>

            <motion.div
              initial={{
                opacity: 0,
              }}

              animate={{
                opacity: 1,
              }}

              exit={{
                opacity: 0,
              }}

              className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 lg:hidden"

              onClick={() =>
                setMobileSidebarOpen(false)
              }
            />

            <motion.div
              initial={{
                x: -280,
              }}

              animate={{
                x: 0,
              }}

              exit={{
                x: -280,
              }}

              transition={{
                type: "spring",
                damping: 30,
                stiffness: 300,
              }}

              className="fixed left-0 top-0 h-full w-64 z-50 lg:hidden"
            >

              <Sidebar
                collapsed={false}
                onToggle={() =>
                  setMobileSidebarOpen(false)
                }
              />

            </motion.div>

          </>
        )}

      </AnimatePresence>

      {/* MAIN CONTENT */}

      <div
        className="
          flex-1
          flex
          flex-col
          min-w-0
          overflow-hidden
          relative
          z-10
        "
      >

        {/* TOP NAVBAR */}

        <header
          className="
            h-14
            flex-shrink-0
            flex
            items-center
            justify-between
            px-4
            lg:px-6
            relative
            z-30
            border-b
            border-white/8
            backdrop-blur-xl
          "
          style={{
            background:
              "rgba(8,11,20,0.72)",

            boxShadow:
              "0 8px 30px rgba(0,0,0,0.22)",
          }}
        >

          {/* LEFT */}

          <div className="flex items-center gap-3">

            <button
              onClick={() =>
                setMobileSidebarOpen(true)
              }

              className="lg:hidden p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition-all"
            >

              <Menu size={18} />

            </button>

            <div className="flex items-center gap-2">

              <span className="text-white font-semibold text-sm tracking-tight">

                {currentTitle}

              </span>

            </div>

          </div>

          {/* SEARCH */}

          <div className="hidden md:flex items-center flex-1 max-w-xs mx-8">

            <div className="relative w-full">

              <Search
                size={14}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500"
              />

              <input
                type="text"

                placeholder="Search products, SKUs..."

                className="
                  w-full
                  h-9
                  pl-9
                  pr-4
                  rounded-xl
                  bg-white/6
                  border
                  border-white/10
                  text-sm
                  text-slate-200
                  placeholder-slate-500
                  focus:outline-none
                  focus:border-[#00A19B]
                  focus:bg-white/10
                  transition-all
                "
              />

            </div>

          </div>

          {/* RIGHT */}

          <div className="flex items-center gap-2">

            {/* ORG BADGE */}

            <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white/5 border border-white/8">

              <div className="w-4 h-4 rounded bg-gradient-to-br from-[#00A19B] to-[#6366f1] flex items-center justify-center">

                <Zap
                  size={9}
                  className="text-white"
                />

              </div>

              <span className="text-xs text-slate-300 font-medium">

                {user?.organization ||
                  "Klypup Inc."}

              </span>

            </div>

            {/* NOTIFICATIONS */}

            <div className="relative">

              <button
                onClick={() => {

                  setNotifOpen(
                    !notifOpen
                  );

                  setProfileOpen(false);
                }}

                className="relative p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition-all"
              >

                <Bell size={17} />

                {unreadCount > 0 && (

                  <motion.span
                    initial={{
                      scale: 0,
                    }}

                    animate={{
                      scale: 1,
                    }}

                    className="absolute -top-0.5 -right-0.5 w-4 h-4 rounded-full bg-gradient-to-br from-[#00A19B] to-[#6366f1] text-[9px] font-bold text-white flex items-center justify-center"
                  >

                    {unreadCount}

                  </motion.span>
                )}

              </button>

              {/* DROPDOWN */}

              <AnimatePresence>

                {notifOpen && (

                  <motion.div
                    initial={{
                      opacity: 0,
                      y: 8,
                      scale: 0.96,
                    }}

                    animate={{
                      opacity: 1,
                      y: 0,
                      scale: 1,
                    }}

                    exit={{
                      opacity: 0,
                      y: 8,
                      scale: 0.96,
                    }}

                    transition={{
                      duration: 0.15,
                    }}

                    className="absolute right-0 top-10 w-80 rounded-2xl border border-white/10 bg-[rgba(12,16,32,0.96)] backdrop-blur-xl shadow-2xl shadow-black/50 overflow-hidden z-50"
                  >

                    <div className="px-4 py-3 border-b border-white/8 flex items-center justify-between">

                      <span className="text-sm font-semibold text-white">

                        Live AI Events

                      </span>

                    </div>

                    <div className="max-h-64 overflow-y-auto">

                      {notifications.length === 0 ? (

                        <div className="px-4 py-6 text-center text-sm text-slate-500">

                          No live events available

                        </div>

                      ) : (

                        notifications.map((n) => (

                          <div
                            key={n.id}

                            onClick={() => {

                              navigate(n.route);

                              setNotifOpen(false);
                            }}

                            className={`px-4 py-3 flex gap-3 hover:bg-white/4 transition-colors cursor-pointer border-b border-white/5 last:border-0 ${
                              n.unread
                                ? "bg-white/2"
                                : ""
                            }`}
                          >

                            <div
                              className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 bg-gradient-to-br ${
                                notifColors[n.type]
                              }`}
                            />

                            <div className="flex-1 min-w-0">

                              <p
                                className={`text-xs ${
                                  n.unread
                                    ? "text-slate-200"
                                    : "text-slate-400"
                                }`}
                              >

                                {n.text}

                              </p>

                              <p className="text-[10px] text-slate-600 mt-0.5">

                                {
                                  new Date(n.time)
                                    .toLocaleString()
                                }

                              </p>

                            </div>

                          </div>
                        ))
                      )}

                    </div>

                  </motion.div>
                )}

              </AnimatePresence>

            </div>

            {/* PROFILE */}

            <div className="relative">

              <button
                onClick={() => {

                  setProfileOpen(
                    !profileOpen
                  );

                  setNotifOpen(false);
                }}

                className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-white/5 transition-all"
              >

                <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-[#00A19B] to-[#6366f1] flex items-center justify-center text-white text-xs font-bold">

                  {user?.name?.[0]
                    ?.toUpperCase() || "U"}

                </div>

                <span className="hidden sm:block text-xs text-slate-300 font-medium max-w-[80px] truncate">

                  {user?.name || "User"}

                </span>

                <ChevronDown
                  size={12}

                  className={`text-slate-500 transition-transform ${
                    profileOpen
                      ? "rotate-180"
                      : ""
                  }`}
                />

              </button>

              <AnimatePresence>

                {profileOpen && (

                  <motion.div
                    initial={{
                      opacity: 0,
                      y: 8,
                      scale: 0.96,
                    }}

                    animate={{
                      opacity: 1,
                      y: 0,
                      scale: 1,
                    }}

                    exit={{
                      opacity: 0,
                      y: 8,
                      scale: 0.96,
                    }}

                    transition={{
                      duration: 0.15,
                    }}

                    className="absolute right-0 top-11 w-52 rounded-2xl border border-white/10 bg-[rgba(12,16,32,0.96)] backdrop-blur-xl shadow-2xl shadow-black/50 overflow-hidden z-50"
                  >

                    <div className="px-4 py-3 border-b border-white/8">

                      <p className="text-sm font-semibold text-white truncate">

                        {user?.name || "User"}

                      </p>

                      <p className="text-xs text-slate-500 truncate mt-0.5">

                        {user?.email ||
                          "user@klypup.com"}

                      </p>

                    </div>

                    <div className="border-t border-white/8 mt-1 pt-1">

                      <button
                        onClick={handleSignOut}

                        className="w-full flex items-center gap-3 px-4 py-2.5 text-xs text-red-400 hover:text-red-300 hover:bg-red-500/10 transition-all"
                      >

                        <LogOut size={14} />

                        Sign out

                      </button>

                    </div>

                  </motion.div>
                )}

              </AnimatePresence>

            </div>

          </div>

        </header>

        {/* PAGE CONTENT */}

        <main className="flex-1 overflow-y-auto">

          <AnimatePresence mode="wait">

            <motion.div
              key={location.pathname}

              variants={pageTransition}

              initial="initial"

              animate="animate"

              exit="exit"

              transition={{
                duration: 0.2,
                ease: "easeOut",
              }}

              className="min-h-full px-4 py-4 lg:px-6 lg:py-5"
            >

              <Outlet />

            </motion.div>

          </AnimatePresence>

        </main>

      </div>

      {/* CLICK OUTSIDE */}

      {(profileOpen || notifOpen) && (

        <div
          className="fixed inset-0 z-20"

          onClick={() => {

            setProfileOpen(false);

            setNotifOpen(false);
          }}
        />

      )}

      {/* =========================================================================
          FLOATING CHATBOT WIDGET
      ========================================================================= */}
      <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end">
        {/* Chat window panel */}
        <AnimatePresence>
          {chatOpen && (
            <motion.div
              initial={{ opacity: 0, y: 50, scale: 0.9 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 50, scale: 0.9 }}
              transition={{ duration: 0.2, ease: "easeOut" }}
              className="w-96 h-[560px] rounded-3xl border border-white/12 shadow-2xl overflow-hidden mb-4 flex flex-col"
              style={{
                background: "linear-gradient(135deg, rgba(12, 17, 34, 0.95), rgba(8, 11, 22, 0.95))",
                boxShadow: "0 24px 60px rgba(0,0,0,0.5)",
              }}
            >
              {/* Purple Header */}
              <div 
                className="px-5 py-4 flex items-center justify-between border-b border-white/10 text-white relative overflow-hidden"
                style={{ background: "linear-gradient(135deg, #6366f1, #3b82f6)" }}
              >
                {/* Header glow */}
                <div className="absolute top-0 right-0 w-24 h-24 opacity-25 blur-xl bg-teal-400" />
                <div className="flex items-center gap-3 relative z-10">
                  <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center border border-white/10 shadow-inner">
                    <Bot size={20} className="text-white" />
                  </div>
                  <div>
                    <h4 className="text-sm font-bold tracking-wide">Klypup AI</h4>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse" />
                      <span className="text-[10px] text-blue-100 font-medium">Online</span>
                    </div>
                  </div>
                </div>
                <button 
                  onClick={() => setChatOpen(false)}
                  className="w-8 h-8 rounded-lg bg-white/10 hover:bg-white/20 flex items-center justify-center text-white/80 hover:text-white transition-all cursor-pointer border border-white/5 relative z-10"
                >
                  <X size={16} />
                </button>
              </div>

              {/* Chat Log Body */}
              <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3.5 scrollbar-thin">
                {chatMessages.map((msg, index) => (
                  <div key={index} className={`flex ${msg.sender === "user" ? "justify-end" : "justify-start"}`}>
                    <div className={`flex gap-2 max-w-[85%] ${msg.sender === "user" ? "flex-row-reverse" : "flex-row"}`}>
                      <div className={`w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0 mt-0.5 shadow ${
                        msg.sender === "user" ? "bg-indigo-600" : "bg-teal-700"
                      }`}>
                        {msg.sender === "user" ? <MessageSquare size={10} className="text-white" /> : <Bot size={10} className="text-white" />}
                      </div>
                      
                      <div className={`rounded-xl px-3 py-2 shadow border ${
                        msg.sender === "user"
                          ? "bg-indigo-600/35 border-indigo-500/30 text-white rounded-tr-none"
                          : "bg-white/5 border-white/10 text-slate-300 rounded-tl-none"
                      }`}>
                        <MessageFormatter content={msg.text} />
                      </div>
                    </div>
                  </div>
                ))}
                
                {/* Typing status */}
                {chatLoading && (
                  <div className="flex justify-start">
                    <div className="flex gap-2">
                      <div className="w-6 h-6 rounded-md flex items-center justify-center bg-teal-700 shadow">
                        <Bot size={10} className="text-white" />
                      </div>
                      <div className="bg-white/5 border border-white/10 rounded-xl rounded-tl-none px-3 py-2.5 flex items-center gap-1">
                        <div className="w-1.5 h-1.5 bg-[#00A19B] rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                        <div className="w-1.5 h-1.5 bg-[#00A19B] rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                        <div className="w-1.5 h-1.5 bg-[#00A19B] rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                      </div>
                    </div>
                  </div>
                )}
                <div ref={chatMessagesEndRef} />
              </div>

              {/* Suggestions chips */}
              <div className="px-4 py-1.5 flex gap-1.5 overflow-x-auto scrollbar-none flex-nowrap border-t border-white/5 bg-white/[0.01]">
                <button
                  onClick={() => handleSendChatMessage("help")}
                  className="flex-shrink-0 px-2.5 py-1 text-[10px] bg-white/5 hover:bg-white/10 border border-white/8 rounded-full text-slate-300 transition-all cursor-pointer"
                >
                  💡 Help Guide
                </button>
                <button
                  onClick={() => handleSendChatMessage("list products")}
                  className="flex-shrink-0 px-2.5 py-1 text-[10px] bg-white/5 hover:bg-white/10 border border-white/8 rounded-full text-slate-300 transition-all cursor-pointer"
                >
                  📋 Catalog
                </button>
                <button
                  onClick={() => handleSendChatMessage("analyse Premium Wireless Headphones")}
                  className="flex-shrink-0 px-2.5 py-1 text-[10px] bg-white/5 hover:bg-white/10 border border-white/8 rounded-full text-slate-300 transition-all cursor-pointer"
                >
                  🧠 Analyze SKU-000
                </button>
              </div>

              {/* Input Form Footer */}
              <div className="p-3 border-t border-white/8 bg-white/5 flex flex-col gap-2">
                <form 
                  onSubmit={(e) => {
                    e.preventDefault();
                    handleSendChatMessage();
                  }}
                  className="flex items-center gap-2 bg-white/5 border border-white/10 rounded-full px-3 py-1.5 focus-within:border-indigo-500/50 transition-all"
                >
                  <button type="button" className="text-slate-400 hover:text-white transition-all cursor-pointer">
                    <Paperclip size={14} />
                  </button>
                  <input
                    type="text"
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    placeholder="Type a message..."
                    className="flex-1 bg-transparent text-white text-xs outline-none placeholder:text-slate-500 py-1"
                  />
                  <button 
                    type="submit" 
                    disabled={!chatInput.trim() || chatLoading}
                    className="w-7 h-7 rounded-full bg-[#6366f1] hover:bg-[#4f46e5] text-white flex items-center justify-center transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <Send size={12} />
                  </button>
                </form>
                <div className="text-center text-[9px] text-slate-600 tracking-wider">
                  Powered by Klypup
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Circular toggle button */}
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={() => setChatOpen(!chatOpen)}
          className="w-14 h-14 rounded-full bg-gradient-to-br from-[#6366f1] to-[#3b82f6] hover:from-[#4f46e5] hover:to-[#2563eb] text-white flex items-center justify-center shadow-lg shadow-indigo-650/40 cursor-pointer border border-white/10 relative"
        >
          {chatOpen ? <X size={22} /> : <MessageSquare size={22} />}
          {/* Notification Badge if closed */}
          {!chatOpen && (
            <span className="absolute top-0 right-0 w-3.5 h-3.5 bg-emerald-400 border-2 border-slate-900 rounded-full" />
          )}
        </motion.button>
      </div>

    </div>
  );
}
