// Koyori kiosk Firefox profile — installed on each install-koyori-kiosk.sh run.
user_pref("browser.fullscreen.autohide", true);
user_pref("full-screen-api.ignore-widgets", true);
user_pref("browser.startup.page", 0);
user_pref("browser.shell.checkDefaultBrowser", false);
user_pref("datareporting.policy.dataSubmissionEnabled", false);
user_pref("toolkit.telemetry.enabled", false);
// Surface Go + minimal X: WebRender/GPU often paints a black screen while JS still runs.
user_pref("gfx.webrender.all", false);
user_pref("gfx.webrender.enabled", false);
user_pref("layers.acceleration.disabled", true);
user_pref("layers.acceleration.force-enabled", false);
user_pref("media.hardware-video-decoding.enabled", false);
user_pref("media.ffmpeg.vaapi.enabled", false);
