# coding=utf-8
from __future__ import absolute_import

import octoprint.plugin
from octoprint.util import RepeatedTimer
from .emc2101 import EMC2101

_I2C_BUS_NUMBER = 11
_FAN_POLL_INTERVAL_SECONDS = 2

class PoppyPlugin(
    octoprint.plugin.StartupPlugin,
    octoprint.plugin.SettingsPlugin,
    octoprint.plugin.AssetPlugin,
    octoprint.plugin.TemplatePlugin
):

    def __init__(self):
        self._fan = None
        self._fan_poll_timer = None
        self._fan_target_temperature = 40
    
    def _init_fan(self):
        try:
            self._fan = EMC2101(_I2C_BUS_NUMBER)
        except Exception:
            self._logger.error("Failed to initialize the fan controller", exc_info = True)
            self._fan = None
            return
        self._logger.info("Initialized the fan controller")
        self._fan_poll_timer = RepeatedTimer(_FAN_POLL_INTERVAL_SECONDS, self._poll_fan, run_first = True)
        self._fan_poll_timer.start()
    
    def _poll_fan(self):
        if self._fan:
            try:
                self._fan.poll()
                self._logger.info("fan: int %s, ext %s, spd %s, status %s",
                    self._fan.internal_temperature,
                    self._fan.external_temperature,
                    self._fan.fan_speed,
                    self._fan.status)
            except Exception:
                self._logger.error("Failed to poll the fan controller", exc_info = True)

    ##~~ StartupPlugin mixin

    def on_after_startup(self):
        self._init_fan()

    ##~~ SettingsPlugin mixin

    def get_settings_defaults(self):
        return {
            # put your plugin's default settings here
        }

    ##~~ AssetPlugin mixin

    def get_assets(self):
        # Define your plugin's asset files to automatically include in the
        # core UI here.
        return {
            "js": ["js/poppy.js"],
            "css": ["css/poppy.css"],
            "less": ["less/poppy.less"]
        }

    ##~~ Temperatures hook

    def get_temperatures(self, comm, parsed_temps):
        if self._fan:
            parsed_temps["fan_internal"] = (self._fan.internal_temperature, None)
            parsed_temps["fan_external"] = (self._fan.external_temperature, self._fan_target_temperature)
        return parsed_temps

    ##~~ Softwareupdate hook

    def get_update_information(self):
        # Define the configuration for your plugin to use with the Software Update
        # Plugin here. See https://docs.octoprint.org/en/master/bundledplugins/softwareupdate.html
        # for details.
        return {
            "poppy": {
                "displayName": "Poppy Plugin",
                "displayVersion": self._plugin_version,

                # version check: github repository
                "type": "github_release",
                "user": "j9brown",
                "repo": "poppy",
                "current": self._plugin_version,

                # update method: pip
                "pip": "https://github.com/j9brown/poppy/archive/{target_version}.zip",
            }
        }


# If you want your plugin to be registered within OctoPrint under a different name than what you defined in setup.py
# ("OctoPrint-PluginSkeleton"), you may define that here. Same goes for the other metadata derived from setup.py that
# can be overwritten via __plugin_xyz__ control properties. See the documentation for that.
#__plugin_name__ = "Poppy"

# Starting with OctoPrint 1.4.0 OctoPrint will also support to run under Python 3 in addition to the deprecated
# Python 2. New plugins should make sure to run under both versions for now. Uncomment one of the following
# compatibility flags according to what Python versions your plugin supports!
#__plugin_pythoncompat__ = ">=2.7,<3" # only python 2
__plugin_pythoncompat__ = ">=3,<4" # only python 3
#__plugin_pythoncompat__ = ">=2.7,<4" # python 2 and 3

def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = PoppyPlugin()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.comm.protocol.temperatures.received": (__plugin_implementation__.get_temperatures, 1),
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
    }
