"use client";

import { useEffect, useState } from "react";
import { api } from "../../lib/api";

export default function AdminPage() {
  const [queue, setQueue] = useState<any>(null);
  const [jobs, setJobs] = useState<any[]>([]);
  const [system, setSystem] = useState<any>(null);
  const [users, setUsers] = useState<any[]>([]);
  const [newUsername, setNewUsername] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [createStatus, setCreateStatus] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const load = () => {
      api("/admin/queue").then(setQueue).catch((e) => setError(String(e)));
      api("/admin/jobs").then(setJobs).catch(() => setJobs([]));
      api("/admin/system").then(setSystem).catch(() => setSystem({}));
      api("/admin/users").then(setUsers).catch(() => setUsers([]));
    };
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, []);

  async function createUser() {
    setCreateStatus("");
    try {
      const created = await api("/admin/users", {
        method: "POST",
        body: JSON.stringify({
          username: newUsername,
          password: newPassword,
          role: "user",
        }),
      });
      setCreateStatus(`User created: ${created.username}`);
      setNewUsername("");
      setNewPassword("");
      const refreshed = await api("/admin/users");
      setUsers(refreshed);
    } catch (e) {
      setCreateStatus(`Create user failed: ${String(e)}`);
    }
  }

  return (
    <div>
      <section className="card">
        <h3 className="pageTitle">Admin Console</h3>
        <p className="muted">Manage users and monitor platform state.</p>
      </section>
      <div className="grid">
      <section className="card">
        <h3 className="pageTitle">Queue</h3>
        {error ? <p className="status-failed">{error}</p> : null}
        <pre>{JSON.stringify(queue, null, 2)}</pre>
      </section>
      <section className="card">
        <h3 className="pageTitle">System</h3>
        <pre>{JSON.stringify(system, null, 2)}</pre>
      </section>
      <section className="card" style={{ gridColumn: "1 / -1" }}>
        <h3 className="pageTitle">User Management</h3>
        <p className="muted">Create users who can login with their credentials.</p>
        <div className="grid">
          <input
            className="input"
            placeholder="username"
            value={newUsername}
            onChange={(e) => setNewUsername(e.target.value)}
          />
          <input
            className="input"
            type="password"
            placeholder="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
          />
        </div>
        <div style={{ height: 10 }} />
        <button className="button" onClick={createUser} disabled={!newUsername || !newPassword}>
          Add User
        </button>
        {createStatus ? <p className="muted">{createStatus}</p> : null}
        <pre>{JSON.stringify(users, null, 2)}</pre>
      </section>
      <section className="card" style={{ gridColumn: "1 / -1" }}>
        <h3 className="pageTitle">All Jobs</h3>
        <p className="muted">Includes jobs from all users.</p>
        <pre>{JSON.stringify(jobs, null, 2)}</pre>
      </section>
      </div>
    </div>
  );
}
