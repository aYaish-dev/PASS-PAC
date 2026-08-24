"use client";

import {
  Activity,
  FlaskConical,
  LayoutDashboard,
  Menu,
  RadioTower,
  ScanLine,
  ShieldCheck,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import type { ReactNode } from "react";

const navigation = [
  { href: "/", label: "Overview", icon: LayoutDashboard, exact: true },
  { href: "/sessions", label: "Sessions", icon: ScanLine },
];

function Navigation({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();

  return (
    <nav aria-label="Primary navigation" className="space-y-1">
      {navigation.map((item) => {
        const active = item.exact
          ? pathname === item.href
          : pathname.startsWith(item.href) ||
            (item.href === "/sessions" && pathname.startsWith("/cards/"));
        const Icon = item.icon;

        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={`nav-link ${active ? "nav-link-active" : ""}`}
          >
            <Icon aria-hidden="true" size={18} strokeWidth={1.8} />
            <span>{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}

function Brand() {
  return (
    <Link href="/" className="brand-lockup" aria-label="PASS-PAC overview">
      <span className="brand-mark" aria-hidden="true">
        <ShieldCheck size={21} strokeWidth={1.8} />
      </span>
      <span>
        <strong>PASS-PAC</strong>
        <small>Access research console</small>
      </span>
    </Link>
  );
}

function SignalScope() {
  return (
    <section className="signal-scope" aria-label="Credential frequency scope">
      <div className="signal-scope-title">
        <RadioTower size={15} aria-hidden="true" />
        <span>Credential scope</span>
      </div>
      <div className="signal-band signal-band-lf">
        <span>LF</span>
        <strong>125 kHz</strong>
      </div>
      <div className="signal-band signal-band-hf">
        <span>HF</span>
        <strong>13.56 MHz</strong>
      </div>
    </section>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>

      <header className="mobile-header">
        <Brand />
        <button
          type="button"
          className="icon-button"
          onClick={() => setMobileOpen((open) => !open)}
          aria-expanded={mobileOpen}
          aria-controls="mobile-navigation"
          aria-label={mobileOpen ? "Close navigation" : "Open navigation"}
          title={mobileOpen ? "Close navigation" : "Open navigation"}
        >
          {mobileOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
      </header>

      {mobileOpen ? (
        <div className="mobile-navigation" id="mobile-navigation">
          <Navigation onNavigate={() => setMobileOpen(false)} />
          <SignalScope />
        </div>
      ) : null}

      <aside className="desktop-sidebar">
        <div>
          <Brand />
          <div className="workspace-label">Workspace</div>
          <Navigation />
        </div>

        <div className="sidebar-footer">
          <SignalScope />
          <div className="local-state">
            <Activity size={15} aria-hidden="true" />
            <span>
              <strong>Local environment</strong>
              <small>Data remains on this machine</small>
            </span>
          </div>
          <div className="research-mark">
            <FlaskConical size={14} aria-hidden="true" />
            Methodology workspace
          </div>
        </div>
      </aside>

      <main id="main-content" className="app-content" tabIndex={-1}>
        {children}
      </main>
    </div>
  );
}
