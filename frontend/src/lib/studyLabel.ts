/** Format a study name for display: replace underscores with spaces, title-case each word. */
export function formatStudyLabel(name: string): string {
  return name
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
