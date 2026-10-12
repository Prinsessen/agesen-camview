# Third-party notices

The Agesen CamView installer and program bundle the third-party components below.
Each component is distributed under its own license. The source code of the
components is available from the projects listed. This file is a summary, not
legal advice; the license texts of the projects apply.

## Program (`AgesenCamView.exe` and `_internal\`)

| Component | Version | License | Project |
|---|---|---|---|
| Python | 3.13 | PSF License | https://www.python.org |
| Qt for Python (PySide6, shiboken6) and Qt 6 | 6.11.2 | LGPL-3.0 | https://www.qt.io/qt-for-python |
| PyAV | 19.0.1 | BSD-3-Clause | https://github.com/PyAV-Org/PyAV |
| FFmpeg libraries (avcodec, avformat, avutil, avfilter, avdevice, swscale, swresample) | bundled with PyAV 19.0.1 | LGPL-3.0-or-later (as reported by the build) | https://ffmpeg.org |
| x264 | bundled with PyAV | GPL-2.0-or-later | https://www.videolan.org/developers/x264.html |
| x265 | bundled with PyAV | GPL-2.0-or-later | https://www.x265.org |
| libvpx | bundled with PyAV | BSD-3-Clause | https://chromium.googlesource.com/webm/libvpx |
| dav1d | bundled with PyAV | BSD-2-Clause | https://code.videolan.org/videolan/dav1d |
| SVT-AV1 | bundled with PyAV | BSD-3-Clause-Clear | https://gitlab.com/AOMediaCodec/SVT-AV1 |
| Opus | bundled with PyAV | BSD-3-Clause | https://opus-codec.org |
| libwebp, libsharpyuv | bundled with PyAV | BSD-3-Clause | https://chromium.googlesource.com/webm/libwebp |
| LAME (libmp3lame) | bundled with PyAV | LGPL-2.0-or-later | https://lame.sourceforge.io |
| libvmaf | bundled with PyAV | BSD-2-Clause-Patent | https://github.com/Netflix/vmaf |
| oneVPL (libvpl) | bundled with PyAV | MIT | https://github.com/intel/libvpl |
| libiconv | bundled with PyAV | LGPL-2.1-or-later | https://www.gnu.org/software/libiconv |
| zlib | bundled with PyAV | Zlib | https://zlib.net |
| MinGW-w64 runtime (libgcc, libstdc++, winpthreads) | bundled with PyAV | GPL-3.0 with GCC Runtime Library Exception; winpthreads MIT/BSD | https://www.mingw-w64.org |
| Requests | 2.32.5 | Apache-2.0 | https://requests.readthedocs.io |
| urllib3 | bundled with Requests | MIT | https://urllib3.readthedocs.io |
| idna | bundled with Requests | BSD-3-Clause | https://github.com/kjd/idna |
| charset-normalizer | bundled with Requests | MIT | https://github.com/jawah/charset_normalizer |
| certifi | bundled with Requests | MPL-2.0 | https://github.com/certifi/python-certifi |
| OpenSSL | bundled with Python | Apache-2.0 | https://www.openssl.org |
| libffi | bundled with Python | MIT | https://sourceware.org/libffi |
| Microsoft Visual C++ runtime (VCRUNTIME140, MSVCP140) | 14.x | Microsoft Visual C++ Redistributable license | https://learn.microsoft.com/cpp/windows/latest-supported-vc-redist |

## Installer (`AgesenCamView-Setup-<version>.exe`)

In addition to the program above, the installer contains:

| Component | License | Project |
|---|---|---|
| PyInstaller bootloader | GPL-2.0 with bootloader exception | https://pyinstaller.org |
| Tcl/Tk (tkinter) | Tcl/Tk License (BSD-style) | https://www.tcl.tk |

## Notes on (L)GPL components

Agesen CamView itself is licensed under GPL-3.0-or-later (see `LICENSE`), which
is compatible with the GPL and LGPL components listed above.

Qt and the FFmpeg libraries are included as separate, dynamically loaded DLLs
in the program folder and can be replaced with compatible versions. The source
code for the exact versions is available from the projects above and from the
PySide6 and PyAV packages on PyPI.

The FFmpeg build that ships with the PyAV wheel also contains the x264 and x265
encoder libraries, which are licensed under the GPL. Agesen CamView only decodes
video and does not use these encoders, but they are part of the bundle.

## Trademarks

"Hikvision" is a trademark of Hangzhou Hikvision Digital Technology Co., Ltd.
Agesen CamView is not affiliated with or endorsed by Hikvision.
