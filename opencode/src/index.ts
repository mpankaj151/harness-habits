import { handoff } from "./features/handoff.ts";
import { idleCompaction } from "./features/idle-compaction.ts";
import { outputGuard } from "./features/output-guard.ts";
import { makeServer } from "./server.ts";

// Order is the contract: handoff writes its note before idle-compaction runs on the same idle.
export default makeServer("harness-habits", [
  { key: "output-guard", feature: outputGuard },
  { key: "handoff", feature: handoff },
  { key: "idle-compaction", feature: idleCompaction },
]);
