import { handoff } from "../features/handoff.ts";
import { makeServer } from "../server.ts";

export default makeServer("harness-habits-handoff", [{ key: "handoff", feature: handoff }]);
