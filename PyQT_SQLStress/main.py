import sys, os
from PyQt5 import QtWidgets
from controllers.main_controller import MainController
def main():
    app=QtWidgets.QApplication(sys.argv)
    ui_path=os.path.join(os.path.dirname(__file__),"ui","main_window.ui")
    w=MainController(ui_path); w.show(); sys.exit(app.exec_())
if __name__=='__main__': main()
