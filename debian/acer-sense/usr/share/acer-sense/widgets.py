# -*- coding: utf-8 -*-
"""Widgets propios: los medidores circulares y el editor de curva."""

import math

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
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
        r_tit = QRectF(caja.x(), caja.y() + caja.height() * 0.62,
                       caja.width(), caja.height() * 0.3)
        p.drawText(r_tit, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                   self.titulo)


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
