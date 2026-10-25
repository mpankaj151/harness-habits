import { outputGuard } from "./features/output-guard.ts";
import { makeServer } from "./server.ts";

export default makeServer("harness-habits", [{ key: "output-guard", feature: outputGuard }]);
