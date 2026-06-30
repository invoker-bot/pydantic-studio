// Dotted-path convention shared by all container components.
// Examples:
//   childPath("", "name")      -> "name"
//   childPath("database", "host") -> "database.host"
//   childPath("tags", 0)       -> "tags.0"
//   childPath("env", 2)        -> "env.2"
//
// The backend's tree._descend (src/pydantic_studio/tree/paths.py) parses
// the same dotted format - numeric segments index into SequenceNode.items
// and MappingNode.entries; string segments select GroupNode fields.

export function childPath(parent: string, segment: string | number): string {
  return parent ? `${parent}.${segment}` : String(segment);
}

export function normalizePath(path: string): string {
  return path.replace(/\[(\d+)\]/g, ".$1").replace(/^\./, "");
}

export function pathsEqual(left: string, right: string): boolean {
  return normalizePath(left) === normalizePath(right);
}

export function pathsOverlap(left: string, right: string): boolean {
  const normalizedLeft = normalizePath(left);
  const normalizedRight = normalizePath(right);
  if (normalizedLeft === "" || normalizedRight === "") {
    return normalizedLeft === normalizedRight;
  }
  return (
    normalizedLeft === normalizedRight ||
    normalizedLeft.startsWith(`${normalizedRight}.`) ||
    normalizedRight.startsWith(`${normalizedLeft}.`)
  );
}

export function pathContains(parent: string, child: string): boolean {
  const normalizedParent = normalizePath(parent);
  const normalizedChild = normalizePath(child);
  return (
    normalizedParent === normalizedChild ||
    normalizedChild.startsWith(`${normalizedParent}.`)
  );
}
