import { toolBudget } from "../features/tool-budget.ts";
import { makeServer } from "../server.ts";

export default makeServer("harness-habits-tool-budget", [{ key: "tool-budget", feature: toolBudget }]);
