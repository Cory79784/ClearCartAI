"use client";

import Link from "next/link";
import { API_BASE } from "../lib/api";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

export default function TopNav() {
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  async function logout() {
    await fetch(`${API_BASE}/auth/logout`, {
      method: "POST",
      credentials: "include",
    });
    router.push("/");
  }

  const links = [
    { href: "/dashboard", label: "Dashboard" },
    { href: "/labeling", label: "Labeling UI" },
    { href: "/admin", label: "Admin" },
  ];

  return (
    <header className="topbar glossy">
      <h1 className="title">ClearCart Segmentation Portal</h1>
      <button className="navToggle" onClick={() => setOpen((v) => !v)} aria-label="Toggle navigation">
        ☰
      </button>
      <nav className={`nav ${open ? "open" : ""}`}>
        {links.map((link) => {
          const active = pathname?.startsWith(link.href);
          return (
            <Link
              key={link.href}
              href={link.href}
              className={`navLink ${active ? "active" : ""}`}
              onClick={() => setOpen(false)}
            >
              {link.label}
            </Link>
          );
        })}
        <button className="button" onClick={logout} style={{ paddingInline: 18 }}>Logout</button>
      </nav>
    </header>
  );
}
