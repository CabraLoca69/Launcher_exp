class TkMenuRenderer:
    _STYLE_MAP = {
        "success": "success-outline",
        "warning": "warning-outline",
        "danger": "danger-outline",
        "info": "info-outline",
    }

    def build(self, menu, options):
        for label, action_type, command in options:
            style = self._STYLE_MAP.get(action_type, "info-outline")
            menu.add_button(label, 25, style, command)
        return menu