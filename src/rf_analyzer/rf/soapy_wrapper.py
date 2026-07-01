"""
SoapySDR ctypes wrapper for Windows + PothosSDR
Minimal implementation for USRP B200/B210 streaming
"""
import ctypes
import logging
import os
import sys
from ctypes import c_char_p, c_void_p, c_int, c_size_t, c_double, POINTER, Structure
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

# Constants
SOAPY_SDR_RX = 0
SOAPY_SDR_TX = 1
SOAPY_SDR_CF32 = "CF32"

class SoapySDRKwargs(Structure):
    _fields_ = [
        ("size", c_size_t),
        ("keys", POINTER(c_char_p)),
        ("vals", POINTER(c_char_p))
    ]

# Keep references to prevent GC of strings passed to C
_KWARGS_REFS = []

class SoapySDR:
    """ctypes wrapper for SoapySDR.dll from PothosSDR"""
    
    def __init__(self):
        self._lib = None
        self._device = None
        self._stream = None
        self._load_library()
    
    def _load_library(self):
        """Load SoapySDR.dll"""
        pothos_path = r"C:\Program Files\PothosSDR"
        pothos_bin = os.path.join(pothos_path, "bin")
        
        if not os.path.exists(pothos_bin):
            # Fallback to check if in PATH already
            pothos_bin = r"C:\Program Files\PothosSDR\bin"
            if not os.path.exists(pothos_bin):
                raise RuntimeError("PothosSDR not found. Install from https://downloads.myriadrf.org/builds/PothosSDR/")
        
        # Add to PATH
        if pothos_bin not in os.environ.get('PATH', ''):
            os.environ['PATH'] = pothos_bin + os.pathsep + os.environ.get('PATH', '')
        
        # Add DLL directory for Python 3.8+
        if hasattr(os, 'add_dll_directory'):
            try:
                os.add_dll_directory(pothos_bin)
            except Exception as e:
                logger.warning(f"Failed to add DLL directory: {e}")
        
        dll_path = os.path.join(pothos_bin, "SoapySDR.dll")
        
        try:
            self._lib = ctypes.CDLL(dll_path)
            logger.info(f"SoapySDR.dll loaded from {dll_path}")
            self._setup_functions()
        except Exception as e:
            raise RuntimeError(f"Failed to load SoapySDR.dll: {e}")
    
    def _setup_functions(self):
        """Setup C API signatures"""
        lib = self._lib
        
        # Device enumeration and creation
        lib.SoapySDRDevice_enumerate.argtypes = [POINTER(SoapySDRKwargs), POINTER(c_size_t)]
        lib.SoapySDRDevice_enumerate.restype = POINTER(SoapySDRKwargs)
        
        lib.SoapySDRDevice_make.argtypes = [POINTER(SoapySDRKwargs)]
        lib.SoapySDRDevice_make.restype = c_void_p
        
        lib.SoapySDRDevice_lastError.argtypes = []
        lib.SoapySDRDevice_lastError.restype = c_char_p
        
        lib.SoapySDRDevice_unmake.argtypes = [c_void_p]
        lib.SoapySDRDevice_unmake.restype = c_int
        
        # Frequency
        lib.SoapySDRDevice_setFrequency.argtypes = [c_void_p, c_int, c_size_t, c_double, POINTER(SoapySDRKwargs)]
        lib.SoapySDRDevice_setFrequency.restype = c_int
        
        lib.SoapySDRDevice_getFrequency.argtypes = [c_void_p, c_int, c_size_t]
        lib.SoapySDRDevice_getFrequency.restype = c_double
        
        # Sample rate
        lib.SoapySDRDevice_setSampleRate.argtypes = [c_void_p, c_int, c_size_t, c_double]
        lib.SoapySDRDevice_setSampleRate.restype = c_int
        
        lib.SoapySDRDevice_getSampleRate.argtypes = [c_void_p, c_int, c_size_t]
        lib.SoapySDRDevice_getSampleRate.restype = c_double
        
        # Gain
        lib.SoapySDRDevice_setGain.argtypes = [c_void_p, c_int, c_size_t, c_double]
        lib.SoapySDRDevice_setGain.restype = c_int
        
        lib.SoapySDRDevice_getGain.argtypes = [c_void_p, c_int, c_size_t]
        lib.SoapySDRDevice_getGain.restype = c_double
        
        # Stream
        lib.SoapySDRDevice_setupStream.argtypes = [c_void_p, c_int, c_char_p, POINTER(c_size_t), c_size_t, POINTER(SoapySDRKwargs)]
        lib.SoapySDRDevice_setupStream.restype = c_void_p
        
        lib.SoapySDRDevice_closeStream.argtypes = [c_void_p, c_void_p]
        lib.SoapySDRDevice_closeStream.restype = c_int
        
        lib.SoapySDRDevice_activateStream.argtypes = [c_void_p, c_void_p, c_int, c_int, c_size_t]
        lib.SoapySDRDevice_activateStream.restype = c_int
        
        lib.SoapySDRDevice_deactivateStream.argtypes = [c_void_p, c_void_p, c_int, c_int]
        lib.SoapySDRDevice_deactivateStream.restype = c_int
        
        lib.SoapySDRDevice_readStream.argtypes = [c_void_p, c_void_p, POINTER(c_void_p), c_size_t, POINTER(c_int), POINTER(c_int), c_int]
        lib.SoapySDRDevice_readStream.restype = c_int

    def _create_kwargs(self, args_input):
        """Helper to create SoapySDRKwargs safely keeping references"""
        kwargs = SoapySDRKwargs()
        items = []
        
        if isinstance(args_input, str) and args_input:
            parts = args_input.split(',')
            for part in parts:
                part = part.strip()
                if '=' in part:
                    k, v = part.split('=', 1)
                    items.append((k, v))
                elif part:
                    items.append((part, ""))
        elif isinstance(args_input, dict):
            items = list(args_input.items())
            
        if not items:
            kwargs.size = 0
            kwargs.keys = None
            kwargs.vals = None
            return kwargs, []
            
        keys_bytes = []
        vals_bytes = []
        for k, v in items:
            keys_bytes.append(str(k).encode('utf-8'))
            vals_bytes.append(str(v).encode('utf-8'))
            
        kwargs.size = len(items)
        kwargs.keys = (c_char_p * kwargs.size)(*keys_bytes)
        kwargs.vals = (c_char_p * kwargs.size)(*vals_bytes)
        
        return kwargs, [keys_bytes, vals_bytes]

    def enumerate(self, args_input="driver=uhd"):
        """Enumerate devices"""
        args, refs = self._create_kwargs(args_input)
        # Keep refs alive during call (refs list does that)
        
        length = c_size_t(0)
        results = self._lib.SoapySDRDevice_enumerate(ctypes.byref(args), ctypes.byref(length))
        
        devices = []
        for i in range(length.value):
            device_info = {}
            kwargs_struct = results[i]
            for j in range(kwargs_struct.size):
                key = kwargs_struct.keys[j].decode('utf-8', errors='ignore')
                val = kwargs_struct.vals[j].decode('utf-8', errors='ignore')
                device_info[key] = val
            devices.append(device_info)
        
        return devices
    
    def make_device(self, args_input="driver=uhd"):
        """Create device"""
        import time
        args, refs = self._create_kwargs(args_input)
        
        logger.info(f"Creating SoapySDR device with args: {args_input}")
        self._device = self._lib.SoapySDRDevice_make(ctypes.byref(args))
        
        if not self._device:
            error_msg = self._lib.SoapySDRDevice_lastError()
            err_str = "Unknown error"
            if error_msg:
                err_str = error_msg.decode('utf-8')
            logger.error(f"SoapySDR error: {err_str}")
            raise RuntimeError(f"Failed to create device: {err_str}")
            
        time.sleep(1) # Give it a moment (especially for USB re-enumeration)
        return self._device

    def unmake_device(self, device=None):
        if device is None:
            device = self._device
        if device:
             self._lib.SoapySDRDevice_unmake(device)
             if device == self._device:
                 self._device = None

    def set_frequency(self, direction, channel, freq):
        return self._lib.SoapySDRDevice_setFrequency(self._device, direction, channel, freq, None) == 0
    
    def get_frequency(self, direction, channel):
        return self._lib.SoapySDRDevice_getFrequency(self._device, direction, channel)
    
    def set_sample_rate(self, direction, channel, rate):
        return self._lib.SoapySDRDevice_setSampleRate(self._device, direction, channel, rate) == 0
    
    def get_sample_rate(self, direction, channel):
        return self._lib.SoapySDRDevice_getSampleRate(self._device, direction, channel)
    
    def set_gain(self, direction, channel, gain):
        return self._lib.SoapySDRDevice_setGain(self._device, direction, channel, gain) == 0
    
    def get_gain(self, direction, channel):
        return self._lib.SoapySDRDevice_getGain(self._device, direction, channel)
    
    def setup_stream(self, direction, format_str="CF32", channels=[0]):
        num_channels = len(channels)
        channel_array = (c_size_t * num_channels)(*channels)
        args, refs = self._create_kwargs("")
        self._stream = self._lib.SoapySDRDevice_setupStream(
            self._device, direction, format_str.encode(), channel_array, num_channels, ctypes.byref(args)
        )
        if not self._stream:
            raise RuntimeError("Failed to setup stream")
        return self._stream
    
    def close_stream(self):
        if self._stream:
            self._lib.SoapySDRDevice_closeStream(self._device, self._stream)
            self._stream = None

    def activate_stream(self):
        if self._stream:
            return self._lib.SoapySDRDevice_activateStream(self._device, self._stream, 0, 0, 0) == 0
        return False
        
    def deactivate_stream(self):
        if self._stream:
            return self._lib.SoapySDRDevice_deactivateStream(self._device, self._stream, 0, 0) == 0
        return False
        
    def read_stream(self, num_samples, timeout_us=1000000):
        if not self._stream:
            return np.array([], dtype=np.complex64)
            
        buffer = np.zeros(num_samples, dtype=np.complex64)
        buffer_ptr = buffer.ctypes.data_as(c_void_p)
        buffs = (c_void_p * 1)(buffer_ptr)
        
        flags = c_int(0)
        time_ns = c_int(0)
        
        ret = self._lib.SoapySDRDevice_readStream(
            self._device, self._stream, buffs, num_samples, ctypes.byref(flags), ctypes.byref(time_ns), timeout_us
        )
        
        if ret <= 0:
            return np.array([], dtype=np.complex64)
            
        return buffer[:ret]
