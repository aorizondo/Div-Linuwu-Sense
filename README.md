# Unofficial Linux Kernel Module for Acer Gaming RGB Keyboard Backlight and Turbo Mode (Acer Predator , Nitro)

---

## Paquetes Debian (este fork)

Este fork anade empaquetado Debian, integracion con `power-profiles-daemon` y
compatibilidad con kernels anteriores a 6.13.

### Instalacion

Descarga los `.deb` del [ultimo release](https://github.com/aorizondo/Div-Linuwu-Sense/releases) e instala:

```bash
sudo apt install ./linuwu-sense-dkms_*.deb ./acer-powersave_*.deb
```

`linuwu-sense-dkms` compila el modulo con DKMS, de modo que se reconstruye solo
en cada actualizacion del kernel. `acer-powersave` es opcional e independiente.

Tras instalar, reinicia (o `sudo modprobe -r acer_wmi && sudo modprobe linuwu_sense`),
y anade tu usuario al grupo para manejar el driver sin `sudo`:

```bash
sudo usermod -aG linuwu_sense $USER
```

Con Secure Boot activo hay que enrolar la clave de DKMS una vez; los detalles
estan en `/usr/share/doc/linuwu-sense-dkms/README.Debian`.

### Que aporta este fork sobre el upstream

| Cambio | Motivo |
|---|---|
| Compatibilidad con la API `platform_profile` < 6.13 | El upstream usa `devm_platform_profile_register()` y `platform_profile_notify(dev)`, que no existen en el kernel 6.12 LTS de Debian 13, asi que no compilaba |
| Quirk del Predator PH315-53 completado | Le faltaban `predator_v4` y `four_zone_kb`: sin ellos no se creaban `predator_sense/` ni `four_zoned_kb/` y hacia falta `enable_all=1` |
| `Makefile` respeta `KERNELRELEASE` | DKMS compila para kernels distintos del que esta corriendo |
| Empaquetado DKMS + CI | `.deb` construidos y publicados automaticamente, con matriz de compilacion sobre trixie, forky y sid |

### Aviso sobre el RGB del teclado: el primer campo no es un "modo"

El README original documenta el primer parametro de `four_zone_mode` como
**Mode (0-7)**, con `0` = *Static*. En al menos algunos firmwares (verificado
en un Predator PH315-53 leyendo su DSDT) **no es eso**: el metodo `WMBH` 0x14
escribe ese byte en `KBLE`, el registro del EC que enciende la
retroiluminacion, y **el valor 0 la apaga por completo**.

```
KBLE = BHLK[0]   <- enciende/apaga  (documentado como "mode")
KBLS = BHLK[1]   <- speed
KBBP = BHLK[2]   <- brightness
KBCS = BHLK[3]   <- color scheme
KBED = BHLK[4]   <- direction
KBCR/KBCG/KBCB   <- red / green / blue
```

Consecuencias practicas:

* `echo "0,0,100,0,255,255,255"` no da un blanco estatico al 100 %: **apaga el
  teclado**, aunque el sysfs siga reportando el valor escrito.
* Las teclas Fn de brillo del teclado **dejan de funcionar** mientras
  `KBLE = 0`, porque el EC solo las atiende con la retroiluminacion habilitada.
  Es facil confundir esto con un driver que no soporta el brillo.
* Para encender, usa un primer campo distinto de cero, por ejemplo:

  ```bash
  echo "2,1,100,1,255,0,0" > .../four_zoned_kb/four_zone_mode
  ```

Este fork corrige ademas un fallo derivado: `set_per_zone_color()` llamaba a
`set_kb_status()` con `0` en ese campo para fijar solo el brillo, de modo que
**cada cambio de color por zona apagaba el teclado**.

### acer-powersave

Aplica los ajustes de energia que corresponden al perfil activo de
`power-profiles-daemon`, **sin fichero de estado**: el perfil de PPD es la
unica fuente de verdad. En KDE, PowerDevil ya traduce conectado/bateria a
perfil, asi que esto sigue al cable y respeta el cambio manual.

```bash
acer-powersave status         # estado actual
acer-powersave medir 60       # consumo mediano en reposo
sudo acer-powersave gpu off   # apagar la dGPU NVIDIA en caliente
sudo acer-powersave gpu on    # y volver a encenderla, sin reiniciar
sudo acer-powersave fan       # curva de ventiladores con histeresis
```

La tasa de refresco la cambia un servicio de sesion aparte, porque
`kscreen-doctor` necesita la sesion Wayland del usuario:

```bash
systemctl --user enable --now acer-powersave-session.service
```

Los perfiles se configuran en `/etc/acer-powersave/profiles.conf`.

No toca el brillo de la pantalla ni la retroiluminacion del teclado.

---
The code base is still in its early stages, as I’ve just started working on developing this kernel module. It's a bit messy at the moment, but I’m hopeful that, with your help, we can collaborate to improve its structure and make it more organized over time.

Inspired by [acer-predator-turbo](https://github.com/JafarAkhondali/acer-predator-turbo-and-rgb-keyboard-linux-module), which has a similar goal, this project was born out of my own challenges. I faced issues detecting the Turbo key and ended up using [acer_wmi](https://github.com/torvalds/linux/blob/master/drivers/platform/x86/acer-wmi.c), but it lacked key features like RGB , custom fan support, battery limiter, and more. As a result, I decided to implement these missing features in my own project.

## 🚀 Installation
To begin, identify your current kernel version:
```bash
uname -r
```

Install the appropriate Linux headers based on your kernel version. This module has been tested with kernel version (6.12,6.13,6.14) zen. 
For Arch Linux:
```bash
sudo pacman -S linux-headers
```
Next, clone the repository and build the module:
```bash
git clone https://github.com/0x7375646F/Linuwu-Sense.git
cd Linuwu-Sense
make install
```
The make command will remove the current acer_wmi module and load the patched version.

To Uninstall:
```bash
make uninstall
```
> **⚠️ Warning!**
> ## Use at your own risk! This driver is independently developed through reverse engineering the official PredatorSense app, without any involvement from Acer. It interacts with low-level WMI methods, which may not be tested across all models.

## 🛠️ Usage
# Example Usage and Configuration

Thermal profiles can be easily switched with a single click! 😎 For battery mode, you can choose between Eco and Balanced, while when plugged into AC, you have the options for Quiet, Balanced, Performance, and Turbo. ⚡💻 Each profile will be different for battery and AC, and the thermal and fan settings will automatically adjust based on your current power source. Customize it to fit your preferences! 🌟

---

For **Predator** laptops, the following path is used: `/sys/module/linuwu_sense/drivers/platform:acer-wmi/acer-wmi/predator_sense`

For **Nitro** laptops, the following path is used: `/sys/module/linuwu_sense/drivers/platform:acer-wmi/acer-wmi/nitro_sense`

predator_sense – This directory includes all the features, excluding the custom boot logo functionality.
four_zoned_kb – If your keyboard is four-zoned, this directory provides support for it. Unfortunately, there is no support for per-key RGB keyboards.
Here is how to interact with the Virtual Filesystems (VFS) mounted in this path:

### **0. Thermal Profiles (Nitro users especially who don't have switch key) 🚀**

Some acer nitro laptops don't come up with the thermal profile switch button in this case we manually need to set it:

To probe the current thermal profile:

`cat /sys/firmware/acpi/platform_profile`

To check the supported thermal profile:

`cat /sys/firmware/acpi/platform_profile_choices`

To switch the platform profile:

`echo balanced | sudo tee /sys/firmware/acpi/platform_profile`

Replace the balanced with the supported profile you have.

#### **1. Backlight Timeout ⏰**

This feature turns off the keyboard RGB after 30 seconds of idle mode.

- **0** – Disabled
- **1** – Enabled

To check the current status, use:

`cat /sys/module/linuwu_sense/drivers/platform:acer-wmi/acer-wmi/predator_sense/backlight_timeout`

To change the state, use:

`echo 1 | sudo tee /sys/module/linuwu_sense/drivers/platform:acer-wmi/acer-wmi/predator_sense/backlight_timeout`

---

#### **2. Battery Calibration 🔋**

This function calibrates your battery to provide a more accurate percentage reading. It involves charging the battery to 100%, draining it to 0%, and recharging it back to 100%. **Do not unplug the laptop from AC power during calibration.**

- **1** – Start calibration
- **0** – Stop calibration

To check the current status:

`cat /sys/module/linuwu_sense/drivers/platform:acer-wmi/acer-wmi/predator_sense/battery_calibration`

To change the state:

`echo 1 | sudo tee /sys/module/linuwu_sense/drivers/platform:acer-wmi/acer-wmi/predator_sense/battery_calibration`

---

#### **3. Battery Limiter ⚡**

Limits battery charging to 80%, preserving battery health for laptops primarily used while plugged into AC power.

- **1** – Enabled
- **0** – Disabled

To check the current status:

`cat /sys/module/linuwu_sense/drivers/platform:acer-wmi/acer-wmi/predator_sense/battery_limiter`

To change the state:

`echo 1 | sudo tee /sys/module/linuwu_sense/drivers/platform:acer-wmi/acer-wmi/predator_sense/battery_limiter`

---

#### **4. Boot Animation Sound 🎶**

Enables or disables custom boot animation and sound.

- **1** – Enabled
- **0** – Disabled

To check the current status:

`cat /sys/module/linuwu_sense/drivers/platform:acer-wmi/acer-wmi/predator_sense/boot_animation_sound`

To change the state:

`echo 0 | sudo tee /sys/module/linuwu_sense/drivers/platform:acer-wmi/acer-wmi/predator_sense/boot_animation_sound`

---

#### **5. Fan Speed  🌬️**

Controls the CPU and GPU fan speeds.

- **0** – Auto
- **1** – Minimum fan speed (not recommended)
- **100** – Maximum fan speed
- Other values like **50, 55, 70** can be set according to your preference.

Example (set CPU to 50 and GPU to 70):

`echo 50,70 | sudo tee /sys/module/linuwu_sense/drivers/platform:acer-wmi/acer-wmi/predator_sense/fan_speed`

---

#### **6. LCD Override 🖥️**

Reduces LCD latency and minimizes ghosting.

- **1** – Enabled
- **0** – Disabled

To check the current status:

`cat /sys/module/linuwu_sense/drivers/platform:acer-wmi/acer-wmi/predator_sense/lcd_override`

To change the state:

`echo 1 | sudo tee /sys/module/linuwu_sense/drivers/platform:acer-wmi/acer-wmi/predator_sense/lcd_override`

---

#### **7. USB Charging ⚡**

Allows the USB charging port to provide power even when the laptop is off.

- **0** – Disabled
- **10** – Provides power until battery reaches 10%
- **20** – Provides power until battery reaches 20%
- **30** – Provides power until battery reaches 30%

To check the current status:

`cat /sys/module/linuwu_sense/drivers/platform:acer-wmi/acer-wmi/predator_sense/usb_charging`

To change the state:

`echo 20 | sudo tee /sys/module/linuwu_sense/drivers/platform:acer-wmi/acer-wmi/predator_sense/usb_charging`

---
## 💻 Keyboard Configuration 
### **Directory: `four_zoned_kb`**

The `four_zoned_kb` directory contains two Virtual File Systems (VFS) that control the RGB backlight behavior of the four-zone keyboard:

1. **`four_zone_mode`**
2. **`per_zone_mode`**

#### **1. Per-Zone Mode (`per_zone_mode`) 🎨**

This mode allows you to set a specific RGB color for each of the four keyboard zones individually. Each zone is represented by an RGB value in hexadecimal format (e.g., `4287f5` where `42` is Red, `87` is Green, and `f5` is Blue).

- **Parameters:**
    
    - The `per_zone_mode` file accepts four parameters, one for each zone, separated by commas.
    - The `per_zone_mode` also accepts brightness value.
    - Each parameter represents the RGB value for a specific zone in the format `RRGGBB`.
- **Example:**

To set all four zones to the same color (`4287f5`) and brightness to full:

`echo 4287f5,4287f5,4287f5,4287f5,100 | sudo tee /sys/module/linuwu_sense/drivers/platform:acer-wmi/acer-wmi/four_zoned_kb/per_zone_mode`

To set each zone with unique colors:

`echo 4287f5,ff5733,33ff57,ff33a6,100 | sudo tee /sys/module/linuwu_sense/drivers/platform:acer-wmi/acer-wmi/four_zoned_kb/per_zone_mode`

When reading (`cat`) the `per_zone_mode` file, the current color values for each zone are displayed in the format:

`4287f5,4287f5,4287f5,4287f5,100`

This indicates the current RGB color for each of the four zones.

### **Four-Zone Mode (`four_zone_mode`) ✨**

The `four_zone_mode` controls advanced RGB effects for your keyboard, requiring seven parameters:

- **Parameters:**
    
    - **Mode (0-7):** Lighting effect type (e.g., static, breathing, wave).
    - **Speed (0-9):** Speed of the effect (if applicable).
    - **Brightness (0-100):** Intensity of the lighting effect.
    - **Direction (1-2):** Direction of the effect (1 = right to left, 2 = left to right).
    - **Red (0-255), Green (0-255), Blue (0-255):** RGB color values.
- **Modes:**
    
    - **0:** Static Mode – Fixed color, no animation.
    - **1:** Breathing Mode – Color fades in and out.
    - **2:** Neon Mode – Neon glow effect, fixed color (black), direction ignored.
    - **3:** Wave Mode – Wave-like effect, color transitions across the keyboard.
    - **4:** Shifting Mode – Shifting light effect, full control over speed, direction, and color.
    - **5:** Zoom Mode – Zoom effect, direction ignored.
    - **6:** Meteor Mode – Meteor-like effect, direction ignored.
    - **7:** Twinkling Mode – Twinkling light effect, direction ignored.
- **Example Command:**
    
    Set to **Neon Mode** with speed 1, full brightness, and top-to-bottom direction:
    
    `echo 3,1,100,2,0,0,0 | sudo tee /sys/module/linuwu_sense/drivers/platform:acer-wmi/acer-wmi/four_zoned_kb/four_zone_mode`
    
    **Explanation:**
    
    - `3`: Neon Mode
    - `1`: Speed (1)
    - `100`: Full brightness
    - `2`: Direction (top to bottom)
    - `0`: Red (black for Neon)
    - `0`: Green (black for Neon)
    - `0`: Blue (black for Neon)
 
The thermal and fan profiles will be saved and loaded on each reboot, ensuring that the settings remain persistent across restarts.
## GUI:
- [Div Acer Manager Max By PXDiv](https://github.com/PXDiv/Div-Acer-Manager-Max)

## License
GNU General Public License v3

