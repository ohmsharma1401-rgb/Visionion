# Mobile client

The prototype uses the React PWA in `../web`, an alternative explicitly allowed in the brief. Camera capture uses an HTML file input with `capture="environment"`; mobile browser support varies. Run behind HTTPS to install it and enable secure browser features. The production service worker caches visited shell resources; local storage retains a single lot draft. Images, credentials and inference models are not cached there.

Native Expo screens, SQLite image queue, secure device storage, GPS consent flow and TFLite offline inference are deferred. Do not advertise full offline operation. The current application needs the backend for image checks, grading and PDF generation.
