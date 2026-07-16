export const PUBLIC_AUTH_PREFIXES = ["/login", "/register"] as const;
export const REQUEST_PATHNAME_HEADER = "x-gulp-pathname";

export function isPublicAuthPath(pathname: string): boolean {
  return PUBLIC_AUTH_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}
