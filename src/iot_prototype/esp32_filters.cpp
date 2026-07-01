// Digital High Pass Filter for ESP32 (Gravity Removal)
// Этот код нужно вставить в твою прошивку перед FFT

#define ALPHA 0.98f // Коэффициент фильтрации (чем ближе к 1.0, тем медленнее)

float gravity_x = 0, gravity_y = 0, gravity_z = 0;

void removeGravity(float ax, float ay, float az, float *out_x, float *out_y, float *out_z) {
    // 1. Ищем постоянную составляющую (Гравитацию)
    gravity_x = ALPHA * gravity_x + (1.0f - ALPHA) * ax;
    gravity_y = ALPHA * gravity_y + (1.0f - ALPHA) * ay;
    gravity_z = ALPHA * gravity_z + (1.0f - ALPHA) * az;
    
    // 2. Вычитаем её из сигнала
    *out_x = ax - gravity_x;
    *out_y = ay - gravity_y;
    *out_z = az - gravity_z;
    
    // Результат: Чистая вибрация без дрейфа "DC Bias"
}

// Windowing Function (Hanning Window)
// Обязательно примени перед FFT, иначе будут "зубцы" по краям спектра
void applyHanningWindow(float *data, int sampleCount) {
    for (int i = 0; i < sampleCount; i++) {
        float multiplier = 0.5f * (1.0f - cos(2.0f * PI * i / (sampleCount - 1)));
        data[i] = data[i] * multiplier;
    }
}
