import sys
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout
from PyQt5.QtCore import QStateMachine, QState, pyqtSignal

class StateMachineExample(QWidget):
    def __init__(self):
        super().__init__()

        # Set up the GUI
        self.initUI()
        
        # Create the state machine
        self.state_machine = QStateMachine(self)

        # Create states
        self.state_one = QState(self.state_machine)
        self.state_two = QState(self.state_machine)

        # Set state properties
        self.state_one.assignProperty(self.button_one, 'enabled', True)
        self.state_one.assignProperty(self.button_two, 'enabled', False)
        
        self.state_two.assignProperty(self.button_one, 'enabled', False)
        self.state_two.assignProperty(self.button_two, 'enabled', True)

        # Add transitions
        self.state_one.addTransition(self.button_one.clicked, self.state_two)
        self.state_two.addTransition(self.button_two.clicked, self.state_one)

        # Set initial state
        self.state_machine.setInitialState(self.state_one)

        # Start the state machine
        self.state_machine.start()

    def initUI(self):
        self.button_one = QPushButton("State 1", self)
        self.button_two = QPushButton("State 2", self)

        layout = QVBoxLayout()
        layout.addWidget(self.button_one)
        layout.addWidget(self.button_two)

        self.setLayout(layout)
        self.setWindowTitle('QStateMachine Example')
        self.resize(300, 200)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    example = StateMachineExample()
    example.show()
    sys.exit(app.exec_())
