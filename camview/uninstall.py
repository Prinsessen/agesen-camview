"""Uninstall: AgesenCamView.exe --uninstall [--silent] [--purge]

Run from "Installed apps" in Windows. Removes the shortcuts, the app list entry and
the program folder. Saved settings (cameras, passwords) are only deleted if the
user chooses so, or with --purge.
"""

import os
import shutil
import sys

from . import config, install_info
from .i18n import tr


def run(argv) -> int:
    silent = "--silent" in argv
    purge = "--purge" in argv
    install_dir = install_info.installed_dir() or os.path.dirname(sys.executable)

    if not silent:
        from PySide6.QtWidgets import QApplication, QMessageBox
        app = QApplication.instance() or QApplication(sys.argv)  # noqa: F841 - kept alive for the dialogs
        box = QMessageBox(QMessageBox.Icon.Question, install_info.DISPLAY_NAME,
                          tr("un_confirm", name=install_info.DISPLAY_NAME))
        yes = box.addButton(tr("un_button"), QMessageBox.ButtonRole.AcceptRole)
        box.addButton(tr("cancel"), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is not yes:
            return 1
        if os.path.isdir(config.APP_DIR):
            ask = QMessageBox(QMessageBox.Icon.Question, install_info.DISPLAY_NAME, tr("un_purge"))
            delete = ask.addButton(tr("yes").capitalize(), QMessageBox.ButtonRole.YesRole)
            no = ask.addButton(tr("no").capitalize(), QMessageBox.ButtonRole.NoRole)
            ask.setDefaultButton(no)
            ask.exec()
            purge = ask.clickedButton() is delete

    for lnk in (install_info.start_menu_shortcut(), install_info.desktop_shortcut()):
        try:
            os.remove(lnk)
        except OSError:
            pass
    install_info.unregister()
    if purge:
        shutil.rmtree(config.APP_DIR, ignore_errors=True)
    if os.path.isfile(os.path.join(install_dir, install_info.EXE_NAME)):
        install_info.delete_dir_after_exit(install_dir)

    if not silent:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(None, install_info.DISPLAY_NAME, tr("un_done"))
    return 0
