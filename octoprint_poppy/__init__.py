# coding=utf-8
from __future__ import absolute_import

import octoprint.plugin
from octoprint.events import Events
from octoprint.util import RepeatedTimer
from flask import make_response
from .emc2101 import EMC2101
from .aw9523 import AW9523

_I2C_BUS_NUMBER = 11
_FAN_POLL_INTERVAL_SECONDS = 2

_LIGHT_MODE_OFF = 0
_LIGHT_MODE_LOW = 1
_LIGHT_MODE_MEDIUM = 2
_LIGHT_MODE_HIGH = 3

class PoppyPlugin(
    octoprint.plugin.StartupPlugin,
    octoprint.plugin.ShutdownPlugin,
    octoprint.plugin.SettingsPlugin,
    octoprint.plugin.EventHandlerPlugin,
    octoprint.plugin.BlueprintPlugin,
    octoprint.plugin.AssetPlugin,
    octoprint.plugin.TemplatePlugin
):

    def __init__(self):
        self._fan = None
        self._fan_poll_timer = None
        self._heating = False
        self._heating_changed = False
        self._chamber_light_mode = _LIGHT_MODE_OFF
        self._chamber_temperature = None

    ##~~ fan control

    def _init_fan(self):
        try:
            self._fan = EMC2101(_I2C_BUS_NUMBER)
        except Exception:
            self._logger.error("Failed to initialize the fan controller", exc_info = True)
            self._fan = None
            return
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
            self._logger.debug("fan: int %s, ext %s, tgt %s, spd %s, status %s",
                self._fan.internal_temperature,
                self._fan.external_temperature,
                self._fan.target_temperature,
                self._fan.fan_speed,
                self._fan.status)
            if self._fan.external_temperature != self._chamber_temperature:
                self._chamber_temperature = self._fan.external_temperature
                self._notify_clients()

    def _update_fan_target_temperature(self):
        if self._fan:
            try:
                self._fan.target_temperature = self._settings.get_int([
                    "chamber_target_temperature_when_heating" if self._heating else
                    "chamber_target_temperature_when_cooling"])
                self._logger.info("new target temperature %s, heating %s",
                        self._fan.target_temperature, self._heating)
            except Exception:
                self._logger.error("Failed to update fan controller target temperature", exc_info = True)

    ##~~ light and relay control

    def _init_io(self):
        try:
            self._io = AW9523(_I2C_BUS_NUMBER)
        except Exception:
            self._logger.error("Failed to initialize the I/O expander", exc_info = True)
            self._io = None
            self._relay_pin = None
            self._led_pin = None
            return
        self._io.reset()
        self._relay_pin = self._io.output_pin(8)
        self._led_pin = self._io.led_pin(9)

    def _update_chamber_light(self):
        brightness = self._chamber_light_brightness_for_mode(self._chamber_light_mode)
        self._led_pin.level = int(max(min(brightness * 255 / 100, 255), 0))

    def _chamber_light_brightness_for_mode(self, mode):
        if mode <= _LIGHT_MODE_OFF:
            return 0
        if mode == _LIGHT_MODE_LOW:
            return self._settings.get_int(["chamber_light_brightness_low"])
        if mode == _LIGHT_MODE_MEDIUM:
            return self._settings.get_int(["chamber_light_brightness_medium"])
        return self._settings.get_int(["chamber_light_brightness_high"])


    ##~~ StartupPlugin mixin

    def on_startup(self, host, port):
        helpers = self._plugin_manager.get_helpers("psucontrol", "register_plugin")
        if helpers and "register_plugin" in helpers:
            helpers["register_plugin"](self)

    def on_after_startup(self):
        self._init_fan()
        self._update_fan_target_temperature()
        self._init_io()

    ##~~ ShutdownPlugin mixin

    def on_shutdown(self):
        self._release_fan()

    ##~~ SettingsPlugin mixin

    def get_settings_defaults(self):
        return {
            "chamber_target_temperature_when_heating": 40,
            "chamber_target_temperature_when_cooling": 30,
            "chamber_light_brightness_low": 10,
            "chamber_light_brightness_medium": 50,
            "chamber_light_brightness_high": 100
        }

    def on_settings_save(self, data):
        octoprint.plugin.SettingsPlugin.on_settings_save(self, data)
        self._update_fan_target_temperature()
        self._update_chamber_light()

    ##~~ EventHandlerPlugin mixin

    def on_event(self, event, payload):
        if event == Events.CLIENT_OPENED:
            self._notify_clients()

    def _notify_clients(self):
        data = {}
        if self._chamber_temperature != None:
            data["chamber_temperature"] = self._chamber_temperature
        data["chamber_light_mode"] = self._chamber_light_mode
        self._plugin_manager.send_plugin_message(self._identifier, data)

    # ~~ BlueprintPlugin mixin

    @octoprint.plugin.BlueprintPlugin.route("/chamberLight/toggleMode", methods=["POST"])
    def handle_toggle_light_mode_request(self):
        self.toggle_chamber_light_mode()
        return make_response('', 200)

    ##~~ AssetPlugin mixin

    def get_assets(self):
        return {
            "js": ["js/poppy.js"],
            "css": ["css/poppy.css"],
            "less": ["less/poppy.less"]
        }

    ##~~ TemplatePlugin mixin

    def get_template_configs(self):
        return [
            dict(type="settings"),
            dict(type="navbar")
        ]

    ##~~ Temperatures hook

    def get_temperatures(self, comm, parsed_temps):
        heating = parsed_temps.get("B", (0, 0))[1] > 0
        if self._heating != heating:
            self._heating = heating
            self._heating_changed = True

        if self._fan:
            parsed_temps["fan_controller"] = (self._fan.internal_temperature, None)
            # "chamber" is reserved so use a variation
            parsed_temps["_chamber"] = (self._fan.external_temperature, self._fan.target_temperature)
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
        self._relay_pin.state = True

    def turn_psu_off(self):
        self._logger.info("Switching power supply off")
        self._relay_pin.state = False

    def get_psu_state(self):
        return self._relay_pin.state if self._relay_pin else False

    ##~~ Helpers

    def get_chamber_temperature(self):
        return self._chamber_temperature if self._chamber_temperature != None else 0

    def set_chamber_light_mode(self, mode):
        if mode < _LIGHT_MODE_OFF:
            mode = _LIGHT_MODE_OFF
        if mode > _LIGHT_MODE_HIGH:
            mode = _LIGHT_MODE_HIGH
        if mode == self._chamber_light_mode:
            return

        self._logger.info("Setting chamber light mode to %s", mode)
        self._chamber_light_mode = mode
        self._update_chamber_light()
        self._notify_clients()
    
    def toggle_chamber_light_mode(self):
        self.set_chamber_light_mode(self._chamber_light_mode - 1 if self._chamber_light_mode > _LIGHT_MODE_OFF else _LIGHT_MODE_HIGH)


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
        get_chamber_temperature = __plugin_implementation__.get_chamber_temperature,
        set_chamber_light_mode = __plugin_implementation__.set_chamber_light_mode,
        toggle_chamber_light_mode = __plugin_implementation__.toggle_chamber_light_mode
    )
