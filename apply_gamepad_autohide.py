#!/usr/bin/env python3
"""
Oculta los controles táctiles cuando hay un mando conectado y los vuelve a
mostrar cuando se desconecta.

Uso (desde la raíz del repositorio):

    python apply_gamepad_autohide.py

Qué hace:
  1. Crea  android/app/src/main/java/org/bo2port/diagnostic/GamepadAutoHide.java
  2. Añade 5 líneas a GameActivity.java para usarla.

Es seguro ejecutarlo varias veces: si ya está aplicado, no hace nada.
Para deshacerlo:  git checkout android/app/src/main/java/org/bo2port/diagnostic/GameActivity.java
                  y borra GamepadAutoHide.java
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent
PKG = ROOT / "android/app/src/main/java/org/bo2port/diagnostic"
ACTIVITY = PKG / "GameActivity.java"
HELPER = PKG / "GamepadAutoHide.java"

HELPER_SOURCE = r'''// SPDX-License-Identifier: GPL-3.0-only
package org.bo2port.diagnostic;

import android.content.Context;
import android.hardware.input.InputManager;
import android.os.Handler;
import android.os.Looper;
import android.view.InputDevice;
import android.view.View;

/**
 * Oculta los controles táctiles mientras haya un mando (gamepad/joystick) conectado
 * y los muestra otra vez cuando se desconecta. El mando en sí lo gestiona SDL.
 */
final class GamepadAutoHide implements InputManager.InputDeviceListener {
    private final InputManager manager;
    private final TouchControlsView controls;
    private final GameMenuLayout menu;
    private boolean started;

    GamepadAutoHide(Context context, TouchControlsView controls, GameMenuLayout menu) {
        this.manager = (InputManager) context.getSystemService(Context.INPUT_SERVICE);
        this.controls = controls;
        this.menu = menu;
    }

    /** Empieza a vigilar los mandos y aplica el estado actual. */
    void start() {
        if (started || manager == null) return;
        started = true;
        manager.registerInputDeviceListener(this, new Handler(Looper.getMainLooper()));
        refresh();
    }

    void stop() {
        if (!started) return;
        started = false;
        manager.unregisterInputDeviceListener(this);
    }

    /** Vuelve a comprobar si hay mando y ajusta la visibilidad de los controles. */
    void refresh() { apply(-1); }

    private void apply(int removedId) {
        // El editor de controles gestiona su propia visibilidad; se reaplica al cerrarlo.
        if (menu.isEditing()) return;
        int wanted = hasGamepad(removedId) ? View.INVISIBLE : View.VISIBLE;
        if (controls.getVisibility() == wanted) return;
        controls.releaseAll(); // suelta cualquier dedo apoyado para no dejar botones "pegados"
        controls.setVisibility(wanted);
    }

    private static boolean hasGamepad(int ignoredId) {
        for (int id : InputDevice.getDeviceIds()) {
            if (id == ignoredId) continue;
            InputDevice device = InputDevice.getDevice(id);
            if (device == null || device.isVirtual()) continue;
            int sources = device.getSources();
            if ((sources & InputDevice.SOURCE_GAMEPAD) == InputDevice.SOURCE_GAMEPAD
                    || (sources & InputDevice.SOURCE_JOYSTICK) == InputDevice.SOURCE_JOYSTICK) return true;
        }
        return false;
    }

    @Override public void onInputDeviceAdded(int deviceId) { apply(-1); }
    @Override public void onInputDeviceRemoved(int deviceId) { apply(deviceId); }
    @Override public void onInputDeviceChanged(int deviceId) { apply(-1); }
}
'''

# (ancla que debe existir exactamente una vez, texto que la sustituye)
EDITS = [
    (
        "private ControlLayoutEditor controlEditor;",
        "private ControlLayoutEditor controlEditor;\n    private GamepadAutoHide gamepadHide;",
    ),
    (
        "mLayout.addView(gameMenu,new RelativeLayout.LayoutParams(-1,-1));gameMenu.requestApplyInsets();",
        "mLayout.addView(gameMenu,new RelativeLayout.LayoutParams(-1,-1));gameMenu.requestApplyInsets();\n"
        "        gamepadHide=new GamepadAutoHide(this,controls,gameMenu);gamepadHide.start();",
    ),
    (
        "public void close(){gameMenu.hideEditor();controlEditor=null;}",
        "public void close(){gameMenu.hideEditor();controlEditor=null;if(gamepadHide!=null)gamepadHide.refresh();}",
    ),
    (
        "@Override protected void onResume(){super.onResume();resourceForeground=true;profileForeground(true);}",
        "@Override protected void onResume(){super.onResume();resourceForeground=true;profileForeground(true);"
        "if(gamepadHide!=null)gamepadHide.refresh();}",
    ),
    (
        "if(resourceMonitor!=null)resourceMonitor.close();",
        "if(resourceMonitor!=null)resourceMonitor.close();\n        if(gamepadHide!=null)gamepadHide.stop();",
    ),
]


def fail(message):
    print("ERROR: " + message, file=sys.stderr)
    sys.exit(1)


def main():
    if not ACTIVITY.is_file():
        fail("no encuentro %s. Ejecuta el script desde la raíz del repositorio." % ACTIVITY)

    text = ACTIVITY.read_text(encoding="utf-8")

    if "GamepadAutoHide" in text:
        print("GameActivity.java ya tiene el parche; no se toca.")
    else:
        for anchor, _ in EDITS:
            count = text.count(anchor)
            if count != 1:
                fail("esperaba 1 coincidencia de:\n  %s\npero hay %d. "
                     "El código de GameActivity.java cambió; hay que ajustar el script." % (anchor, count))
        for anchor, replacement in EDITS:
            text = text.replace(anchor, replacement)
        ACTIVITY.write_text(text, encoding="utf-8")
        print("Parcheado: %s" % ACTIVITY.relative_to(ROOT))

    HELPER.write_text(HELPER_SOURCE, encoding="utf-8")
    print("Escrito:   %s" % HELPER.relative_to(ROOT))
    print("Listo. Compila el APK como siempre.")


if __name__ == "__main__":
    main()
