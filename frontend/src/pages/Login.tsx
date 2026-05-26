import { useState } from "react";
import { auth } from "@/lib/api";

interface Props {
  onLogin: () => void;
}

export function Login({ onLogin }: Readonly<Props>) {
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

  const inputCls =
    "w-full rounded-xl border border-white/8 bg-white/4 px-4 py-3 text-sm text-white placeholder-white/20 outline-none transition-all focus:border-accent/40 focus:ring-2 focus:ring-accent/8";

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-surface px-4">
      <div className="w-full max-w-[340px]">
        {/* Logo */}
        <div className="mb-10 flex flex-col items-center gap-4">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-accent/10 ring-1 ring-accent/20">
            <svg
              className="h-5 w-5 text-accent"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.5}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z"
              />
            </svg>
          </div>
          <div className="text-center">
            <h1 className="text-xl font-semibold tracking-tight">
              tux<span className="text-accent">.ai</span>
            </h1>
            <p className="mt-1.5 text-sm text-white/35">Sign in to continue</p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-2.5">
          {error && (
            <div className="rounded-xl border border-red-500/20 bg-red-500/8 px-4 py-3 text-sm text-red-300">
              {error}
            </div>
          )}

          <input
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={inputCls}
            placeholder="Email"
          />

          <input
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={inputCls}
            placeholder="Password"
          />

          <button
            type="submit"
            disabled={loading}
            className="mt-1 w-full rounded-xl bg-accent py-3 text-sm font-medium text-black/75 transition-all hover:bg-accent-hover disabled:opacity-40"
          >
            {loading ? "Signing in…" : "Continue"}
          </button>
        </form>

        <p className="mt-10 text-center text-xs text-white/18">
          PII is detected and encrypted before leaving your device.
        </p>
      </div>
    </div>
  );
}
