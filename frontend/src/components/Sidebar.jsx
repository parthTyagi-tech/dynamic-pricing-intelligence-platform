import {
  LayoutDashboard,
  Package,
  Sparkles,
  CheckCircle,
  History,
  LogOut,
} from "lucide-react";

import { NavLink } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const navItems = [
  {
    label: "Dashboard",
    icon: LayoutDashboard,
    path: "/dashboard",
  },
  {
    label: "Products",
    icon: Package,
    path: "/products",
  },
  {
    label: "Recommendations",
    icon: Sparkles,
    path: "/recommendations",
  },
  {
    label: "Approvals",
    icon: CheckCircle,
    path: "/approvals",
  },
  {
    label: "Audit History",
    icon: History,
    path: "/audit-history",
  },
];

export default function Sidebar() {
  const { logout } = useAuth();

  return (
    <aside className="w-64 min-h-screen bg-[#0f172a] border-r border-white/10 flex flex-col">
      <div className="p-6 border-b border-white/10">
        <h1 className="text-2xl font-bold text-white">
          Klypup
        </h1>

        <p className="text-sm text-slate-400 mt-1">
          AI Pricing Engine
        </p>
      </div>

      <nav className="flex-1 p-4 space-y-2">
        {navItems.map((item) => {
          const Icon = item.icon;

          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${
                  isActive
                    ? "bg-violet-500/20 text-violet-300"
                    : "text-slate-400 hover:bg-white/5 hover:text-white"
                }`
              }
            >
              <Icon size={18} />

              <span>{item.label}</span>
            </NavLink>
          );
        })}
      </nav>

      <div className="p-4 border-t border-white/10">
        <button
          onClick={logout}
          className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-all"
        >
          <LogOut size={16} />

          Logout
        </button>
      </div>
    </aside>
  );
}