import { NextRequest, NextResponse } from "next/server";

const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";

type RouteContext = {
  params: Promise<{
    path: string[];
  }>;
};

function backendUrl(path: string[], search: string) {
  const configuredApiBaseUrl = (
    process.env.BACKEND_API_BASE_URL
    ?? process.env.NEXT_PUBLIC_API_BASE_URL
  )?.trim();
  const apiBaseUrl = configuredApiBaseUrl
    ? configuredApiBaseUrl.replace(/\/$/, "")
    : DEFAULT_API_BASE_URL;
  const joinedPath = path.join("/");
  return `${apiBaseUrl}/${joinedPath}${search}`;
}

async function proxyRequest(request: NextRequest, context: RouteContext) {
  const params = await context.params;
  const url = backendUrl(params.path, request.nextUrl.search);
  const hasBody = request.method !== "GET" && request.method !== "HEAD";
  const response = await fetch(url, {
    method: request.method,
    headers: {
      "Content-Type": request.headers.get("Content-Type") ?? "application/json",
    },
    body: hasBody ? await request.arrayBuffer() : undefined,
    cache: "no-store",
  });

  const body = await response.text();
  return new NextResponse(body, {
    status: response.status,
    headers: {
      "Content-Type": response.headers.get("Content-Type") ?? "application/json",
    },
  });
}

export async function GET(request: NextRequest, context: RouteContext) {
  return proxyRequest(request, context);
}

export async function POST(request: NextRequest, context: RouteContext) {
  return proxyRequest(request, context);
}

export async function PATCH(request: NextRequest, context: RouteContext) {
  return proxyRequest(request, context);
}

export async function PUT(request: NextRequest, context: RouteContext) {
  return proxyRequest(request, context);
}

export async function DELETE(request: NextRequest, context: RouteContext) {
  return proxyRequest(request, context);
}
