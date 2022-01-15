$(function() {
    function PoppyViewModel(parameters) {
        var self = this;

        self.loginState = parameters[0];
        self.settingsViewModel = parameters[1];
        self.settings = undefined

        self.chamberTemperature = ko.observable(undefined);

        self.chamberLightIndicator = $("#poppy_chamber_light_indicator");
        self.chamberLightMode = ko.observable(undefined);

        self.onBeforeBinding = function() {
            self.settings = self.settingsViewModel.settings;
        }

        self.onStartup = function() {
            self.chamberLightMode.subscribe(function() {
                self.chamberLightIndicator.removeClass("off low medium high");
                switch (self.chamberLightMode()) {
                    case 0:
                        self.chamberLightIndicator.addClass("off");
                        break;
                    case 1:
                        self.chamberLightIndicator.addClass("low");
                        break;
                    case 2:
                        self.chamberLightIndicator.addClass("medium");
                        break;
                    case 3:
                        self.chamberLightIndicator.addClass("high");
                        break;
                }
            });
        };

        self.onDataUpdaterPluginMessage = function(plugin, data) {
            if (plugin == "poppy") {
                if (data.chamber_temperature !== undefined) {
                    self.chamberTemperature(data.chamber_temperature);
                }
                if (data.chamber_light_mode !== undefined) {
                    self.chamberLightMode(data.chamber_light_mode);
                }
            }
        };

        self.toggleChamberLightMode = function() {
            $.post(BASEURL + "plugin/poppy/chamberLight/toggleMode");
        };
    }

    OCTOPRINT_VIEWMODELS.push({
        construct: PoppyViewModel,
        dependencies: [ "loginStateViewModel", "settingsViewModel" ],
        elements: ["#navbar_plugin_poppy", "#settings_plugin_poppy"]
    });
});
