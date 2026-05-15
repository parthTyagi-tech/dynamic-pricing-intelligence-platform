import { useState, useEffect } from "react";

import {
  Outlet,
  useLocation,
  useNavigate,
} from "react-router-dom";

import {
  motion,
  AnimatePresence,
} from "framer-motion";

import {
  Bell,
  Search,
  ChevronDown,
  LogOut,
  Menu,
  Zap,
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
      "from-violet-500 to-purple-600",

    alert:
      "from-amber-500 to-orange-600",

    success:
      "from-emerald-500 to-teal-600",

    info:
      "from-sky-500 to-blue-600",
  };


  return (

    <div className="flex h-screen bg-[#080b14] overflow-hidden font-sans">

      {/* DESKTOP SIDEBAR */}

      <div
        className={`hidden lg:flex transition-all duration-300 ease-in-out ${
          sidebarOpen ? "w-64" : "w-16"
        } flex-shrink-0`}
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

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">

        {/* TOP NAVBAR */}

        <header className="h-14 flex-shrink-0 flex items-center justify-between px-4 lg:px-6 border-b border-white/5 bg-[#080b14]/80 backdrop-blur-xl relative z-30">

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

                className="w-full h-8 pl-8 pr-4 rounded-lg bg-white/5 border border-white/8 text-sm text-slate-300 placeholder-slate-600 focus:outline-none focus:border-violet-500/50 focus:bg-white/8 transition-all"
              />

            </div>

          </div>


          {/* RIGHT */}

          <div className="flex items-center gap-2">

            {/* ORG BADGE */}

            <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white/5 border border-white/8">

              <div className="w-4 h-4 rounded bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center">

                <Zap
                  size={9}
                  className="text-white"
                />

              </div>

              <span className="text-xs text-slate-400 font-medium">

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

                    className="absolute -top-0.5 -right-0.5 w-4 h-4 rounded-full bg-gradient-to-br from-violet-500 to-purple-600 text-[9px] font-bold text-white flex items-center justify-center"
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

                    className="absolute right-0 top-10 w-80 rounded-xl border border-white/10 bg-[#0e1220]/95 backdrop-blur-xl shadow-2xl shadow-black/50 overflow-hidden z-50"
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

                <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center text-white text-xs font-bold">

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

                    className="absolute right-0 top-11 w-52 rounded-xl border border-white/10 bg-[#0e1220]/95 backdrop-blur-xl shadow-2xl shadow-black/50 overflow-hidden z-50"
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
                        onClick={logout}

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

              className="min-h-full"
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

    </div>
  );
}