"""The company bar at the bottom. Fixed in the program and cannot be changed by the customer."""

import base64

from .brand_logo import LOGO_PNG_B64

COMPANY = "Agesen EL-Teknik"
CONTACT = "www.agesen.dk  ·  +45 98 23 20 10"
ACCENT = "#DA3648"
LOGO_PNG = base64.b64decode(LOGO_PNG_B64)
