"""Danish and English. tr("key", name=value) returns the text in the selected language."""

import ctypes

LANGUAGES = [("da", "Dansk"), ("en", "English")]
_lang = "da"

STRINGS = {
    # Main window
    "monitoring": ("Kameraovervågning", "Camera monitoring"),
    "ptz_panel": ("PTZ-panel", "PTZ panel"),
    "fullscreen": ("Fuld skærm", "Full screen"),
    "settings": ("Indstillinger", "Settings"),
    "zoom_in": ("+  Zoom", "+  Zoom"),
    "zoom_out": ("−  Zoom", "−  Zoom"),
    "speed": ("Fart: {v} %", "Speed: {v} %"),
    "ptz_hint": ("Træk i knappen for at dreje kameraet. Piletaster og + / − virker også.",
                 "Drag the knob to move the camera. Arrow keys and + / − also work."),
    "ptz_title": ("PTZ: {name}", "PTZ: {name}"),
    "camera_n": ("Kamera {n}", "Camera {n}"),
    "already_running": ("Programmet kører allerede i et andet vindue.",
                        "The program is already running in another window."),
    "close_before_uninstall": ("Luk Agesen CamView, før programmet afinstalleres.",
                               "Close Agesen CamView before uninstalling it."),
    "page": ("Side {n} / {total}", "Page {n} / {total}"),
    "prev_page": ("Forrige side (Page Up)", "Previous page (Page Up)"),
    "next_page": ("Næste side (Page Down)", "Next page (Page Down)"),
    "overview": ("Oversigt", "Overview"),
    "no_cameras": ("Ingen kameraer endnu\nKlik her eller åbn Indstillinger for at tilføje",
                   "No cameras yet\nClick here or open Settings to add cameras"),
    "click_full": ("Klik for at vise kameraet i hele vinduet", "Click to show the camera in the whole window"),
    "click_back": ("Klik eller tryk Esc for at gå tilbage til oversigten",
                   "Click or press Esc to go back to the overview"),
    "per_page": ("Kameraer pr. side", "Cameras per page"),
    "cameras_list": ("Kameraer ({n} af højst {max})", "Cameras ({n} of max {max})"),
    "add_camera": ("Tilføj", "Add"),
    "duplicate": ("Kopiér", "Copy"),
    "duplicate_tip": ("Kopiér kameraet med næste kanalnummer, fx til en NVR",
                      "Copy the camera with the next channel number, e.g. for an NVR"),
    "remove_camera": ("Fjern", "Remove"),
    "move_up": ("Op", "Up"),
    "move_down": ("Ned", "Down"),
    "add_selected": ("Tilføj valgte", "Add selected"),
    "max_cameras": ("Der kan højst være {n} kameraer.", "A maximum of {n} cameras is supported."),
    "no_camera_selected": ("Tilføj et kamera med knapperne til venstre.", "Add a camera with the buttons on the left."),
    # Video
    "connecting": ("Forbinder ...", "Connecting ..."),
    "err_auth": ("Forkert brugernavn eller adgangskode", "Wrong user name or password"),
    "err_auth_fix": ("Ret det under Indstillinger", "Correct it under Settings"),
    "err_channel": ("Kanalen findes ikke på enheden", "The channel does not exist on the device"),
    "err_conn": ("Ingen forbindelse", "No connection"),
    "retrying": ("prøver igen", "retrying"),
    "stream_lost": ("Forbindelsen blev afbrudt - prøver igen", "Connection lost - retrying"),
    # Settings
    "customer": ("Kundenavn", "Customer name"),
    "customer_ph": ("fx Eksempel ApS  (vises øverst i vinduet)",
                    "e.g. Example Ltd  (shown at the top of the window)"),
    "language": ("Sprog", "Language"),
    "name": ("Navn", "Name"),
    "ip": ("IP-adresse", "IP address"),
    "ip_ph": ("fx 192.168.1.64  (tom = ikke i brug)", "e.g. 192.168.1.64  (empty = not used)"),
    "search_net": ("Søg på netværket ...", "Search network ..."),
    "ports": ("Porte", "Ports"),
    "user": ("Brugernavn", "User name"),
    "password": ("Adgangskode", "Password"),
    "show": ("Vis", "Show"),
    "channel": ("Kanal", "Channel"),
    "channel_tip": ("1 for et kamera. Ved en NVR: kameraets kanalnummer i optageren.",
                    "1 for a camera. For an NVR: the camera's channel number in the recorder."),
    "quality": ("Videokvalitet", "Video quality"),
    "stream_auto": ("Automatisk (anbefalet)", "Automatic (recommended)"),
    "stream_main": ("Mainstream (høj kvalitet)", "Main stream (high quality)"),
    "stream_sub": ("Substream (lav båndbredde)", "Sub stream (low bandwidth)"),
    "test": ("Test forbindelse", "Test connection"),
    "enter_ip_first": ("Skriv en IP-adresse først.", "Enter an IP address first."),
    "testing": ("Tester ...", "Testing ..."),
    "test_ok": ("OK: {model}  ·  PTZ: {ptz}", "OK: {model}  ·  PTZ: {ptz}"),
    "yes": ("ja", "yes"),
    "no": ("nej", "no"),
    "no_conn_detail": ("Ingen forbindelse ({e})", "No connection ({e})"),
    "pw_note": ("Adgangskoder gemmes krypteret og kan kun læses af din Windows-bruger på denne pc.",
                "Passwords are stored encrypted and can only be read by your Windows user on this PC."),
    "save": ("Gem", "Save"),
    "cancel": ("Annuller", "Cancel"),
    "select": ("Vælg", "Select"),
    "discover_title": ("Kameraer på netværket", "Cameras on the network"),
    "discover_searching": ("Søger efter Hikvision-enheder ...", "Searching for Hikvision devices ..."),
    "discover_none": ("Ingen enheder fundet. Tjek at pc'en er på samme netværk som kameraerne.",
                      "No devices found. Check that the PC is on the same network as the cameras."),
    "discover_found": ('{n} enheder fundet. Vælg en eller flere, og klik Tilføj.',
                      '{n} devices found. Select one or more and click Add.'),
    # Uninstall
    "un_confirm": ("Vil du afinstallere {name}?", "Do you want to uninstall {name}?"),
    "un_button": ("Afinstaller", "Uninstall"),
    "un_purge": ("Skal kameraopsætningen og de gemte adgangskoder også slettes?\n\n"
                 "Vælg Nej, hvis programmet skal installeres igen senere.",
                 "Delete the camera setup and saved passwords as well?\n\n"
                 "Choose No if the program will be installed again later."),
    "un_done": ("Programmet er afinstalleret.", "The program has been uninstalled."),
    # Installer
    "in_window": ("Installer {name}", "Install {name}"),
    "in_welcome": ("Velkommen", "Welcome"),
    "in_upgrade": ("Programmet er allerede installeret på denne pc og bliver opdateret.",
                   "The program is already installed on this PC and will be updated."),
    "in_new": ('Installerer Agesen CamView, der viser op til 32 Hikvision-kameraer og styrer PTZ-kameraer.',
              'Installs Agesen CamView, which shows up to 32 Hikvision cameras and controls PTZ cameras.'),
    "in_folder": ("Installeres i", "Install to"),
    "in_browse": ("Gennemse ...", "Browse ..."),
    "in_choose_folder": ("Vælg mappe", "Choose folder"),
    "in_customer": ("Kundens navn (vises øverst i programmet)", "Customer name (shown at the top of the program)"),
    "in_desktop": ("Opret genvej på skrivebordet", "Create a desktop shortcut"),
    "in_reset": ("Start helt forfra: slet tidligere kameraopsætning på denne pc",
                 "Start fresh: delete the earlier camera setup on this PC"),
    "in_noadmin": ("Kræver ikke administrator. Kan afinstalleres under Installerede apps i Windows.",
                   "No administrator rights needed. Uninstall it under Installed apps in Windows."),
    "in_install": ("Installer", "Install"),
    "in_installing": ("Installerer ...", "Installing ..."),
    "in_failed": ("Installationen mislykkedes", "Installation failed"),
    "in_done": ("Agesen CamView er installeret", "Agesen CamView is installed"),
    "in_where_desk": ("Programmet findes i startmenuen og på skrivebordet.",
                      "The program is in the Start menu and on the desktop."),
    "in_where": ("Programmet findes i startmenuen.", "The program is in the Start menu."),
    "in_start": ("Start Agesen CamView nu", "Start Agesen CamView now"),
    "in_finish": ("Afslut", "Finish"),
    "in_running": ("Agesen CamView kører. Luk programmet og prøv igen.", "Agesen CamView is running. Close it and try again."),
    "in_notempty": ("Mappen er ikke tom. Vælg en tom mappe eller en ny mappe.",
                    "The folder is not empty. Choose an empty or a new folder."),
    "in_remove_old": ("Fjerner den gamle version ...", "Removing the old version ..."),
    "in_copy": ("Kopierer filer ...", "Copying files ..."),
    "in_shortcuts": ("Opretter genveje ...", "Creating shortcuts ..."),
    "in_register": ("Registrerer programmet ...", "Registering the program ..."),
    "in_finished": ("Færdig", "Done"),
    "in_need_folder": ("Vælg en mappe.", "Choose a folder."),
}


def system_language() -> str:
    """Danish if Windows runs in Danish, otherwise English."""
    try:
        lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        return "da" if (lang_id & 0x3FF) == 0x06 else "en"
    except (AttributeError, OSError):
        return "en"


def set_language(code: str):
    global _lang
    _lang = code if code in dict(LANGUAGES) else system_language()


def language() -> str:
    return _lang


def tr(key: str, **kw) -> str:
    da, en = STRINGS[key]
    s = da if _lang == "da" else en
    return s.format(**kw) if kw else s
