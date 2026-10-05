import { execFileSync } from "node:child_process";
import fs from "node:fs";

import { expect, test } from "@playwright/test";

test.beforeAll(() => {
  const source = process.env.FIXTURE_SOURCE || "/opt/fixtures/service_app";
  const destination = process.env.FIXTURE_DEST || "/fixtures/service_app";
  fs.rmSync(destination, { recursive: true, force: true });
  fs.cpSync(source, destination, { recursive: true });
  const git = (...args: string[]) => {
    execFileSync(
      "git",
      ["-c", "user.email=test@example.com", "-c", "user.name=test", "-c", "init.defaultBranch=main", ...args],
      { cwd: destination },
    );
  };
  git("init");
  git("add", ".");
  git("commit", "-m", "init");
});

test.describe.configure({ mode: "serial" });

let repositoryPath = "/";

async function signIn(page: import("@playwright/test").Page) {
  await page.goto("/");
  await page.getByLabel("Token").fill(process.env.ALICE_TOKEN || "alice-local-token");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByLabel("Repository URL")).toBeVisible();
}

test("import, ask, trace, and open a cited file", async ({ page }) => {
  await signIn(page);
  await page.getByLabel("Repository URL").fill("file:///fixtures/service_app");
  await page.getByRole("button", { name: "Import" }).click();
  await expect(page.getByText(/Commit:/)).toBeVisible({ timeout: 90000 });
  repositoryPath = new URL(page.url()).pathname;
  await page.getByRole("button", { name: "explain_repository" }).click();
  const row = page.locator("[data-trace-row]").first();
  await expect(row).toBeVisible({ timeout: 120000 });
  await expect(row).toContainText("repository-mcp");
  await expect(page.locator("table")).not.toContainText("from fastapi");
  await page.getByRole("link", { name: /Found in/ }).first().click();
  await expect(page.locator(".file")).toContainText("FastAPI");
});

test("approve a comment and open the new line", async ({ page }) => {
  await signIn(page);
  await page.getByRole("link", { name: /service_app/ }).click();
  await page.getByLabel("Question").fill("Add the comment reviewed to app/main.py");
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page.getByRole("button", { name: "Approve" })).toBeVisible({ timeout: 120000 });
  await expect(page.locator("pre.diff")).toContainText("# reviewed");
  await page.getByRole("button", { name: "Approve" }).click();
  await expect(page.getByRole("button", { name: "Apply" })).toBeEnabled();
  await page.getByRole("button", { name: "Apply" }).click();
  await page.getByRole("link", { name: "app/main.py" }).click();
  await expect(page.locator(".file")).toContainText("# reviewed");
});

test("search cites a symbol after analysis", async ({ page }) => {
  await signIn(page);
  await page.getByRole("link", { name: /service_app/ }).click();
  await page.getByRole("link", { name: "Jobs" }).click();
  await page.getByRole("button", { name: "Run analysis" }).click();
  await expect(page.getByText("succeeded").first()).toBeVisible({ timeout: 120000 });
  await page.getByRole("link", { name: "Overview" }).click();
  await page.getByLabel("Symbol search").fill("create_user");
  await page.getByRole("button", { name: "Search" }).click();
  const match = page.getByRole("link", { name: "create_user" });
  await expect(match).toBeVisible({ timeout: 60000 });
  await match.click();
  await expect(page.locator(".file")).toBeVisible();
});

test("overview stacks on a narrow screen", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 800 });
  await signIn(page);
  const link = page.getByRole("link", { name: /service_app/ });
  await expect(link).toBeVisible({ timeout: 30000 });
  await link.click();
  const first = page.locator(".region").nth(0);
  const second = page.locator(".region").nth(1);
  await expect(first).toBeVisible();
  const top = await first.boundingBox();
  const next = await second.boundingBox();
  expect(top).toBeTruthy();
  expect(next).toBeTruthy();
  expect(next!.y).toBeGreaterThan(top!.y + top!.height - 2);
});
