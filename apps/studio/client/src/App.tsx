import { Route, Switch } from "wouter";

import { StudioLayout } from "./components/StudioLayout";
import { Toaster } from "./components/ui/sonner";
import Dashboard from "./pages/Dashboard";
import Onboarding from "./pages/Onboarding";
import Replay from "./pages/Replay";
import RunDetail from "./pages/RunDetail";
import Runs from "./pages/Runs";
import Settings from "./pages/Settings";

export default function App() {
  // Local-first, single-user: no login gate, no project provider — the Studio is
  // the one debugger window onto the agent you're building on this machine.
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
