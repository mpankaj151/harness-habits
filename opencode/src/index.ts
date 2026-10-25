import { cacheBreak } from "./features/cache-break.ts";
import { costLogger } from "./features/cost-logger.ts";
import { handoff } from "./features/handoff.ts";
import { idleCompaction } from "./features/idle-compaction.ts";
import { outputGuard } from "./features/output-guard.ts";
import { sizeLint } from "./features/size-lint.ts";
import { toolBudget } from "./features/tool-budget.ts";
import { makeServer } from "./server.ts";

// Order is the contract: handoff writes its note before idle-compaction runs on the same idle.
export default makeServer("harness-habits", [
  { key: "output-guard", feature: outputGuard },
  { key: "handoff", feature: handoff },
  { key: "idle-compaction", feature: idleCompaction },
  { key: "cost-logger", feature: costLogger },
  { key: "cache-break", feature: cacheBreak },
  { key: "size-lint", feature: sizeLint },
  { key: "tool-budget", feature: toolBudget },
]);
