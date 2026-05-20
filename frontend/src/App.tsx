import { useEffect, useState } from "react";
import { BrowserRouter, Route, Routes, Navigate } from "react-router-dom";
import { auth, type User } from "@/lib/api";
import { Login } from "@/pages/Login";
import { Chat } from "@/pages/Chat";
import { Admin } from "@/pages/Admin";

function useAuth() {
  const [user, setUser] = useState<User | null | "loading">("loading");

  useEffect(() => {
    auth.me().then(setUser).catch(() => setUser(null));
  }, []);

  return { user, setUser };
}

export default function App() {
  const { user, setUser } = useAuth();

  const handleLogin = () => {
    auth.me().then(setUser).catch(() => setUser(null));
  };

  const handleLogout = async () => {
    await auth.logout().catch(() => {});
    setUser(null);
  };

  if (user === "loading") {
    return (
      <div className="flex h-screen items-center justify-center bg-surface">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-accent border-t-transparent" />
      </div>
    );
  }

  if (!user) {
    return <Login onLogin={handleLogin} />;
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Chat user={user} onLogout={handleLogout} />} />
        <Route
          path="/admin"
          element={
            user.role === "admin" ? <Admin /> : <Navigate to="/" replace />
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
