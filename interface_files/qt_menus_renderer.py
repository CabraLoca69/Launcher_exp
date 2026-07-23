class QtMenuRenderer:
    _STYLE_MAP = {
        "success": "btnSuccess",
        "danger": "btnDanger",
        "warning": "btnWarning",  # agregar si querés distinguirlo en QSS
        "info": None,             # estilo default de botón de CustomPopupMenu
    }

    def build(self, menu, options):
        for label, action_type, command in options:
            btn = menu.add_button(label, command) 
            object_name = self._STYLE_MAP.get(action_type)
            if object_name and btn:
                btn.setObjectName(object_name)
        return menu