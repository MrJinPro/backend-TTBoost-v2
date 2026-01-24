// Centralized runtime configuration (Vite env)

// Public Android testing link (Google Play testing page or direct APK URL).
// Configure via .env: VITE_ANDROID_TEST_URL=
export const ANDROID_TEST_URL: string =
  ((import.meta as any).env?.VITE_ANDROID_TEST_URL as string | undefined)?.trim() ||
  "https://play.google.com/apps/testing/com.mrjinpro.novaboostmobile";
