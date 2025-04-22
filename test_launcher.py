import unittest
import os
from unittest.mock import patch, MagicMock
import time
import threading
from datetime import datetime

from launcher69 import loader,GameLauncherController , config

class TestLoader(unittest.TestCase):

    @patch("launcher69.ImageTk.PhotoImage", return_value="mock_icon")
    @patch("launcher69.Image.open")
    @patch("launcher69.filedialog.askdirectory", return_value="fake_dir")
    def test_add_folder_crea_config_correctamente(self, mock_dialog, mock_open, mock_photo):
        mock_open.return_value.resize.return_value = "mock_image"

        test_loader = loader()
        result = test_loader.add_folder("Steam")

        self.assertEqual(result, "fake_dir")

    @patch("launcher69.ImageTk.PhotoImage")  # mockea la creación de la imagen
    @patch("launcher69.Image.open")  # mockea apertura de imagen
    @patch("launcher69.os.walk")
    @patch("launcher69.loader.save_config")
    def test_scan_for_games_agrega_exe_correctamente(self, mock_save, mock_walk, mock_open, mock_photo):
        mock_open.return_value.resize.return_value = "fake_image"
        mock_photo.return_value = "mock_icon"
        l = loader()
        platform = "Steam"
        config[platform] = {"platform_folders": ["test_folder"], "game_list": {}}

        mock_walk.return_value = [
            ("test_folder", [], ["juego.exe", "setup.exe", "otro.bat"])
        ]

        l.scan_for_games(platform)

        # setup.exe debe ignorarse
        self.assertIn("juego", config[platform]["game_list"])
        self.assertIn("otro", config[platform]["game_list"])
        self.assertNotIn("setup", config[platform]["game_list"])
        mock_save.assert_called_once()

class TestGameLauncherController(unittest.TestCase):
    
    @patch("subprocess.Popen")
    def test_launch_game_prevents_multiple_games(self, mock_popen):
        mock_process = MagicMock()
        # Simulamos que el proceso demora 0.5 segundos en terminar
        mock_process.wait.side_effect = lambda: time.sleep(0.5)
        mock_popen.return_value = mock_process

        controller = GameLauncherController()
    
        # Nos aseguramos de que el estado inicial está limpio
        controller.launched = False

        # Lanza el primer juego
        controller.launch_game("Steam", "Game1", "path_to_game.exe")
        time.sleep(0.1)  # Simula que el primer juego sigue corriendo

        with self.assertLogs(level='INFO') as log:
            controller.launch_game("Steam", "Game2", "path_to_another_game.exe")
            time.sleep(0.1)  # Espera a que el segundo intento se procese

        # Verifica que solo se haya iniciado un proceso
        self.assertEqual(mock_popen.call_count, 1)
        self.assertIn("Ya hay un juego en ejecución", log.output[0])

    @patch("subprocess.Popen")
    def test_launch_game_when_no_game_is_running(self, mock_popen):
        # Configuramos el mock para que el juego no se inicie realmente
        mock_process = MagicMock()
        mock_popen.return_value = mock_process

        # Creamos una instancia del controlador
        controller = GameLauncherController()

        # Lanzamos el primer juego
        controller.launch_game("Steam", "Game1", "path_to_game.exe")
        time.sleep(0.1)  # Simulamos un poco de espera

        # Verificamos que el juego fue lanzado
        mock_popen.assert_called_once_with("path_to_game.exe")

        # Ahora lanzamos otro juego y verificamos que también se pueda
        controller.launch_game("Steam", "Game2", "path_to_another_game.exe")
        time.sleep(0.1)

        # Verificamos que el segundo juego también se haya lanzado
        mock_popen.assert_called_with("path_to_another_game.exe")


if __name__ == '__main__':
    unittest.main()