# ec2m

[English README](./README.md)

`ec2m` — терминальная утилита для просмотра локальных метрик Linux и нативных AWS EC2 / CloudWatch метрик прямо из терминала.

Утилита рассчитана на запуск по требованию:

- не требует веб-консоли AWS
- не требует постоянно работающего фонового сервиса
- особенно удобна для burstable EC2-инстансов, где важны CPU credits

Исходный код утилиты находится в `src/ec2m.py`.

## Установка

Установка последней стабильной версии:

```bash
curl -fsSL https://github.com/Danila-F/ec2m/releases/latest/download/install-ec2m.sh | bash
```

Установка в свой prefix:

```bash
curl -fsSL https://github.com/Danila-F/ec2m/releases/latest/download/install-ec2m.sh | INSTALL_PREFIX=/opt/ec2m bash
```

Установка конкретного релиза:

```bash
curl -fsSL https://github.com/Danila-F/ec2m/releases/download/v2026.03.31/install-ec2m.sh | bash
```

Установка текущей версии из ветки `main`:

```bash
curl -fsSL https://raw.githubusercontent.com/Danila-F/ec2m/main/install-ec2m.sh | bash
```

## Удаление

```bash
curl -fsSL https://github.com/Danila-F/ec2m/releases/latest/download/install-ec2m.sh | bash -s -- --uninstall
```

## Что устанавливается

- `ec2m`
- `ec2-metrics`
- встроенные Python-зависимости, необходимые для работы утилиты

Установщик проверяет наличие `python3` и `pip`, при необходимости устанавливает их, а затем устанавливает или обновляет утилиту.

## Что умеет показывать

- локальные CPU, память, диск и load average
- нативные EC2 / CloudWatch метрики, включая `CPUUtilization`, `CPUCreditBalance`, `CPUCreditUsage`, сеть и status checks
- live-режим с обновлением данных в терминале
- JSON-вывод для скриптов

## Базовое использование

Показать стандартную сводку:

```bash
ec2m
```

Показать список доступных метрик:

```bash
ec2m --list
```

Показать live-режим:

```bash
ec2m --live
```

Показать компактный watch-режим:

```bash
ec2m --watch
```

Показать только выбранные метрики:

```bash
ec2m -m local:cpu -m local:memory -m AWS/EC2:CPUUtilization
```

Показать JSON:

```bash
ec2m --json
```

## Что нужно для AWS-метрик

Чтобы читать AWS-метрики изнутри EC2-инстанса, этому инстансу нужна IAM role с правами на чтение CloudWatch.

Если AWS-доступ не настроен, `ec2m` всё равно будет работать для локальных метрик машины.

## Справка и диагностика

```bash
ec2m --help
ec2m --version
ec2m --release-info
ec2m --doctor
```

## Настройка AWS

Утилита умеет печатать встроенный гайд по настройке AWS:

```bash
ec2m --setup-aws
```

Для обычного on-demand режима EC2-инстансу достаточно прав на чтение CloudWatch.

## Примеры

```bash
ec2m
ec2m --live
ec2m --watch
ec2m --doctor
ec2m -m local:disk -m AWS/EC2:CPUCreditBalance
ec2m -m AWS/EC2:NetworkIn:Sum:300 -m AWS/EC2:NetworkOut:Sum:300
ec2m -m local:cpu -m local:memory -m AWS/EC2:CPUUtilization
ec2m --json
```

## Проверка установки

После установки:

```bash
ec2m --version
ec2m --help
```

## Версионирование

Стабильные версии публикуются git-тегами формата `vYYYY.MM.DD`.

Ссылка на установщик последней стабильной версии:

```bash
curl -fsSL https://github.com/Danila-F/ec2m/releases/latest/download/install-ec2m.sh | bash
```

Ссылка на установщик конкретного релиза:

```bash
curl -fsSL https://github.com/Danila-F/ec2m/releases/download/v2026.03.31/install-ec2m.sh | bash
```

Релизы для следующих тегов публикуются автоматически через GitHub Actions при пуше тега, подходящего под шаблон `v*`.
