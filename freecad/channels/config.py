# SPDX-License: LGPL-3.0-or-later
# (c) 2025 Frank David Martínez Muñoz. <mnesarco at gmail.com>

from .vendor.fcapi.resources import Resources
from .vendor.fcapi.commands import CommandRegistry

from . import resources as channels_resources
from .preferences import ChannelsPreferences

resources = Resources(channels_resources)
commands = CommandRegistry("Chn_")
preferences = ChannelsPreferences()
