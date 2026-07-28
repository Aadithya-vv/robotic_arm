from __future__ import annotations
from threading import Thread
from .process_manager import ProcessManager,reachable


class HealthMonitor(Thread):
    """Restart owned services only after confirmed failure, not transient load."""
    def __init__(self,manager:ProcessManager,failure_threshold:int=3):
        super().__init__(name="taskgraph-health",daemon=True)
        self.manager=manager;self.failure_threshold=max(1,failure_threshold);self._misses={"backend":0,"frontend":0}

    def run(self):
        state=self.manager.state
        while not state.stopping.wait(5):self.check_once()

    def check_once(self):
        state=self.manager.state
        self._check("backend",state.backend,"http://127.0.0.1:8000/health")
        self._check("frontend",state.frontend,"http://127.0.0.1:5173")

    def _check(self,name,process,url):
        if process is None:return
        exited=process.poll() is not None
        healthy=False if exited else reachable(url,timeout=3)
        if healthy:
            if self._misses[name]:self.manager.log.info("%s health recovered after %s missed probe(s)",name,self._misses[name])
            self._misses[name]=0;return
        self._misses[name]+=1
        self.manager.log.warning("%s health probe missed (%s/%s)%s",name,self._misses[name],self.failure_threshold,"; process exited" if exited else "; process remains alive")
        if not exited and self._misses[name]<self.failure_threshold:return
        self._restart(name,process,url)

    def _restart(self,name,process,url):
        state=self.manager.state;self.manager.log.error("%s failure confirmed; restarting",name);self.manager.stop_process(process)
        if name=="backend":self.manager.start_backend();state.backend_restarts+=1;replacement=state.backend
        else:self.manager.start_frontend();state.frontend_restarts+=1;replacement=state.frontend
        count=state.backend_restarts if name=="backend" else state.frontend_restarts
        state.mark(name,restart_count=count,state="starting")
        try:
            self.manager.wait_ready(replacement,url,name.title(),timeout=60)
            self._misses[name]=0;self.manager.log.info("%s restart ready",name)
        except (OSError,RuntimeError,TimeoutError):
            self._misses[name]=self.failure_threshold;self.manager.log.exception("%s restart did not become ready",name)
