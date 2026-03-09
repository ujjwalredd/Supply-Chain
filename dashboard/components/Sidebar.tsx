"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useWebSocket } from "@/hooks/useWebSocket";

const NAV_ITEMS = [
  {
    href: "/",
    label: "Overview",
    icon: (
      <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
        <path d="M7.5 1L13.5 6V14H9.5V10H5.5V14H1.5V6L7.5 1Z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/>
      </svg>
    ),
  },
  {
    href: "/alerts",
    label: "Deviations",
    icon: (
      <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
        <path d="M7.5 2L13 12H2L7.5 2Z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/>
        <path d="M7.5 6V8.5M7.5 10.5V11" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
      </svg>
    ),
  },
  {
    href: "/suppliers",
    label: "Suppliers",
    icon: (
      <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
        <circle cx="7.5" cy="5.5" r="2.5" stroke="currentColor" strokeWidth="1.2"/>
        <path d="M2 13C2 10.5 4.5 8.5 7.5 8.5S13 10.5 13 13" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
      </svg>
    ),
  },
  {
    href: "/orders",
    label: "Orders",
    icon: (
      <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
        <rect x="2" y="2" width="11" height="11" rx="1.5" stroke="currentColor" strokeWidth="1.2"/>
        <path d="M2 6h11M6 6v7" stroke="currentColor" strokeWidth="0.9"/>
      </svg>
    ),
  },
  {
    href: "/analytics",
    label: "Analytics",
    icon: (
      <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
        <rect x="2" y="9" width="2.5" height="4" rx="0.5" fill="currentColor" opacity="0.5"/>
        <rect x="6.25" y="6" width="2.5" height="7" rx="0.5" fill="currentColor" opacity="0.7"/>
        <rect x="10.5" y="2" width="2.5" height="11" rx="0.5" fill="currentColor"/>
      </svg>
    ),
  },
  {
    href: "/actions",
    label: "Actions",
    icon: (
      <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
        <circle cx="7.5" cy="7.5" r="5.5" stroke="currentColor" strokeWidth="1.2"/>
        <path d="M7.5 4.5V7.5L9.5 9" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
      </svg>
    ),
  },
  {
    href: "/network",
    label: "Network",
    icon: (
      <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
        <circle cx="3.5" cy="7.5" r="1.5" stroke="currentColor" strokeWidth="1.2"/>
        <circle cx="11.5" cy="3.5" r="1.5" stroke="currentColor" strokeWidth="1.2"/>
        <circle cx="11.5" cy="11.5" r="1.5" stroke="currentColor" strokeWidth="1.2"/>
        <path d="M5 7L10 4M5 8L10 11" stroke="currentColor" strokeWidth="1" strokeLinecap="round"/>
      </svg>
    ),
  },
  {
    href: "/scorecard",
    label: "Scorecard",
    icon: (
      <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
        <path d="M2 11L5.5 7L8.5 9.5L12 5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
        <circle cx="5.5" cy="7" r="1" fill="currentColor" opacity="0.6"/>
        <circle cx="8.5" cy="9.5" r="1" fill="currentColor" opacity="0.6"/>
        <circle cx="12" cy="5" r="1" fill="currentColor" opacity="0.6"/>
      </svg>
    ),
  },
  {
    href: "/whatif",
    label: "What-If",
    icon: (
      <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
        <path d="M7.5 2C7.5 2 5 4 5 7C5 8.5 6 9.5 7.5 9.5C9 9.5 10 8.5 10 7C10 4 7.5 2Z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/>
        <path d="M7.5 9.5V12.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
        <path d="M6 12.5H9" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
      </svg>
    ),
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const { connected } = useWebSocket();

  return (
    <aside
      className="fixed top-0 left-0 h-full flex flex-col z-30"
      style={{
        width: "220px",
        background: "#ffffff",
        borderRight: "1px solid #e2e8f0",
      }}
    >
      {/* Brand */}
      <div className="px-5 py-5 flex items-center gap-3" style={{ borderBottom: "1px solid #e2e8f0" }}>
        <div
          className="h-8 w-8 rounded-lg flex items-center justify-center shrink-0"
          style={{ background: "rgba(0,112,243,0.08)", border: "1px solid rgba(0,112,243,0.20)" }}
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M7 0.8L13 4V10L7 13.2L1 10V4L7 0.8Z" stroke="#0070F3" strokeWidth="1.2" strokeLinejoin="round"/>
            <circle cx="7" cy="7" r="2" fill="#0070F3"/>
          </svg>
        </div>
        <div>
          <p className="text-[13px] font-semibold text-foreground leading-none">Supply Chain</p>
          <p className="text-[11px] text-mutedForeground mt-0.5">AI Control Tower</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          const isActive = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className="sidebar-link"
              style={
                isActive
                  ? { background: "rgba(0,112,243,0.08)", color: "#0070F3" }
                  : {}
              }
            >
              <span style={{ color: isActive ? "#0070F3" : "#94a3b8" }}>{item.icon}</span>
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Bottom: status + links */}
      <div className="px-3 pb-4 space-y-3" style={{ borderTop: "1px solid #e2e8f0", paddingTop: "12px" }}>
        {/* WebSocket status */}
        <div className="px-3 py-2 rounded-lg flex items-center gap-2.5"
          style={{
            background: connected ? "rgba(16,185,129,0.06)" : "rgba(0,0,0,0.03)",
            border: connected ? "1px solid rgba(16,185,129,0.15)" : "1px solid #e2e8f0",
          }}
        >
          {connected ? (
            <span className="relative flex h-1.5 w-1.5 shrink-0">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-success opacity-60" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-success" />
            </span>
          ) : (
            <span className="h-1.5 w-1.5 rounded-full bg-mutedForeground opacity-40 shrink-0" />
          )}
          <span className="text-[11px] font-medium" style={{ color: connected ? "#10b981" : "#94a3b8" }}>
            {connected ? "Live feed" : "Offline"}
          </span>
        </div>

        {/* API Docs link */}
        <a
          href="http://localhost:8000/docs"
          target="_blank"
          rel="noopener noreferrer"
          className="sidebar-link text-[11px]"
          style={{ color: "#94a3b8" }}
        >
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
            <rect x="1" y="1" width="11" height="11" rx="1.5" stroke="currentColor" strokeWidth="1"/>
            <path d="M4 6.5h5M4 4.5h5M4 8.5h3" stroke="currentColor" strokeWidth="0.8" strokeLinecap="round"/>
          </svg>
          API Docs
        </a>
      </div>
    </aside>
  );
}
