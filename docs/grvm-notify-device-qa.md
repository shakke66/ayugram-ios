# GRVM Notify — журнал device QA

Этот журнал заполняется только после установки фактической IPA и PWA с production origin на физическое устройство. Пустые поля не означают PASS. Для каждого прогона приложить наблюдаемые шаги, а при ошибке — безопасный фрагмент лога без login token, auth URL, endpoint/ключей subscription, account ID, push payload и текста сообщения.

## Provenance прогона

- Native Git SHA: `[заполнить перед device run]`
- Web Git SHA: `[заполнить перед device run]`
- GitHub workflow/run: `[заполнить перед device run]`
- IPA SHA-256: `[заполнить перед device run]`
- PWA origin/deployment: `[заполнить перед device run]`
- Устройство / iOS/iPadOS: `[заполнить перед device run]`
- Исполнитель / дата: `[заполнить перед device run]`

### GN01 — Add to Home Screen and click count

- **Предпосылки:** iOS/iPadOS 16.4+; Safari открыт на production setup URL; PWA ещё не установлена.
- **Проверка:** добавить GRVM Notify на Home Screen, запустить только с иконки и записать число обязательных пользовательских нажатий от setup page до native confirmation и возврата в PWA. Отдельно отметить, сработал ли automatic custom-scheme open или понадобилась видимая fallback-кнопка.
- **Ожидаемый результат:** до установки показана понятная инструкция; после standalone-запуска доступен один основной setup flow без QR, copy/paste, Telegram password и лишнего pre-Safari alert. Нулевой click count не заявляется без фактического наблюдения.
- **Статус:**
- **Наблюдение:**

### GN02 — Permission denied/recovery

- **Предпосылки:** установленная PWA; notification permission ещё не предоставлен.
- **Проверка:** отказать в permission prompt, повторно открыть setup/management surface, выполнить описанное восстановление через системные настройки и повторить регистрацию.
- **Ожидаемый результат:** отказ не запускает login-token flow и не создаёт ложную готовность; UI объясняет recovery, а повтор после разрешения проходит через тот же сериализованный setup flow.
- **Статус:**
- **Наблюдение:**

### GN03 — Same-device auth and session in Devices

- **Предпосылки:** одна native Telegram account и одна незалогиненная PWA; native app готов и разблокирован.
- **Проверка:** начать setup в PWA, перейти по `grvmgram://notify-auth`, проверить точное имя account в confirmation, подтвердить Web-сессию и открыть штатный список Devices.
- **Ожидаемый результат:** rotating token не показывается и не копируется; подтверждается ровно выбранная account; Web-сессия появляется в Devices, а native UI сообщает только `Web-сессия подключена`, не заявляя о permission/subscription.
- **Статус:**
- **Наблюдение:**

### GN04 — Single-account block under login churn

- **Предпосылки:** успешная single-account PWA-регистрация; подготовлена возможность login/logout второй Web account во время pending register.
- **Проверка:** попытаться добавить вторую Web account до setup, во время server acknowledgement и после готовности; отдельно изменить account set во время register/unregister и повторить операцию после отказа.
- **Ожидаемый результат:** preflight блокирует две Web accounts до mutation subscription/settings; generation change отменяет либо откатывает captured registration; одна subscription не привязывается к нескольким accounts; после disconnect возможен явный re-pair.
- **Статус:**
- **Наблюдение:**

### GN05 — Passcode OFF closed plain preview

- **Предпосылки:** local passcode в PWA выключен; PWA полностью закрыта; plain preview разрешён Telegram privacy settings.
- **Проверка:** доставить push с различимыми sender/body и убедиться, что Service Worker показывает фактический full preview без открытого PWA client.
- **Ожидаемый результат:** plain full preview появляется стабильно только для реально доказанного OFF-режима; notification icon/branding корректны; hosting URL/referrer не получает account/chat/message IDs.
- **Статус:**
- **Наблюдение:**

### GN06 — Passcode ON closed generic fallback

- **Предпосылки:** local passcode включён; PWA полностью закрыта; push требует decrypt.
- **Проверка:** доставить encrypted push при cold Service Worker, включая storage/base64/JSON/decrypt failure fixtures.
- **Ожидаемый результат:** показывается только generic `GRVM Notify` / `Новое сообщение` без sender, body и IDs; `push_key` не хранится в plaintext Service Worker storage; malformed data не приводит к silent drop или privacy leak.
- **Статус:**
- **Наблюдение:**

### GN07 — Live unlocked decrypt

- **Предпосылки:** local passcode включён; существует живой разблокированный PWA client.
- **Проверка:** доставить encrypted push при foreground и background живом client, затем заблокировать PWA и повторить.
- **Ожидаемый результат:** preview расшифровывается только через live unlocked client; после lock/dead client применяется generic fallback, а ключ и decrypted payload не попадают в logs/storage.
- **Статус:**
- **Наблюдение:**

### GN08 — Foreground/background/killed-IPA click

- **Предпосылки:** paired account; валидный notification target; GRVMgram поочерёдно foreground, background и killed.
- **Проверка:** нажать notification во всех трёх состояниях; отметить automatic scheme open и видимую landing fallback-кнопку; повторить с native app lock до unlock.
- **Ожидаемый результат:** все UIKit admission paths используют один coordinator; killed launch не теряет URL; обработка ждёт readiness/unlock и не передаёт malformed `grvmgram` URL в stock routing.
- **Статус:**
- **Наблюдение:**

### GN09 — Exact user/group/channel/message and forum fallback

- **Предпосылки:** paired account содержит доступные user chat, basic group, supergroup/channel и forum topic с известными server message IDs.
- **Проверка:** открыть notification для каждого peer type и конкретного message; для topic проверить положительный `thread_id`, отсутствие topic metadata и deleted/inaccessible message.
- **Ожидаемый результат:** выбираются точные CloudUser/CloudGroup/CloudChannel namespaces, account и message; валидный thread открывает topic, иначе применяется parent forum/chat fallback без cross-account перехода.
- **Статус:**
- **Наблюдение:**

### GN10 — Missing peer/malformed payload safety

- **Предпосылки:** fixtures с unknown account, disagreement `user_id`/`push_accounts`, отсутствующим peer, несколькими peer kinds, non-positive/unsafe ID и message ID вне Int32.
- **Проверка:** нажать каждое уведомление и прямую malformed `grvmgram://notify-open` ссылку.
- **Ожидаемый результат:** Web открывает безопасный PWA root либо landing без ID; native показывает локализованную ошибку/timeout и никогда не выбирает произвольные account/chat/message.
- **Статус:**
- **Наблюдение:**

### GN11 — Register/unregister network retry

- **Предпосылки:** управляемое отключение сети до и после server acknowledgement для register и unregister.
- **Проверка:** оборвать каждый этап, восстановить сеть и повторить ту же операцию без перезапуска setup.
- **Ожидаемый результат:** failed register не коммитит candidate `registeredDevice`; failed unregister сохраняет retry material и не запускает logout/local cleanup; повтор использует корректный token/account set и завершается после server acknowledgement.
- **Статус:**
- **Наблюдение:**

### GN12 — PWA/native/Devices revoke

- **Предпосылки:** активная paired Web-сессия и push subscription.
- **Проверка:** отдельно выполнить PWA disconnect, native `Отключить` и ручной revoke в Telegram Devices; после каждого варианта доставить контрольный push и открыть PWA/native management surface.
- **Ожидаемый результат:** server delivery прекращается; state очищается только после подтверждённого unregister/terminate либо успешной reconciliation без session hash; partial/error stage остаётся retryable и не выдаётся за disconnect.
- **Статус:**
- **Наблюдение:**

### GN13 — Removed native account/orphaned ownership

- **Предпосылки:** PWA paired с account, которая затем logout/удалена из GRVMgram; другая native account остаётся активной.
- **Проверка:** открыть settings, auth/click URL и notification после удаления owner; затем проверить Devices-инструкцию и ручное восстановление.
- **Ожидаемый результат:** состояние показывает orphaned ownership и сохраняет session hash до подтверждённого revoke; coordinator не retarget’ит запрос на оставшуюся account и не выполняет cross-account navigation.
- **Статус:**
- **Наблюдение:**

### GN14 — Relaunch/account switch/seven-day Sideloadly re-sign

- **Предпосылки:** рабочая pairing; две native accounts; зафиксированы IPA/PWA версии перед семидневным re-sign cycle.
- **Проверка:** перезапустить PWA и GRVMgram, переключить active native account, выполнить Sideloadly re-sign/reinstall IPA через семь дней и повторить delivery/click/revoke smoke.
- **Ожидаемый результат:** install-wide ownership остаётся привязано к public user ID, а не active record; PWA subscription продолжает работать независимо от re-sign IPA; после переустановки не происходит silent retarget или самовольный second-account pair.
- **Статус:**
- **Наблюдение:**
