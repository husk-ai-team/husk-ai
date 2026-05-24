// Studio header + footer chrome. Visually identical to the marketing
// SiteLayout: sticky nav with backdrop-blur, brand mark left, links center,
// account chip right.

import { BrandMark } from "@/components/BrandMark";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useSession } from "@/lib/auth";
import {
  ChevronDown,
  ExternalLink,
  LogOut,
  RotateCcw,
  Settings,
} from "lucide-react";
import { type ReactNode } from "react";
import { toast } from "sonner";
import { Link, useLocation } from "wouter";

interface StudioLayoutProps {
  children: ReactNode;
}

const NAV = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/runs", label: "Runs" },
  { href: "/onboarding", label: "Onboarding" },
  { href: "/settings", label: "Settings" },
];

export function StudioLayout({ children }: StudioLayoutProps) {
  const [location] = useLocation();
  const { session, clear } = useSession();

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col">
      <nav className="border-b border-border/30 px-4 py-4 sm:px-6 sm:py-5 md:px-12 md:py-6 flex items-center justify-between sticky top-0 bg-background/80 backdrop-blur-sm z-40 gap-3">
        <Link href="/dashboard" className="hover:opacity-80 transition-opacity">
          <BrandMark />
        </Link>

        <div className="hidden md:flex gap-8 text-sm">
          {NAV.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={
                location === l.href ||
                (l.href !== "/dashboard" && location.startsWith(l.href))
                  ? "text-foreground transition-colors"
                  : "text-muted-foreground hover:text-foreground transition-colors"
              }
            >
              {l.label}
            </Link>
          ))}
        </div>

        <div className="flex items-center gap-3">
          {session && (
            <AccountMenu
              email={session.email}
              isGuest={!!session.is_guest}
              onLogout={clear}
            />
          )}
        </div>
      </nav>

      <main className="flex-1">{children}</main>

      <footer className="border-t border-border/30 px-6 md:px-12 py-8">
        <div className="max-w-6xl mx-auto flex flex-wrap items-center justify-between gap-3 text-xs text-muted-foreground">
          <div className="flex items-center gap-4">
            <BrandMark className="opacity-70" />
            <span>Local-first. Your data never leaves this machine.</span>
          </div>
          <a
            href="https://husk.dev"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 hover:text-foreground transition-colors"
          >
            husk.dev <ExternalLink className="size-3" />
          </a>
        </div>
      </footer>
    </div>
  );
}

function AccountMenu({
  email,
  isGuest,
  onLogout,
}: {
  email: string;
  isGuest: boolean;
  onLogout: () => Promise<void>;
}) {
  const initial = isGuest ? "G" : email.slice(0, 1).toUpperCase();
  const label = isGuest ? "Guest" : email;
  const logout = async () => {
    await onLogout();
    toast.success(isGuest ? "Guest session cleared." : "Signed out.");
  };
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="inline-flex items-center gap-2 rounded-md border border-border/50 hover:border-accent/50 transition-colors px-2 py-1.5 text-sm"
        >
          <span className="flex size-6 items-center justify-center rounded-full bg-accent text-white text-[11px] font-bold uppercase">
            {initial}
          </span>
          <span className="hidden lg:inline text-foreground/80 max-w-[160px] truncate">
            {label}
          </span>
          <ChevronDown className="size-3 text-muted-foreground" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="end"
        className="w-60 bg-popover border-border/60"
      >
        <DropdownMenuLabel className="text-xs text-muted-foreground">
          {isGuest ? "Guest mode" : "Signed in"}
          <div className="text-foreground font-medium mt-0.5 truncate">
            {label}
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link href="/settings" className="cursor-pointer">
            <Settings className="size-3.5 mr-2" />
            Settings
          </Link>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onClick={logout}
          className="cursor-pointer text-destructive focus:text-destructive"
        >
          {isGuest ? (
            <>
              <RotateCcw className="size-3.5 mr-2" />
              Reset session
            </>
          ) : (
            <>
              <LogOut className="size-3.5 mr-2" />
              Sign out
            </>
          )}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
