import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const protectedRoutes = ["/dashboard", "/labeling", "/upload", "/jobs", "/admin"];

export function proxy(request: NextRequest) {
  const path = request.nextUrl.pathname;
  const isProtected = protectedRoutes.some((p) => path.startsWith(p));
  if (!isProtected) return NextResponse.next();
  const session = request.cookies.get("cc_session");
  if (!session) {
    return NextResponse.redirect(new URL("/", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*", "/labeling/:path*", "/upload/:path*", "/jobs/:path*", "/admin/:path*"],
};
