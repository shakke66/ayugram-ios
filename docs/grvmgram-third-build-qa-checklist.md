# GRVMgram third-build targeted QA checklist

Этот checklist покрывает только изменённые second-build проверки и adjacent regression guards, подтверждённые фактическим third-build diff. Он не повторяет остальные 84 карточки предыдущего checklist.

## Provenance внешней сборки и device run

- Build/IPA: `[заполнить после отдельной сборки]`
- Git SHA: `[заполнить]`
- Workflow/run: `[заполнить либо N/A для локальной сборки]`
- IPA SHA-256: `[заполнить]`
- Устройство / iOS: `[заполнить перед device run]`
- Язык по умолчанию: `Русский`, кроме явно указанной EN-проверки.

Поля выше являются только placeholders. Этот документ не заявляет о наличии готовой IPA, успешной установке или фактическом device PASS. `Ожидаемый результат` каждой карточки описывает критерий будущей проверки, а не уже полученный результат.

## Отдельная проверка context menu

### ST15 — Прочитать сообщение

- **Причина включения:** изменён action path: выбранное входящее сообщение теперь запускает local read-to-top для точного chat/topic, а не чтение только до индекса выбранного сообщения.
- **Точный RU UI path:** нижняя вкладка `Настройки` → `Настройки GRVMgram` → `Основное` → включить `Не отправлять отчёты о прочтении`; затем нижняя вкладка `Чаты` → нужный чат или форум-тема → удерживать любое входящее cloud-сообщение → `Прочитать сообщение`.
- **Предпосылки:** два клиента A/B; B отправляет A минимум три непрочитанных сообщения; отдельно подготовлены форум-тема с unread и соседняя тема/чат с unread.
- **Шаги:** на A удержать старое или среднее сообщение и выбрать `Прочитать сообщение`; повторить в форум-теме; проверить состояние на B и untouched unread в соседней теме/чате.
- **Ожидаемый результат:** весь текущий dialog/topic локально прочитан до верхнего cloud-сообщения независимо от выбранной строки; server read receipt на B не появляется; соседние chats/topics и другой account не меняются. В `Избранном`, secret chat и scheduled/custom chat action отсутствует.
- **Статус:**
- **Наблюдение:**

## Shared setup: consumable media и stability

Выполнить один раз перед `ST20`, `ST21`, `ST22` и `Q05`:

- Использовать два клиента A/B: A — проверяемый iPhone, B — sender/reference client.
- На B отправить A отдельные unopened fixtures: one-view photo, one-play voice и one-play round video. Для фото подготовить полностью загруженный и blur/ещё не загруженный fixtures; рядом оставить обычное старое и новое media.
- На A подготовить `Настройки` → `Настройки GRVMgram` → `Основное` → `Сохранять удалённые сообщения` в состояниях OFF и ON.
- Подготовить destinations `Избранное`, обычный личный чат и форум → конкретная тема; отдельно иметь item с недоступными/неподдерживаемыми bytes.
- Для каждой необратимой ветки использовать отдельный fixture; один one-view item не переиспользовать между mutually exclusive checks.

### ST20 — Сжечь

- **Причина включения:** изменены terminal fetch, fail-closed preservation, порядок dismiss → confirmation и first-open consumers одноразового media.
- **Точный RU UI path:** `Чаты` → DM с unopened one-view/one-play media → удерживать сообщение → `Сжечь` → confirmation `Сжечь`; переключатель: `Настройки` → `Настройки GRVMgram` → `Основное` → `Сохранять удалённые сообщения`.
- **Предпосылки:** выполнен shared consumable setup; есть отдельные fixtures для OFF, ON-loaded, ON-blurred и network/error cases.
- **Шаги:** при OFF выполнить Burn и подтвердить штатный consume/receipt; при ON повторить для loaded и blurred media; для error case отключить сеть до завершения fetch либо использовать отсутствующие bytes.
- **Ожидаемый результат:** OFF выполняет direct consume. ON consumes только после exact fetch, положительных bytes и durable local save; после успеха item доступен для replay. Ошибка видима и оставляет media unconsumed; empty completion не даёт silent no-op. Confirmation появляется после закрытия context menu.
- **Статус:**
- **Наблюдение:**

### ST21 — Повтор one-view/one-play

- **Причина включения:** это обязательный guard общей preservation preparation и first-open path; требуется доказать exact standalone viewer и отсутствие второго receipt.
- **Точный RU UI path:** после успешного сохранения/consume: `Чаты` → исходный chat/topic → нажать сохранённую запись; альтернативно удерживать её → `Воспроизвести снова`.
- **Предпосылки:** выполнен shared consumable setup; успешно сохранены photo, voice и round; рядом есть другие media; B показывает receipt первого открытия.
- **Шаги:** для каждого типа открыть запись обычным tap и через `Воспроизвести снова`; повторить после relaunch.
- **Ожидаемый результат:** оба route открывают exact выбранный resource, а не соседнее media; voice/round playback scoped к этому сообщению; B видит только первый receipt. При отсутствии durable bytes action отсутствует либо показывает typed unavailable; blur не снимается побочным эффектом.
- **Статус:**
- **Наблюдение:**

### ST22 — Переслать локальную копию

- **Причина включения:** исправлен critical freeze: preparation должна принадлежать peer picker, быть cancellable/bounded и завершать success, error, empty completion, timeout и cancel.
- **Точный RU UI path:** `Чаты` → удерживать deleted/TTL/one-view/copy-protected item → `Переслать локальную копию` → в picker выбрать последовательно `Избранное`, обычный чат и форум → нужная тема.
- **Предпосылки:** выполнен shared consumable setup; есть item с durable bytes и unavailable/unsupported item.
- **Шаги:** отправить валидный item в три destinations; отдельно запустить preparation и нажать cancel; затем проверить unavailable/timeout path.
- **Ожидаемый результат:** success создаёт standalone upload без forward header, callback, TTL/view-once и copy protection, сохраняя caption/entities; progress завершается. Cancel возвращает интерактивный picker без отправки. На error/empty/timeout видимая ошибка показана поверх picker, overlay снят, source не меняется; бесконечного loading нет.
- **Статус:**
- **Наблюдение:**

### Q05 — Стабильность mixed run

- **Причина включения:** предыдущий общий FAIL был вызван hard freeze local-copy; затронуты несколько async media consumers и terminal paths.
- **Точный RU UI path:** использовать маршруты shared consumable setup; затем `Настройки` → список аккаунтов в шапке → A ↔ B; закрыть приложение через iOS app switcher и запустить снова; повторно открыть `Настройки GRVMgram` и message context menus.
- **Предпосылки:** assertions `ST20`, `ST21` и `ST22` выполнены хотя бы по одному разу; на установке есть два Telegram-аккаунта.
- **Шаги:** 15 минут чередовать settings, context menus, one-view open/Burn/replay, local-copy success/cancel/error, A ↔ B и два cold relaunch.
- **Ожидаемый результат:** нет crash, hard freeze, launch loop, вечного overlay, потери media, duplicate send/receipt или смешивания account data; после каждого error/cancel интерфейс остаётся интерактивным.
- **Статус:**
- **Наблюдение:**

## Shared setup: client-wide settings и account isolation

Выполнить один раз перед `Q01`:

- Добавить в одну установку два Telegram-аккаунта A/B.
- На A задать заметный snapshot через `Настройки GRVMgram` → `Оформление` → `Иконка приложения`; `Настройки GRVMgram` → `Основное` → `Не отправлять отчёты о прочтении`; `Настройки GRVMgram` → `Чаты` → `Показывать реакции в группах`.
- В A и B подготовить разные локально сохранённые удалённые сообщения. Scoped archive: нужный chat/topic → удерживать аватар в шапке → `Архивы GRVMgram` → `Просмотреть удалённые`.

### Q01 — Единые настройки клиента

- **Причина включения:** settings storage и migration переведены с per-account map на единый client-wide snapshot; account-scoped archives/revisions/media/read data должны остаться изолированными.
- **Точный RU UI path:** нижняя вкладка `Настройки` → `Настройки GRVMgram` → указанные в shared setup rows; затем `Настройки` → список аккаунтов в шапке → B → обратно A. Isolation: чат каждого account → удерживать аватар в шапке → `Архивы GRVMgram` → `Просмотреть удалённые`.
- **Предпосылки:** выполнен shared client-settings setup; A выбран как исходный account migration; у A/B различимые archive fixtures.
- **Шаги:** изменить три значения на A, перейти A → B → A, выполнить cold relaunch и повторить A → B; на обоих accounts открыть scoped archives.
- **Ожидаемый результат:** одинаковые settings value и UI отображаются на A/B после переходов; новое изменение с B сразу становится общим. Archive B не появляется в A и наоборот; message revisions, preserved media и unread/read state не смешиваются между accounts.
- **Статус:**
- **Наблюдение:**

## Removals: отсутствие GRVM-функции и surviving stock behavior

### G09 — Удалённая отложка / штатное Schedule Messages

- **Причина включения:** feature slice удалён полностью; необходимо доказать отсутствие schema/UI/runtime и сохранность штатного Telegram scheduling и соседней отправки без звука.
- **Точный RU UI path:** `Настройки` → `Настройки GRVMgram` → `Основное` → раздел `Гост-режим`; stock guard: `Чаты` → обычный cloud-chat → ввести текст → удерживать кнопку отправки → `Отправить позже`.
- **Предпосылки:** обычный чат без slow mode; доступны RU и EN; подготовлено сообщение для native scheduling.
- **Шаги:** в RU/EN убедиться, что `Использовать отложенные сообщения` / `Schedule Messages` отсутствует; обычным tap отправить сообщение; через `Отправить позже` назначить время и открыть scheduled messages; проверить `Отправлять без звука` в GRVM settings.
- **Ожидаемый результат:** удалённой строки, скрытого auto-delay и GRVM schedule side effects нет; native schedule picker/queue/enqueue и отправка без звука работают штатно.
- **Статус:**
- **Наблюдение:**

### A06 — Удалённое отключение кастомных фонов / штатные обои

- **Причина включения:** полностью удалены row/schema/policy/runtime branch; guard должен сохранить stock global/per-chat wallpaper flow и приоритет forced preview wallpaper.
- **Точный RU UI path:** `Настройки` → `Настройки GRVMgram` → `Оформление`; stock guard: `Настройки` → `Оформление` → `Обои для чатов` → выбрать собственное фото/фон, затем открыть чат с отдельно заданным оформлением.
- **Предпосылки:** доступны RU и EN; подготовлены global custom wallpaper и чат с отдельным wallpaper/theme.
- **Шаги:** убедиться, что `Отключить пользовательские фоны` / `Disable Custom Backgrounds` отсутствует; установить или сменить global wallpaper, открыть per-chat wallpaper, выполнить relaunch.
- **Ожидаемый результат:** удалённой строки нет; custom wallpapers устанавливаются, отображаются и сохраняются; per-chat override не теряется; preview/forced wallpaper имеет штатный приоритет. Legacy value не проявляется в UI и не влияет на renderer.
- **Статус:**
- **Наблюдение:**

### C15 — Удалённые простые replies / штатный reply renderer

- **Причина включения:** удалён весь toggle/policy/runtime slice; требуется guard штатного Telegram name-color reply renderer и навигации.
- **Точный RU UI path:** `Настройки` → `Настройки GRVMgram` → `Чаты` → раздел `Сообщения`; stock guard: `Чаты` → чат → удерживать сообщение Premium/name-colored peer → `Ответить` → отправить reply → нажать reply block.
- **Предпосылки:** доступны RU и EN; есть ordinary peer и peer с preset/collectible name color либо Premium presentation; желательно исходное сообщение с media thumbnail.
- **Шаги:** убедиться, что `Отключить цветные ответы` / `Disable Colored Replies` отсутствует; создать replies к ordinary и colored peer; перейти по reply к source; повторить smoke после relaunch.
- **Ожидаемый результат:** отдельной GRVM-настройки нет; Telegram применяет штатные accent/name/preview colors; author, quote text и media thumbnail сохранены; tap ведёт к exact source. Legacy value ничего не меняет.
- **Статус:**
- **Наблюдение:**

## Shared setup: sliders, avatars, stickers и layout

Выполнить один раз перед `A08`, `C05` и `Q04`:

- У account есть настоящая profile photo; в chat list видны Story ring и status/premium/badge overlays; доступны chat header/video avatar и forum/topic icon.
- Накопить минимум 25 разных recent stickers в сохранённом порядке и оставить sticker keyboard открытой для live-change проверки.
- Первый вход после cold launch выполнить в RU; layout smoke повторить в EN и при увеличенном iOS text size.
- Общие paths: `Настройки` → `Настройки GRVMgram` → `Оформление` → `Скругление аватаров`; `Настройки` → `Настройки GRVMgram` → `Чаты` → `Количество недавних стикеров`.

### A08 — Закругление аватаров

- **Причина включения:** изменены shared slider lifecycle, preview identity, avatar radius normalization, Story/header overlays и live invalidation видимого chat UI.
- **Точный RU UI path:** `Настройки` → `Настройки GRVMgram` → `Оформление` → `Скругление аватаров`; затем нижняя вкладка `Чаты` → chat list → нужный chat/topic → header/profile.
- **Предпосылки:** выполнен shared slider/layout setup; экран впервые открывается после cold launch.
- **Шаги:** на первом показе выставить `0`, `23`, `50` и промежуточное целое значение; наблюдать preview и уже видимые avatars без background/foreground; проверить chat list, header, profile, forum/topic, Story ring и overlays; выполнить relaunch.
- **Ожидаемый результат:** thumb/track сразу имеют правильную позицию; шаг ровно `1`; preview показывает текущую account photo, placeholder — только при её отсутствии. Все поверхности обновляются live; radius считается от фактических bounds; нет ромба, обрезки ring/overlay или stale geometry при reuse; значение сохраняется.
- **Статус:**
- **Наблюдение:**

### C05 — Количество недавних стикеров

- **Причина включения:** использован тот же slider fix и изменены четыре runtime write paths плюс live data source открытой sticker keyboard, чтобы убрать hardcoded limit `20`.
- **Точный RU UI path:** `Настройки` → `Настройки GRVMgram` → `Чаты` → `Количество недавних стикеров`; runtime surface: любой чат → кнопка emoji/stickers → вкладка недавних стикеров.
- **Предпосылки:** выполнен shared slider/layout setup; накоплено минимум 25 distinct recent stickers.
- **Шаги:** на первом открытии выставить `25`, не закрывая keyboard проверить список; затем выставить `10` и `30`; добавить новый sticker и выполнить relaunch.
- **Ожидаемый результат:** slider меняется по `1` в диапазоне `1...200`; открытая keyboard применяет limit live; порядок сохраняется; count выше `20` поддерживается всеми write paths; после relaunch выбранное значение и порядок сохранены.
- **Статус:**
- **Наблюдение:**

### Q04 — Layout

- **Причина включения:** shared controls и avatar consumers существенно менялись; нужен соседний визуальный guard первого layout, длинных RU labels, enlarged text и overlay geometry.
- **Точный RU UI path:** paths shared slider/layout setup; дополнительно `Настройки GRVMgram` → `Основное`, `Оформление`, `Чаты`; затем `Чаты` → chat list → chat header/context menu.
- **Предпосылки:** выполнен shared slider/layout setup; доступны RU, EN и увеличенный text size.
- **Шаги:** открыть оба slider screens первым заходом; пройти settings rows с длинными labels; открыть chat list/header и большое message context menu с reaction panel.
- **Ожидаемый результат:** нет thumb в левом верхнем углу, clipping, overlap, diamond avatars, конфликтующих masks/rings или обрезанных trailing controls; длинные labels читаемы; context menu и status/reaction areas не перекрываются. Folder-badge width проверяется в отдельном shared folder setup.
- **Статус:**
- **Наблюдение:**

## Shared setup: folders, tabs и persistence

Выполнить один раз перед `A13`, `A14` и `Q02`:

- Использовать non-Premium account A и второй account B.
- На A открыть `Настройки` → `Папки с чатами`, создать минимум две пользовательские папки, получить unread badge на обеих, переставить `Все чаты` не на первое место и запомнить порядок.
- Открыть обе surfaces: нижняя вкладка `Чаты`; затем любой чат → удерживать сообщение → `Переслать` → peer picker с folder tabs.
- GRVM paths: `Настройки` → `Настройки GRVMgram` → `Оформление` → `Скрыть счётчики папок` и `Скрыть «Все чаты»`.

### A13 — Скрыть счётчики папок

- **Причина включения:** main HorizontalTabs и legacy peer-picker переведены на одну live badge policy; исправлены alpha, width и spacing.
- **Точный RU UI path:** `Настройки` → `Настройки GRVMgram` → `Оформление` → `Скрыть счётчики папок`; проверить нижнюю вкладку `Чаты` и `Чаты` → удерживать сообщение → `Переслать` → peer picker.
- **Предпосылки:** выполнен shared folder setup; на двух папках есть ненулевые badges.
- **Шаги:** включить настройку при открытом main list, затем открыть picker; вызвать layout/filter refresh и дождаться animation; выключить без relaunch.
- **Ожидаемый результат:** badges исчезают live на обеих surfaces, не оставляют пустую ширину/spacing и не возвращаются после layout; folders, порядок и unread model не меняются. OFF возвращает актуальные badges без пустых tabs.
- **Статус:**
- **Наблюдение:**

### A14 — Скрыть «Все чаты»

- **Причина включения:** main и peer-picker теперь используют единый visible-filter set, selection fallback и content filter; исправлен split UI.
- **Точный RU UI path:** `Настройки` → `Настройки GRVMgram` → `Оформление` → `Скрыть «Все чаты»`; surfaces: нижняя вкладка `Чаты` и `Чаты` → удерживать сообщение → `Переслать` → peer picker.
- **Предпосылки:** выполнен shared folder setup; сначала доступны две пользовательские папки, затем можно временно оставить только `Все чаты`.
- **Шаги:** включить настройку с несколькими folders; сверить visible tab, highlight и фактически показанный список на обеих surfaces; затем оставить единственной `Все чаты` и выключить setting.
- **Ожидаемый результат:** `Все чаты` скрыта live только при наличии другой папки; selected highlight и content совпадают; tab strip не пуст. Если она единственная, она остаётся доступной. OFF возвращает её на обеих surfaces без изменения folders/unread.
- **Статус:**
- **Наблюдение:**

### Q02 — Сохранение после relaunch

- **Причина включения:** удалены reload-normalizations, принудительно возвращавшие `Все чаты` в index 0; изменены main и peer-picker reload paths.
- **Точный RU UI path:** `Настройки` → `Папки с чатами` → изменить порядок; затем iOS app switcher → cold relaunch; нижняя вкладка `Настройки` → вернуться в `Чаты`; `Настройки` → список аккаунтов в шапке → A → B → A.
- **Предпосылки:** выполнен shared folder setup; сохранён порядок с `Все чаты` не первой; есть один выбранный GRVM setting и один account-scoped local item как guards.
- **Шаги:** сверить порядок после cold relaunch, после `Чаты` → `Настройки` → `Чаты`, после A → B → A и в peer picker.
- **Ожидаемый результат:** сохранённый порядок ни на одном reload-trigger не нормализуется к index 0; выбранный GRVM setting сохраняется; local item остаётся только в своём account; main tabs и picker показывают один порядок.
- **Статус:**
- **Наблюдение:**

## Shared setup: reaction display и picker placement

Выполнить один раз перед `C02`, `C03`, `C04` и `CM01`:

- Использовать два клиента A/B; подготовить broadcast channel, legacy group, supergroup, DM и secret chat.
- На каждой применимой surface иметь reactions на text, media caption, sticker и round video; для channel/group желательно также poll/footer.
- B используется для проверки, что server reaction остаётся видимой, пока A скрывает её только локально.
- Settings paths: `Настройки` → `Настройки GRVMgram` → `Чаты` → `Показывать реакции в каналах`, `Показывать реакции в группах`, `Показывать реакции в личных чатах`, `Панель реакций`.

### C02 — Реакции в каналах

- **Причина включения:** display-only policy применена ко всем channel renderer paths и добавлена live invalidation уже открытого канала.
- **Точный RU UI path:** `Настройки` → `Настройки GRVMgram` → `Чаты` → `Показывать реакции в каналах`; затем `Чаты` → нужный broadcast channel.
- **Предпосылки:** выполнен shared reaction setup; канал открыт на сообщении с reactions.
- **Шаги:** выключить setting, не закрывая канал; проверить подготовленные renderer types; открыть picker и поставить новую reaction; включить обратно.
- **Ожидаемый результат:** существующие reaction chips/rows исчезают сразу только на A и возвращаются live; picker и отправка/снятие reaction работают; B видит server state. Groups и private chats не меняются.
- **Статус:**
- **Наблюдение:**

### C03 — Реакции в группах

- **Причина включения:** единая display-only policy и live invalidation добавлены для legacy groups/supergroups во всех renderer paths.
- **Точный RU UI path:** `Настройки` → `Настройки GRVMgram` → `Чаты` → `Показывать реакции в группах`; затем `Чаты` → legacy group и supergroup.
- **Предпосылки:** выполнен shared reaction setup; обе group types открыты на сообщениях с reactions.
- **Шаги:** выключить setting и проверить renderer types в обеих groups; открыть picker, поставить/снять reaction; включить обратно.
- **Ожидаемый результат:** reactions скрываются и возвращаются live только локально; picker/server mutation сохранены и видны B. Broadcast channel и private chats не меняются.
- **Статус:**
- **Наблюдение:**

### C04 — Реакции в private chats (regression guard)

- **Причина включения:** direct defect уже был зелёным, но shared reaction wrappers и live invalidation изменили private/secret renderer paths; карточка включена только как regression guard.
- **Точный RU UI path:** `Настройки` → `Настройки GRVMgram` → `Чаты` → `Показывать реакции в личных чатах`; затем `Чаты` → DM и secret chat.
- **Предпосылки:** выполнен shared reaction setup; DM и secret chat содержат reactions на нескольких renderer types.
- **Шаги:** после channel/group checks выключить private setting; поставить новую reaction; включить setting обратно.
- **Ожидаемый результат:** только уже поставленные reactions скрываются локально и возвращаются live; picker остаётся; новая reaction уходит на server и видна B; channel/group settings не влияют на DM/secret chat.
- **Статус:**
- **Наблюдение:**

### CM01 — Панель реакций

- **Причина включения:** three-state policy переподключена с read/reaction statistics к настоящему picker `reactionItems` и единому submenu.
- **Точный RU UI path:** `Настройки` → `Настройки GRVMgram` → `Чаты` → `Панель реакций`; последовательно выбрать `Скрыто`, `Показано`, `С модификатором`; после каждого значения открыть `Чаты` → удерживать сообщение.
- **Предпосылки:** выполнен shared reaction setup; сообщение допускает реакции; обычные context actions доступны.
- **Шаги:** открыть новое context menu для каждого значения и проверить placement picker; в modifier mode открыть `Действия GRVMgram`.
- **Ожидаемый результат:** `Скрыто` — picker отсутствует; `Показано` — picker на top level; `С модификатором` — picker только внутри `Действия GRVMgram`. Statistics/read-report UI не влияет на placement; `Копировать`, `Ответить`, `Переслать`, `Удалить` и mutation reactions продолжают работать.
- **Статус:**
- **Наблюдение:**

## Standalone archive, filter и compatibility checks

### AR05A — Безвозвратное удаление отдельной сохранённой удалёнки

- **Причина включения:** добавлены chat-level typed purge, exact persistent suppression tombstone и server-delete → local-purge sequence; изменён archive admission.
- **Точный RU UI path:** подготовка: `Настройки` → `Настройки GRVMgram` → `Основное` → `Сохранять удалённые сообщения`; action: `Чаты` → DM/group/topic/channel → удерживать сохранённую удалённую запись или live message с правом удаления у всех → `Удалить локально` → destructive confirmation; archive check: удерживать аватар в шапке chat/topic → `Архивы GRVMgram` → `Просмотреть удалённые`.
- **Предпосылки:** DM; group/topic admin; тот же scope под non-admin; две записи с общим media resource; distinct neighboring message.
- **Шаги:** already-deleted запись удалить локально как non-admin; live message удалить как admin через confirmation; проверить chat history, scoped archive, search/revisions, relaunch и account switch; для shared media удалить только одну запись.
- **Ожидаемый результат:** already-deleted purge не требует admin/server delete; live path сначала удаляет у всех, затем exact local record. Target не respawn после replayed update/relaunch; соседние rows и общий media второй записи целы; другой topic/account не затронут; ошибки finalization видимы.
- **Статус:**
- **Наблюдение:**

### F22 — Shadow Ban forwarded origin

- **Причина включения:** изменены semantic roles целей, resolved presentation и формат публичного Telegram ID при сохранении внутреннего `PeerId` как mutation key.
- **Точный RU UI path:** B отправляет сообщение C, C пересылает его A с видимой атрибуцией; на A: `Чаты` → удерживать forwarded message → пункты `Теневой бан — Автор…`, `Теневой бан — Автор пересланного сообщения…`, `Теневой бан — Автор исходного сообщения…`; list check: `Настройки` → `Настройки GRVMgram` → `Фильтры` → `Теневой бан`.
- **Предпосылки:** три различимых пользователя A/B/C; известны публичные Telegram IDs B и C; forwarded attribution не скрыта.
- **Шаги:** до mutation сопоставить role, resolved name и публичный ID; выбрать target с ID B; проверить контент B/C; удалить B из `Теневой бан`.
- **Ожидаемый результат:** роли не схлопнуты и однозначны; показаны resolved name и публичный Telegram ID, а не raw namespaced Int64. Скрывается именно контент B; собственные/wrapper messages C остаются; self-target недоступен. После удаления B контент возвращается live без relaunch.
- **Статус:**
- **Наблюдение:**

### SP04A — Поддерживаемое Local Premium compatibility state

- **Причина включения:** изменены exact compatibility ingestion, persistent provenance, account+peer cache, local self-status branch и title/profile presentation; требуется двухклиентная device matrix в фактически поддерживаемой границе.
- **Точный RU UI path:** на A: `Настройки` → `Настройки GRVMgram` → `Основное` → `Локальный Telegram Premium`; затем профиль A → кнопка emoji-status → выбрать custom emoji. На B: `Настройки` → `Настройки GRVMgram` → `Оформление` → `Скрыть Premium-статусы` OFF. Message path: A → чат с B → отправить и затем отредактировать сообщение, содержащее один custom emoji, который приходит на B как exact `tg://emoji?id=<positive fileId>` entity; проверить title и профиль A на B.
- **Предпосылки:** два raw non-Premium accounts A/B на двух GRVMgram-клиентах; отдельный genuine Telegram Premium peer/status; fixtures для exact marker, plain message без marker, более старого marker и нового replacement marker.
- **Шаги:** включить Local Premium на A, выбрать self status и выполнить relaunch; доставить B exact compatibility entity и проверить live title/profile projection; отправить plain message без marker; доставить более старый и затем новый marker; проверить expiry fixture/время; выключить Local Premium на A и проверить очистку только marker-owned self status; повторить stock guards для genuine Premium/status и `Скрыть Premium-статусы`.
- **Ожидаемый результат:** на A local-only status сохраняется только для raw non-Premium nil/marker-matching state; OFF очищает только exact marker-owned self status. На B только последний доказанный exact marker создаёт account+peer presentation; старый marker не откатывает state, новый заменяет его, plain message не означает OFF, а state исчезает только после replacement или 7-day expiry. Remote `Peer.isPremium`, stored peer status и серверные capabilities не меняются; genuine Telegram Premium/status и `hidePremiumStatuses` сохраняют штатный приоритет.
- **Техническое ограничение:**

  > SP04A синхронизирует не произвольный выбранный profile status и не сам toggle Local Premium, а только последний custom emoji, доказанный реально полученной exact `tg://emoji?id=<fileId>` compatibility entity. Обычное сообщение без marker не доказывает remote OFF; состояние заменяется новым marker либо истекает через 7 дней. Instant profile/toggle/sticker sync и серверные Premium capabilities без backend остаются unsupported; genuine Telegram Premium/status не мутируются.

- **Статус:**
- **Наблюдение:**

## Отдельная проверка локализации и branding

### Q03 — EN/RU и branding

- **Причина включения:** context-menu `История` переведён с hardcoded English на typed localization; затронуты RU/EN resources и общий presentation path.
- **Точный RU UI path:** нижняя вкладка `Настройки` → `Язык` → `Русский`; затем `Чаты` → чат с отредактированным сообщением → удерживать сообщение → `История`. Для EN-половины: `Настройки` → `Язык` → `English` → тот же message context menu.
- **Предпосылки:** есть сообщение с сохранённой revision; доступны RU и EN; для branding smoke доступно `Настройки` → `Настройки GRVMgram`.
- **Шаги:** в RU открыть action и экран revisions; повторить в EN; просмотреть заголовок и основные разделы `Настройки GRVMgram` в обеих локалях.
- **Ожидаемый результат:** RU показывает `История`, EN — `History`; нет смешанной локализации, пустых labels и публичного `AyuGram`/upstream branding. Допустимы собственные названия Telegram, например `Telegram Premium` и `Telegram API`.
- **Статус:**
- **Наблюдение:**

## GRVM Notify — только native regression

Полная PWA/device matrix находится в отдельном [журнале GRVM Notify](grvm-notify-device-qa.md). Карточки ниже проверяют только затронутые native entry points и state transitions и не заменяют 14 строк этого журнала.

### GN-N01 — grvmgram cold/foreground routing

- **Причина включения:** добавлены новый URL scheme, killed-launch admission и единый foreground helper; stock URL routing не должен получить ни валидный, ни malformed `grvmgram` URL.
- **Точный RU UI path:** при закрытом GRVMgram открыть валидную `grvmgram://notify-auth` либо `grvmgram://notify-open` ссылку; повторить при foreground через каждый доступный UIKit open-URL entry point. Отдельно открыть malformed `grvmgram` URL и штатную `tg://`/`tgfork` ссылку.
- **Предпосылки:** собранная IPA с зарегистрированным scheme; готовые валидные и malformed fixtures без реальных token/account ID в журнале.
- **Шаги:** проверить cold launch из URL и foreground admission; для malformed fixture дождаться готовности UI; затем выполнить stock-link smoke.
- **Ожидаемый результат:** killed launch не теряет ссылку, все foreground paths вызывают один enqueue helper, malformed link показывает одну локализованную ошибку и не уходит в stock routing; `tg://`, `tgfork` и native APNs behavior не меняются.
- **Статус:**
- **Наблюдение:**

### GN-N02 — Locked readiness

- **Причина включения:** coordinator откладывает confirmation/navigation до готового authorized root и снятия App Lock, затем повторно проверяет owner и наличие account.
- **Точный RU UI path:** включить local App Lock → закрыть/заблокировать GRVMgram → открыть валидную GRVM Notify ссылку → убедиться в отсутствии presentation → разблокировать приложение. Повторить, удалив owner account до unlock, и с двумя последовательными ссылками.
- **Предпосылки:** paired account, включённый App Lock, две ссылки с разными message IDs и отдельный fixture для logout/removal.
- **Шаги:** открыть ссылку в locked/cold state; дождаться root readiness; снять lock; повторить после logout и проверить, что новый request отменяет старый.
- **Ожидаемый результат:** до readiness/unlock нет confirmation/navigation; после unlock обрабатывается только последний request; logout/removal даёт `account unavailable` и никогда не retarget’ит другую account.
- **Статус:**
- **Наблюдение:**

### GN-N03 — Settings row/localization

- **Причина включения:** в callback-driven GRVMgram settings добавлены стабильная строка `Уведомления`/`Notifications`, management controller и truthful native-only session states.
- **Точный RU UI path:** `Настройки` → `Настройки GRVMgram` → `Основное` → `Уведомления`; повторить после переключения языка на English. Проверить состояния без pair, connected session, missing owner, disconnect in flight и reconciliation error.
- **Предпосылки:** RU/EN locales и подготовленные state fixtures; iOS/iPadOS ниже и не ниже 16.4 для unsupported guard.
- **Шаги:** открыть строку во всех состояниях, проверить actions `Настроить`/`Продолжить настройку`, `Открыть устройства`, `Отключить` и вернуться назад без unsolicited sheet.
- **Ожидаемый результат:** labels полностью локализованы и не пусты; экран говорит `Web-сессия подключена`, а не `Уведомления работают`; unsupported, orphaned и status-not-verified состояния не заявляют готовность PWA.
- **Статус:**
- **Наблюдение:**

### GN-N04 — Exact account/message navigation

- **Причина включения:** native parser/coordinator преобразует allowlisted query в точные public account ID, PeerId namespace, optional thread и Cloud MessageId.
- **Точный RU UI path:** при двух native accounts открыть подготовленные `grvmgram://notify-open` fixtures для paired account и конкретного user/group/channel message; отдельно открыть forum thread, неизвестный peer и ссылку с чужим account ID.
- **Предпосылки:** paired account не является текущей; известны доступные server message IDs; есть missing-peer и owner-mismatch fixtures.
- **Шаги:** открыть каждую ссылку, сверить выбранную account/chat/message; для forum проверить thread и parent fallback; дождаться bounded peer synchronization timeout.
- **Ожидаемый результат:** приложение переключается только на paired public user ID и открывает exact message с `alwaysKeepMessageId`; positive `thread_id` сохраняется, missing peer даёт локализованный timeout, owner mismatch не имеет fallback на current account.
- **Статус:**
- **Наблюдение:**

### GN-N05 — Session revoke/orphaned state

- **Причина включения:** native disconnect и one-shot reconciliation различают подтверждённое отсутствие session hash, network error и удалённую owner account.
- **Точный RU UI path:** `Настройки` → `Настройки GRVMgram` → `Основное` → `Уведомления` → `Открыть устройства` либо `Отключить`; отдельно удалить paired native account и вернуться на экран с другой account.
- **Предпосылки:** paired session, управляемая network error/timeout, ручной Devices revoke и fixture с removed native owner.
- **Шаги:** выполнить native revoke с success/error; повторно открыть экран после manual Devices revoke; проверить orphaned state после removal и отсутствие destructive auto-clear при fetch error.
- **Ожидаемый результат:** ownership очищается только после exact terminate completion либо успешного server response без hash; timeout/error сохраняет state и показывает `Статус не проверен`; removed owner показывает orphaned warning и не позволяет revoke/navigate через другую account.
- **Статус:**
- **Наблюдение:**

## Подписание targeted checklist

- Checklist: `[исполнитель и дата после заполнения 28 карточек: 23 существующих + 5 GRVM Notify]`
- Внешняя сборка/IPA: `[заполнить после отдельной сборки]`
- Внешний device run: `[устройство/iOS, исполнитель и дата]`
- Итог внешней проверки: `[заполнить только после фактического build/device run]`
