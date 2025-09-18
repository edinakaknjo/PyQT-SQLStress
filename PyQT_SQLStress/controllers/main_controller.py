import threading
from PyQt5 import QtCore, QtWidgets, QtGui, uic
from core.config import RunConfig
from core.logger import LogBuffer
from core.runner import Runner
from PyQt5.QtCore import QTimer, QTime
import psutil
import pyqtgraph as pg

class MainController(QtWidgets.QMainWindow):
    def __init__(self, ui_path:str):
        super().__init__(); uic.loadUi(ui_path,self)
        # --- Table resize setup ---
        header = self.table_summary.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.Stretch)  # sve kolone iste širine

        self.logger=LogBuffer(); self.runner=Runner(self.logger)
        self._last_summary=None
        self.logger.updated.connect(self.on_log_update)
        self.btn_testConn.clicked.connect(self.on_test_connection)
        self.btn_run.clicked.connect(self.on_run_clicked)
        self.btn_stop.clicked.connect(self.on_stop_clicked)

        # --- Timer setup ---
        self.timer = QTimer()
        self.time = QTime(0, 0, 0, 0)
        self.timer.timeout.connect(self.update_timer)

        # --- CPU graph setup ---
        self.cpu_data = []
        self.cpu_plot = pg.PlotWidget()
        self.cpu_plot.setBackground('k')  # crna pozadina
        self.cpu_plot.showGrid(x=True, y=True, alpha=0.3)  # tanke grid linije
        self.cpu_plot.setTitle("CPU Usage (%)", color="w", size="12pt")

        styles = {"color": "w", "font-size": "10pt"}
        self.cpu_plot.setLabel("left", "Usage %", **styles)
        self.cpu_plot.setLabel("bottom", "Samples", **styles)

        self.cpu_curve = self.cpu_plot.plot(pen=pg.mkPen(color=(0, 255, 0), width=2))

        layout = QtWidgets.QVBoxLayout(self.cpuPlotWidget)
        layout.addWidget(self.cpu_plot)

        self.cpu_timer = QTimer()
        self.cpu_timer.timeout.connect(self.update_cpu_graph)

    def on_log_update(self,line:str): self.edit_log.appendPlainText(line)
    def _gather_config(self)->RunConfig:
        return RunConfig(
            dsn=self.edit_dsn.text().strip() or None,
            server=self.edit_server.text().strip(),
            database=self.edit_database.text().strip(),
            username=self.edit_username.text().strip() or None,
            password=self.edit_password.text(),
            trusted=self.check_trusted.isChecked(),
            query=self.edit_query.toPlainText().strip(),
            threads=self.spin_threads.value(),
            iterations_per_thread=self.spin_iterations.value(),
            delay_ms=self.spin_delay.value(),
            autocommit=self.check_autocommit.isChecked()
        )
    def on_test_connection(self):
        try:
            import pyodbc; cfg=self._gather_config()
            auth="Trusted_Connection=yes;" if cfg.trusted else f"UID={cfg.username};PWD={cfg.password};"
            conn=pyodbc.connect("Driver={ODBC Driver 17 for SQL Server};"
                                f"Server={cfg.server};Database={cfg.database};"
                                f"{auth}TrustServerCertificate=yes;",timeout=10)
            cur=conn.cursor(); cur.execute("SELECT 1;"); cur.fetchone(); cur.close(); conn.close()
            self.label_connMsg.setText("Connection OK ✔")
            self.logger.log("Test connection succeeded.")
        except Exception as e:
            self.label_connMsg.setText(f"Connection failed: {e}")
            self.logger.log(f"Test connection failed: {e}")

    def on_run_clicked(self):
        cfg=self._gather_config()
        if not cfg.query: 
            QtWidgets.QMessageBox.warning(self,"Query required","Enter a query"); 
            return
        self.edit_log.clear(); self.logger.log("Starting run...")

        # --- Timer start ---
        self.time = QTime(0, 0, 0, 0)
        self.timerLabel.setText("00:00.000")
        self.timer.start(100)  # update svakih 100ms

        # --- CPU graph start ---
        self.cpu_data = []
        self.cpu_timer.start(1000)  # update svakih 1s

        self.btn_run.setEnabled(False); self.btn_stop.setEnabled(True)

        def _bg():
            summary=self.runner.run(cfg)
            self._last_summary=summary; QtCore.QTimer.singleShot(0,self._finish_after)

        threading.Thread(target=_bg,daemon=True).start()

    @QtCore.pyqtSlot()
    def _finish_after(self):
        # --- Stop timer kada završi ---
        self.timer.stop()
        # --- Stop CPU graph kada završi ---
        self.cpu_timer.stop()

        if self._last_summary: self._fill_summary(self._last_summary)
        self.btn_run.setEnabled(True); self.btn_stop.setEnabled(False); self.label_status.setText("Finished")

    def _fill_summary(self,data:dict):
        self.table_summary.setRowCount(0)
        for k,v in data.items():
            r=self.table_summary.rowCount(); self.table_summary.insertRow(r)
            self.table_summary.setItem(r,0,QtWidgets.QTableWidgetItem(str(k)))
            self.table_summary.setItem(r,1,QtWidgets.QTableWidgetItem("" if v is None else str(v)))

    def on_stop_clicked(self): 
        self.runner.stop(); self.btn_stop.setEnabled(False)

    # --- Update funkcija za timer ---
    def update_timer(self):
        self.time = self.time.addMSecs(100)
        self.timerLabel.setText(self.time.toString("mm:ss.zzz"))

    # --- Update funkcija za CPU graf ---
    def update_cpu_graph(self):
        usage = psutil.cpu_percent(interval=None)  # non-blocking
        self.cpu_data.append(usage)
        if len(self.cpu_data) > 100:  # čuvaj zadnjih 100 mjerenja
            self.cpu_data.pop(0)
        self.cpu_curve.setData(self.cpu_data)
