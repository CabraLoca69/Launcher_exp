import os
import sys
from datafiles import db, ICONS

class MenuCreator:
    def create_menu(self, menu, platform_name, game_name, btn_props, frame):
        raise NotImplementedError

class BaseMenuCreator(MenuCreator):
    def add_play_button(self, menu, platform_name, game_name, btn_props, frame):
        if not btn_props:
                menu.add_button("▶ Jugar", 25, "success-outline", frame.launch_game)
    
    def add_common_buttons(self, menu, platform_name, game_name, btn_props, frame):
        if game_name:
            menu.add_button("★ Favoritos", 25, "warning-outline",
                            lambda: frame.toggle_favorite(game_name))

            menu.add_button("⤓ Crear acceso directo", 25, "info-outline",
                            lambda: frame.create_direct_access(
                                game_name,
                                os.path.abspath(sys.argv[0]),
                                db.get(f"{platform_name}.game_list.{game_name}", ),
                                destino_desktop=True)
                                )

            menu.add_button("📌 Añadir a inicio", 25, "info-outline",
                            lambda: frame.create_start_menu_shortcut(
                                game_name,
                                db.get(f"{platform_name}.game_list.{game_name}"),
                                ICONS))

            menu.add_button("📁 Archivos locales", 25, "info-outline",
                            lambda: frame.gotofolder(game_name))

            menu.add_button("📂 Cambiar directorio", 25, "info-outline",
                            lambda: frame.change_game_directory(game_name))

            menu.add_button("🗑 Eliminar juego", 25, "danger-outline",
                            frame.confirm_remove)

        else:
            menu.add_button("＋ Agregar juego", 25, "success-outline", frame.add_exe)

        return menu

class WindowsMenuCreator(BaseMenuCreator):
    def create_menu(self, menu, platform_name, game_name, btn_props, frame):
        self.add_play_button(menu, platform_name, game_name, btn_props, frame)
        return self.add_common_buttons(menu, game_name, btn_props, frame, platform_name)

class LinuxMenuCreator(BaseMenuCreator):
    def create_menu(self, menu, platform_name, game_name, btn_props, frame, ):
        self.add_play_button(menu, platform_name, game_name, btn_props, frame)
        if game_name:
            menu.add_button("Steam ID", 25, "info-outline",
                            lambda: frame.ask_steam_id(game_name))

        return self.add_common_buttons(menu, platform_name, game_name, btn_props, frame)

