import { useState } from "react";
import { auth } from "@/lib/api";

interface Props {
  onLogin: () => void;
}

export function Login({ onLogin }: Props) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await auth.login(email, password);
      onLogin();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-semibold tracking-tight text-white">tux.ai</h1>
          <p className="mt-1 text-sm text-white/50">Sign in to your workspace</p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="rounded-2xl border border-white/10 bg-surface-raised p-6 shadow-2xl"
        >
          {error && (
            <div className="mb-4 rounded-lg border border-red-500/30 bg-red-900/20 px-3 py-2 text-sm text-red-400">
              {error}
            </div>
          )}

          <div className="space-y-4">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-white/60">
                Email
              </label>
              <input
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-lg border border-white/10 bg-surface px-3 py-2 text-sm text-white placeholder-white/20 outline-none focus:border-accent focus:ring-1 focus:ring-accent/50 transition-colors"
                placeholder="you@company.com"
              />
            </div>

            <div>
              <label className="mb-1.5 block text-xs font-medium text-white/60">
                Password
              </label>
              <input
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-lg border border-white/10 bg-surface px-3 py-2 text-sm text-white placeholder-white/20 outline-none focus:border-accent focus:ring-1 focus:ring-accent/50 transition-colors"
                placeholder="••••••••"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="mt-6 w-full rounded-lg bg-accent py-2.5 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50 transition-colors"
          >
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}
