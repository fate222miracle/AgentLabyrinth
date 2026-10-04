import type * as z from 'zod/mini';
import { episodeResponseSchema, experimentResponseSchema, jobSchema, errorSchema,
  parseApi, requireIdentity } from './apiContracts.ts';

/** Read a validated standard error or show a neutral HTTP failure. */
export async function requireOk(response: Response): Promise<void> {
  if (response.ok) return;
  const value: unknown = await response.json().catch(() => null);
  const error = errorSchema.safeParse(value);
  throw new Error(error.success ? error.data.message : `接口请求失败 (${response.status})`);
}

/** A JSON response is unknown until its consumer Schema accepts it. */
export async function readApi<T>(response: Response, schema: z.ZodMiniType<T>): Promise<T> {
  await requireOk(response);
  const value: unknown = await response.json().catch(() => { throw new Error('接口返回的 JSON 无效。'); });
  return parseApi(schema, value);
}

/** Read an Episode, binding historical/resume results to the requested ID. */
export async function readEpisode(response: Response, expectedId?: string) {
  const data = await readApi(response, episodeResponseSchema);
  if (expectedId) requireIdentity(data.artifact.episode.episode_id, expectedId);
  return data;
}

/** Read a complete Experiment with compatible historical optional metrics. */
export async function readExperiment(response: Response, expectedId?: string) {
  const data = await readApi(response, experimentResponseSchema);
  if (expectedId) requireIdentity(data.experiment.experiment_id, expectedId);
  return data;
}

/** Accept only supported Job states belonging to the current operation. */
export async function readJob(response: Response, expectedId?: string) {
  const data = await readApi(response, jobSchema);
  if (expectedId) requireIdentity(data.experiment_id, expectedId);
  return data;
}
