# SPDX-License: LGPL-3.0-or-later
# (c) 2025 Frank David Martínez Muñoz. <mnesarco at gmail.com>

# ruff: noqa: F401

from . import service
from . import commands
from . import config

from freecad.channels.vendor.fcapi.workbenches import Rules

config.commands.install()

rules = Rules("Channels_WBM")

# Tools menu
rules.menubar_append(commands.StartService.name, sibling="Std_DlgParameter")
rules.menubar_append(commands.StopService.name, sibling="Std_DlgParameter")
rules.menubar_append(commands.BlenderFindService.name, sibling="Std_DlgParameter")
rules.menubar_append(commands.BlenderDownloadExtension.name, sibling="Std_DlgParameter")

# Context menu
rules.context_menu_append(commands.BlenderSendObj.name, sibling="Std_Placement")
rules.context_menu_append(commands.BlenderSendGltf.name, sibling="Std_Placement")

rules.install()
