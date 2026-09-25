# -*- coding: utf-8 -*-
"""Widgets propios: los medidores circulares y el editor de curva."""

import math

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (QBrush, QColor, QFont, QFontMetrics,
                         QLinearGradient, QPainter, QPainterPath, QPen)
from PyQt6.QtWidgets import QSizePolicy, QWidget

ACENTO = QColor("#00c8d7")
ACENTO_TENUE = QColor("#0b5f68")
FONDO = QColor("#16191d")
SUPERFICIE = QColor("#1e2329")
TINTA = QColor("#e6edf3")
TINTA_SUAVE = QColor("#8b99a6")
AVISO = QColor("#e0a03a")
CRITICO = QColor("#e05a4f")


def color_por_temperatura(t):
    """Verde-cian hasta 60, ambar hasta 80, rojo por encima."""
    if t < 60:
        return ACENTO
    if t < 80:
        return AVISO
    return CRITICO


class Medidor(QWidget):
    """Medidor circular al estilo del PredatorSense original."""

    def __init__(self, titulo, unidad="°C", maximo=100, parent=None):
        super().__init__(parent)
        self.titulo = titulo
        self.unidad = unidad
        self.maximo = maximo
        self.valor = None
        self.setMinimumSize(132, 132)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Expanding)

    def set_valor(self, v):
        if v != self.valor:
            self.valor = v
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        lado = min(self.width(), self.height())
        margen = lado * 0.12
        caja = QRectF((self.width() - lado) / 2 + margen,
                      (self.height() - lado) / 2 + margen,
                      lado - 2 * margen, lado - 2 * margen)
        grosor = max(6.0, lado * 0.075)

        # El arco abarca 270 grados, dejando el hueco abajo
        inicio, extension = 225 * 16, -270 * 16

        p.setPen(QPen(SUPERFICIE.lighter(135), grosor, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap))
        p.drawArc(caja, inicio, extension)

        if self.valor is not None:
            frac = max(0.0, min(1.0, self.valor / self.maximo))
            color = (color_por_temperatura(self.valor)
                     if self.unidad == "°C" else ACENTO)
            p.setPen(QPen(color, grosor, Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
            p.drawArc(caja, inicio, int(extension * frac))

        texto = "--" if self.valor is None else f"{self.valor:.0f}"
        p.setPen(TINTA)
        f = QFont(self.font())
        f.setPointSizeF(max(13.0, lado * 0.19))
        f.setWeight(QFont.Weight.DemiBold)
        p.setFont(f)
        r_valor = QRectF(caja.x(), caja.y() + caja.height() * 0.24,
                         caja.width(), caja.height() * 0.40)
        p.drawText(r_valor, Qt.AlignmentFlag.AlignCenter, texto + self.unidad)

        p.setPen(TINTA_SUAVE)
        f.setPointSizeF(max(8.0, lado * 0.088))
        f.setWeight(QFont.Weight.Normal)
        p.setFont(f)
        r_tit = QRectF(caja.x() - grosor, caja.y() + caja.height() * 0.62,
                       caja.width() + 2 * grosor, caja.height() * 0.3)
        # Recortar con puntos suspensivos en vez de desbordar: un titulo largo
        # salia cortado por los dos lados ("GPU suspendida" -> "PU suspendid").
        texto_tit = QFontMetrics(f).elidedText(
            self.titulo, Qt.TextElideMode.ElideRight, int(r_tit.width()))
        p.drawText(r_tit, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                   texto_tit)


class EditorCurva(QWidget):
    """
    Curva de ventiladores editable: temperatura de arranque y escalado.

    Los puntos se arrastran con el raton. Por debajo del primer punto los
    ventiladores quedan al minimo, que es justo lo que se pide cuando se quiere
    silencio absoluto en reposo.
    """

    curva_cambiada = pyqtSignal()

    T_MIN, T_MAX = 30, 100

    def __init__(self, puntos=None, parent=None):
        super().__init__(parent)
        # lista de (temperatura, porcentaje)
        self.puntos = puntos or [(40, 0), (50, 20), (60, 35), (70, 55),
                                 (80, 75), (90, 100)]
        self.arrastrando = None
        self.temp_actual = None
        self.setMinimumHeight(220)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Expanding)

    # -- conversion entre datos y pixeles ---------------------------------
    def _caja(self):
        return QRectF(46, 14, self.width() - 62, self.height() - 46)

    def _a_pixel(self, t, pct):
        c = self._caja()
        x = c.x() + (t - self.T_MIN) / (self.T_MAX - self.T_MIN) * c.width()
        y = c.y() + (1 - pct / 100) * c.height()
        return QPointF(x, y)

    def _a_datos(self, pos):
        c = self._caja()
        t = self.T_MIN + (pos.x() - c.x()) / c.width() * (self.T_MAX - self.T_MIN)
        pct = (1 - (pos.y() - c.y()) / c.height()) * 100
        return (max(self.T_MIN, min(self.T_MAX, t)),
                max(0, min(100, pct)))

    def set_temp_actual(self, t):
        self.temp_actual = t
        self.update()

    def porcentaje_para(self, t):
        """Interpolacion lineal, igual que aplicara el servicio."""
        pts = sorted(self.puntos)
        if not pts or t < pts[0][0]:
            return 0
        for i in range(len(pts) - 1):
            (t0, p0), (t1, p1) = pts[i], pts[i + 1]
            if t0 <= t <= t1:
                if t1 == t0:
                    return int(p1)
                return int(p0 + (p1 - p0) * (t - t0) / (t1 - t0))
        return int(pts[-1][1])

    # -- interaccion -------------------------------------------------------
    def mousePressEvent(self, e):
        for i, (t, pct) in enumerate(self.puntos):
            if (self._a_pixel(t, pct) - e.position()).manhattanLength() < 18:
                self.arrastrando = i
                return

    def mouseMoveEvent(self, e):
        if self.arrastrando is None:
            return
        t, pct = self._a_datos(e.position())
        i = self.arrastrando
        # No dejar que un punto adelante a sus vecinos: la curva debe ser
        # monotona en temperatura o deja de tener sentido.
        t_min = self.puntos[i - 1][0] + 1 if i > 0 else self.T_MIN
        t_max = self.puntos[i + 1][0] - 1 if i < len(self.puntos) - 1 else self.T_MAX
        self.puntos[i] = (int(max(t_min, min(t_max, t))), int(pct))
        self.update()

    def mouseReleaseEvent(self, _):
        if self.arrastrando is not None:
            self.arrastrando = None
            self.curva_cambiada.emit()

    # -- pintado -----------------------------------------------------------
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = self._caja()

        p.fillRect(self.rect(), SUPERFICIE)

        # rejilla
        p.setPen(QPen(SUPERFICIE.lighter(140), 1))
        f = QFont(self.font())
        f.setPointSize(8)
        p.setFont(f)
        for pct in range(0, 101, 25):
            y = c.y() + (1 - pct / 100) * c.height()
            p.setPen(QPen(SUPERFICIE.lighter(140), 1))
            p.drawLine(QPointF(c.x(), y), QPointF(c.right(), y))
            p.setPen(TINTA_SUAVE)
            p.drawText(QRectF(0, y - 9, 40, 18),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       f"{pct}%")
        for t in range(self.T_MIN, self.T_MAX + 1, 10):
            x = c.x() + (t - self.T_MIN) / (self.T_MAX - self.T_MIN) * c.width()
            p.setPen(QPen(SUPERFICIE.lighter(140), 1))
            p.drawLine(QPointF(x, c.y()), QPointF(x, c.bottom()))
            p.setPen(TINTA_SUAVE)
            p.drawText(QRectF(x - 18, c.bottom() + 4, 36, 16),
                       Qt.AlignmentFlag.AlignCenter, f"{t}°")

        # temperatura actual
        if self.temp_actual is not None:
            x = c.x() + ((self.temp_actual - self.T_MIN)
                         / (self.T_MAX - self.T_MIN)) * c.width()
            if c.x() <= x <= c.right():
                p.setPen(QPen(AVISO, 1, Qt.PenStyle.DashLine))
                p.drawLine(QPointF(x, c.y()), QPointF(x, c.bottom()))

        # curva
        pts = sorted(self.puntos)
        camino = QPainterPath()
        primero = self._a_pixel(pts[0][0], pts[0][1])
        camino.moveTo(QPointF(c.x(), primero.y()))
        for t, pct in pts:
            camino.lineTo(self._a_pixel(t, pct))
        camino.lineTo(QPointF(c.right(), self._a_pixel(*pts[-1]).y()))
        p.setPen(QPen(ACENTO, 2))
        p.drawPath(camino)

        relleno = QPainterPath(camino)
        relleno.lineTo(QPointF(c.right(), c.bottom()))
        relleno.lineTo(QPointF(c.x(), c.bottom()))
        relleno.closeSubpath()
        p.fillPath(relleno, QColor(0, 200, 215, 28))

        # puntos
        for t, pct in pts:
            centro = self._a_pixel(t, pct)
            p.setBrush(FONDO)
            p.setPen(QPen(ACENTO, 2))
            p.drawEllipse(centro, 5.5, 5.5)


class Ventilador(QWidget):
    """Aspas que giran a la velocidad real del ventilador.

    Es la unica forma honesta de mostrar unas rpm de un vistazo: un numero no
    distingue "parado" de "girando despacio", y en este portatil esa diferencia
    es justo la que interesa cuando se persigue el silencio.

    El giro se detiene del todo a 0 rpm en lugar de quedarse a velocidad
    minima, porque el EC si los para por completo por debajo de la temperatura
    de arranque de la curva.
    """

    ASPAS = 7
    RPM_MAX = 5000.0

    def __init__(self, etiqueta, parent=None):
        super().__init__(parent)
        self.etiqueta = etiqueta
        self.rpm = None
        self._angulo = 0.0
        self.setMinimumSize(108, 128)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Expanding)
        self._reloj = QTimer(self)
        self._reloj.timeout.connect(self._girar)
        self._reloj.start(33)          # ~30 fotogramas por segundo

    def set_rpm(self, rpm):
        self.rpm = rpm
        self.update()

    def _girar(self):
        if not self.rpm:
            return
        # Se dibuja a una fraccion de la velocidad real: a 3000 rpm de verdad
        # las aspas serian un borron y el efecto estroboscopico haria que
        # pareciesen ir al reves.
        self._angulo = (self._angulo + min(self.rpm, self.RPM_MAX) / 260.0) % 360.0
        self.update()

    def paintEvent(self, _):
        import math
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        lado = min(self.width(), self.height() - 26)
        cx, cy = self.width() / 2.0, (self.height() - 26) / 2.0
        radio = lado / 2.0 - 6

        p.setPen(QPen(SUPERFICIE.lighter(135), 2))
        p.setBrush(FONDO)
        p.drawEllipse(QPointF(cx, cy), radio, radio)

        activo = bool(self.rpm)
        color = ACENTO if activo else TINTA_SUAVE.darker(140)

        p.save()
        p.translate(cx, cy)
        p.rotate(self._angulo)
        camino = QPainterPath()
        for i in range(self.ASPAS):
            a = math.radians(i * 360.0 / self.ASPAS)
            # Cada aspa es una curva desde el buje hasta el borde, con el
            # extremo desplazado para que se vea el paso de helice.
            x1, y1 = math.cos(a) * radio * 0.22, math.sin(a) * radio * 0.22
            x2, y2 = math.cos(a + 0.5) * radio * 0.86, math.sin(a + 0.5) * radio * 0.86
            camino.moveTo(x1, y1)
            camino.quadTo(math.cos(a + 0.1) * radio * 0.6,
                          math.sin(a + 0.1) * radio * 0.6, x2, y2)
        p.setPen(QPen(color, max(3.0, radio * 0.17),
                      Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawPath(camino)
        p.restore()

        p.setBrush(SUPERFICIE.lighter(130))
        p.setPen(QPen(color, 2))
        p.drawEllipse(QPointF(cx, cy), radio * 0.2, radio * 0.2)

        f = QFont(self.font())
        f.setPointSizeF(10.5)
        f.setWeight(QFont.Weight.DemiBold)
        p.setFont(f)
        p.setPen(TINTA if activo else TINTA_SUAVE)
        texto = "parado" if self.rpm == 0 else (
            "--" if self.rpm is None else f"{self.rpm} rpm")
        p.drawText(QRectF(0, self.height() - 26, self.width(), 14),
                   Qt.AlignmentFlag.AlignCenter, texto)

        f.setPointSizeF(8.5)
        f.setWeight(QFont.Weight.Normal)
        p.setFont(f)
        p.setPen(TINTA_SUAVE)
        p.drawText(QRectF(0, self.height() - 13, self.width(), 13),
                   Qt.AlignmentFlag.AlignCenter, self.etiqueta)


class TecladoZonas(QWidget):
    """Dibujo del teclado con sus cuatro zonas, clicables.

    El trazado se define por COORDENADAS en unidades de tecla, como en un
    teclado real, no como filas independientes: asi las columnas quedan
    alineadas de arriba abajo y las teclas anchas (Tab, Bloq Mayus, Mayus,
    espaciadora) empujan a las demas exactamente como lo hacen en el teclado
    fisico.

    Un intento anterior dibujaba cada fila repartiendo el ancho entre sus
    teclas, con una sangria en las filas impares. El resultado no se parecia a
    un teclado sino a un muro de ladrillos: ninguna columna coincidia con la
    de arriba.

    Se reproduce el teclado de un Predator de 15,6 pulgadas: bloque principal
    de 15 unidades, fila de funcion mas baja, flechas en cruz invertida y
    teclado numerico de cuatro columnas con las teclas + e Intro de doble
    altura.
    """

    zona_pulsada = pyqtSignal(int)         # 0..3

    ANCHO_PPAL = 15.0                      # unidades de tecla
    SEPARACION = 0.4
    NUM_X = ANCHO_PPAL + SEPARACION
    ANCHO_TOTAL = NUM_X + 4.0
    ALTO_FUNCION = 0.8
    SEPARACION_FILA = 0.06

    # Fronteras entre zonas, en unidades de tecla, como (arriba, abajo).
    #
    # Solo la PRIMERA va inclinada. Medido sobre el teclado encendiendo una
    # zona cada vez:
    #
    #   \  zona 1 | 2 : arriba abarca 3 teclas y abajo 4 -- Ctrl, Fn, Win y
    #                    Alt--, de ahi la inclinacion. Es la que parte por la
    #                    mitad las teclas 3, E y D al cruzar cada fila en un
    #                    punto distinto.
    #   |  zona 2 | 3 : vertical. Pasa por el centro de O, L y Alt Gr, que
    #                    son las tres teclas que se ven partidas ahi.
    #   |  zona 3 | 4 : vertical, justo en el arranque del numerico.
    #
    # Repartir el ancho en cuartos iguales, que fue el primer intento, no se
    # parece en nada a lo que hace el teclado.
    # La primera frontera se da POR FILA, no como una recta entre dos
    # extremos. El escalonado del teclado no es uniforme --media tecla entre
    # la fila de numeros y la de Tab, un cuarto entre Tab y Bloq Mayus-- asi
    # que una recta no puede pasar a la vez por el centro de 3, E y D. Con una
    # recta lo suficientemente inclinada para cortarlas por la mitad, la
    # espaciadora quedaba tambien partida, y en el teclado real no lo esta.
    #
    # Cada valor es el centro de la tecla que se ve partida en esa fila:
    #   funcion   3,00  -> la zona abarca 3 teclas
    #   numeros   3,50  -> centro del 3
    #   Tab       4,00  -> centro de la E
    #   Bloq May  4,25  -> centro de la D
    #   Mayus     4,40
    #   inferior  4,50  -> justo donde acaba Alt, que queda entera en la zona 1
    FRONTERA_12 = (3.00, 3.50, 4.00, 4.25, 4.50, 4.00)

    FRONTERAS = (None, (10.0, 10.0), (ANCHO_PPAL, ANCHO_PPAL))

    def __init__(self, parent=None):
        super().__init__(parent)
        self.colores = [QColor("#00c8d7") for _ in range(4)]
        self.brillo = 100
        self._trazado = self._construir_trazado()
        self.setMinimumHeight(225)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # Expanding en vertical y con heightForWidth: asi el teclado crece
        # hasta llenar el ancho disponible en vez de quedarse pequeño y
        # centrado, que era lo que pasaba con una altura fija.
        pol = QSizePolicy(QSizePolicy.Policy.Expanding,
                          QSizePolicy.Policy.Preferred)
        pol.setHeightForWidth(True)
        self.setSizePolicy(pol)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, ancho):
        """Alto que mantiene la proporcion real del teclado."""
        util = max(1.0, ancho - 20)
        alto = util * self._alto_unidades() / self.ANCHO_TOTAL
        return int(alto + 16 + self.ALTO_ETIQUETAS)

    # -- trazado -----------------------------------------------------------
    @classmethod
    def _construir_trazado(cls):
        """Devuelve la lista de teclas como (x, y, ancho, alto) en unidades.

        Los anchos son los del estandar: Tab 1,5 / Bloq Mayus 1,75 /
        Mayus izquierda 2,25 / Intro 2,25 / espaciadora 6. Cada fila suma
        exactamente 15, que es lo que hace que las columnas cuadren.
        """
        t = []
        paso = 1.0 + cls.SEPARACION_FILA

        # Fila de funcion: mas baja que el resto, como en un portatil, y
        # recorriendo TODO el ancho. Si solo cubriese el bloque principal, la
        # zona del teclado numerico se quedaria con un hueco vacio arriba que
        # no existe en el teclado real.
        for i in range(15):
            t.append((i, 0.0, 1.0, cls.ALTO_FUNCION))
        for i in range(4):
            t.append((cls.NUM_X + i, 0.0, 1.0, cls.ALTO_FUNCION))

        y = cls.ALTO_FUNCION + cls.SEPARACION_FILA

        def fila(anchos, x0=0.0, altura=1.0):
            x = x0
            for w in anchos:
                t.append((x, y, w, altura))
                x += w

        # Numeros: trece teclas y retroceso doble.
        fila([1.0] * 13 + [2.0])
        fila([1.0] * 4, cls.NUM_X)                       # Bloq Num / * -
        y += paso

        fila([1.5] + [1.0] * 12 + [1.5])                 # Tab ... Intro
        fila([1.0] * 4, cls.NUM_X)                       # 7 8 9 +
        y += paso

        fila([1.75] + [1.0] * 11 + [2.25])               # Bloq Mayus ... Intro
        fila([1.0] * 4, cls.NUM_X)                       # 4 5 6 y una mas
        y += paso

        # Mayus derecho de 1,5, medido en el teclado. El izquierdo absorbe la
        # diferencia para que la fila siga sumando 15.
        fila([2.5] + [1.0] * 10 + [1.5])                 # Mayus ... Mayus
        t.append((14.0, y, 1.0, 1.0))                    # flecha arriba
        fila([1.0] * 3, cls.NUM_X)                       # 1 2 3
        # El Intro es la UNICA tecla de doble altura del numpad: el +, al
        # contrario que en un teclado de sobremesa, aqui es de altura simple.
        t.append((cls.NUM_X + 3.0, y, 1.0, 2.0 + cls.SEPARACION_FILA))
        y += paso

        # Fila inferior, con los anchos medidos en el teclado: Ctrl, Fn, Win,
        # Alt y Alt Gr de una unidad, espaciadora de 5, Ctrl derecho de 1,5 y
        # los tres cursores de 1. Suman 14,5 y no 15 porque en estas Predator
        # el bloque de cursores no va pegado al Ctrl derecho, sino separado
        # media tecla. Ese hueco es lo que deja a Alt Gr en 9-10, entera
        # dentro de la segunda zona, mientras la O de encima (9,5-10,5) si
        # cae partida por la frontera.
        fila([1.0, 1.0, 1.0, 1.0, 5.0, 1.0, 1.5])        # Ctrl ... Ctrl
        fila([1.0] * 3, 12.0)                            # cursores tras el hueco
        # El 0 es una tecla NORMAL, no de doble ancho, y la fila queda llena:
        # tres teclas mas la mitad inferior del Intro.
        fila([1.0] * 3, cls.NUM_X)                       # 0, punto y una mas
        return t

    def set_colores(self, colores):
        self.colores = [QColor(c) for c in colores]
        self.update()

    def set_brillo(self, brillo):
        self.brillo = brillo
        self.update()

    ALTO_ETIQUETAS = 20                    # sitio reservado para "zona N"

    def _caja(self):
        """Area del dibujo, sin contar la franja de etiquetas de abajo."""
        return QRectF(10, 8, self.width() - 20,
                      self.height() - 16 - self.ALTO_ETIQUETAS)

    def _alto_unidades(self):
        return (self.ALTO_FUNCION + self.SEPARACION_FILA
                + 5 * (1 + self.SEPARACION_FILA))

    def _rect_teclado(self):
        """El rectangulo que ocupa el teclado dibujado, centrado en la caja.

        Todo lo demas -las franjas de color, las etiquetas y el reparto de
        zonas- se calcula sobre ESTE rectangulo y no sobre la caja. Usando la
        caja, el teclado quedaba centrado y estrecho mientras las franjas
        seguian abarcandolo todo: las zonas de los extremos salian como
        bloques de color vacios, sin teclas dentro.
        """
        c = self._caja()
        u = min(c.width() / self.ANCHO_TOTAL, c.height() / self._alto_unidades())
        ancho = self.ANCHO_TOTAL * u
        alto = self._alto_unidades() * u
        return QRectF(c.x() + (c.width() - ancho) / 2.0,
                      c.y() + (c.height() - alto) / 2.0, ancho, alto), u

    # Altura a la que empieza cada fila, en unidades. Sirve para saber en que
    # fila cae un punto y aplicarle la frontera que le toca.
    @classmethod
    def _ys_fila(cls):
        paso = 1.0 + cls.SEPARACION_FILA
        y = cls.ALTO_FUNCION + cls.SEPARACION_FILA
        return (0.0,) + tuple(y + i * paso for i in range(5))

    def _frontera(self, i, y_u):
        """Posicion en unidades de la frontera i a la altura y_u (unidades)."""
        if self.FRONTERAS[i] is None:
            ys = self._ys_fila()
            fila = 0
            for n, y0 in enumerate(ys):
                # La tolerancia importa: ys se acumula sumando alturas, y sin
                # ella un punto justo en la union de dos filas cae en la
                # anterior por un epsilon de coma flotante.
                if y_u >= y0 - 1e-6:
                    fila = n
            return self.FRONTERA_12[fila]
        arriba, abajo = self.FRONTERAS[i]
        t = max(0.0, min(1.0, y_u / self._alto_unidades()))
        return arriba + (abajo - arriba) * t

    def _zona_de(self, x, y=None):
        """Zona de un punto. Sin y se usa la mitad del teclado, que es lo
        razonable para una pulsacion sobre la etiqueta."""
        r, u = self._rect_teclado()
        if u <= 0:
            return 0
        x_u = (x - r.x()) / u
        y_u = (self._alto_unidades() / 2.0 if y is None
               else max(0.0, (y - r.y()) / u))
        for i in range(3):
            if x_u < self._frontera(i, y_u):
                return i
        return 3

    def mousePressEvent(self, e):
        if self._caja().contains(e.position()):
            self.zona_pulsada.emit(
                self._zona_de(e.position().x(), e.position().y()))

    # -- pintado -----------------------------------------------------------
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = self._caja()

        r, u = self._rect_teclado()
        marco = r.adjusted(-6, -5, 6, 5)
        p.setPen(QPen(SUPERFICIE.lighter(140), 1.5))
        p.setBrush(QColor("#0d0f12"))
        p.drawRoundedRect(marco, 8, 8)

        ox, oy = r.x(), r.y()
        factor = self.brillo / 100.0

        # La luz de cada zona se difumina por detras de las teclas, que es
        # como se ve un teclado retroiluminado de verdad.
        alto_u = self._alto_unidades()

        def borde_x(i, y_px):
            """Frontera i, en pixeles, a una altura dada en pixeles."""
            if i < 0:
                return marco.left()
            if i >= len(self.FRONTERAS):
                return marco.right()
            return r.x() + self._frontera(i, (y_px - r.y()) / u) * u

        # Cada zona es un cuadrilatero, no una franja: sus lados izquierdo y
        # derecho siguen la inclinacion de las fronteras.
        for i, color in enumerate(self.colores):
            arriba, abajo = marco.top(), marco.bottom()
            izq_a = borde_x(i - 1, arriba) if i else marco.left()
            izq_b = borde_x(i - 1, abajo) if i else marco.left()
            der_a = borde_x(i, arriba) if i < 3 else marco.right()
            der_b = borde_x(i, abajo) if i < 3 else marco.right()

            forma = QPainterPath()
            forma.moveTo(izq_a, arriba)
            forma.lineTo(der_a, arriba)
            forma.lineTo(der_b, abajo)
            forma.lineTo(izq_b, abajo)
            forma.closeSubpath()

            for paso in range(3):
                halo = QColor(color)
                halo.setAlpha(int((14 + paso * 20) * factor))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(halo)
                p.drawPath(forma)

        # Teclas oscuras con el borde encendido del color de su zona.
        #
        # Una tecla que cruza la frontera entre dos zonas se pinta con los dos
        # colores, con el cambio justo donde cae la frontera. En el teclado
        # real ocurre exactamente eso: las teclas 3, E y D salen medio
        # iluminadas de cada color, porque el corte no respeta las teclas.
        alfa = int(55 + 200 * factor)
        for x, y, w, h in self._trazado:
            tecla = QRectF(ox + x * u + 0.8, oy + y * u + 0.8,
                           w * u - 1.6, h * u - 1.6)
            medio = tecla.center().y()
            zi = self._zona_de(tecla.left(), medio)
            zd = self._zona_de(tecla.right(), medio)

            if zi == zd:
                borde = QColor(self.colores[zi])
                borde.setAlpha(alfa)
                pincel = QPen(borde, 1.1)
            else:
                # La frontera se evalua a la altura de ESTA tecla: al estar
                # inclinada, cada fila la cruza en un punto distinto.
                corte = self._frontera(zi, (medio - r.y()) / u)
                pos = (r.x() + corte * u - tecla.left()) / max(1.0, tecla.width())
                deg = QLinearGradient(tecla.topLeft(), tecla.topRight())
                ci, cd = QColor(self.colores[zi]), QColor(self.colores[zd])
                ci.setAlpha(alfa)
                cd.setAlpha(alfa)
                deg.setColorAt(0.0, ci)
                deg.setColorAt(max(0.0, min(1.0, pos)), ci)
                deg.setColorAt(max(0.0, min(1.0, pos + 0.001)), cd)
                deg.setColorAt(1.0, cd)
                pincel = QPen(QBrush(deg), 1.1)

            p.setBrush(QColor(22, 25, 30, 235))
            p.setPen(pincel)
            p.drawRoundedRect(tecla, 2.2, 2.2)

        # Etiqueta de zona, con fondo propio para que se lea sobre cualquier
        # color: sobre amarillo el texto claro desaparecia.
        f = QFont(self.font())
        f.setPointSizeF(8.0)
        f.setWeight(QFont.Weight.DemiBold)
        p.setFont(f)
        for i in range(4):
            izq = 0.0 if i == 0 else self._frontera(i - 1, alto_u / 2.0)
            der = (self.ANCHO_TOTAL if i == 3
                   else self._frontera(i, alto_u / 2.0))
            centro = r.x() + (izq + der) / 2.0 * u
            etiqueta = QRectF(centro - 26,
                              self.height() - self.ALTO_ETIQUETAS + 2, 52, 15)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(13, 15, 18, 215))
            p.drawRoundedRect(etiqueta, 7, 7)
            p.setPen(TINTA_SUAVE)
            p.drawText(etiqueta, Qt.AlignmentFlag.AlignCenter, f"zona {i + 1}")


class SelectorDireccion(QWidget):
    """Direccion de los efectos animados. Faltaba por completo en la interfaz.

    El driver la exige mayor que cero en Onda y Desplazamiento, asi que no es
    un adorno: sin ella esos dos efectos se rechazan con -EINVAL.
    """

    cambiada = pyqtSignal(int)             # 1 o 2

    def __init__(self, parent=None):
        super().__init__(parent)
        self.valor = 1
        self.setFixedHeight(34)
        self.setMinimumWidth(120)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_valor(self, v):
        if v in (1, 2) and v != self.valor:
            self.valor = v
            self.update()

    def mousePressEvent(self, e):
        # El boton de la izquierda emite 2 y el de la derecha 1: en este
        # firmware la direccion va al reves de lo que sugiere el numero, y se
        # comprobo en el teclado. Corregirlo aqui evita tener que recordarlo
        # en cada sitio que llame al driver.
        self.set_valor(2 if e.position().x() < self.width() / 2 else 1)
        self.cambiada.emit(self.valor)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        mitad = self.width() / 2.0
        for i, (v, flecha) in enumerate(((2, "◀"), (1, "▶"))):
            r = QRectF(i * mitad, 0, mitad, self.height())
            activo = self.valor == v
            p.setPen(QPen(ACENTO if activo else SUPERFICIE.lighter(140), 1.5))
            p.setBrush(ACENTO_TENUE if activo else SUPERFICIE)
            p.drawRoundedRect(r.adjusted(2, 2, -2, -2), 5, 5)
            p.setPen(TINTA if activo else TINTA_SUAVE)
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, flecha)
