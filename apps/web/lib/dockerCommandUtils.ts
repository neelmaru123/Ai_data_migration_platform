// Shared utilities for filling in connection-detail placeholders in
// generated Docker commands. Used by both DockerCommandOutput.tsx (the
// agent-creation flow) and the dashboard's Docker command modal (the
// view/regenerate flow), so they never drift out of sync with each other
// or with the backend's placeholder format.

export interface ConnectionDetails {
  host: string;
  port: string;
  username: string;
  database: string;
  ssl: boolean;
}

// Mirrors the backend's AgentCommandGenerator._sanitize_identifier exactly
// (apps/api/app/modules/agents/agents_command_generator.py). If this ever
// drifts from the backend's version, placeholder substitution will silently
// fail to match and the raw <..._HOST> style text will still be shown.
export function sanitizeIdentifier(identifier: string): string {
  const cleaned = identifier
    .trim()
    .replace(/[^A-Za-z0-9_]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .toUpperCase();
  return cleaned || 'DB';
}

// Mirrors the backend's used_prefixes collision-avoidance loop exactly, so
// that if two identifiers sanitize to the same base string, the second one
// gets the same "_2", "_3", ... suffix the backend would have generated.
export function resolvePrefix(baseClean: string, rolePrefix: 'SRC' | 'DEST', usedPrefixes: Set<string>): string {
  const base = `${rolePrefix}_${baseClean}`;
  let prefix = base;
  let counter = 2;
  while (usedPrefixes.has(prefix)) {
    prefix = `${base}_${counter}`;
    counter += 1;
  }
  usedPrefixes.add(prefix);
  return prefix;
}

// Substitutes <PREFIX_HOST>, <PREFIX_PORT>, <PREFIX_USER>, <PREFIX_NAME>
// placeholders in the raw command text with real values from
// connectionDetailsByIdentifier. Password placeholders are deliberately
// left untouched -- the user fills those in manually.
export function substituteConnectionPlaceholders(
  rawText: string,
  sources: { identifier: string }[],
  destination: { identifier: string } | null | undefined,
  connectionDetailsByIdentifier: Record<string, ConnectionDetails>
): string {
  if (!rawText) return rawText;
  let result = rawText;
  const usedPrefixes = new Set<string>();

  const applyForIdentifier = (identifier: string, rolePrefix: 'SRC' | 'DEST') => {
    const details = connectionDetailsByIdentifier[identifier];
    const cleanId = sanitizeIdentifier(identifier);
    const prefix = resolvePrefix(cleanId, rolePrefix, usedPrefixes);
    if (!details) return;
    if (details.host) {
      result = result.split(`<${prefix}_HOST>`).join(details.host);
    }
    if (details.port) {
      result = result.split(`<${prefix}_PORT>`).join(details.port);
    }
    if (details.username) {
      result = result.split(`<${prefix}_USER>`).join(details.username);
    }
    if (details.database) {
      result = result.split(`<${prefix}_NAME>`).join(details.database);
    }
  };

  sources.forEach((s) => applyForIdentifier(s.identifier, 'SRC'));
  if (destination) applyForIdentifier(destination.identifier, 'DEST');

  return result;
}
