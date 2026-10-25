export function log(client: any, level: "debug" | "info" | "warn" | "error", message: string, extra?: Record<string, unknown>): void {
  try {
    const r = client?.app?.log?.({ body: { service: "harness-habits", level, message, extra } });
    if (r && typeof r.catch === "function") r.catch(() => {});
  } catch {
    // logging must never break the harness
  }
}

export function toast(client: any, message: string, variant: "info" | "success" | "warning" | "error" = "info"): void {
  try {
    const r = client?.tui?.showToast?.({ body: { message, variant } });
    if (r && typeof r.catch === "function") r.catch(() => {});
  } catch {
    // ignore
  }
}
