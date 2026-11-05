import cv2
import mss
import numpy as np
import time
import threading
import ctypes
import random
import tkinter as tk
from tkinter import font as tkfont

UMBRAL_RAPIDO = 0.62
UMBRAL_FINAL = 0.70
ENFRIAMIENTO = 3         
POS_X, POS_Y = 30, 250    
ANCHO, ALTO = 290, 120  
MONITOR = 1              
PANEL_OPACO = True        
MOSTRAR_AYUDA = True      
MS_POR_CUADRO = 16        


ZONA = None              
PAUSA_ESCANEO = 0.03      
GUARDAR_CAPTURAS = False  

TECLA_MENOS, TECLA_MAS, TECLA_RESET, TECLA_PAUSA, TECLA_SALIR = 0x76, 0x77, 0x78, 0x79, 0x7B


AMARILLO = "#fcee0a"
CIAN = "#00f0ff"
ROJO = "#ff003c"
FONDO_PANEL = "#0b0b09"
LINEA_SCAN = "#14140a"
GRIS = "#9a9432"
OSCURO = "#55511a"
HAZ = "#3d3a0c"

GLITCH_CHARS = "@#%*$!?/\\<>[]{}0123456789ABCDEFX"

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass
ref = cv2.imread("referencia.png")
if ref is None:
    raise SystemExit("No encuentro referencia.png en esta carpeta")
molde = cv2.cvtColor(ref, cv2.COLOR_BGR2GRAY)
alto_m, ancho_m = molde.shape

nucleo = ((ref[:, :, 2] > 150) & (ref[:, :, 0] > 180)).astype(np.uint8)
mascara = (cv2.dilate(nucleo, np.ones((3, 3), np.uint8)) * 255).astype(np.uint8)
if int((mascara > 0).sum()) < 50:
    raise SystemExit("referencia.png no tiene suficiente texto claro. Usa la que te di.")

contador = 0
ultimo = 0.0
pausado = False
corriendo = True
s1 = 0.0
s2 = 0.0
pico = 0.0
t_pico = 0.0
pulso_cofre = 0.0  


def guardar():
    with open("contador.txt", "w") as f:
        f.write(str(contador))

def analizar(frame_bgra):
    gris = cv2.cvtColor(frame_bgra, cv2.COLOR_BGRA2GRAY)
    if gris.shape[0] < alto_m or gris.shape[1] < ancho_m:
        return 0.0, 0.0, 0, 0

    r1 = cv2.matchTemplate(gris, molde, cv2.TM_CCOEFF_NORMED)
    _, p1, _, (x, y) = cv2.minMaxLoc(r1)
    if p1 < UMBRAL_RAPIDO:
        return p1, 0.0, x, y

    x0, y0 = max(0, x - 6), max(0, y - 6)
    ventana = gris[y0:y0 + alto_m + 12, x0:x0 + ancho_m + 12]
    if ventana.shape[0] < alto_m or ventana.shape[1] < ancho_m:
        return p1, 0.0, x, y
    r2 = cv2.matchTemplate(ventana, molde, cv2.TM_CCOEFF_NORMED, mask=mascara)
    p2 = float(np.nan_to_num(r2, nan=0, posinf=0, neginf=0).max())
    return p1, p2, x, y


def vigilar():
    global contador, ultimo, s1, s2, pico, t_pico, pulso_cofre
    MSS = getattr(mss, "MSS", None) or mss.mss
    with MSS() as sct:
        indice = MONITOR if MONITOR < len(sct.monitors) else 1
        pantalla = sct.monitors[indice]  
        if ZONA:
            zx, zy = ZONA["left"], ZONA["top"]
            region = {"left": pantalla["left"] + zx, "top": pantalla["top"] + zy,
                      "width": ZONA["width"], "height": ZONA["height"]}
        else:
            zx, zy = 0, 0
            region = pantalla

        while corriendo:
            inicio = time.time()
            if not pausado:
                try:
                    frame = np.array(sct.grab(region))
                    ax0, ay0 = max(POS_X - zx, 0), max(POS_Y - zy, 0)
                    ax1 = min(POS_X + ANCHO - zx, frame.shape[1])
                    ay1 = min(POS_Y + ALTO - zy, frame.shape[0])
                    if ax1 > ax0 and ay1 > ay0:
                        frame[ay0:ay1, ax0:ax1] = 0

                    s1, s2, x, y = analizar(frame)

                    ahora = time.time()
                    if s1 > pico or ahora - t_pico > 4:
                        pico = s1
                        t_pico = ahora

                    if s2 > UMBRAL_FINAL and ahora - ultimo > ENFRIAMIENTO:
                        contador += 1
                        ultimo = ahora
                        pulso_cofre = ahora
                        guardar()
                        print(f"Cofres: {contador} (rapido {s1:.2f}, final {s2:.2f})")
                        if not ZONA:
                            w = min(ancho_m + 300, pantalla["width"])
                            h = min(alto_m + 200, pantalla["height"])
                            sug = {"left": max(0, min(x - 150, pantalla["width"] - w)),
                                   "top": max(0, min(y - 100, pantalla["height"] - h)),
                                   "width": w, "height": h}
                            print(f"  Zona sugerida para ir mas rapido: ZONA = {sug}")
                        if GUARDAR_CAPTURAS:
                            foto = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                            cv2.rectangle(foto, (x, y), (x + ancho_m, y + alto_m), (0, 255, 0), 3)
                            cv2.imwrite(f"conteo_{contador}.png", foto)
                except Exception as e:
                    print("Error en el vigilante:", e)
                    time.sleep(1)
            time.sleep(max(0.0, PAUSA_ESCANEO - (time.time() - inicio)))

root = tk.Tk()
root.overrideredirect(True)
root.attributes("-topmost", True)
root.configure(bg="black")
root.attributes("-transparentcolor", "black")
root.geometry(f"{ANCHO}x{ALTO}+{POS_X}+{POS_Y}")


def elegir_fuente(candidatas, por_defecto):
    disponibles = set(tkfont.families())
    for nombre in candidatas:
        if nombre in disponibles:
            return nombre
    return por_defecto


FUENTE_TAG = elegir_fuente(
    ["Bahnschrift SemiBold Condensed", "Bahnschrift", "Segoe UI Semibold"], "Consolas")


def embrollar(texto, prob):
    """Cambia caracteres al azar (efecto de datos corruptos)."""
    prob = min(prob, 0.9)
    return "".join(random.choice(GLITCH_CHARS) if random.random() < prob else c for c in texto)


def descifrar(texto, progreso):
    """Revela el texto de izquierda a derecha, con basura en lo que falta."""
    n = int(len(texto) * min(1.0, max(0.0, progreso)))
    resto = "".join(" " if c == " " else random.choice(GLITCH_CHARS) for c in texto[n:])
    return texto[:n] + resto


class HUD:
    CORTE = 14 

    def __init__(self, raiz):
        self.cv = tk.Canvas(raiz, width=ANCHO, height=ALTO, bg="black",
                            highlightthickness=0, bd=0)
        self.cv.pack()

        self.f_tag = (FUENTE_TAG, -12, "bold")
        self.f_small = ("Consolas", -12, "bold")
        self.f_num = ("Consolas", -38, "bold")
        self.f_mini = ("Consolas", -10)

        c = self.CORTE
        self.pts = [(c, 1), (ANCHO - 1, 1), (ANCHO - 1, ALTO - c),
                    (ANCHO - c, ALTO - 1), (1, ALTO - 1), (1, c)]
        self.fondo_corte = FONDO_PANEL if PANEL_OPACO else "black"

        ahora = time.time()
        self.t_inicio = ahora
        self.t_evento = -999.0
        self.pulso_visto = pulso_cofre
        self.rafaga = 0
        self.intensidad = 1
        self.tipo = "datos"
        self.sig_rafaga = ahora + 3.0

        self.dibujar_base()

    def rango_x(self, y):
        """Ancho útil de una línea horizontal respetando las esquinas cortadas."""
        c = self.CORTE
        x0 = 3 if y >= c else c - y + 2
        x1 = ANCHO - 3 if y <= ALTO - c else ANCHO + ALTO - c - y - 3
        return x0, x1

    def dibujar_base(self):
        cv = self.cv
        if PANEL_OPACO:
            cv.create_polygon(self.pts, fill=FONDO_PANEL, outline="", tags="base")
            for y in range(3, ALTO - 2, 4):         
                x0, x1 = self.rango_x(y)
                cv.create_line(x0, y, x1, y, fill=LINEA_SCAN, tags="base")
        cv.create_line(12, 27, ANCHO - 16, 27, fill=OSCURO, tags="base")

    def txt(self, x, y, s, color, fuente, ancla="nw"):
        self.cv.create_text(x, y, text=s, fill=color, font=fuente, anchor=ancla, tags="dyn")

    def cuadro(self):
        ahora = time.time()
        cv = self.cv
        cv.delete("dyn")
        if pulso_cofre != self.pulso_visto:
            self.pulso_visto = pulso_cofre
            self.t_evento = ahora
            self.rafaga = 18
            self.intensidad = 3
            self.tipo = "datos"
        if self.rafaga <= 0 and ahora >= self.sig_rafaga:
            self.rafaga = random.randint(4, 10)
            self.intensidad = random.choice([1, 1, 2, 3])
            self.tipo = random.choice(["datos", "datos", "brecha", "critico"])
            self.sig_rafaga = ahora + random.uniform(1.5, 5.0)

        glitch = self.rafaga > 0
        if glitch:
            self.rafaga -= 1
        n = self.intensidad
        tag = "KIROSHI_OPTICS //"
        estado = "▲ PAUSE" if pausado else "▼ LINK"
        col_tag = CIAN
        col_estado = ROJO if pausado else CIAN
        col_borde = AMARILLO
        col_num = AMARILLO
        txt_num = f"{contador:03d}"
        txt_dbg = f"RAM {s1:.2f} | NET {s2:.2f} | PK {pico:.2f}"
        banner = ""
        dt_boot = ahora - self.t_inicio
        if dt_boot < 1.6:
            tag = descifrar(tag, dt_boot / 1.3)
        dt_evt = ahora - self.t_evento
        if dt_evt < 1.8:
            if dt_evt < 0.5 or int(dt_evt * 8) % 2 == 0:
                banner = "LOOT_REGISTERED"
            if dt_evt < 0.35:
                col_num = CIAN

        if pausado and int(ahora * 2) % 2:
            col_num = OSCURO

        if glitch:
            if self.tipo == "datos":
                txt_num = embrollar(txt_num, 0.35 * n)
                txt_dbg = txt_dbg.replace("RAM", "ERR").replace("NET", "???")
            elif self.tipo == "brecha":
                col_borde = col_num = col_tag = ROJO
                tag = "ERROR_SYS_BREACH //"
                txt_num = embrollar(txt_num, 0.2)
            elif self.tipo == "critico":
                col_num = col_estado = ROJO
                txt_num = f"{random.randint(100, 999)}"
                estado = "CRITICAL"

        dx = random.randint(-2 * n, 2 * n) if glitch else 0
        dx_tag = random.randint(-3, 3) if glitch and random.random() < 0.5 else 0
        if not (glitch and random.random() < 0.25):
            jx = random.randint(-n, n) if glitch and n >= 2 else 0
            puntos = [(x + jx, y) for x, y in self.pts]
            cv.create_polygon(puntos, fill="", outline=col_borde, tags="dyn")
        cv.create_rectangle(self.CORTE + 4, 1, self.CORTE + 30, 4,
                            fill=col_borde, outline="", tags="dyn")

        sy = int((ahora * 45) % ALTO)
        x0, x1 = self.rango_x(sy)
        cv.create_line(x0, sy, x1, sy, fill=HAZ, tags="dyn")

        self.txt(12 + dx_tag, 9, tag, col_tag, self.f_tag, "nw")
        self.txt(ANCHO - 16, 9, estado, col_estado, self.f_tag, "ne")
        self.txt(12, 33, "CHST_CNT >", GRIS, self.f_small, "w")
        if banner:
            self.txt(ANCHO - 16, 33, banner, CIAN, self.f_small, "e")

        y_num = 66
        if glitch:
            desfase = 2 * n
            self.txt(12 + dx - desfase, y_num, txt_num, CIAN, self.f_num, "w")
            self.txt(12 + dx + desfase, y_num, txt_num, ROJO, self.f_num, "w")
        self.txt(12 + dx, y_num, txt_num, col_num, self.f_num, "w")

        if glitch:
            for _ in range(random.randint(1, 2 * n)):
                by = random.randint(42, 90)
                bh = random.randint(2, 7)
                cv.create_rectangle(8, by, ANCHO - 16, by + bh,
                                    fill=self.fondo_corte, outline="", tags="dyn")
                bx = random.randint(8, ANCHO - 90)
                bw = random.randint(30, 110)
                cv.create_rectangle(bx, by, bx + bw, by + max(1, bh // 2),
                                    fill=random.choice([CIAN, ROJO, AMARILLO]),
                                    outline="", tags="dyn")
            for _ in range(3 * n):
                px = random.randint(4, ANCHO - 4)
                py = random.randint(4, ALTO - 4)
                cv.create_rectangle(px, py, px + random.randint(1, 3), py + 1,
                                    fill=random.choice([CIAN, ROJO, AMARILLO]),
                                    outline="", tags="dyn")

        self.txt(12, 99, txt_dbg, OSCURO if not glitch else GRIS, self.f_mini, "w")
        if MOSTRAR_AYUDA:
            self.txt(12, 111, "F7 -   F8 +   F9 RESET   F10 PAUSA   F12 SALIR",
                     OSCURO, self.f_mini, "w")


hud = HUD(root)

root.update()
hwnd = ctypes.windll.user32.GetParent(root.winfo_id()) or root.winfo_id()
estilo = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
ctypes.windll.user32.SetWindowLongW(hwnd, -20, estilo | 0x80000 | 0x20 | 0x80)

previas = {}


def tecla_pulsada(vk):
    abajo = bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)
    antes = previas.get(vk, False)
    previas[vk] = abajo
    return abajo and not antes


def salir():
    global corriendo
    corriendo = False
    root.destroy()


def teclas():
    global contador, pausado, pulso_cofre
    if tecla_pulsada(TECLA_MAS):
        contador += 1
        guardar()
        pulso_cofre = time.time()
    if tecla_pulsada(TECLA_MENOS):
        contador = max(0, contador - 1)
        guardar()
    if tecla_pulsada(TECLA_RESET):
        contador = 0
        guardar()
    if tecla_pulsada(TECLA_PAUSA):
        pausado = not pausado
    if tecla_pulsada(TECLA_SALIR):
        salir()
        return False
    return True


def bucle():
    if not corriendo:
        return
    if not teclas():
        return
    hud.cuadro()
    root.attributes("-topmost", True)
    root.after(MS_POR_CUADRO, bucle)


guardar()
threading.Thread(target=vigilar, daemon=True).start()
bucle()
try:
    root.mainloop()
finally:
    corriendo = False