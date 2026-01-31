import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "../store/auth";
import { apiFetch } from "../api/client";

export default function LoginPage() {
  const nav = useNavigate();
  const setToken = useAuthStore((s) => s.setToken);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    setErr("");
    setLoading(true);
    try {
      // Adjust path to match your auth service route.
      // Example assumes proxy routes /api -> auth-service and auth routes under /auth
      const resp = await apiFetch("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });

      // Adjust token field name depending on your backend response
      const token = resp?.access_token || resp?.token || "";
      if (!token) throw new Error("No token returned from server");

      setToken(token);
      nav("/app", { replace: true });
    } catch (e2) {
      setErr(e2.message || "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-8">
      <div className="w-full max-w-md panel p-6">
        <div className="text-xl font-semibold">Memoir</div>
        <div className="text-sm opacity-70">The Memory Layer</div>

        <form onSubmit={onSubmit} className="mt-6 space-y-3">
          <div>
            <div className="text-xs opacity-70 mb-1">Email</div>
            <input
              className="w-full bg-transparent border border-white/10 rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-white/30"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
            />
          </div>

          <div>
            <div className="text-xs opacity-70 mb-1">Password</div>
            <input
              type="password"
              className="w-full bg-transparent border border-white/10 rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-white/30"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </div>

          {err && (
            <div className="text-xs text-red-300 border border-red-500/30 bg-red-500/10 rounded-xl p-2">
              {err}
            </div>
          )}

          <button
            disabled={loading}
            className="w-full rounded-xl bg-white/10 hover:bg-white/20 transition px-4 py-2 text-sm disabled:opacity-50"
          >
            {loading ? "Signing in..." : "Sign in"}
          </button>

          <div className="text-xs opacity-60 pt-2">
            Tip: local dev tokens are stored in your browser for now. We’ll move to httpOnly cookies later when we deploy.
          </div>
        </form>
      </div>
    </div>
  );
}
 