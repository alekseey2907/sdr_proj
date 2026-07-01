# Быстрый старт удаленного обслуживания Orange Pi (RF + Acoustic)

Этот документ для самого простого сценария: удаленный доступ, обновление и логи.

## 1) Что нужно установить

На вашем ноутбуке (Windows):

1. Tailscale: https://tailscale.com/download
2. OpenSSH Client (обычно уже есть в Windows 10/11)

На каждом Orange Pi:

1. Tailscale
2. git
3. systemd-сервисы ваших проектов

## 2) Зачем Tailscale

Tailscale дает приватную защищенную сеть между вашим ноутбуком и Orange Pi.
Не нужно открывать порты на роутере и не нужен белый IP.

После установки у устройства будет адрес вида `100.x.x.x` или имя `device.tailnet.ts.net`.

## 3) Установка Tailscale на Orange Pi

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

После команды откроется ссылка авторизации. Зайдите в тот же аккаунт Tailscale, что на ноутбуке.

Проверка:

```bash
tailscale ip -4
```

## 4) Проверка удаленного SSH

С ноутбука:

```powershell
ssh root@100.64.10.25
```

Где `100.64.10.25` - Tailscale IP Orange Pi.

## 5) Обновление проектов одной командой

Скрипт в этом репозитории:

- `scripts/remote_update.ps1`

### Обновить только RF проект

```powershell
./scripts/remote_update.ps1 -TargetHost 100.64.10.25 -Project rf -Branch main
```

### Обновить только Acoustic проект

```powershell
./scripts/remote_update.ps1 -TargetHost 100.64.10.25 -Project acoustic -Branch main
```

### Обновить оба проекта

```powershell
./scripts/remote_update.ps1 -TargetHost 100.64.10.25 -Project all -Branch main
```

По умолчанию пути такие:

- RF: `/opt/skyshield`
- Acoustic: `/opt/skyshield-acoustic`

Если у вас другие пути/имена сервисов - передайте параметры `-RfRoot`, `-AcousticRoot`, `-RfBackendService`, `-RfWorkerService`, `-AcousticBackendService`, `-AcousticWorkerService`.

## 6) Просмотр логов

Скрипт:

- `scripts/remote_logs.ps1`

### Логи RF в реальном времени

```powershell
./scripts/remote_logs.ps1 -TargetHost 100.64.10.25 -Project rf
```

### Логи Acoustic в реальном времени

```powershell
./scripts/remote_logs.ps1 -TargetHost 100.64.10.25 -Project acoustic
```

### Логи всех сервисов без follow

```powershell
./scripts/remote_logs.ps1 -TargetHost 100.64.10.25 -Project all -NoFollow
```

## 6.1) Команды одной кнопкой (копировать как есть)

Ниже команды для PowerShell на ноутбуке. Выполняйте по одной.

### Подготовка сессии

```powershell
cd D:\projects\sdr\sdr_rf_analyzer
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
```

### Проверка удаленных логов RF (10-20 строк и Ctrl+C)

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\remote_logs.ps1 -TargetHost 100.70.123.76 -Project rf
```

### Обновить только RF

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\remote_update.ps1 -TargetHost 100.70.123.76 -Project rf -Branch main
```

### Обновить RF + Acoustic

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\remote_update.ps1 -TargetHost 100.70.123.76 -Project all -Branch main
```

### Если на Orange Pi еще нет git-копии RF-проекта

```powershell
ssh root@100.70.123.76
mkdir -p /opt/skyshield
cd /opt/skyshield
git clone https://github.com/alekseey2907/sdr_proj.git .
exit
```

## 7) Что требуется от вас

1. Установить Tailscale на ноутбук и на каждую Orange Pi.
2. Прислать/зафиксировать для себя таблицу:
   - имя клиента,
   - Tailscale IP,
   - логин SSH,
   - путь RF проекта,
   - путь Acoustic проекта,
   - имена systemd-сервисов.
3. Убедиться, что оба проекта на Orange Pi лежат в git-репозиториях (скрипт обновляет через git pull).

## 8) Важные замечания

1. Скрипт обновления делает `git checkout <branch>` и `git pull --ff-only`.
2. Если локально на Orange Pi есть ручные правки, `pull --ff-only` может не пройти. Тогда сначала сохраните/уберите ручные изменения.
3. Для первого подключения можно продолжать использовать PuTTY, но через Tailscale IP.
