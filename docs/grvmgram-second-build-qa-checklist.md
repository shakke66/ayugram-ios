# GRVMgram — второй iPhone build: полный QA-чеклист

**Назначение:** самостоятельный runbook для повторной проверки IPA после post-release fix wave. Чеклист дополняет [основной функциональный журнал](grvmgram-functional-test-checklist.md), но не заменяет его acceptance criteria.

**Дата шаблона:** 2026-07-23
**Языки интерфейса:** русский (`RU`) и английский (`EN`)
**Область:** Stream A (удаления), Stream B (partial/UI), Stream C (runtime), отдельный сквозной F19 и сохранённые Telegram-инварианты.

---

## 0. Карточка прогона и правила результата

Заполнить до первого теста:

| Поле | Значение |
|---|---|
| IPA version/build | `________________` |
| Git commit | `________________` |
| GitHub Actions run ID | `________________` |
| Artifact name | `________________` |
| IPA SHA-256 | `________________` |
| iPhone A / iOS | `________________` |
| Второй клиент B (iPhone/desktop) / iOS | `________________` |
| Дата и часовой пояс | `________________` |
| Тестер | `________________` |
| RU pass timestamp | `________________` |
| EN pass timestamp | `________________` |

### Статусы

- `PASS` — ожидаемый результат подтверждён на указанной сборке.
- `FAIL` — наблюдается дефект, несовпадение или регрессия; приложить шаги воспроизведения.
- `BLOCKED` — внешний предусловие недоступно (например, Telegram не выдал рекламу или нет Premium-аккаунта); указать, что именно отсутствует.
- `N/A` — сценарий не относится к iPhone; это не ошибка.
- `NOT RUN` — ещё не проверено. Нельзя выдавать общий sign-off при оставшихся `NOT RUN` в обязательных блоках.

Для каждого ID записать: `Result`, краткий фактический результат, время, ссылку на локальный screenshot/log (без персональных данных), build и account scope.

### Правила доказательств

1. Не публиковать номера телефонов, usernames, peer IDs, тексты личной переписки, push-токены, crash logs с PII или полный экспорт базы.
2. Скриншоты обрезать до UI и перед сохранением закрывать имена, аватары, ссылки, коды и уведомления с личным содержимым.
3. Для межклиентских сценариев сохранять две отметки времени: действие на A и наблюдение на B.
4. Для unread/read-сценариев фиксировать состояние до и после на A и receipt/read mark на B; локальное уменьшение badge само по себе не доказывает server receipt.
5. Любой crash, freeze, повторный enqueue/sound, потеря media или смешение account scope — немедленный `FAIL` и остановка связанного блока.

---

## 1. Обязательный стенд и фикстуры

### 1.1 Клиенты и аккаунты

- [ ] iPhone A с тестовой GRVMgram IPA и включёнными разрешениями, необходимыми для сценария (Notifications, Photos, Microphone при необходимости).
- [ ] Клиент B на отдельном устройстве или в отдельной сессии; аккаунт B не должен быть тем же самым аккаунтом, что A.
- [ ] Непремиальный аккаунт A и отдельный Premium-аккаунт/peer для проверки локального Premium; для `SP04A` нужны два непремиальных GRVMgram-клиента.
- [ ] Аккаунт A добавил B в личный чат; B доступен для отправки, удаления, редактирования, typing и presence.
- [ ] Тестовая группа/supergroup, forum supergroup с минимум двумя topics и broadcast-канал с discussion; отдельный канал без discussion.
- [ ] Контролируемый бот с обычными командами, inline callback-кнопкой и callback payload в UTF-8 и binary-байтах.

### 1.2 Сообщения и локальные данные

- [ ] Уникальные tokens: `GRVM_QA_42`, `GRVM_PAGE_FILL`, `GRVM_BUTTON_PAYLOAD`.
- [ ] Набор сообщений: text, URL, concealed `TextUrl`, photo, GIF, sticker, voice, round video, spoiler, reaction, reply, forwarded message, service action и one-view/one-play media.
- [ ] Два сообщения, отредактированные по нескольку раз, с разными текстами и timestamp; одна revision должна быть сохранена до выключения SP02.
- [ ] Удалённые B text/photo в DM, group и topic; одно собственное исходящее A для проверки author boundary; отдельный bot-delete.
- [ ] Не менее 100 сообщений для pagination; последние 50 содержат `GRVM_PAGE_FILL`, более старые — нет; sparse-вариант с одним видимым сообщением среди скрытых.
- [ ] Несколько chat folders, custom wallpaper и локально загруженная Saved Music artwork.
- [ ] До начала прогона зафиксирован чистый baseline: видимые counters, unread, список папок, app icon, язык и настройки.

### 1.3 Условия повторной сборки

- [ ] Установить второй build поверх предыдущего поддерживаемого build, если это upgrade-тест; отдельно записать результат миграции.
- [ ] Выполнить один cold launch и один полный relaunch до функциональных тестов; не использовать relaunch для «починки» сценария, который обязан обновляться live.
- [ ] Проверить, что системная дата/время, push connectivity и сеть стабильны; при offline-тесте явно записать режим.

---

## 2. Build smoke, миграция и публичные границы

### BLD-01 — Установка и launch

- [ ] IPA устанавливается без ручного удаления пользовательских данных.
- [ ] Version/build совпадает с карточкой прогона; app icon и splash используют публичное имя `GRVMgram`.
- [ ] Первый launch завершается на основном экране без crash, launch loop, бесконечного spinner или пустого root controller.
- [ ] После получения входящего сообщения локальный in-app banner появляется только в штатном overlay и не перекрывает safe area/Dynamic Island.

### BLD-02 — Upgrade/relaunch

- [ ] После upgrade сохраняются client-wide GRVM settings и account-scoped archive/revision/media/read data.
- [ ] После cold relaunch не происходит повторной отправки старых локальных уведомлений, повторного звука или повторной миграции.
- [ ] Переключение A → B → A не меняет client-wide app icon/Ghost/Filters/General/Appearance/Chats/Other; archives, revisions, media и read/action state не смешиваются.

### BLD-03 — Scope guard

- [ ] Открыть Settings GRVMgram на RU и EN; ни одна legacy AyuGram-внутренняя строка не показывается публично.
- [ ] Stock Telegram settings, profile, chat, calls, media picker и authorization flows по-прежнему доступны.

---

## 3. Stream A — удалённые функции: negative guards

Цель Stream A — отсутствие публичной строки, editor route, action, runtime consumer и нового write для следующих 27 IDs. Legacy значения могут безопасно декодироваться для совместимости, но не должны быть видны или активны.

### 3.1 Точный removal set

| Группа | IDs | Проверка второго build |
|---|---|---|
| Ghost | `G02`, `G07`, `G08` | Нет строк «Закреплённые компоненты», отдельного locks-screen, «Автоматически уходить Offline» и «Читать при действиях»; Ghost показывает `N/4`. |
| Archive/History | `AR01`, `AR07` | Нет глобальных пунктов «Удалённые сообщения» и «История» в Settings; chat-scoped archive/history остаются. |
| General WebView | `N11`, `N12`, `N13` | Нет строк spoof Android, Increase WebView Height/Width и старого общего size-control; штатный WebView открывается. |
| Appearance | `A04`, `A09`, `A10`, `A12` | Нет MD3 Switches, отдельных Bubble/Single corner-radius и Adaptive Saved Music Color rows; stock switch/radius/music fallback не ломаются. |
| Chats | `C08` | Нет Message Shot master, editor route, action и settings; обычный screenshot/Share не изменён. |
| Compose popups | `CP02`, `CP03`, `CP06` | Нет Attach Popup, Commands override и Emoji Popup controls/long-press routes; обычные Attach/Commands/Emoji работают. |
| Message Shot children | `MS01`–`MS10` | Нет orphaned Background/Date/Reactions/Header/Decorations/Replies/Spoiler/Theme/Copy/Save rows и routes. |
| Standalone | `ST05` | Нет Created/Joined UI, action или persistent row; обычный profile/chat не содержит ghost entry. |

### 3.2 Negative-path procedure

Для каждой строки таблицы:

1. Проверить RU, затем EN, поиск Settings (если есть), profile menu, chat long press и context menu.
2. Попытаться открыть старый route через back-stack после upgrade и через повторное нажатие старого места.
3. Убедиться, что приложение не crash-ит, не показывает пустой экран и не пишет новый legacy setting.
4. Включить рядом стоящую штатную функцию и подтвердить, что она работает без удалённого override.

**Evidence:** два локализованных скриншота Settings и один screenshot stock fallback; для каждого ID — `PASS/FAIL`, route и observed text.

---

## 4. Stream B — partial/UI и сохранённые пользовательские сценарии

### 4.1 Ghost и скрытые read/presence-компоненты

#### G01 — Ghost master (`N/4`) и независимые компоненты

- [ ] В RU и EN master с `0/4` включает ровно четыре surviving components и показывает `4/4`.
- [ ] Выключение одного компонента меняет master на `3/4`; остальные три продолжают работать. Включение обратно возвращает `4/4`.
- [ ] Выключение master отключает все четыре; включённый отдельный компонент работает по собственному значению даже когда master выключен (master не является runtime gate).
- [ ] A ↔ B сохраняет одни и те же client-wide значения; relaunch не возвращает старый `N/5`.

#### G03/G04/G05/G06/G09/G10

- [ ] `G03` Read receipts: B отправляет text и voice; A открывает чат/проигрывает voice; у B нет read/content-consumed receipt.
- [ ] `G04` Stories: A открывает Story B; при Ghost у B нет viewer; prompt `Enable Ghost Mode / View Normally` показывается не более одного раза на Story-screen.
- [ ] `G05` Online: B наблюдает A 20–30 секунд и после send; A не рекламирует Online и возвращается Offline по ожидаемому переходу.
- [ ] `G06` Typing/upload: при наборе и большой загрузке B не видит typing/upload activity, готовое сообщение приходит.
- [ ] `G09` Schedule: измерить text (12 s), voice/round video (17 s), новый файл по формуле из основного журнала; при proxy применить ×1.2 вверх. При OFF задержки нет.
- [ ] `G10` Send without sound: проверить `Never`, `In Ghost`, `Always` до и после включения отдельного Ghost-компонента; silent-флаг соответствует режиму.

### 4.2 Spy/archive/history: SP01–SP05 и AR02–AR06

| ID | Шаги второго build | PASS-критерий |
|---|---|---|
| `SP01` | B удаляет text/photo в DM, group и topic; A удаляет собственный исходящий; повторить после relaunch и OFF. | Известные локально удаления B остаются inline и в exact account+dialog+topic archive; сообщения A не сохраняются, не ищутся и не появляются inline. |
| `SP02` | A и B редактируют два сообщения несколько раз; открыть History каждого; выключить switch и внести новую правку. | Только выбранный message ID показывает старые/current версии; новые revisions после OFF не добавляются, старые остаются. |
| `SP03` | Bot удаляет сообщение при OFF/ON; повторить bot-delete в группе. | ON сохраняет bot-delete inline/archive; edit history не зависит от SP03; group behavior не смешивает scopes. |
| `SP04` | На непремиальном A включить local Premium; проверить A, обычного B и реальную Premium-операцию. | UI Premium только для exact current account; серверные ограничения не обходятся; настоящий Premium B не исчезает. |
| `SP05` | Найти канал/search с реальной sponsored message; сравнить OFF/ON. | Реклама скрывается, обычные messages сохраняются; если Telegram не выдаёт рекламу — `BLOCKED` с доказательством. |
| `SP04A` | На двух непремиальных GRVMgram-клиентах включить local Premium только A; B проверяет profile/emoji/sticker; повторить OFF и после relaunch. | Поддерживаемые synced Premium fields видны на B ровно при ON, не смешиваются с приватными settings и исчезают после OFF; если протокол/fixture недоступен — `BLOCKED`, не `PASS`. |
| `AR02` | В profile DM/group/channel/topic открыть `Архивы GRVMgram`; сравнить соседний dialog и другой account. | Row расположена под `О себе`, перед media tabs, не является четвёртой tab; archive exact-scoped и исключает собственные удаления. |
| `AR03` | В каждом archive искать уникальные слова, очистить search. | Search ограничен текущим scope; очистка возвращает только его записи. |
| `AR04` | Нажать archive record из DM/group/topic. | Открывается точный dialog/topic/message и account, без перехода в соседний scope. |
| `AR05` | Cancel, затем Confirm для chat и topic; relaunch. | Cancel ничего не удаляет; Confirm чистит только выбранный archive scope и его local data. |
| `AR05A` | Long press сохранённой deletion → permanent Delete; проверить archive/search/revisions/media до и после relaunch. | Удаляется только `account+dialog+topic+message ID`; shared media и соседние записи целы; server повторно не вызывается. |
| `AR06` | Открыть History двух сообщений на RU и EN. | Первая revision — `Версия 1`/`Version 1`, далее one-based; current version подписана отдельно; RU action `История`, EN `History`. |

### 4.3 Filters UI: F01–F10, F12–F18, F24–F26B

- [ ] `F01/F02`: включение Filters и применение в chats; выключение полностью возвращает stock visibility.
- [ ] `F03–F08`: список, Add/Edit/Delete/Reorder и per-filter enable; Cancel не меняет snapshot, Done применяет его.
- [ ] `F09/F10`: case-insensitive и reversed semantics на mixed-case token; reversed не превращается в allow-list для outgoing.
- [ ] `F11/F11A`: text, ordinary URL и concealed `TextUrl`; reply на hidden message и последующая reply chain скрыты каскадно, цитата не раскрывает origin.
- [ ] `F12`: `<type>` для photo/voice; test incoming B и outgoing A отдельно.
- [ ] `F13`: `<button>` проверяет title и payload (UTF-8 и binary), не visible text בלבד.
- [ ] `F14/F15`: Select Chat и Excluded Chats; другой chat/account не меняется.
- [ ] `F16/F17`: Export → inspect version/expressions/options/scopes → Import; invalid/Cancel не портит действующий snapshot.
- [ ] `F18`: Clear Filters очищает только filters, сохраняя master, blocked и Shadow Ban.
- [ ] `F24`: View Filters показывает действующие правила без редактирования.
- [ ] `F25`: long press message → Add Filter; expression и current dialog scope заполнены; Done скрывает уже открытый chat live, Cancel ничего не создаёт.
- [ ] `F26`: Show Filtered/Hide Filtered live только для `account+chat`; rules не меняются, relaunch сбрасывает override.
- [ ] `F26A`: при >100 messages hidden raw pages pagination идёт по raw boundaries, автоматически backfill-ит видимые записи и не зацикливается на anchor; Show Filtered не требуется для восстановления.
- [ ] `F26B`: после Show Filtered между двумя incoming groups avatar/header разделяются корректно, без исчезновения второго avatar и stale node reuse.

### 4.4 F19 — blocked users и forwarded origin (обязательный отдельный gate)

Выполнить без relaunch на A, затем повторить выключение и повторное включение switch.

1. Добавить B в blocked set A и включить «Скрывать пользователей из ЧС». Записать baseline последнего сообщения, per-chat unread, topic unread, tab badge, app badge и notification overlay.
2. B отправляет text/photo/voice в DM, group и forum topic. Ни один hidden incoming message не появляется в chat history, chat-list preview, per-chat unread, aggregate/tab/app badge или local in-app notification.
3. C пересылает сообщение B. Forwarded origin также скрывается во всех тех же поверхностях; обычные сообщения C остаются видимыми.
4. Включить `Show Filtered` для одного `account+chat`: hidden messages и зависимые replies временно возвращаются только там; соседний chat/topic/account не меняется. Нажать Hide Filtered — скрытие и counters возвращаются.
5. Переключить filter/blocked setting при уже открытом чате и при уже показанном local notification. Пересчёт должен быть live, без нового `notificationMessages` event, relaunch или ручного выхода/входа.
6. Для notification overlay проверить: raw notification event — единственный enqueue/sound; toggle revision удаляет уже видимый скрытый `ChatMessageNotificationItem`, не повторяет старый banner, звук или vibration. Видимый peer/сообщение не удаляется.
7. Для topic проверить parent chat и forum topic отдельно: unread/message preview не протекают между topic и root; incomplete/holes не превращаются в ложный полный zero.
8. Выключить фильтр/blocked setting: новые incoming messages снова видимы; уже снятый transient banner не обязан resurrect-иться без нового event, но следующий event должен enqueue один раз.

**F19 evidence matrix:**

| Поверхность | До toggle | После hide | После Show Filtered | После Hide/ON→OFF | Evidence |
|---|---|---|---|---|---|
| Chat history | `____` | `____` | `____` | `____` | `____` |
| Chat-list preview | `____` | `____` | `____` | `____` | `____` |
| Per-chat unread | `____` | `____` | `____` | `____` | `____` |
| Topic unread | `____` | `____` | `____` | `____` | `____` |
| Tab/app badge | `____` | `____` | `____` | `____` | `____` |
| In-app notification | `____` | `____` | `____` | `____` | `____` |

### 4.5 General partial/UI: N01–N10

- [ ] `N01` Translation Provider: Telegram/Google labels localized; selected provider applies only where supported.
- [ ] `N02` Hide Stories and `N03` Disable Similar Channels: live ON/OFF, account/client scope as specified, no stock recommendations crash.
- [ ] `N05` Disable Notification Delay: compare incoming local notification timing ON/OFF; no duplicate notification.
- [ ] `N06` Filter Zalgo: pathological combining marks are bounded/readable, ordinary text unchanged.
- [ ] `N07` Improve Link Previews: supported-domain preview rewrites preserve scheme/port/path/query/fragment; unsupported host unchanged.
- [ ] `N08` Message Seconds: eligible timestamps show `HH:mm:ss`, service/media layouts do not receive duplicate time.
- [ ] `N09` Dialog ID: exact Telegram/Bot API ID actions copy without freeze; see `ST03` below.
- [ ] `N10` External-link warning: only the intended concealed/external confirmation is bypassed; unsafe schemes, login and permission prompts remain protected.

---

## 5. Stream C — broken runtime and P0 scenarios

### 5.1 Self-safety and filter runtime

- [ ] `F22`: Shadow Ban hides forwarded origin B while preserving aggregate reaction count and unrelated peers.
- [ ] `F23`: adding own account ID to Shadow Ban is rejected/normalized; self never becomes hidden.
- [ ] `F23A`: sending a message that matches a hidden rule remains safe; own outgoing message is not filtered, shadow-banned or lost.
- [ ] `F27`: text, `<type>`, `<button>`, reversed, Shadow Ban and blocked filters apply only to effectively incoming content; Saved Messages, send-as and channel-as-current-account outgoing stay visible.

### 5.2 Chats, reactions and context menus

- [ ] `C02/C03/C04`: channel, group and private-chat reactions obey their surviving settings; stock counts and reaction list stay intact.
- [ ] `C15`: simple replies preserve reply target, quote and navigation without hiding unrelated metadata.
- [ ] `CM01`: reaction panel opens/closes, long press does not duplicate context controllers or freeze.
- [ ] `CM07`: Add Filter from message context uses exact current dialog and applies live.
- [ ] `ST03`: copy Telegram ID and Bot API ID for user/group/channel; regular tap copies; one context menu only; no freeze, overlay leak or forced relaunch.
- [ ] `ST18`: long press callback button copies UTF-8 text or lowercase hex bytes without executing callback; short tap still executes callback.

### 5.3 Read actions and topics

With Ghost master OFF and only `G03` enabled, generate fresh incoming unread:

- [ ] `ST15` Read Message appears on eligible incoming cloud message; local boundary advances through selected ID, B sees no server receipt.
- [ ] `ST16` Read All Locally appears in normal chat, forum topic and bot-forum routes; only selected dialog/topic local unread is cleared.
- [ ] `ST17` Read All on Server is separately visible and sends exact server receipt only when chosen; other dialog/topic/account unaffected.
- [ ] Repeat all three with master ON and OFF; visibility must depend on the independent read-receipt component, not master gate.

### 5.4 Preserved media: ST06, ST20–ST22

- [ ] `ST06` GIF controls pause/resume at the correct frame; PiP/fullscreen route does not change stock playback.
- [ ] `ST20` Burn on unopened one-view media: with SP01 ON, fully fetch/archive bytes before consuming; if bytes cannot be made durable, action stops visibly and does not silently burn.
- [ ] `ST21` Replay opens the exact saved one-view/one-play resource/message, not a neighboring gallery image; sender receives no second receipt. Without durable bytes action is unavailable with a clear reason.
- [ ] `ST22` Forward Local Copy to Saved Messages creates a new standalone upload without forward header, TTL/view-once/protection/callback linkage; caption/entities survive; unavailable bytes show an error over the picker and do not dismiss/no-op.
- [ ] Ordinary photo/GIF/sticker/voice/round-video send, download and playback remain stock after these tests.

---

## 6. Appearance and adaptive RU/EN UI

### 6.1 Appearance acceptance

- [ ] `A01` App icon changes live and persists after relaunch/account switch; icon setting is client-wide.
- [ ] `A02` Hide app badge and `A03` hide lower-tab counters affect only intended surfaces; unread data itself is not mutated.
- [ ] `A07` monospace font applies to intended message/text surfaces; settings and system labels remain readable.
- [ ] `A08` avatar corners, `A11` hide Premium statuses, `A13` folder counters and `A14` hide All Chats each apply live and persist.
- [ ] `A06` custom backgrounds: ON/OFF affects only intended chat wallpaper, does not reset stock wallpaper or account data.
- [ ] Removed `A04/A09/A10/A12` rows/routes stay absent while stock switch/radius/music behavior remains functional.

### 6.2 Layout matrix

Run each settings screen in RU and EN at default and largest available Dynamic Type:

| Screen | Check |
|---|---|
| Core/Ghost | Long switch titles wrap/stack without clipping or overlapping trailing switch; master count remains readable. |
| Filters | Add/Edit disclosure title/value, expression and scope remain readable; buttons do not overlap keyboard. |
| General | Provider, notification-delay, Zalgo, seconds, IDs and warning rows have correct localized spacing. |
| Appearance | App-icon/disclosure and multiline labels fit narrow iPhone width. |
| Chats | Reaction/mark/media rows and adaptive switches keep stable height after reuse. |
| Profile/archive/history | `Архивы GRVMgram`, `История/History`, timestamps and topic labels do not collide with media tabs. |
| Context menu | Reaction panel, status area and long titles do not overlap; dismiss returns to chat. |

**Evidence:** one RU and one EN screenshot per screen at narrow width; record device width, Dynamic Type and whether row height changed safely.

---

## 7. Notifications, unread, topics and badges regression matrix

This section is run after F19 and again after all appearance/filter toggles.

- [ ] Fresh visible incoming message produces one local banner, at most one sound/vibration, correct grouping key and correct tap destination.
- [ ] Muted, scheduled, imported, autoremove and conference-call actions retain stock suppression behavior.
- [ ] Active chat suppresses the banner as stock; opening a different chat navigates to the exact peer/topic.
- [ ] Filter revision never replays old `notificationMessages`, sound, vibration or enqueue; hidden current item is removed safely.
- [ ] Chat-list preview, per-chat unread, forum-topic unread, aggregate tab badge and app badge all agree after incoming, read-local, read-server, filter hide/show and account switch.
- [ ] Unknown/hole/incomplete unread scan keeps the unknown portion instead of claiming zero; no Postbox/server read mutation occurs in a display-only correction.
- [ ] Switch A ↔ B while one account has hidden unread: B does not inherit A's filtered count or notification item.

Record a small event timeline:

| Time | Account | Event | Chat/topic | Raw unread | Adjusted display | Banner/sound | Receipt on B |
|---|---|---|---|---:|---:|---|---|
| `____` | `A` | `____` | `____` | `____` | `____` | `____` | `____` |
| `____` | `A` | `____` | `____` | `____` | `____` | `____` | `____` |
| `____` | `B` | `____` | `____` | `____` | `____` | `____` | `____` |

---

## 8. Preserved Telegram behavior and broad regression

### 8.1 Stock smoke after GRVM toggles

- [ ] Send/receive text, photo, GIF, sticker, voice, round video, file, poll, reaction and reply in DM/group/channel.
- [ ] Open/close forum topic, jump to beginning, search, share, forward ordinary content and use Saved Messages.
- [ ] Open profile, media tabs, calls/voice chat, attachment picker, camera, permissions and external links.
- [ ] Verify Telegram verified/fake/scam/server-provided trust indicators remain stock; no custom supporter/developer/official badge appears.
- [ ] Verify notification overlay safe area, top animation and minimized browser/media controllers.

### 8.2 Account and persistence invariants

- [ ] Client-wide settings remain equal on A and B inside one installation: app icon, Ghost, Filters, General, Appearance, Chats and Other.
- [ ] Account-scoped data remains isolated: deleted archive, revisions, saved media, filter revisions, unread/read/action state and topic overrides.
- [ ] Full relaunch preserves settings and durable local state; no launch loop or migration warning.
- [ ] Reset Settings: Cancel is no-op; Confirm resets client-wide settings while preserving authorization, Telegram preferences and account archives/media according to product policy.

### 8.3 Stability and performance

- [ ] Run a 15-minute mixed scenario (chat, filter toggle, account switch, notification, archive, media viewer) without crash, freeze, unbounded spinner or memory-warning loop.
- [ ] Repeat ST03 and context-menu routes after the mixed scenario; no stale overlay remains.
- [ ] Capture crash/freeze evidence locally only; redact before sharing and never commit raw logs.

---

## 9. Final sign-off gate

### Mandatory completion conditions

- [ ] All mandatory IDs in Sections 2–8 are `PASS` or explicitly `BLOCKED` with reproducible external reason; no unexplained `FAIL`/`NOT RUN`.
- [ ] All 27 Stream A negative guards pass in both RU and EN.
- [ ] F19 matrix has evidence for history, chat preview, per-chat/topic unread, tab/app badge and notification overlay, including live toggle without relaunch.
- [ ] SP04A and ad/Premium-dependent tests have a named external fixture or are marked `BLOCKED`.
- [ ] No duplicate local notification enqueue/sound after filter revision; no hidden message/content leak in any listed surface.
- [ ] `ST03` hard-freeze route is explicitly rerun after all context-menu tests.
- [ ] macOS Swift/Bazel compile, IPA validation and device smoke are recorded separately from Windows source/contract tests.

### Evidence index

| Artifact | Path/link | Redacted? | Build | Notes |
|---|---|---|---|---|
| IPA metadata | `________________` | `yes/no` | `________________` | `________________` |
| RU screenshots | `________________` | `yes/no` | `________________` | `________________` |
| EN screenshots | `________________` | `yes/no` | `________________` | `________________` |
| F19 timeline | `________________` | `yes/no` | `________________` | `________________` |
| Archive/history evidence | `________________` | `yes/no` | `________________` | `________________` |
| Media evidence | `________________` | `yes/no` | `________________` | `________________` |
| CI/build logs (metadata only) | `________________` | `yes/no` | `________________` | `________________` |

### Verdict

```text
Build: ______________________________
RU: PASS / FAIL / BLOCKED
EN: PASS / FAIL / BLOCKED
Stream A removals: PASS / FAIL
Stream B partial/UI: PASS / FAIL / BLOCKED
Stream C runtime: PASS / FAIL / BLOCKED
F19 cross-surface: PASS / FAIL
Preserved Telegram regression: PASS / FAIL
Final device verdict: PASS / FAIL / BLOCKED

Open defects / external blockers:
1. ________________________________________________
2. ________________________________________________

Tester: __________________  Date: __________________
Reviewer: ________________ Date: __________________
```

### External release records (filled only after device QA)

- [ ] macOS Swift/Bazel build result and exact command recorded.
- [ ] IPA validation result recorded.
- [ ] GitHub Actions run ID, artifact name, version/build and IPA SHA-256 recorded.
- [ ] No commit contains personal screenshots, account identifiers, tokens, cookies or unredacted logs.
