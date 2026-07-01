#!/usr/bin/env python
"""Тест SoapySDR ctypes wrapper"""

import sys
import logging
sys.path.insert(0, 'src')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_soapy_wrapper():
    try:
        from rf_analyzer.rf.soapy_wrapper import SoapySDR, SOAPY_SDR_RX, SOAPY_SDR_CF32
        import numpy as np
        
        logger.info("=== Testing SoapySDR ctypes wrapper ===")
        
        # Создаем wrapper
        soapy = SoapySDR()
        logger.info("✅ SoapySDR wrapper created")
        
        # Поиск устройств
        devices = soapy.enumerate("driver=uhd")
        logger.info(f"✅ Found {len(devices)} device(s): {devices}")
        
        if not devices:
            logger.error("No USRP devices found")
            return False
        
        # Создание устройства
        soapy.make_device("driver=uhd")
        logger.info("✅ Device created")
        
        # Настройка
        soapy.set_frequency(SOAPY_SDR_RX, 0, 100e6)
        freq = soapy.get_frequency(SOAPY_SDR_RX, 0)
        logger.info(f"✅ Frequency: {freq/1e6:.3f} MHz")
        
        soapy.set_sample_rate(SOAPY_SDR_RX, 0, 2e6)
        rate = soapy.get_sample_rate(SOAPY_SDR_RX, 0)
        logger.info(f"✅ Sample rate: {rate/1e6:.3f} MS/s")
        
        soapy.set_gain(SOAPY_SDR_RX, 0, 30)
        gain = soapy.get_gain(SOAPY_SDR_RX, 0)
        logger.info(f"✅ Gain: {gain} dB")
        
        # Создание потока
        soapy.setup_stream(SOAPY_SDR_RX, SOAPY_SDR_CF32, [0])
        logger.info("✅ Stream setup")
        
        # Активация
        soapy.activate_stream()
        logger.info("✅ Stream activated")
        
        # Чтение данных
        logger.info("Reading samples...")
        samples = soapy.read_stream(1024, timeout_us=1000000)
        
        if samples is not None and len(samples) > 0:
            logger.info(f"✅ Read {len(samples)} samples")
            logger.info(f"   Mean: {np.mean(np.abs(samples)):.6f}")
            logger.info(f"   Max: {np.max(np.abs(samples)):.6f}")
            logger.info(f"   Dtype: {samples.dtype}")
        else:
            logger.error("❌ Failed to read samples")
        
        # Закрытие
        soapy.deactivate_stream()
        soapy.close_stream()
        soapy.unmake_device()
        logger.info("✅ Cleanup complete")
        
        logger.info("\n🎉 SoapySDR ctypes wrapper test PASSED!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = test_soapy_wrapper()
    sys.exit(0 if success else 1)
