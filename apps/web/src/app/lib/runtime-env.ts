/**
 * Read server configuration at request time.
 *
 * Dynamic lookup keeps standalone Next.js builds from freezing private
 * deployment values into the image during `next build`.
 */
export function runtimeEnv(name: string): string | undefined {
  const value = process.env[name]?.trim();
  return value || undefined;
}
