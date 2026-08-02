## Resumen de lo que ya está marcado como "cuidado"

1. `platform_adapters/registry.py` — no tocar, se está eliminando.
2. `helpers/icon_utils.py` vs `helpers/qicon_utils.py` — separados a propósito (Tk vs Qt), comparten `ico_to_png`.
3. `helpers/games_launcher.py :: _save_playtime` vs `_finalize_playtime` — mucha lógica compartida, candidato a extraer un helper común antes de tocarlos de nuevo.
4. `data_access/cloudsync.py` — el pipeline de 4 funciones (`flatten_config` → `merge_backup_data` → `rebuild_nested_config` → `build_cloud_payload_for_upload`) es donde vive toda la lógica de "mezclar sin pisar"; cualquier función nueva de sync probablemente ya tiene un lugar ahí.
5. Tk vs Qt en `interface_files/` — duplicación estructural esperada, no accidental.

## Refactors pendientes / deuda técnica conocida

- [ ] Eliminar `registry.py` una vez migrado todo a `platform_handler.py`.
- [ ] Evaluar si `helpers.py` debería renombrarse a algo como `tk_helpers.py` ya que no es genérico.
- [ ] Cuando la UI Qt reemplace del todo a Tk, deprecar `icon_utils.py`, `tk_*` y sus dependencias.

# A implementar
quitar acc directos y menu de inicio?

# Reparar
self.parent.favorites_panel.refresh() revisar esto dentro de gamedetailspanel

hacer bien lo de agregar steam_id (se ve horrible)
