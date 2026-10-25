import { costLogger } from "../features/cost-logger.ts";
import { makeServer } from "../server.ts";

export default makeServer("harness-habits-cost-logger", [{ key: "cost-logger", feature: costLogger }]);
