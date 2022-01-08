# coding=utf-8
from __future__ import absolute_import

import octoprint.plugin
from octoprint.util import RepeatedTimer
from .emc2101 import EMC2101

_I2C_BUS_NUMBER = 11
_FAN_POLL_INTERVAL_SECONDS = 2

class PoppyPlugin(
    octoprint.plugin.StartupPlugin,
    octoprint.plugin.ShutdownPlugin,
    octoprint.plugin.SettingsPlugin,
    octoprint.plugin.AssetPlugin,
    octoprint.plugin.TemplatePlugin
):

    def __init__(self):
        self._fan = None
        self._fan_poll_timer = None
        self._heating = False
        self._heating_changed = False
    
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

    def _release_fan(self):
        fan = self._fan
        self._fan = None
        if fan:
            try:
                fan.close()
            except Exception:
                self._logger.error("Failed to release the fan controller", exc_info = True)

    def _poll_fan(self):
        if self._heating_changed:
            self._heating_changed = False
            self._update_fan_target_temperature()
        if self._fan:
            try:
                self._fan.poll()
            except Exception:
                self._logger.error("Failed to poll the fan controller", exc_info = True)
                return
            self._logger.info("fan: int %s, ext %s, tgt %s, spd %s, status %s",
                self._fan.internal_temperature,
                self._fan.external_temperature,
                self._fan.target_temperature,
                self._fan.fan_speed,
                self._fan.status)

    def _update_fan_target_temperature(self):
        if self._fan:
            try:
                self._fan.target_temperature = self._settings.get_int([
                    "chamber_target_temperature_when_heating" if self._heating else
                    "chamber_target_temperature_when_cooling"])
                self._logger.info("new target temperature %s, heating %s",
                        self._fan.target_temperature, self._heating)
            except Exception:
                self._logger.error("Failed to update fan target temperature", exc_info = True)

    ##~~ StartupPlugin mixin

    def on_startup(self, host, port):
        helpers = self._plugin_manager.get_helpers("psucontrol", "register_plugin")
        if helpers and "register_plugin" in helpers:
            helpers["register_plugin"](self)

    def on_after_startup(self):
        self._init_fan()
        self._update_fan_target_temperature()

    ##~~ ShutdownPlugin mixin

    def on_shutdown(self):
        self._release_fan()

    ##~~ SettingsPlugin mixin

    def get_settings_defaults(self):
        return {
            "chamber_target_temperature_when_heating": 40,
            "chamber_target_temperature_when_cooling": 30
        }

    def on_settings_save(self, data):
        octoprint.plugin.SettingsPlugin.on_settings_save(self, data)
        self._update_fan_target_temperature()

    ##~~ AssetPlugin mixin

    def get_assets(self):
        # Define your plugin's asset files to automatically include in the
        # core UI here.
        return {
            "js": ["js/poppy.js"],
            "css": ["css/poppy.css"],
            "less": ["less/poppy.less"]
        }

    ##~~ TemplatePlugin mixin

    def get_template_configs(self):
        return [
            dict(type="settings", custom_bindings=False)
        ]

    ##~~ Temperatures hook

    def get_temperatures(self, comm, parsed_temps):
        heating = parsed_temps.get("B", (0, 0))[1] > 0
        if self._heating != heating:
            self._heating = heating
            self._heating_changed = True

        if self._fan:
            parsed_temps["fan_internal"] = (self._fan.internal_temperature, None)
            parsed_temps["fan_external"] = (self._fan.external_temperature, self._fan.target_temperature)
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

    ##~~ PSU Control plug-in

    def turn_psu_on(self):
        self._logger.info("Switching power supply on")

    def turn_psu_off(self):
        self._logger.info("Switching power supply off")

    def get_psu_state(self):
        self._logger.info("Getting power supply state")
        return True

    ##~~ Helpers

    def get_fan_external_temperature(self):
        return self._fan.external_temperature if self._fan else 0

__plugin_pythoncompat__ = ">=3,<4" # only python 3

def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = PoppyPlugin()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.comm.protocol.temperatures.received": (__plugin_implementation__.get_temperatures, 1),
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
    }

    global __plugin_helpers__
    __plugin_helpers__ = dict(
        get_fan_external_temperature = __plugin_implementation__.get_fan_external_temperature
    )
