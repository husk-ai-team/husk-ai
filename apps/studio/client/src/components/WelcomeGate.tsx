// First-run welcome screen. Husk is free for everyone — anyone can use it
// immediately, no account, no cloud. One click creates a local guest session
// (POST /api/auth/anonymous → writes ~/.husk/auth.json) and the Dashboard
// opens. That's the whole flow.

import { BrandMark } from "@/components/BrandMark";
import { auth } from "@/lib/auth";
import { ArrowRight, Loader2, Sparkles } from "lucide-react";
import { useState } from "react";

export function WelcomeGate() {
  const [tryingFree, setTryingFree] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const tryFree = async () => {
    setTryingFree(true);
    setError(null);
    try {
      await auth.anonymous();
      // Reload so every useSession() consumer (App, StudioLayout, pages)
      // picks up the new guest session at the same time.
      window.location.reload();
    } catch (e) {
      setError(`Couldn't reach Husk backend: ${e}`);
      setTryingFree(false);
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col">
      <div className="px-6 md:px-12 py-6">
        <BrandMark />
      </div>

      <div className="flex-1 flex items-center justify-center px-6 pb-16">
        <div className="w-full max-w-md text-center">
          <div className="inline-flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-accent mb-3">
            <Sparkles className="size-3.5" />
            Free for everyone
          </div>
          <h1 className="text-3xl md:text-4xl font-bold tracking-[-0.02em]">
            Welcome to <span className="text-accent">Husk</span>
          </h1>
          <p className="mt-3 text-sm text-muted-foreground leading-relaxed">
            See what your AI is thinking. Free, local, no telemetry, no
            account.
          </p>

          <div className="mt-8 space-y-3">
            <button
              type="button"
              onClick={tryFree}
              disabled={tryingFree}
              className="w-full h-12 inline-flex items-center justify-center gap-2 rounded-md bg-accent text-white hover:bg-accent/90 px-5 text-sm font-semibold transition-colors disabled:opacity-50"
            >
              {tryingFree ? (
                <>
                  <Loader2 className="size-4 animate-spin" />
                  Starting…
                </>
              ) : (
                <>
                  Try free
                  <ArrowRight className="size-4" />
                </>
              )}
            </button>

            {error && (
              <div className="rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive text-left">
                {error}
              </div>
            )}
          </div>

          <p className="mt-10 text-[11px] text-muted-foreground/80 leading-relaxed">
            Your agent data never leaves this computer.
          </p>
        </div>
      </div>
    </div>
  );
}
