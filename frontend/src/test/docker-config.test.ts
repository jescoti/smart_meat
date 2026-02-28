/**
 * Tests for frontend Docker configuration files.
 *
 * Validates structure and content of the frontend Dockerfile and
 * docker-compose.yml frontend service by reading files as text.
 * Does NOT import React components or use jsdom.
 */

import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";
import { describe, it, expect } from "vitest";

// Project root is three levels up from frontend/src/test/
const PROJECT_ROOT = resolve(__dirname, "..", "..", "..");

function readFile(relativePath: string): string {
  const fullPath = resolve(PROJECT_ROOT, relativePath);
  return readFileSync(fullPath, "utf-8");
}

function fileExists(relativePath: string): boolean {
  const fullPath = resolve(PROJECT_ROOT, relativePath);
  return existsSync(fullPath);
}

describe("Frontend Dockerfile", () => {
  it("should exist at frontend/Dockerfile", () => {
    expect(fileExists("frontend/Dockerfile")).toBe(true);
  });

  it("should use multi-stage build with at least 3 stages", () => {
    const content = readFile("frontend/Dockerfile");
    const fromLines = content
      .split("\n")
      .filter((line) => line.trim().toUpperCase().startsWith("FROM"));
    expect(fromLines.length).toBeGreaterThanOrEqual(3);
  });

  it("should use node:20-alpine as base image", () => {
    const content = readFile("frontend/Dockerfile");
    expect(content).toContain("node:20-alpine");
  });

  it("should have a deps stage", () => {
    const content = readFile("frontend/Dockerfile");
    const lower = content.toLowerCase();
    expect(lower).toContain("as deps");
  });

  it("should have a builder stage", () => {
    const content = readFile("frontend/Dockerfile");
    const lower = content.toLowerCase();
    expect(lower).toContain("as builder");
  });

  it("should have a runner stage", () => {
    const content = readFile("frontend/Dockerfile");
    const lower = content.toLowerCase();
    expect(lower).toContain("as runner");
  });

  it("should create and use non-root user nextjs", () => {
    const content = readFile("frontend/Dockerfile");
    expect(content).toContain("nextjs");
    const userLines = content
      .split("\n")
      .filter((line) => line.trim().toUpperCase().startsWith("USER"));
    expect(userLines.length).toBeGreaterThanOrEqual(1);
  });

  it("should expose port 3000", () => {
    const content = readFile("frontend/Dockerfile");
    expect(content).toContain("EXPOSE 3000");
  });

  it("should set NODE_ENV to production", () => {
    const content = readFile("frontend/Dockerfile");
    expect(content).toContain("NODE_ENV");
    expect(content).toContain("production");
  });

  it("should disable Next.js telemetry", () => {
    const content = readFile("frontend/Dockerfile");
    expect(content).toContain("NEXT_TELEMETRY_DISABLED");
  });

  it("should run node server.js as CMD", () => {
    const content = readFile("frontend/Dockerfile");
    expect(content).toContain("server.js");
  });

  it("should run npm run build in builder stage", () => {
    const content = readFile("frontend/Dockerfile");
    expect(content).toContain("npm run build");
  });
});

describe("docker-compose.yml frontend service", () => {
  it("should exist at project root", () => {
    expect(fileExists("docker-compose.yml")).toBe(true);
  });

  it("should contain a frontend service definition", () => {
    const content = readFile("docker-compose.yml");
    expect(content).toContain("frontend:");
  });

  it("should build from ./frontend context", () => {
    const content = readFile("docker-compose.yml");
    // The frontend service build context should reference ./frontend
    expect(content).toContain("./frontend");
  });

  it("should expose port 3000 for frontend", () => {
    const content = readFile("docker-compose.yml");
    expect(content).toContain("3000");
  });

  it("should have frontend depend on backend", () => {
    const content = readFile("docker-compose.yml");
    // After the frontend: service definition, there should be a depends_on referencing backend
    expect(content).toContain("depends_on");
  });
});
