/** Reject ambiguous object names before JSON.parse discards their first value. */
export function parseStrictJson(source: string): unknown {
  // JSON strings must exclude literal control characters.
  const token =
    // eslint-disable-next-line no-control-regex
    /\s*("(?:[^"\\\u0000-\u001f]|\\(?:["\\/bfnrt]|u[0-9a-fA-F]{4}))*"|[{}[\]:,]|-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?|true|false|null)/gy;
  const stack: { keys: Set<string> | null; expectingKey: boolean }[] = [];
  let offset = 0;
  while (offset < source.length) {
    token.lastIndex = offset;
    const match = token.exec(source);
    if (!match) {
      if (/^\s*$/u.test(source.slice(offset))) break;
      throw new SyntaxError("Invalid JSON token");
    }
    offset = token.lastIndex;
    const value = match[1];
    if (value === undefined) throw new SyntaxError("Invalid JSON token");
    const current = stack.at(-1);
    if (value === "{" || value === "[") {
      stack.push({
        keys: value === "{" ? new Set() : null,
        expectingKey: true,
      });
      if (stack.length > 64)
        throw new SyntaxError("JSON nesting limit exceeded");
    } else if (value === "}" || value === "]") {
      stack.pop();
    } else if (value === ":" && current) {
      current.expectingKey = false;
    } else if (value === "," && current) {
      current.expectingKey = true;
    } else if (value.startsWith('"') && current?.keys && current.expectingKey) {
      const key = JSON.parse(value) as string;
      if (current.keys.has(key)) throw new SyntaxError("Duplicate JSON key");
      current.keys.add(key);
    }
  }
  return JSON.parse(source) as unknown;
}
