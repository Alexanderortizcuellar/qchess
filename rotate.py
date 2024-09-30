import sys
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QGraphicsView, QGraphicsScene, QGraphicsProxyWidget
from PyQt5.QtCore import QPropertyAnimation, Qt, QPointF, QEasingCurve

class FlippingWidget(QWidget):
    def __init__(self):
        super().__init__()

        # Set up the main layout
        layout = QVBoxLayout()
        
        self.graphicsview = QGraphicsView(self)
        self.scene = QGraphicsScene(self.graphicsview)
        self.graphicsview.setScene(self.scene)

        self.button = QPushButton("Flip Me!")
        self.proxy = QGraphicsProxyWidget()
        self.proxy.setWidget(self.button)
        self.proxy.setTransformOriginPoint(self.proxy.boundingRect().center())
        self.scene.addItem(self.proxy)
        layout.addWidget(self.graphicsview)
        self.setLayout(layout)
        self.box = QWidget(self)
        self.button.clicked.connect(self.flip_widget)

    def flip_widget(self):
        # Create an animation to flip the widget
        if self.proxy.rotation() == 180:
            self.proxy.setRotation(0)
        else:
            self.proxy.setRotation(180)
        """ animation = QPropertyAnimation(self.proxy, b"rotation")
        animation.setDuration(1000)
        animation.setStartValue(0)
        animation.setEndValue(360)
        animation.setEasingCurve(QEasingCurve.OutInCubic)
        animation.start() """

if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = FlippingWidget()
    widget.show()
    sys.exit(app.exec_())
