# Changelog

## 1.2.0 – first public release

- Released as Agesen CamView under GPL-3.0-or-later. An earlier installation
  named HikViewer is removed by the installer, and its settings are kept.

- Live view of up to 32 Hikvision cameras or NVR channels over RTSP, spread
  over pages with 4, 6, 9 or 16 cameras per page. Only the current page is
  streamed.
- Click a camera to show it alone in the whole window in full quality; click
  again or press Esc to go back.
- PTZ control in the single view with an on-screen joystick, zoom, speed and
  keyboard, directly on the camera or through an NVR.
- Network discovery (SADP) that can add several cameras at once, reusing the
  login of the selected camera; copy a camera with the next channel number for
  NVRs; connection test.
- Automatic main/sub stream selection.
- Customer name at the top; fixed Agesen EL-Teknik branding at the bottom.
- Danish and English user interface, switchable at runtime.
- Passwords encrypted with Windows DPAPI.
- No automatic retry after a failed login, to avoid Hikvision IP lockout.
- Single-instance lock, so two windows cannot overwrite each other's setup.
- Per-user installer without administrator rights: Start menu and desktop
  shortcuts, entry in Installed apps, silent install and uninstall, and an
  option to start fresh on a PC that had Agesen CamView before.
