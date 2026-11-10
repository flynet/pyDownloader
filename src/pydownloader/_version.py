"""Version of the application.

``build.ps1`` overwrites this file with the value taken from ``git describe --tags``,
so the only source of the version in the code is this module. During development
it stays ``0.0.0-dev``.
"""

VERSION = "0.0.0-dev"
