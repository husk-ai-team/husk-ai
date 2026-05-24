import {
  ActivityIcon,
  BookOpenIcon,
  HomeIcon,
  ListIcon,
  PlayIcon,
  SettingsIcon,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useLocation } from "wouter";

import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from "@/components/ui/command";
import { getRuns, shortId, type Run } from "@/lib/api";

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [, setLocation] = useLocation();
  const [runs, setRuns] = useState<Run[]>([]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (open) {
      getRuns().then(setRuns).catch(() => {});
    }
  }, [open]);

  const go = (path: string) => {
    setOpen(false);
    setLocation(path);
  };

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput placeholder="Jump to a page or run…" />
      <CommandList>
        <CommandEmpty>No matches.</CommandEmpty>
        <CommandGroup heading="Pages">
          <CommandItem onSelect={() => go("/dashboard")}>
            <HomeIcon />
            <span>Dashboard</span>
            <CommandShortcut>D</CommandShortcut>
          </CommandItem>
          <CommandItem onSelect={() => go("/runs")}>
            <ListIcon />
            <span>Runs</span>
            <CommandShortcut>R</CommandShortcut>
          </CommandItem>
          <CommandItem onSelect={() => go("/")}>
            <BookOpenIcon />
            <span>Onboarding</span>
          </CommandItem>
          <CommandItem onSelect={() => go("/settings")}>
            <SettingsIcon />
            <span>Settings</span>
            <CommandShortcut>S</CommandShortcut>
          </CommandItem>
        </CommandGroup>
        {runs.length > 0 && (
          <>
            <CommandSeparator />
            <CommandGroup heading="Recent runs">
              {runs.slice(0, 8).map((r) => (
                <CommandItem
                  key={r.id}
                  onSelect={() => go(`/runs/${r.id}`)}
                  value={`${r.id} ${r.framework} ${r.script_path}`}
                >
                  <ActivityIcon />
                  <span className="truncate">
                    <span className="font-mono text-xs text-muted-foreground">
                      {shortId(r.id, 10)}
                    </span>{" "}
                    <span>{r.script_path || r.framework}</span>
                  </span>
                  <CommandShortcut>{r.status}</CommandShortcut>
                </CommandItem>
              ))}
              <CommandSeparator />
              <CommandItem onSelect={() => go("/runs/" + (runs[0]?.id ?? ""))}>
                <PlayIcon />
                <span>Open latest run</span>
              </CommandItem>
            </CommandGroup>
          </>
        )}
      </CommandList>
    </CommandDialog>
  );
}
