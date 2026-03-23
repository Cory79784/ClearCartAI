"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { API_BASE } from "../lib/api";

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const router = useRouter();

  async function onLogin(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      setError("Invalid credentials");
      return;
    }
    router.push("/dashboard");
  }

  return (
    <div className="card" style={{ maxWidth: 460, margin: "64px auto" }}>
      <h3 className="pageTitle">Login</h3>
      <p className="muted">Sign in to access the labeling workspace and admin tools.</p>
      <form onSubmit={onLogin}>
        <input
          className="input"
          placeholder="Username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />
        <div style={{ height: 10 }} />
        <input
          className="input"
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <div style={{ height: 12 }} />
        <button className="button" type="submit" style={{ width: "100%" }}>Login</button>
      </form>
      {error ? <p className="status-failed">{error}</p> : null}
    </div>
  );
}
