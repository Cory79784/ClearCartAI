import { NextRequest, NextResponse } from "next/server";

function resolveBackendBase(req: NextRequest): string {
  const configured = process.env.NEXT_PUBLIC_API_BASE?.trim();
  if (configured) {
    return configured.replace(/\/+$/, "");
  }

  const host = req.headers.get("host") ?? "";
  const proto = req.headers.get("x-forwarded-proto") ?? "http";
  const runpodHost = host.match(/^(.*)-3000\.proxy\.runpod\.net$/);
  if (runpodHost) {
    return `${proto}://${runpodHost[1]}-8000.proxy.runpod.net/api`;
  }

  return "http://localhost:8000/api";
}

async function proxy(req: NextRequest, path: string[]): Promise<NextResponse> {
  const backendBase = resolveBackendBase(req);
  const query = req.nextUrl.search ?? "";
  const target = `${backendBase}/${path.join("/")}${query}`;

  const headers = new Headers(req.headers);
  headers.delete("host");
  headers.delete("content-length");

  const method = req.method.toUpperCase();
  const hasBody = method !== "GET" && method !== "HEAD";
  const body = hasBody ? await req.arrayBuffer() : undefined;

  const upstream = await fetch(target, {
    method,
    headers,
    body,
    redirect: "manual",
    cache: "no-store",
  });

  const responseHeaders = new Headers(upstream.headers);
  responseHeaders.delete("content-encoding");
  responseHeaders.delete("transfer-encoding");

  return new NextResponse(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
}

type RouteContext = {
  params: Promise<{ path: string[] }>;
};

export async function GET(req: NextRequest, ctx: RouteContext): Promise<NextResponse> {
  const { path } = await ctx.params;
  return proxy(req, path);
}

export async function POST(req: NextRequest, ctx: RouteContext): Promise<NextResponse> {
  const { path } = await ctx.params;
  return proxy(req, path);
}

export async function PUT(req: NextRequest, ctx: RouteContext): Promise<NextResponse> {
  const { path } = await ctx.params;
  return proxy(req, path);
}

export async function PATCH(req: NextRequest, ctx: RouteContext): Promise<NextResponse> {
  const { path } = await ctx.params;
  return proxy(req, path);
}

export async function DELETE(req: NextRequest, ctx: RouteContext): Promise<NextResponse> {
  const { path } = await ctx.params;
  return proxy(req, path);
}

export async function OPTIONS(req: NextRequest, ctx: RouteContext): Promise<NextResponse> {
  const { path } = await ctx.params;
  return proxy(req, path);
}
