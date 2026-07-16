import { NextResponse, type NextRequest } from "next/server";
import {
  isPublicAuthPath,
  REQUEST_PATHNAME_HEADER,
} from "@/lib/authRoutes";

const SESSION_COOKIE = "gulp_session"; // must match API settings.session_cookie_name

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const isPublic = isPublicAuthPath(pathname);
  const hasSession = request.cookies.has(SESSION_COOKIE);

  if (!hasSession && !isPublic) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    return NextResponse.redirect(url);
  }

  // The root layout spans both public and authenticated pages. Pass the route
  // through explicitly so its Server Component can avoid resolving protected
  // shell data on /login and /register. Do not trust cookie presence to bounce
  // public pages: an expired/revoked cookie must still be able to reach login.
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set(REQUEST_PATHNAME_HEADER, pathname);
  return NextResponse.next({ request: { headers: requestHeaders } });
}

export const config = {
  // Everything except Next internals, the API proxy, and files with extensions.
  matcher: ["/((?!api|_next/static|_next/image|.*\\..*).*)"],
};
