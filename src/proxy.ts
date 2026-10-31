import { createHash, timingSafeEqual } from "node:crypto";
import { NextResponse, type NextRequest } from "next/server";

// HTTP Basic Auth in front of the whole app, including /api/chat.
// Fails closed: if SITE_USERNAME or SITE_PASSWORD is unset, nobody gets in.
export function proxy(request: NextRequest) {
  const username = process.env.SITE_USERNAME;
  const password = process.env.SITE_PASSWORD;
  if (!username || !password) {
    return new NextResponse("Site login is not configured. Set SITE_USERNAME and SITE_PASSWORD.", {
      status: 503,
    });
  }

  const header = request.headers.get("authorization");
  if (header?.startsWith("Basic ")) {
    const decoded = Buffer.from(header.slice(6), "base64").toString("utf8");
    const sep = decoded.indexOf(":");
    if (
      sep !== -1 &&
      safeEqual(decoded.slice(0, sep), username) &&
      safeEqual(decoded.slice(sep + 1), password)
    ) {
      return NextResponse.next();
    }
  }

  return new NextResponse("Unauthorized", {
    status: 401,
    headers: { "WWW-Authenticate": 'Basic realm="Startup Job Research", charset="UTF-8"' },
  });
}

// Compare fixed-length hashes so the comparison time doesn't leak the value.
function safeEqual(a: string, b: string): boolean {
  const hash = (s: string) => createHash("sha256").update(s).digest();
  return timingSafeEqual(hash(a), hash(b));
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
