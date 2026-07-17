import { useState } from "react";

import {
  Link,
  useNavigate,
  useLocation,
} from "react-router-dom";

import {
  motion,
  AnimatePresence,
} from "framer-motion";

import {
  Mail,
  Lock,
  Eye,
  EyeOff,
  AlertCircle,
  Zap,
  Sparkles,
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
        gap: 8,
      }}
    >

      <label
        htmlFor={id}
        style={{
          fontSize: "0.7rem",
          fontWeight: 700,
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
            left: 16,
            top: "50%",
            transform: "translateY(-50%)",

            color: error
              ? "#ef4444"
              : "rgba(255,255,255,0.55)",

            pointerEvents: "none",

            display: "flex",
          }}
        >

          <Icon size={16} />

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

            padding:
              "14px 44px 14px 46px",

            borderRadius: 24,

            background:
              "#171717",

            border: `1px solid ${
              error
                ? "#ef4444"
                : "rgba(255,255,255,0.03)"
            }`,

            boxShadow:
              "inset 2px 5px 10px rgba(0,0,0,0.5), inset -1px -1px 2px rgba(255,255,255,0.05)",

            color: "#ffffff",

            fontSize: "0.92rem",

            outline: "none",

            transition: "0.4s ease-in-out",
          }}
        />

        {right && (

          <span
            style={{
              position: "absolute",
              right: 16,
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

              fontSize: "0.74rem",

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

  const [authError, setAuthError] =
    useState("");

  const [showPw, setShowPw] =
    useState(false);

  const [loading, setLoading] =
    useState(false);

  const set = (field) => (e) => {

    setForm((f) => ({
      ...f,
      [field]: e.target.value,
    }));

    setErrors((er) => ({
      ...er,
      [field]: "",
    }));

    setAuthError("");
  };

  const validate = () => {

    const e = {};

    if (!form.email) {

      e.email =
        "Email is required";

    } else if (
      !/\S+@\S+\.\S+/.test(form.email)
    ) {

      e.email =
        "Invalid email address";
    }

    if (!form.password) {

      e.password =
        "Password is required";

    } else if (
      form.password.length < 6
    ) {

      e.password =
        "At least 6 characters";
    }

    return e;
  };

  const handleSubmit = async (ev) => {

    ev.preventDefault();

    setAuthError("");

    const errs = validate();

    if (Object.keys(errs).length) {

      setErrors(errs);

      return;
    }

    setLoading(true);

    try {

      await login(form);

      navigate(from, {
        replace: true,
      });

    } catch (err) {

      console.log(err);

      const message =
        err.response?.data?.message ||
        "Invalid email or password";

      setAuthError(message);

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

        padding: 20,

        position: "relative",

        overflow: "hidden",

        background: "transparent",
      }}
    >

      <motion.div
        variants={containerV}

        initial="hidden"

        animate="visible"

        style={{
          width: "100%",
          maxWidth: 500,
          position: "relative",
          zIndex: 10,
        }}
      >

        <motion.div
          whileHover={{ scale: 1.05 }}
          transition={{ duration: 0.4, ease: "easeInOut" }}
          style={{
            borderRadius: 25,

            padding: 24,

            display: "flex",

            flexDirection: "column",

            gap: 16,

            background:
              "#171717",

            border:
              "1px solid rgba(255,255,255,0.05)",

            boxShadow:
              "0 32px 80px rgba(0,0,0,0.55)",
          }}
        >

          {/* LOGO */}

          <motion.div
            variants={itemV}

            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 14,
              textAlign: "center",
            }}
          >

            <div
              style={{
                width: 56,
                height: 56,

                borderRadius: 18,

                background:
                  "linear-gradient(135deg,#047857,#10b981)",

                display: "flex",

                alignItems: "center",

                justifyContent: "center",

                boxShadow:
                  "0 14px 30px rgba(0,161,155,0.25)",
              }}
            >

              <Zap
                size={24}
                color="white"
              />

            </div>

            <div>

              <div
                style={{
                  fontSize: "1.3rem",
                  fontWeight: 700,
                  color: "#ffffff",
                }}
              >

                Klypup

              </div>

              <div
                style={{
                  fontSize: "0.68rem",

                  letterSpacing: "0.2em",

                  textTransform:
                    "uppercase",

                  color:
                    "rgba(255,255,255,0.68)",

                  marginTop: 3,
                }}
              >

                AI Pricing Intelligence

              </div>

            </div>

          </motion.div>

          {/* HEADER */}

          <motion.div variants={itemV}>

            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 8,

                padding:
                  "8px 14px",

                borderRadius: 999,

                background:
                  "rgba(0,161,155,0.10)",

                border:
                  "1px solid rgba(0,161,155,0.18)",

                color: "#ffffff",

                fontSize: "0.76rem",

                fontWeight: 600,

                marginBottom: 18,
              }}
            >

              <Sparkles size={14} />

              Secure Workspace Access

            </div>

            <h1
              style={{
                margin: 0,

                fontSize: "2rem",

                fontWeight: 700,

                color: "#ffffff",
              }}
            >

              Welcome back

            </h1>

            <p
              style={{
                marginTop: 8,

                fontSize: "0.95rem",

                color:
                  "rgba(255,255,255,0.72)",

                lineHeight: 1.7,
              }}
            >

              Sign in to continue managing
              intelligent pricing analytics
              and recommendation workflows.

            </p>

          </motion.div>

          {/* FORM */}

          <motion.form
            variants={itemV}

            onSubmit={handleSubmit}

            style={{
              display: "flex",
              flexDirection: "column",
              gap: 12,
            }}
          >
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-2 text-left">
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
                showPw
                  ? "text"
                  : "password"
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

                    <EyeOff size={15} />

                  ) : (

                    <Eye size={15} />
                  )}

                </button>
              }
            />
            </div>

            <AnimatePresence>

              {authError && (

                <motion.div
                  initial={{
                    opacity: 0,
                    y: -5,
                  }}

                  animate={{
                    opacity: 1,
                    y: 0,
                  }}

                  exit={{
                    opacity: 0,
                    y: -5,
                  }}

                  style={{
                    padding:
                      "13px 15px",

                    borderRadius: 14,

                    background:
                      "rgba(239,68,68,0.10)",

                    border:
                      "1px solid rgba(239,68,68,0.28)",

                    color: "#ef4444",

                    fontSize: "0.84rem",

                    display: "flex",

                    alignItems: "center",

                    gap: 8,
                  }}
                >

                  <AlertCircle size={16} />

                  {authError}

                </motion.div>
              )}

            </AnimatePresence>

            <div style={{ display: "flex", gap: 12, width: "100%", marginTop: 8 }}>
              <motion.button
                type="submit"
                disabled={loading}
                whileHover={{ scale: loading ? 1 : 1.05 }}
                whileTap={{ scale: loading ? 1 : 0.95 }}
                style={{
                  flex: 1,
                  padding: "12px 0",
                  borderRadius: 12,
                  border: "none",
                  background: "#212121",
                  color: "white",
                  fontSize: "0.85rem",
                  fontWeight: 600,
                  cursor: loading ? "not-allowed" : "pointer",
                  transition: "0.2s ease-in-out",
                  boxShadow: "3px 3px 6px rgba(0,0,0,0.5), -1px -1px 2px rgba(255,255,255,0.05)"
                }}
              >
                {loading ? "Signing in..." : "Login"}
              </motion.button>

              <motion.button
                type="button"
                onClick={() => navigate("/signup")}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                style={{
                  flex: 1,
                  padding: "12px 0",
                  borderRadius: 12,
                  border: "none",
                  background: "#212121",
                  color: "white",
                  fontSize: "0.85rem",
                  fontWeight: 600,
                  cursor: "pointer",
                  transition: "0.2s ease-in-out",
                  boxShadow: "3px 3px 6px rgba(0,0,0,0.5), -1px -1px 2px rgba(255,255,255,0.05)"
                }}
              >
                Sign Up
              </motion.button>
            </div>

            <div style={{ textAlign: "center", marginTop: 4 }}>
              <motion.button
                type="button"
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                style={{
                  padding: "10px 24px",
                  borderRadius: 12,
                  border: "none",
                  background: "#212121",
                  color: "rgba(255,255,255,0.8)",
                  fontSize: "0.80rem",
                  cursor: "pointer",
                  boxShadow: "3px 3px 6px rgba(0,0,0,0.5), -1px -1px 2px rgba(255,255,255,0.05)"
                }}
              >
                Forgot Password
              </motion.button>
            </div>

          </motion.form>

        </motion.div>

      </motion.div>

    </div>
  );
}