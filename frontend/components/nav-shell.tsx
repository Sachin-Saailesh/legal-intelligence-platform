"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", icon: "dashboard", label: "Dashboard" },
  { href: "/matters", icon: "folder_shared", label: "Matters" },
  { href: "/timeline", icon: "timeline", label: "Timeline" },
  { href: "/discovery", icon: "folder_open", label: "Discovery" },
  { href: "/review", icon: "task", label: "Review Queue" },
  { href: "/alerts", icon: "security", label: "Compliance Alerts" },
];

export function NavShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();

  const isActive = (href: string) =>
    href === "/" ? path === "/" : path.startsWith(href);

  return (
    <div className="flex min-h-screen bg-[#0F2340]">
      {/* Sidebar */}
      <aside className="flex flex-col h-screen fixed left-0 top-0 w-64 bg-[#0A192F] border-r border-white/5 z-50">
        {/* Logo */}
        <div className="px-6 py-7 flex items-center gap-3">
          <div className="w-8 h-8 bg-sky-500 flex items-center justify-center rounded">
            <span className="material-symbols-outlined text-[#0F2340] text-xl" style={{ fontVariationSettings: "'FILL' 1" }}>
              balance
            </span>
          </div>
          <div>
            <h1 className="text-base font-bold text-white tracking-tight leading-none">LexMind</h1>
            <p className="text-[10px] text-sky-400 tracking-widest uppercase mt-0.5">Intelligence</p>
          </div>
        </div>

        {/* Nav Items */}
        <nav className="flex-1 px-4 space-y-0.5">
          {NAV.map((item) => {
            const active = isActive(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-4 py-3 rounded-md text-sm font-medium tracking-wide uppercase transition-colors ${
                  active
                    ? "bg-[#1E3A5F] text-white border-l-4 border-sky-400"
                    : "text-slate-400 hover:text-white hover:bg-[#1E3A5F]/50 border-l-4 border-transparent"
                }`}
              >
                <span className={`material-symbols-outlined text-xl ${active ? "text-sky-400" : ""}`}>
                  {item.icon}
                </span>
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Bottom */}
        <div className="p-4 border-t border-white/5">
          <div className="flex items-center gap-3 px-4 py-2 text-slate-500 text-xs font-mono uppercase tracking-wider">
            <span className="w-2 h-2 rounded-full bg-sky-400 shadow-[0_0_6px_rgba(56,189,248,0.6)]"></span>
            System Active
          </div>
        </div>
      </aside>

      {/* Main area */}
      <div className="ml-64 flex-1 flex flex-col min-h-screen">
        {/* Topbar */}
        <header className="fixed top-0 right-0 h-16 w-[calc(100%-16rem)] z-40 bg-[#0F2340]/90 backdrop-blur-md border-b border-white/5 flex items-center justify-between px-8">
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined text-slate-500">search</span>
            <input
              className="bg-transparent border-none focus:outline-none text-sm text-slate-300 placeholder-slate-600 w-64"
              placeholder="Search matters, documents..."
            />
          </div>
          <div className="flex items-center gap-4">
            <Link href="/alerts" className="relative text-slate-400 hover:text-white transition-colors">
              <span className="material-symbols-outlined">notifications</span>
            </Link>
            <div className="h-6 w-px bg-slate-700" />
            <div className="flex items-center gap-2 text-slate-300">
              <span className="text-sm font-semibold">LexMind Intelligence</span>
              <span className="material-symbols-outlined text-slate-500">account_circle</span>
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="mt-16 flex-1">
          {children}
        </main>
      </div>
    </div>
  );
}
