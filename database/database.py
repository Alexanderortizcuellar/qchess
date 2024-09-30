from PyQt5.QtSql import QSqlDatabase, QSqlDriver
from PyQt5.QtCore import QObject, pyqtSignal

from PyQt5 import QtCore

from models.user import User


class Database(QObject):
    error = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.database = QSqlDatabase("QSQLITE")
        self.database.setDatabaseName("database.db")

    def open(self):
        if not self.database.open():
            print(self.database.lastError().text())
            self.error.emit(self.database.lastError().text())
            return False
        return True
