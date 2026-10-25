import { idleCompaction } from "../features/idle-compaction.ts";
import { makeServer } from "../server.ts";

export default makeServer("harness-habits-idle-compaction", [{ key: "idle-compaction", feature: idleCompaction }]);
