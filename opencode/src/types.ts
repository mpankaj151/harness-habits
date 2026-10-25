// Minimal local shapes for the parts of @opencode-ai/plugin that harness-habits uses.
export type FeatureKey =
  | "output-guard"
  | "size-lint"
  | "cache-break"
  | "handoff"
  | "idle-compaction"
  | "cost-logger"
  | "tool-budget"
  | "precompact-snapshot";

export interface OpenCodeEvent {
  type: string;
  properties?: Record<string, any>;
}

export interface Hooks {
  config?: (cfg: any) => Promise<void>;
  event?: (input: { event: OpenCodeEvent }) => Promise<void>;
  "tool.execute.before"?: (
    input: { tool: string; sessionID: string; callID: string },
    output: { args: any },
  ) => Promise<void>;
  "tool.execute.after"?: (
    input: { tool: string; sessionID: string; callID: string; args: any },
    output: { title: string; output: string; metadata: any },
  ) => Promise<void>;
  "experimental.chat.system.transform"?: (
    input: { sessionID?: string; model: any },
    output: { system: string[] },
  ) => Promise<void>;
  "experimental.session.compacting"?: (
    input: { sessionID: string },
    output: { context: string[]; prompt?: string },
  ) => Promise<void>;
  dispose?: () => Promise<void>;
}

export interface PluginInput {
  client: any;
  directory: string;
  worktree?: string;
  project?: any;
  serverUrl?: unknown;
  [key: string]: unknown;
}
