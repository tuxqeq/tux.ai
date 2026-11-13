import { useState } from "react";
import { auth } from "@/lib/api";
import { RedactionDemo } from "@/components/RedactionDemo";
import { Wordmark } from "@/components/Wordmark";

interface Props {
  onLogin: () => void;
}

export function Login({ onLogin }: Readonly<Props>) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [shake, setShake] = useState(0);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await auth.login(email, password);
      onLogin();
    } catch (err) {
      setError((err as Error).message || "Sign-in failed.");
      setShake((n) => n + 1);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid min-h-dvh grid-cols-1 bg-paper lg:grid-cols-[minmax(0,1fr)_440px]">
      {/* Both columns share the same top rhythm, so the record and the form start on one line. */}
      <section className="px-6 pb-12 pt-6 sm:px-10 lg:px-16">
        <Wordmark size="lg" />
        <div className="mt-12 lg:mt-[22vh]">
          <RedactionDemo />
        </div>
      </section>

      <section className="border-t border-rule bg-sheet px-6 pb-16 pt-10 sm:px-10 lg:border-l lg:border-t-0 lg:pt-6">
        <div className="hidden h-[30px] lg:block" aria-hidden />
        <form onSubmit={handleSubmit} className="w-full max-w-[340px] lg:mt-[22vh]">
          <h1 className="text-xl font-semibold tracking-[-0.01em]">Sign in</h1>
          <p className="mt-1 text-sm text-ink-2">Use the account your admin created for you.</p>

          <div className="mt-8 space-y-4">
            <div>
              <label htmlFor="email" className="field-label">
                Email
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="field py-2.5"
              />
            </div>
            <div>
              <label htmlFor="password" className="field-label">
                Password
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="field py-2.5"
              />
            </div>
          </div>

          {error && (
            <p
              key={shake}
              role="alert"
              className="shake mt-4 border-l-2 border-alert py-1 pl-3 text-sm text-alert"
            >
              {error}
            </p>
          )}

          <button type="submit" disabled={loading} className="btn-ink mt-6 w-full py-2.5">
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </section>
    </div>
  );
}
