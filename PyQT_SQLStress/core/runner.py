import time, threading, queue, statistics
from typing import List, Optional
try:
    import pyodbc
except Exception:
    pyodbc = None
from .config import ExecResult, RunConfig

class Runner:
    def __init__(self, logger):
        self._stop_event = threading.Event()
        self._threads: List[threading.Thread] = []
        self._q: "queue.Queue[ExecResult]" = queue.Queue()
        self._logger = logger
    def stop(self):
        self._logger.log("Stop requested."); self._stop_event.set()
    def _make_conn(self, cfg: RunConfig):
        if pyodbc is None:
            raise RuntimeError("pyodbc not installed")
        if cfg.dsn:
            conn_str = f"DSN={cfg.dsn};"
            if not cfg.trusted:
                conn_str += f"UID={cfg.username};PWD={cfg.password};"
            if cfg.database:
                conn_str += f"DATABASE={cfg.database};"
        else:
            auth = "Trusted_Connection=yes;" if cfg.trusted else f"UID={cfg.username};PWD={cfg.password};"
            conn_str = ("Driver={ODBC Driver 17 for SQL Server};"
                        f"Server={cfg.server};Database={cfg.database};"
                        f"{auth}TrustServerCertificate=yes;")
        self._logger.log("Opening SQL connection...")
        conn = pyodbc.connect(conn_str, autocommit=cfg.autocommit, timeout=30)
        self._logger.log("SQL connection opened.")
        return conn
    def _worker(self, cfg: RunConfig, idx: int):
        try:
            conn = self._make_conn(cfg); cur = conn.cursor()
        except Exception as e:
            self._logger.log(f"Thread {idx} connection error: {e}")
            self._q.put(ExecResult(False,0.0,str(e))); return
        
        for _ in range(cfg.iterations_per_thread):
            if self._stop_event.is_set(): break
            start=time.perf_counter(); ok=True; err=None
            try:
                cur.execute(cfg.query)
                if not cfg.autocommit: conn.commit()
            except Exception as e:
                ok=False; err=str(e)
                if not cfg.autocommit:
                    try: conn.rollback()
                    except: pass
            end=time.perf_counter()
            self._q.put(ExecResult(ok,(end-start)*1000.0,err))
            if cfg.delay_ms>0: time.sleep(cfg.delay_ms/1000.0)
        cur.close(); conn.close()
    def run(self,cfg:RunConfig,on_progress=None):
        self._stop_event.clear(); self._threads=[]
        total=cfg.threads*cfg.iterations_per_thread; done=0
        durations=[]; okc=0; errc=0
        for t in range(cfg.threads):
            th=threading.Thread(target=self._worker,args=(cfg,t+1),daemon=True); th.start(); self._threads.append(th)
        while any(th.is_alive() for th in self._threads) or not self._q.empty():
            try:
                res=self._q.get(timeout=0.15); done+=1
                if res.ok: okc+=1
                else: errc+=1
                if res.duration_ms>0: durations.append(res.duration_ms)
                if on_progress: on_progress(done,total)
            except queue.Empty: pass
        for th in self._threads: th.join(timeout=0.1)
        return {
            "total":total,"completed":len(durations),"ok":okc,"errors":errc,
            "avg_ms":round(statistics.mean(durations),2) if durations else None,
            "min_ms":round(min(durations),2) if durations else None,
            "max_ms":round(max(durations),2) if durations else None
        }
