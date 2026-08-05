# Custom Agent Rules: Ponytail

Before writing any code or proposing modifications in this workspace, the agent must traverse the **Ponytail Decision Ladder** to avoid over-engineering, bloat, and unnecessary dependencies.

## The Ponytail Decision Ladder

1. **Does this need to exist? (YAGNI)**
   * Avoid adding features the user has not explicitly requested or that do not directly serve the core objective.
   * If a feature is a nice-to-have but not critical, ask or default to not writing it.

2. **Does the standard library handle it?**
   * Favor built-in Python modules (e.g., `re`, `json`, `math`, `urllib`, `collections`) or native JavaScript APIs (e.g., `Array.prototype` methods, `Math`) over third-party utilities.

3. **Is there a native platform/browser feature?**
   * Rely on native HTML5 inputs, CSS custom properties/animations, and web standards before reaching for libraries.

4. **Does an already-installed dependency solve it?**
   * Check `requirements.txt` (Python) and `package.json` (JavaScript) before proposing any new packages. If a library like `requests`, `cryptography`, or `Flask-Cors` is already present, use it.

5. **Can it be done in one or a few lines?**
   * Prefer clean, standard, and compact syntax. Avoid creating multi-layered abstractions, new classes, or design-pattern wrappers unless strictly necessary for safety.

6. **Do not compromise on essential safeguards:**
   * Being "lazy" does not mean neglecting security, input validation, accessibility, database rollbacks, or clean error handling. Always handle failure cases robustly.
