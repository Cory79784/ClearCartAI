import React from "react";
import "./globals.css";
import TopNav from "../components/TopNav";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="shell">
          <TopNav />
          {children}
        </div>
      </body>
    </html>
  );
}
