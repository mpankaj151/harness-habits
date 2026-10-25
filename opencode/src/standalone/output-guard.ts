import { compose } from "../compose.ts";
import { outputGuard } from "../features/output-guard.ts";
import { loadOptions } from "../options.ts";
import type { Hooks, PluginInput } from "../types.ts";

const server = async (input: PluginInput, options?: Record<string, unknown>): Promise<Hooks> => {
  const opts = loadOptions(options);
  return compose([{ key: "output-guard", feature: outputGuard }], {
    client: input.client,
    directory: input.directory,
    options: opts,
    input,
  });
};

export default { id: "harness-habits-output-guard", server };
