from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, JSON
from sqlalchemy.sql import func
from app.database import Base
from app.schemas.telemetry import DeviceStatus as StatusEnum

class Telemetry(Base):
    __tablename__ = "telemetry"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, index=True, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Metrics
    velocity_rms_mm_s = Column(Float, nullable=False)
    accel_peak_g = Column(Float, nullable=False)
    crest_factor = Column(Float, nullable=False)
    temperature_c = Column(Float, nullable=False)
    dominant_freq_hz = Column(Float, nullable=False)
    
    # Spectrum (храним как JSON, так как массивы могут меняться)
    spectrum_bins = Column(JSON, nullable=False)
    
    # Status
    status = Column(String, nullable=False)  # Храним как строку для простоты
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
