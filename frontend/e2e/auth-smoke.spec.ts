import { expect, test, type Page } from "@playwright/test";

const landingHeading = /Build crop-risk intelligence with production-ready geospatial AI\./i;

function isSignInFlowUrl(url: URL): boolean {
  const href = url.href.toLowerCase();
  const pathname = url.pathname.toLowerCase();

  return pathname.startsWith("/login") || href.includes("sign-in") || href.includes("clerk");
}

async function expectSignedOutRedirect(page: Page): Promise<void> {
  await expect(page).toHaveURL(isSignInFlowUrl);
}

test("landing page is public", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: landingHeading })).toBeVisible();
});

test("protected dashboard redirects signed-out users to Clerk sign-in flow", async ({ page }) => {
  await page.goto("/dashboard");

  await expectSignedOutRedirect(page);
});
