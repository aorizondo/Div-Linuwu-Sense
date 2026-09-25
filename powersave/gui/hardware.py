# -*- coding: utf-8 -*-
"""
Acceso al hardware para la interfaz de Acer Sense.

Todo lo que toca sysfs vive aqui, de modo que la interfaz no sepa de rutas ni
de formatos del driver. Las escrituras que necesitan privilegios pasan por
pkexec; las de los atributos del driver no, porque el paquete cede esos
ficheros al grupo linuwu_sense.
"""

import glob
import os
import re
import subprocess
from pathlib import Path

BASE = Path("/sys/module/linuwu_sense/drivers/platform:acer-wmi/acer-wmi")
PREDATOR = BASE / "predator_sense"
NITRO = BASE / "nitro_sense"
KB = BASE / "four_zoned_kb"
BAT = Path("/sys/class/power_supply/BAT1")
PSTATE = Path("/sys/devices/system/cpu/intel_pstate")
NVIDIA_PORT = "0000:00:01.0"
NVIDIA_GPU = "0000:01:00.0"


# ---------------------------------------------------------------------------
#  utilidades
# ---------------------------------------------------------------------------

def _leer(path, defecto=""):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return defecto


def _motivo_sin_permiso(path):
    """Explica POR QUE no se puede escribir, que son dos casos distintos.

    Decir siempre "anadete al grupo" despista cuando el usuario ya esta en el,
    que es el caso mas habitual: los atributos de sysfs no sobreviven a una
    recarga del modulo y el kernel los recrea con root:root, perdiendo el
    grupo. Pasa al actualizar por DKMS o con un modprobe a mano."""
    try:
        import grp
        en_el_grupo = "linuwu_sense" in (
            grp.getgrgid(g).gr_name for g in os.getgroups())
    except (OSError, KeyError, ImportError):
        en_el_grupo = False

    if not en_el_grupo:
        return ("sin permiso: tu usuario no esta en el grupo linuwu_sense.\n\n"
                "  sudo usermod -aG linuwu_sense $USER\n\n"
                "Hay que volver a iniciar sesion para que surta efecto.")

    try:
        propietario = grp.getgrgid(Path(path).stat().st_gid).gr_name
    except (OSError, KeyError):
        propietario = "?"
    return (f"sin permiso, aunque ya estas en el grupo linuwu_sense.\n\n"
            f"El atributo pertenece ahora al grupo '{propietario}': los "
            f"permisos se pierden cuando se recarga el modulo, porque el "
            f"kernel recrea el sysfs con root:root.\n\n"
            f"Se arregla sin reiniciar la sesion:\n"
            f"  sudo systemd-tmpfiles --create "
            f"/usr/lib/tmpfiles.d/linuwu-sense.conf")


def _escribir(path, valor):
    """Devuelve (ok, mensaje). No lanza: la interfaz muestra el motivo."""
    try:
        Path(path).write_text(str(valor))
        return True, ""
    except PermissionError:
        return False, _motivo_sin_permiso(path)
    except OSError as e:
        return False, str(e)


def panel():
    """Directorio del modelo: los Predator y los Nitro no exponen lo mismo."""
    if PREDATOR.exists():
        return PREDATOR
    if NITRO.exists():
        return NITRO
    return None


def driver_presente():
    return BASE.exists()


# ---------------------------------------------------------------------------
#  sensores
# ---------------------------------------------------------------------------

def _hwmon(nombre):
    for d in glob.glob("/sys/class/hwmon/hwmon*"):
        if _leer(Path(d) / "name") == nombre:
            return Path(d)
    return None


def temperaturas():
    """Devuelve dict nombre -> grados. El hwmon 'acer' lo publica el driver."""
    out = {}
    core = _hwmon("coretemp")
    if core:
        v = _leer(core / "temp1_input")
        if v:
            out["CPU"] = int(v) / 1000

    acer = _hwmon("acer")
    if acer:
        # temp1/temp2 del EC: en los Predator suelen ser sistema y GPU.
        # El EC devuelve 0 para la GPU mientras esta suspendida en D3cold: no
        # es un fallo de lectura, es que no hay nada encendido que medir.
        for idx, etiqueta in ((1, "Sistema"), (2, "GPU")):
            v = _leer(acer / f"temp{idx}_input")
            if v and int(v) > 0:
                out[etiqueta] = int(v) / 1000

    # El equipo puede llevar NVMe y disco mecanico. El hwmon "nvme" es el
    # SSD; el disco duro solo publica temperatura si esta cargado drivetemp.
    nvme = _hwmon("nvme")
    if nvme:
        v = _leer(nvme / "temp1_input")   # temp1 = Composite
        if v:
            out["NVMe"] = int(v) / 1000

    disco = _hwmon("drivetemp")
    if disco:
        v = _leer(disco / "temp1_input")
        if v:
            out["HDD"] = int(v) / 1000
    return out


def ventiladores_rpm():
    acer = _hwmon("acer")
    if not acer:
        return []
    rpm = []
    for f in sorted(glob.glob(str(acer / "fan*_input"))):
        v = _leer(f)
        if v:
            rpm.append(int(v))
    return rpm


def consumo_mw():
    """Consumo del sistema en mW, o None si no es medible.

    No hay power_now en este equipo, asi que se calcula de current_now por
    voltage_now. Pero eso SOLO vale descargando: mientras carga, current_now es
    la corriente que ENTRA en la bateria, y darla por consumo es enganoso --
    llegaba a mostrar 21 W cuando el sistema consumia la mitad."""
    if _leer(BAT / "status") != "Discharging":
        return None
    i, v = _leer(BAT / "current_now"), _leer(BAT / "voltage_now")
    if not i or not v:
        return None
    return (int(i) // 1000) * (int(v) // 1000) // 1000


def bateria():
    return {
        "capacidad": _leer(BAT / "capacity", "?"),
        "estado": _leer(BAT / "status", "?"),
        "consumo_mw": consumo_mw(),
    }


# ---------------------------------------------------------------------------
#  ventiladores
# ---------------------------------------------------------------------------

def fan_get():
    """Devuelve (cpu, gpu) en por ciento. 0 significa curva automatica del EC."""
    p = panel()
    if not p:
        return None
    v = _leer(p / "fan_speed")
    m = re.match(r"^(\d+),(\d+)", v)
    return (int(m.group(1)), int(m.group(2))) if m else None


def fan_set(cpu, gpu):
    p = panel()
    if not p:
        return False, "el driver no expone fan_speed"
    return _escribir(p / "fan_speed", f"{cpu},{gpu}")


def fan_auto():
    return fan_set(0, 0)


# ---------------------------------------------------------------------------
#  teclado RGB
# ---------------------------------------------------------------------------
#  Lo que apaga el teclado es la VELOCIDAD 0, no el efecto 0.
#
#  Durante mucho tiempo se creyo lo contrario, porque el driver forzaba
#  "speed = 0" justo en los dos efectos que no se veian (0 estatico y 1
#  respiracion) y las dos causas quedaban superpuestas. Al dejar pasar la
#  velocidad, el efecto estatico aparecio sin mas.
#
#  Pero la velocidad 0 NO siempre apaga: congela el efecto. En Respiracion da
#  un color fijo -- el unico color estatico que tiene este firmware-- mientras
#  que en Desplazamiento deja el teclado negro. Depende del efecto, asi que se
#  deja elegir el 0 y se avisa, en vez de prohibirlo.
#
#  Para apagar a proposito se usa el brillo, que funciona en todos.

# (nombre, valor, soportado_por_el_firmware)
#
# Verificado efecto por efecto en un PH315-53, con brillo 100 y velocidad
# distinta de cero para que la velocidad no enturbie el resultado:
#
#   0  es el efecto ESTATICO, no el apagado. Parecia apagar porque sin zonas
#      activas el teclado no tiene nada que pintar; con ellas activas muestra
#      un color fijo por zona. Se aplica escribiendo per_zone_mode, que hace
#      la secuencia entera (activar zonas, colores, estatico).
#   6 y 7 llegan con parametros validos y no producen luz. Limitacion del EC
#      de este modelo, no del driver.
#
# El 1 estuvo mucho tiempo en la lista de "no funciona" por un motivo
# distinto: el driver le forzaba velocidad 0, que apaga. Arreglado eso, va.
EFECTOS = [
    ("Estático", 0, True),
    ("Respiración", 1, True),
    ("Neón", 2, True),
    ("Onda", 3, True),
    ("Desplazamiento", 4, True),
    ("Zoom", 5, True),
    ("Meteoro", 6, False),
    ("Parpadeo", 7, False),
]

# El rango completo que acepta el driver. El 0 es un valor util, no un error:
# congela la animacion.
VELOCIDAD_MIN, VELOCIDAD_MAX = 0, 9


def kb_disponible():
    return KB.exists()


def kb_get():
    v = _leer(KB / "four_zone_mode")
    partes = v.split(",")
    if len(partes) < 7:
        return None
    try:
        efecto, vel, brillo, direccion, r, g, b = (int(x) for x in partes[:7])
    except ValueError:
        return None
    return {"efecto": efecto, "velocidad": vel, "brillo": brillo,
            "direccion": direccion, "rgb": (r, g, b)}


def kb_set(efecto, velocidad, brillo, direccion, rgb):
    r, g, b = rgb
    velocidad = max(VELOCIDAD_MIN, min(VELOCIDAD_MAX, velocidad))
    return _escribir(KB / "four_zone_mode",
                     f"{efecto},{velocidad},{brillo},{direccion},{r},{g},{b}")


def kb_apagar():
    """Apaga bajando el brillo, no con el efecto 0.

    Las dos vias apagan, pero no dan lo mismo: con KBLE a 0 el EC deja de
    atender las teclas Fn de brillo, y el teclado se queda muerto hasta que
    algo le escriba un efecto valido. Bajando el brillo se apaga la luz y las
    teclas siguen respondiendo."""
    actual = kb_get()
    if actual is None or not actual["efecto"]:
        return kb_set(2, 1, 0, 1, (0, 0, 0))
    return kb_set(actual["efecto"], actual["velocidad"], 0,
                  actual["direccion"], actual["rgb"])


def kb_zonas_get():
    """Devuelve ([c1,c2,c3,c4], brillo) con los colores en RRGGBB."""
    v = _leer(KB / "per_zone_mode")
    partes = v.split(",")
    if len(partes) < 5:
        return None
    return partes[:4], int(partes[4]) if partes[4].isdigit() else 0


def guardar_curva(temp_minima, curva):
    """Escribe la curva en /etc/acer-powersave/profiles.conf.

    Hace falta root, asi que se delega en la propia orden acer-powersave, que
    es la que declara la accion de polkit."""
    try:
        r = subprocess.run(
            ["pkexec", "/usr/bin/acer-powersave", "guardar-curva",
             str(temp_minima), curva],
            capture_output=True, text=True, timeout=60)
        return r.returncode == 0, (r.stderr or r.stdout).strip()
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e)


def tope_carga_get():
    """Tope de carga en por ciento, o None si el driver no lo publica."""
    try:
        return int(_leer(BAT / "charge_control_end_threshold"))
    except ValueError:
        return None


def tope_carga_set(porcentaje):
    """Fija el tope de carga.

    El atributo lo cede el paquete al grupo linuwu_sense igual que el resto,
    asi que en el caso normal se escribe directamente y el cambio es
    inmediato. Solo si eso falla -permisos perdidos tras recargar el modulo,
    por ejemplo- se recurre a pkexec, que ademas lo deja guardado.

    De la persistencia se encarga el servicio, que vigila el atributo y lo
    anota en su configuracion cuando cambia: el modulo no puede recordar un
    valor intermedio entre arranques."""
    ruta = BAT / "charge_control_end_threshold"
    if not ruta.exists():
        return False, ("El módulo no publica el tope de carga. "
                       "¿Está cargado linuwu_sense?")

    ok, err = _escribir(ruta, str(porcentaje))
    if ok:
        return True, ""

    try:
        r = subprocess.run(
            ["pkexec", "/usr/bin/acer-powersave", "charge-limit",
             str(porcentaje)],
            capture_output=True, text=True, timeout=60)
        if r.returncode == 0:
            return True, ""
        return False, (r.stderr or r.stdout).strip() or err
    except (OSError, subprocess.SubprocessError) as e:
        return False, f"{err}\n{e}"


def kb_zonas_set(colores, brillo):
    return _escribir(KB / "per_zone_mode", ",".join(colores) + f",{brillo}")


# ---------------------------------------------------------------------------
#  atributos varios del panel
# ---------------------------------------------------------------------------

def attr_get(nombre):
    p = panel()
    return _leer(p / nombre) if p else ""


def attr_set(nombre, valor):
    p = panel()
    if not p:
        return False, "el driver no esta cargado"
    return _escribir(p / nombre, valor)


# ---------------------------------------------------------------------------
#  energia
# ---------------------------------------------------------------------------

def perfil_actual():
    try:
        r = subprocess.run(["powerprofilesctl", "get"], capture_output=True,
                           text=True, timeout=5)
        return r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def perfiles_disponibles():
    try:
        r = subprocess.run(["powerprofilesctl", "list"], capture_output=True,
                           text=True, timeout=5)
        return re.findall(r"^[* ] (\S+):", r.stdout, re.M)
    except (OSError, subprocess.SubprocessError):
        return []


def perfil_set(nombre):
    try:
        r = subprocess.run(["powerprofilesctl", "set", nombre],
                           capture_output=True, text=True, timeout=10)
        return r.returncode == 0, r.stderr.strip()
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e)


def cpu_info():
    gov = _leer("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor")
    epp = _leer("/sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference")
    minf = _leer("/sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq")
    maxf = _leer("/sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq")
    turbo = _leer(PSTATE / "no_turbo")
    modo = _leer(PSTATE / "status")
    actual = ""
    try:
        with open("/proc/cpuinfo") as f:
            for linea in f:
                if "MHz" in linea:
                    actual = f"{float(linea.split(':')[1]):.0f}"
                    break
    except OSError:
        pass
    return {"governor": gov, "epp": epp, "min": minf, "max": maxf,
            "turbo": "off" if turbo == "1" else "on", "modo": modo,
            "mhz": actual}


def refresco_actual():
    try:
        r = subprocess.run(["kscreen-doctor", "-o"], capture_output=True,
                           text=True, timeout=10)
        limpio = re.sub(r"\x1b\[[0-9;]*m", "", r.stdout)
        m = re.search(r"(\d+x\d+)@(\d+)\*", limpio)
        return (m.group(1), int(m.group(2))) if m else None
    except (OSError, subprocess.SubprocessError):
        return None


def refrescos_disponibles():
    try:
        r = subprocess.run(["kscreen-doctor", "-o"], capture_output=True,
                           text=True, timeout=10)
        limpio = re.sub(r"\x1b\[[0-9;]*m", "", r.stdout)
        res = re.findall(r"(\d+x\d+)@(\d+)", limpio)
        actual = refresco_actual()
        if not actual:
            return []
        return sorted({int(hz) for r_, hz in res if r_ == actual[0]}, reverse=True)
    except (OSError, subprocess.SubprocessError):
        return []


def refresco_set(hz):
    actual = refresco_actual()
    if not actual:
        return False, "no se pudo leer el modo actual"
    try:
        r = subprocess.run(
            ["kscreen-doctor", f"output.eDP-1.mode.{actual[0]}@{hz}"],
            capture_output=True, text=True, timeout=15)
        return r.returncode == 0, r.stderr.strip()
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e)


# ---------------------------------------------------------------------------
#  GPU dedicada
# ---------------------------------------------------------------------------

def gpu_estado():
    """Solo sysfs: lspci y nvidia-smi DESPIERTAN el puente y falsean la lectura."""
    if Path(f"/sys/bus/pci/devices/{NVIDIA_GPU}").exists():
        return "encendida"
    estado = _leer(f"/sys/bus/pci/devices/{NVIDIA_PORT}/power_state", "?")
    return f"apagada ({estado})"


def gpu_set(encender):
    """Requiere privilegios: se delega en la orden acer-powersave."""
    try:
        r = subprocess.run(
            ["pkexec", "/usr/bin/acer-powersave", "gpu",
             "on" if encender else "off"],
            capture_output=True, text=True, timeout=60)
        return r.returncode == 0, (r.stderr or r.stdout).strip()
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e)
