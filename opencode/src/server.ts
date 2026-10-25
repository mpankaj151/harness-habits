import { compose } from "./compose.ts";
import type { Feature } from "./compose.ts";
import { loadOptions } from "./options.ts";
import type { FeatureKey, Hooks, PluginInput } from "./types.ts";

export function makeServer(id: string, features: Array<{ key: FeatureKey; feature: Feature }>) {
  const server = async (input: PluginInput, options?: Record<string, unknown>): Promise<Hooks> =>
    compose(features, { client: input.client, directory: input.directory, options: loadOptions(options), input });
  return { id, server };
}
