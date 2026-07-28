"""Replaceable Camera providers; OpenCV remains an optional lazy dependency."""
from __future__ import annotations
from importlib import import_module
from threading import RLock
from .contracts import CameraConfiguration,CameraDevice,CameraProvider,ProviderDiscovery,ProviderFrame,ProviderResult
class MockCameraProvider:
    def __init__(self,frames=None,*,provider_id="mock",device_id="mock-camera-0",fail_open=False,fail_acquire_at=None,repeat=True):
        self._provider_id=provider_id;self._device_id=device_id;self._frames=tuple(frames or (b"mock-frame",));self._fail_open=fail_open;self._fail_at=fail_acquire_at;self._repeat=repeat;self._open=False;self._index=0;self._configuration=None;self._lock=RLock()
    @property
    def provider_id(self):return self._provider_id
    def discover(self):return ProviderDiscovery(True,(CameraDevice(self._device_id,"Mock Camera",self.provider_id,True,{"virtual":True}),))
    def open(self,configuration):
        with self._lock:
            if self._fail_open:return ProviderResult(False,"mock.open.failed","mock connection failure")
            if configuration.device_id!=self._device_id:return ProviderResult(False,"mock.device.not_found","mock device not found")
            self._configuration=configuration;self._open=True;self._index=0;return ProviderResult(True,metadata={"connected":True})
    def acquire(self):
        with self._lock:
            if not self._open:return ProviderFrame(False,error_code="mock.not_open",error_summary="mock camera is closed")
            if self._fail_at is not None and self._index==self._fail_at:return ProviderFrame(False,error_code="mock.capture.failed",error_summary="mock acquisition failure")
            if not self._frames:return ProviderFrame(False,error_code="mock.frames.empty",error_summary="no mock frames configured")
            if self._index>=len(self._frames) and not self._repeat:return ProviderFrame(False,error_code="mock.frames.exhausted",error_summary="mock frames exhausted")
            data=self._frames[self._index%len(self._frames)];self._index+=1;c=self._configuration
            return ProviderFrame(True,data,c.width,c.height,3,c.pixel_format,f"mock-frame-{self._index}",{"mock_index":self._index})
    def diagnostics(self):
        with self._lock:return {"provider":"mock","open":self._open,"acquisitions":self._index,"device_id":self._device_id}
    def close(self):
        with self._lock:self._open=False;return ProviderResult(True,metadata={"connected":False})
class OpenCVCameraProvider:
    def __init__(self,*,provider_id="opencv",device_indices=tuple(range(4))):self._provider_id=provider_id;self._indices=tuple(device_indices);self._capture=None;self._configuration=None;self._count=0;self._lock=RLock()
    @property
    def provider_id(self):return self._provider_id
    def _cv2(self):return import_module("cv2")
    def discover(self):
        try:cv2=self._cv2()
        except ImportError:return ProviderDiscovery(False,error_code="opencv.unavailable",error_summary="OpenCV is not installed")
        devices=[]
        for index in self._indices:
            capture=cv2.VideoCapture(index);opened=bool(capture.isOpened());capture.release()
            if opened:devices.append(CameraDevice(str(index),f"Camera {index}",self.provider_id))
        return ProviderDiscovery(True,tuple(devices))
    def open(self,configuration):
        with self._lock:
            try:cv2=self._cv2()
            except ImportError:return ProviderResult(False,"opencv.unavailable","OpenCV is not installed")
            try:index=int(configuration.device_id)
            except ValueError:return ProviderResult(False,"opencv.device.invalid","OpenCV device_id must be an integer")
            capture=cv2.VideoCapture(index);capture.set(cv2.CAP_PROP_FRAME_WIDTH,configuration.width);capture.set(cv2.CAP_PROP_FRAME_HEIGHT,configuration.height);capture.set(cv2.CAP_PROP_FPS,configuration.frames_per_second)
            if not capture.isOpened():capture.release();return ProviderResult(False,"opencv.open.failed","camera could not be opened")
            self._capture=capture;self._configuration=configuration;self._count=0;return ProviderResult(True)
    def acquire(self):
        with self._lock:
            if self._capture is None:return ProviderFrame(False,error_code="opencv.not_open",error_summary="camera is closed")
            ok,frame=self._capture.read()
            if not ok:return ProviderFrame(False,error_code="opencv.capture.failed",error_summary="frame acquisition failed")
            self._count+=1;height,width=frame.shape[:2];channels=1 if len(frame.shape)==2 else frame.shape[2]
            return ProviderFrame(True,frame.tobytes(),width,height,channels,self._configuration.pixel_format,None,{"opencv_sequence":self._count})
    def diagnostics(self):return {"provider":"opencv","open":self._capture is not None,"acquisitions":self._count}
    def close(self):
        with self._lock:
            if self._capture is not None:self._capture.release();self._capture=None
            return ProviderResult(True)
class CameraProviderCatalog:
    def __init__(self,providers):
        self._providers={};self._errors=[]
        for provider in providers:
            try:provider_id=provider.provider_id.strip()
            except Exception:self._errors.append("invalid provider identity");continue
            if not provider_id:self._errors.append("empty provider identity")
            elif provider_id in self._providers:self._errors.append(f"duplicate provider: {provider_id}")
            elif not isinstance(provider,CameraProvider):self._errors.append(f"invalid provider contract: {provider_id}")
            else:self._providers[provider_id]=provider
    @property
    def errors(self):return tuple(self._errors)
    @property
    def provider_ids(self):return tuple(sorted(self._providers))
    def get(self,provider_id):return self._providers.get(provider_id)
    @classmethod
    def default(cls,*,include_opencv=False):
        providers=[MockCameraProvider()]
        if include_opencv:providers.append(OpenCVCameraProvider())
        return cls(providers)
