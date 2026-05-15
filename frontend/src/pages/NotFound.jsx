// ===============================
// NotFound.jsx
// ===============================

import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { AlertTriangle } from "lucide-react";

export default function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-[#080b14] px-6">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        className="max-w-md w-full rounded-3xl border border-white/10 bg-white/5 backdrop-blur-xl p-10 text-center"
      >
        <div className="w-16 h-16 rounded-2xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center mx-auto mb-5">
          <AlertTriangle
            size={28}
            className="text-violet-400"
          />
        </div>

        <h1 className="text-5xl font-bold text-white mb-3">
          404
        </h1>

        <p className="text-slate-400 leading-relaxed">
          The page you’re looking for doesn’t exist
          or has been moved.
        </p>

        <Link
          to="/dashboard"
          className="inline-flex items-center justify-center mt-6 px-5 py-3 rounded-xl bg-violet-600 hover:bg-violet-500 text-white font-semibold transition-all"
        >
          Return Dashboard
        </Link>
      </motion.div>
    </div>
  );
}