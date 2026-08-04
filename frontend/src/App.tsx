import { useEffect, useState } from "react";

type HealthStatus =
  | { state: "loading" }
  | { state: "ok"; status: string }
  | { state: "error"; message: string };

function useBackendHealth(): HealthStatus {
  const [health, setHealth] = useState<HealthStatus>({ state: "loading" });

  useEffect(() => {
    let cancelled = false;

    fetch("/health")
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Backend responded with ${response.status}`);
        }
        return response.json() as Promise<{ status: string }>;
      })
      .then((data) => {
        if (!cancelled) setHealth({ state: "ok", status: data.status });
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          const message = error instanceof Error ? error.message : "Unknown error";
          setHealth({ state: "error", message });
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return health;
}

function App() {
  const health = useBackendHealth();

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50">
      <div className="rounded-lg border border-slate-200 bg-white p-8 shadow-sm">
        <h1 className="text-2xl font-semibold text-slate-900">VigilAI</h1>
        <p className="mt-1 text-sm text-slate-500">Backend health status</p>

        <div className="mt-4 flex items-center gap-2">
          <span
            className={`h-2.5 w-2.5 rounded-full ${
              health.state === "ok"
                ? "bg-emerald-500"
                : health.state === "error"
                  ? "bg-red-500"
                  : "bg-amber-400"
            }`}
          />
          <span className="text-sm font-medium text-slate-700">
            {health.state === "loading" && "Checking..."}
            {health.state === "ok" && `Backend: ${health.status}`}
            {health.state === "error" && `Backend unreachable: ${health.message}`}
          </span>
        </div>
      </div>
    </div>
  );
}

export default App;
