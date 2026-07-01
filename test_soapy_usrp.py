#!/usr/bin/env python
"""Тест подключения USRP через SoapySDR"""

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_soapy_usrp():
    try:
        import SoapySDR
        logger.info("SoapySDR module imported successfully")
        
        # Поиск устройств
        logger.info("Searching for UHD devices...")
        results = SoapySDR.Device.enumerate("driver=uhd")
        
        if not results:
            logger.error("No USRP devices found")
            return False
        
        logger.info(f"Found {len(results)} device(s):")
        for i, result in enumerate(results):
            logger.info(f"  Device {i}: {result}")
        
        # Подключение к устройству
        logger.info("Opening device...")
        sdr = SoapySDR.Device({"driver": "uhd"})
        
        # Получение информации
        logger.info(f"Hardware key: {sdr.getHardwareKey()}")
        logger.info(f"Driver key: {sdr.getDriverKey()}")
        logger.info(f"Hardware info: {sdr.getHardwareInfo()}")
        
        # Частотные диапазоны
        freq_ranges = sdr.getFrequencyRange(SoapySDR.SOAPY_SDR_RX, 0)
        logger.info(f"Frequency ranges: {freq_ranges}")
        
        # Sample rate диапазоны
        sample_ranges = sdr.getSampleRateRange(SoapySDR.SOAPY_SDR_RX, 0)
        logger.info(f"Sample rate ranges: {sample_ranges}")
        
        # Настройка базовых параметров
        logger.info("Configuring device...")
        sdr.setFrequency(SoapySDR.SOAPY_SDR_RX, 0, 100e6)
        sdr.setSampleRate(SoapySDR.SOAPY_SDR_RX, 0, 2e6)
        sdr.setGain(SoapySDR.SOAPY_SDR_RX, 0, 30)
        
        actual_freq = sdr.getFrequency(SoapySDR.SOAPY_SDR_RX, 0)
        actual_rate = sdr.getSampleRate(SoapySDR.SOAPY_SDR_RX, 0)
        actual_gain = sdr.getGain(SoapySDR.SOAPY_SDR_RX, 0)
        
        logger.info(f"Configured - Freq: {actual_freq/1e6:.3f} MHz, Rate: {actual_rate/1e6:.3f} MHz, Gain: {actual_gain} dB")
        
        # Создание потока
        logger.info("Setting up RX stream...")
        stream = sdr.setupStream(SoapySDR.SOAPY_SDR_RX, SoapySDR.SOAPY_SDR_CF32)
        
        # Активация потока
        logger.info("Activating stream...")
        sdr.activateStream(stream)
        
        # Чтение нескольких сэмплов
        import numpy as np
        buff = np.zeros(1024, dtype=np.complex64)
        
        logger.info("Reading samples...")
        sr = sdr.readStream(stream, [buff], 1024, timeoutUs=1000000)
        
        if sr.ret > 0:
            logger.info(f"Successfully read {sr.ret} samples")
            logger.info(f"Sample mean: {np.mean(np.abs(buff[:sr.ret])):.6f}")
            logger.info(f"Sample max: {np.max(np.abs(buff[:sr.ret])):.6f}")
        else:
            logger.error(f"Read failed with code: {sr.ret}")
        
        # Закрытие
        logger.info("Cleaning up...")
        sdr.deactivateStream(stream)
        sdr.closeStream(stream)
        
        logger.info("Test completed successfully!")
        return True
        
    except ImportError as e:
        logger.error(f"SoapySDR not available: {e}")
        return False
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    test_soapy_usrp()
