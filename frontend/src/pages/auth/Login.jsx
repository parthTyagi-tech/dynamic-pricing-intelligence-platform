import { useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  Mail,
  Lock,
  Eye,
  EyeOff,
  AlertCircle,
  ArrowRight,
  Zap,
} from "lucide-react";
import { useAuth } from "../../context/AuthContext";

const containerV = {
  hidden: {},
  visible: {
    transition: {
      staggerChildren: 0.09,
      delayChildren: 0.1,
    },
  },
};

const itemV = {
  hidden: {
    opacity: 0,
    y: 22,
  },

  visible: {
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.6,
    },
  },
};

function Field({
  label,
  id,
  type,
  value,
  onChange,
  placeholder,
  Icon,
  error,
  right,
}) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 6,
      }}
    >
      <label
        htmlFor={id}
        style={{
          fontSize: "0.68rem",
          fontWeight: 600,
          letterSpacing: "0.14em",
          textTransform: "uppercase",
          color: "rgba(255,255,255,0.75)",
        }}
      >
        {label}
      </label>

      <div style={{ position: "relative" }}>
        <span
          style={{
            position: "absolute",
            left: 14,
            top: "50%",
            transform: "translateY(-50%)",
            color: error
              ? "#ef4444"
              : "rgba(255,255,255,0.6)",
            pointerEvents: "none",
            display: "flex",
          }}
        >
          <Icon size={15} />
        </span>

        <input
          id={id}
          type={type}
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          autoComplete={
            type === "password"
              ? "current-password"
              : "email"
          }
          style={{
            width: "100%",
            boxSizing: "border-box",
            padding: "12px 40px 12px 42px",
            borderRadius: 12,
            background: "rgba(255,255,255,0.04)",
            border: `1px solid ${
              error
                ? "#ef4444"
                : "rgba(255,255,255,0.12)"
            }`,
            color: "#ffffff",
            fontSize: "0.875rem",
            outline: "none",
          }}
        />

        {right && (
          <span
            style={{
              position: "absolute",
              right: 14,
              top: "50%",
              transform: "translateY(-50%)",
            }}
          >
            {right}
          </span>
        )}
      </div>

      <AnimatePresence>
        {error && (
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 5,
              fontSize: "0.72rem",
              color: "#ef4444",
              margin: 0,
            }}
          >
            <AlertCircle size={11} />
            {error}
          </motion.p>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function Login() {
  const { login } = useAuth();

  const navigate = useNavigate();
  const location = useLocation();

  const from =
    location.state?.from?.pathname ||
    "/dashboard";

  const [form, setForm] = useState({
    email: "",
    password: "",
  });

  const [errors, setErrors] = useState({});
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);

  const set = (field) => (e) => {
    setForm((f) => ({
      ...f,
      [field]: e.target.value,
    }));

    setErrors((er) => ({
      ...er,
      [field]: "",
    }));
  };

  const validate = () => {
    const e = {};

    if (!form.email) {
      e.email = "Email is required";
    } else if (
      !/\S+@\S+\.\S+/.test(form.email)
    ) {
      e.email = "Invalid email address";
    }

    if (!form.password) {
      e.password = "Password is required";
    } else if (form.password.length < 6) {
      e.password = "At least 6 characters";
    }

    return e;
  };

  const handleSubmit = async (ev) => {
    ev.preventDefault();

    const errs = validate();

    if (Object.keys(errs).length) {
      setErrors(errs);
      return;
    }

    setLoading(true);

    try {
      await login(form);
      navigate(from, { replace: true });
    } catch (err) {
      console.log(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 16,
        background: "#080b14",
      }}
    >
      <motion.div
        variants={containerV}
        initial="hidden"
        animate="visible"
        style={{
          width: "100%",
          maxWidth: 440,
        }}
      >
        <div
          style={{
            borderRadius: 20,
            padding: 36,
            display: "flex",
            flexDirection: "column",
            gap: 28,
            background: "rgba(12,16,32,0.95)",
            border:
              "1px solid rgba(255,255,255,0.08)",
            boxShadow:
              "0 32px 80px rgba(0,0,0,0.55)",
          }}
        >
          <motion.div
            variants={itemV}
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 12,
              textAlign: "center",
            }}
          >
            <div
              style={{
                width: 48,
                height: 48,
                borderRadius: 14,
                background:
                  "linear-gradient(135deg,#6366f1,#8b5cf6)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Zap size={22} color="white" />
            </div>

            <div>
              <div
                style={{
                  fontSize: "1.15rem",
                  fontWeight: 700,
                  color: "#ffffff",
                }}
              >
                Klypup
              </div>

              <div
                style={{
                  fontSize: "0.65rem",
                  letterSpacing: "0.2em",
                  textTransform: "uppercase",
                  color:
                    "rgba(255,255,255,0.7)",
                  marginTop: 2,
                }}
              >
                AI Pricing Intelligence
              </div>
            </div>
          </motion.div>

          <motion.div variants={itemV}>
            <h1
              style={{
                margin: 0,
                fontSize: "1.6rem",
                fontWeight: 700,
                color: "#ffffff",
              }}
            >
              Welcome back
            </h1>

            <p
              style={{
                marginTop: 4,
                fontSize: "0.875rem",
                color:
                  "rgba(255,255,255,0.75)",
              }}
            >
              Sign in to your workspace
            </p>
          </motion.div>

          <motion.form
            variants={itemV}
            onSubmit={handleSubmit}
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 16,
            }}
          >
            <Field
              label="Email"
              id="email"
              type="email"
              value={form.email}
              onChange={set("email")}
              placeholder="you@company.com"
              Icon={Mail}
              error={errors.email}
            />

            <Field
              label="Password"
              id="password"
              type={
                showPw ? "text" : "password"
              }
              value={form.password}
              onChange={set("password")}
              placeholder="••••••••"
              Icon={Lock}
              error={errors.password}
              right={
                <button
                  type="button"
                  onClick={() =>
                    setShowPw((s) => !s)
                  }
                  style={{
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    color:
                      "rgba(255,255,255,0.6)",
                  }}
                >
                  {showPw ? (
                    <EyeOff size={14} />
                  ) : (
                    <Eye size={14} />
                  )}
                </button>
              }
            />

            <motion.button
              type="submit"
              disabled={loading}
              whileHover={{
                scale: loading ? 1 : 1.02,
              }}
              whileTap={{
                scale: loading ? 1 : 0.98,
              }}
              style={{
                width: "100%",
                padding: "13px 0",
                borderRadius: 12,
                border: "none",
                background:
                  "linear-gradient(135deg,#6366f1,#8b5cf6)",
                color: "white",
                fontSize: "0.875rem",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              {loading
                ? "Signing in..."
                : "Sign in"}
            </motion.button>
          </motion.form>

          <motion.p
            variants={itemV}
            style={{
              margin: 0,
              textAlign: "center",
              fontSize: "0.85rem",
              color: "rgba(255,255,255,0.75)",
            }}
          >
            Don't have an account?{" "}
            <Link
              to="/signup"
              style={{
                color: "#6366f1",
                fontWeight: 600,
                textDecoration: "none",
              }}
            >
              Create one
            </Link>
          </motion.p>
        </div>
      </motion.div>
    </div>
  );
}