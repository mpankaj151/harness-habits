import { outputGuard } from "../features/output-guard.ts";
import { makeServer } from "../server.ts";

export default makeServer("harness-habits-output-guard", [{ key: "output-guard", feature: outputGuard }]);
