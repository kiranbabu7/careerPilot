"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Bot,
  Briefcase,
  Building2,
  FileText,
  Home,
  LayoutDashboard,
  LogOut,
  MessageSquare,
  Scale,
  Send,
  Settings,
  Sparkles,
} from "lucide-react";

import { useAuth } from "@/contexts/auth-context";
import { cn } from "@/lib/utils";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";

const navItems = [
  { href: "/", label: "Home", icon: Home },
  { href: "/workspace", label: "Workspace", icon: LayoutDashboard },
  { href: "/opportunities", label: "Opportunities", icon: Briefcase },
  { href: "/companies", label: "Companies", icon: Building2 },
  { href: "/resume", label: "Resume", icon: FileText },
  { href: "/interviews", label: "Interviews", icon: MessageSquare },
  { href: "/decisions", label: "Decisions", icon: Scale },
  { href: "/applications", label: "Applications", icon: Send },
  { href: "/agent-runs", label: "Agent Runs", icon: Bot },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function AppSidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  const initials =
    user?.full_name
      ?.split(" ")
      .map((part) => part[0])
      .join("")
      .slice(0, 2)
      .toUpperCase() || "CP";

  return (
    <aside className="flex h-full w-64 shrink-0 flex-col border-r border-border bg-sidebar text-sidebar-foreground">
      <div className="shrink-0 flex items-center gap-2 px-6 py-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <Sparkles className="h-5 w-5" />
        </div>
        <div>
          <p className="text-sm font-semibold tracking-tight">CareerPilot</p>
          <p className="text-xs text-muted-foreground">AI career workspace</p>
        </div>
      </div>

      <Separator />

      <ScrollArea className="min-h-0 flex-1 px-3 py-4">
        <nav className="space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);

            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                  active
                    ? "bg-accent text-accent-foreground"
                    : "text-muted-foreground hover:bg-accent/50 hover:text-foreground",
                )}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>
      </ScrollArea>

      <div className="mt-auto shrink-0 border-t border-border p-4">
        <div className="mb-3 flex items-center gap-3">
          <Avatar className="h-9 w-9">
            {user?.avatar_url ? (
              <AvatarImage src={user.avatar_url} alt={user.full_name} />
            ) : null}
            <AvatarFallback>{initials}</AvatarFallback>
          </Avatar>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium">
              {user?.full_name || "Guest"}
            </p>
            <p className="truncate text-xs text-muted-foreground">
              {user?.email || "Not signed in"}
            </p>
          </div>
        </div>
        {user ? (
          <Button variant="outline" size="sm" className="w-full" onClick={logout}>
            <LogOut className="h-4 w-4" />
            Sign out
          </Button>
        ) : (
          <Button asChild variant="outline" size="sm" className="w-full">
            <Link href="/login">Sign in</Link>
          </Button>
        )}
      </div>
    </aside>
  );
}
