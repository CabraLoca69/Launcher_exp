class MenuOptions:
    def get_options(self, game_name, btn_props, frame):
        raise NotImplementedError

class BaseMenuOptions(MenuOptions):
    def _play_option(self, btn_props, frame):
        if not btn_props:
            return [("▶ Jugar", "success", frame.launch_game)]
        return []

    def _common_options(self, game_name, frame):
        if not game_name:
            return [("＋ Agregar juego", "success", frame.add_exe)]

        return [
            ("★ Favoritos", "warning", lambda: frame.toggle_favorite(game_name)),
            ("⤓ Crear acceso directo", "info", lambda: frame.create_direct_access(game_name)),
            ("📌 Añadir a inicio", "info", lambda: frame.create_start_menu_shortcut(game_name)),
            ("📁 Archivos locales", "info", lambda: frame.gotofolder(game_name)),
            ("📂 Cambiar directorio", "info", lambda: frame.change_game_directory(game_name)),
            ("🗑 Eliminar juego", "danger", frame.confirm_remove),
        ]

class WindowsMenuOptions(BaseMenuOptions):
    def get_options(self, game_name, btn_props, frame):
        options= []
        if game_name:
            options = self._play_option(btn_props, frame)
        options += self._common_options(game_name, frame)
        return options

class LinuxMenuOptions(BaseMenuOptions):
    def get_options(self, game_name, btn_props, frame):
        options= []
        if game_name:
            options = self._play_option(btn_props, frame)
            options.append(("Steam ID", "info", lambda: frame.ask_steam_id(game_name)))
        options += self._common_options(game_name, frame)
        return options