# Changelog

All notable changes to **MotoGP VideoPass for Kodi** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.1] – 2026-09-06

### Fixed
- **Failed logins were silent.** When the email/password sign-in was rejected, the add-on just showed "[ Set Up Authentication ]" again with no explanation, which looked like the login itself was broken. The main menu now shows *why* it failed ("Λάθος email ή κωδικός", a missing field, a network error, …).
- Login errors are classified from the server's JSON body instead of the bare HTTP status (`invalid_grant` vs. malformed request), and the reason is written to `kodi.log`.
- A password with leading/trailing spaces (easy to get from Kodi's on-screen keyboard) is retried once without them.

## [0.3.0] – 2026-07-13

### Added
- **Email + password login.** Enter your MotoGP account credentials in the add-on settings and it signs in directly (OAuth2 password grant against `api.motogp.com`), obtaining and storing the token itself. No more copying the `DAT` cookie from a browser — works fully headless on LibreELEC.
- **Automatic token refresh.** When the token expires the add-on logs in again transparently before VOD and live requests.

### Changed
- Authentication settings now show **Email** and **Password** fields. A manually pasted `auth_token` is still supported as a fallback.

### Tested on
- Windows 10 / 11 with Kodi 21 Omega
- LibreELEC running Kodi 21 Omega

## [0.2.0] – 2026-04-26

### Added
- Live race streaming. A new **● Live** entry appears at the top of the main menu and plays the currently live event (race, sprint, qualifying, practice, warm-up) when one is on.
- HLS playback path via `inputstream.adaptive` for the live endpoint
- Optional `access_token` setting for accounts whose live Bearer token differs from the DAT cookie (most accounts share the same JWT)

### Changed
- Live response shape (`cdns`, `dvr_range`, `user`, `video_info` — no `access` object) handled in a separate render path from VOD
- Tokenised live URLs (`live/v2/url?data=…`) are resolved with `&client=true` and `Authorization: Bearer <token>` before playback

### Tested on
- Windows 10 / 11 with Kodi 21 Omega
- LibreELEC running Kodi 21 Omega

## [0.1.0] – 2026-04-04

### Added
- First public Kodi-forum release of the MotoGP VideoPass add-on
- Browse seasons, events, categories (MotoGP / Moto2 / Moto3)
- Multiple camera feeds: Commentary, Ambient, Helicopter, Onboard 1–4
- DASH playback via `inputstream.adaptive`
- DAT-cookie based authentication
