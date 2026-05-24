import { Loader2 } from "lucide-react";
import { Route, Switch } from "wouter";

import { StudioLayout } from "./components/StudioLayout";
import { WelcomeGate } from "./components/WelcomeGate";
import { Toaster } from "./components/ui/sonner";
import { useSession } from "./lib/auth";
import Dashboard from "./pages/Dashboard";
import Onboarding from "./pages/Onboarding";
import Replay from "./pages/Replay";
import RunDetail from "./pages/RunDetail";
import Runs from "./pages/Runs";
import Settings from "./pages/Settings";

export default function App() {
  const { session, loading } = useSession();

  if (loading) {
    return (
      <div className="min-h-screen bg-background text-foreground grid place-items-center">
        <div className="inline-flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" />
          Checking session…
        </div>
        <Toaster richColors position="bottom-right" />
      </div>
    );
  }

  if (!session) {
    return (
      <>
        <WelcomeGate />
        <Toaster richColors position="bottom-right" />
      </>
    );
  }

  return (
    <StudioLayout>
      <Switch>
        <Route path="/" component={Dashboard} />
        <Route path="/dashboard" component={Dashboard} />
        <Route path="/onboarding" component={Onboarding} />
        <Route path="/runs" component={Runs} />
        <Route path="/runs/:id" component={RunDetail} />
        <Route path="/runs/:id/replay" component={Replay} />
        <Route path="/settings" component={Settings} />
        <Route>
          <div className="px-6 md:px-12 py-24 text-center text-muted-foreground">
            404 — page not found
          </div>
        </Route>
      </Switch>
      <Toaster richColors position="bottom-right" />
    </StudioLayout>
  );
}
