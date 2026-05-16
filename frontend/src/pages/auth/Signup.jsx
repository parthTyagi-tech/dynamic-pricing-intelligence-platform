import { useState } from "react";

import {
  Link,
  useNavigate,
} from "react-router-dom";

import {
  motion,
  AnimatePresence,
} from "framer-motion";

import {
  User,
  Mail,
  Lock,
  Building2,
  Eye,
  EyeOff,
  AlertCircle,
  CheckCircle2,
  ArrowRight,
  Zap,
  Sparkles,
} from "lucide-react";

import { useAuth } from "../../context/AuthContext";

const containerV = {
  hidden: {},

  visible: {
    transition: {
      staggerChildren: 0.08,
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

          autoComplete="off"

          style={{
            width: "100%",

            boxSizing: "border-box",

            padding:
              "14px 44px 14px 46px",

            borderRadius: 16,

            background:
              "rgba(255,255,255,0.05)",

            border: `1px solid ${
              error
                ? "#ef4444"
                : "rgba(255,255,255,0.08)"
            }`,

            color: "#ffffff",

            fontSize: "0.92rem",

            outline: "none",

            transition: "0.2s ease",

            backdropFilter: "blur(10px)",
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

function pwStrength(password) {

  if (!password) return 0;

  let score = 0;

  if (password.length >= 8) score++;

  if (/[A-Z]/.test(password)) score++;

  if (/[0-9]/.test(password)) score++;

  if (/[^A-Za-z0-9]/.test(password)) score++;

  return score;
}

const strengthLabels = [
  "",
  "Weak",
  "Fair",
  "Good",
  "Strong",
];

const strengthColors = [
  "",
  "#ef4444",
  "#f59e0b",
  "#22c55e",
  "#10b981",
];

export default function Signup() {

  const { signup } = useAuth();

  const navigate = useNavigate();

  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
    organization_name: "",
  });

  const [errors, setErrors] =
    useState({});

  const [showPw, setShowPw] =
    useState(false);

  const [loading, setLoading] =
    useState(false);

  const [apiError, setApiError] =
    useState("");

  const [success, setSuccess] =
    useState(false);

  const strength =
    pwStrength(form.password);

  const set = (field) => (e) => {

    setForm((f) => ({
      ...f,
      [field]: e.target.value,
    }));

    setErrors((er) => ({
      ...er,
      [field]: "",
    }));

    setApiError("");
  };

  const validate = () => {

    const e = {};

    if (!form.name.trim()) {

      e.name =
        "Full name is required";
    }

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

    if (
      !form.organization_name.trim()
    ) {

      e.organization_name =
        "Organization name is required";
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

    setApiError("");

    try {

      await signup(form);

      setSuccess(true);

      setTimeout(() => {

        navigate("/dashboard", {
          replace: true,
        });

      }, 1000);

    } catch (err) {

      console.log(err);

      setApiError(

        err.response?.data?.message ||

        err.response?.data?.error ||

        "Registration failed. Please try again."
      );

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

        background:
          "linear-gradient(135deg,#080b14 0%,#0f172a 45%,#0f766e 100%)",
      }}
    >

      {/* GLOW */}

      <div
        style={{
          position: "absolute",

          width: 320,
          height: 320,

          borderRadius: "50%",

          background:
            "rgba(0,161,155,0.16)",

          filter: "blur(120px)",

          top: -100,
          right: -100,
        }}
      />

      <div
        style={{
          position: "absolute",

          width: 260,
          height: 260,

          borderRadius: "50%",

          background:
            "rgba(99,102,241,0.14)",

          filter: "blur(120px)",

          bottom: -80,
          left: -80,
        }}
      />

      <motion.div
        variants={containerV}

        initial="hidden"

        animate="visible"

        style={{
          width: "100%",
          maxWidth: 460,
          position: "relative",
          zIndex: 10,
        }}
      >

        <div
          style={{
            borderRadius: 28,

            padding: 40,

            display: "flex",

            flexDirection: "column",

            gap: 30,

            background:
              "rgba(12,16,32,0.82)",

            backdropFilter:
              "blur(18px)",

            border:
              "1px solid rgba(255,255,255,0.08)",

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
                  "linear-gradient(135deg,#00A19B,#6366f1)",

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

                color: "#7FF6EE",

                fontSize: "0.76rem",

                fontWeight: 600,

                marginBottom: 18,
              }}
            >

              <Sparkles size={14} />

              Create Secure Workspace

            </div>

            <h1
              style={{
                margin: 0,

                fontSize: "2rem",

                fontWeight: 700,

                color: "#ffffff",
              }}
            >

              Create your account

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

              Start managing intelligent pricing analytics,
              competitor monitoring and recommendation workflows.

            </p>

          </motion.div>

          {/* FORM */}

          <motion.form
            variants={itemV}

            onSubmit={handleSubmit}

            style={{
              display: "flex",
              flexDirection: "column",
              gap: 18,
            }}
          >

            <Field
              label="Full Name"
              id="name"
              type="text"
              value={form.name}
              onChange={set("name")}
              placeholder="John Doe"
              Icon={User}
              error={errors.name}
            />

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
              label="Organization"
              id="organization"
              type="text"
              value={form.organization_name}
              onChange={set("organization_name")}
              placeholder="Acme Corp"
              Icon={Building2}
              error={
                errors.organization_name
              }
            />

            {/* PASSWORD */}

            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 6,
              }}
            >

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

                placeholder="Min. 6 characters"

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

              {form.password && (

                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: 5,
                  }}
                >

                  <div
                    style={{
                      display: "flex",
                      gap: 4,
                    }}
                  >

                    {[1, 2, 3, 4].map(
                      (i) => (

                        <div
                          key={i}

                          style={{
                            flex: 1,
                            height: 4,

                            borderRadius: 999,

                            background:
                              i <= strength

                                ? strengthColors[
                                    strength
                                  ]

                                : "rgba(255,255,255,0.08)",

                            transition:
                              "0.3s",
                          }}
                        />
                      )
                    )}

                  </div>

                  <p
                    style={{
                      margin: 0,

                      fontSize: "0.72rem",

                      color:
                        strengthColors[
                          strength
                        ],
                    }}
                  >

                    {
                      strengthLabels[
                        strength
                      ]
                    }

                  </p>

                </div>
              )}

            </div>

            {/* API ERROR */}

            <AnimatePresence>

              {apiError && (

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

                  {apiError}

                </motion.div>
              )}

            </AnimatePresence>

            {/* SUCCESS */}

            <AnimatePresence>

              {success && (

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
                      "rgba(34,197,94,0.10)",

                    border:
                      "1px solid rgba(34,197,94,0.28)",

                    color: "#22c55e",

                    fontSize: "0.84rem",

                    display: "flex",

                    alignItems: "center",

                    gap: 8,
                  }}
                >

                  <CheckCircle2 size={16} />

                  Account created successfully

                </motion.div>
              )}

            </AnimatePresence>

            {/* BUTTON */}

            <motion.button
              type="submit"

              disabled={
                loading || success
              }

              whileHover={{
                scale:
                  loading || success
                    ? 1
                    : 1.02,
              }}

              whileTap={{
                scale:
                  loading || success
                    ? 1
                    : 0.98,
              }}

              style={{
                width: "100%",

                padding:
                  "15px 0",

                borderRadius: 16,

                border: "none",

                background:
                  "linear-gradient(135deg,#00A19B,#6366f1)",

                color: "white",

                fontSize: "0.94rem",

                fontWeight: 700,

                cursor:
                  loading || success
                    ? "not-allowed"
                    : "pointer",

                opacity:
                  loading || success
                    ? 0.7
                    : 1,

                boxShadow:
                  "0 14px 30px rgba(0,161,155,0.20)",

                display: "flex",

                alignItems: "center",

                justifyContent: "center",

                gap: 8,
              }}
            >

              {loading ? (

                "Creating account..."

              ) : (

                <>
                  Create account

                  <ArrowRight size={16} />
                </>
              )}

            </motion.button>

          </motion.form>

          {/* FOOTER */}

          <motion.p
            variants={itemV}

            style={{
              margin: 0,

              textAlign: "center",

              fontSize: "0.88rem",

              color:
                "rgba(255,255,255,0.75)",
            }}
          >

            Already have an account?{" "}

            <Link
              to="/login"

              style={{
                color: "#00A19B",

                fontWeight: 700,

                textDecoration: "none",
              }}
            >

              Sign in

            </Link>

          </motion.p>

        </div>

      </motion.div>

    </div>
  );
}