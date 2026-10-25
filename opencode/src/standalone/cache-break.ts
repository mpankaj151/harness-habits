import { cacheBreak } from "../features/cache-break.ts";
import { makeServer } from "../server.ts";

export default makeServer("harness-habits-cache-break", [{ key: "cache-break", feature: cacheBreak }]);
