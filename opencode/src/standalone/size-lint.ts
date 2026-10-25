import { sizeLint } from "../features/size-lint.ts";
import { makeServer } from "../server.ts";

export default makeServer("harness-habits-size-lint", [{ key: "size-lint", feature: sizeLint }]);
