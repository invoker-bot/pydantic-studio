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
