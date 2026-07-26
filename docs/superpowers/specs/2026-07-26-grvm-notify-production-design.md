# GRVM Notify Production Design

**Дата:** 2026-07-26

**Статус:** согласованное направление; требуется подтверждение письменной спецификации перед implementation plan

**Native repository:** `Telegram-iOS-clean`

**Web baseline:** `morethanwords/tweb@e52b5d9318848ab83316cb53138358cf49d2a27f`

## 1. Решение

`GRVM Notify` реализуется как отдельная Home Screen PWA для iOS/iPadOS 16.4+ и как встроенный в GRVMgram мастер её подключения.

Пользователь воспринимает настройку как один последовательный сценарий:

1. запускает мастер из GRVMgram для текущего Telegram-аккаунта;
2. добавляет служебную PWA на Home Screen обязательными системными действиями iOS;
3. один раз нажимает `Активировать` в PWA;
4. разрешает уведомления и подтверждает создание отдельной Telegram Web-сессии в GRVMgram;
5. PWA завершает push-регистрацию автоматически.

QR-сканирование, пароль Telegram, копирование token/URL, ручной ввод кода и ручной выбор аккаунта в штатном сценарии отсутствуют.

PWA остаётся отдельным служебным значком. iOS не позволяет GRVMgram программно установить, скрыть или удалить Home Screen PWA и не позволяет автоматически подтвердить системное разрешение уведомлений.

## 2. Цели и критерии успеха

- Получать Telegram Web Push на iOS/iPadOS 16.4+ независимо от APNs-entitlement переподписанной через Sideloadly IPA.
- Не использовать собственный GRVM backend для хранения Telegram-сессий, переписки или push payload.
- Поддерживать ровно один Telegram Web-account на одну установленную PWA.
- В штатном сценарии заранее выбирать аккаунт, из которого пользователь открыл мастер GRVMgram.
- Исключить QR, login/password и copy/paste.
- Оставить только обязательные действия iOS и одно явное подтверждение чувствительной авторизации.
- Открывать из plain notification точный native account/chat/message, включая cold start приложения, когда target валиден и peer разрешается в локальном Telegram state; иначе показывать явную ошибку без перехода в другой чат.
- Не раскрывать preview при закрытой PWA с включённым local passcode.
- Проверить результат на реально собранной IPA и физическом устройстве.
- Добавить в третий QA checklist только проверки реально затронутых native областей; отдельную device-матрицу уведомлений хранить в отдельном документе.

Целевой happy-path budget — около восьми осознанных касаний от строки настроек GRVMgram до готового push:

1. `Настроить уведомления` в GRVMgram;
2. `Поделиться` в Safari;
3. `На экран «Домой»`;
4. системное `Добавить`;
5. открыть установленный значок `GRVM Notify`;
6. `Активировать`;
7. системное `Разрешить`;
8. `Подключить` в native confirmation.

iOS может добавить собственный prompt открытия GRVMgram. Если после native confirmation система не возвращает именно в standalone PWA, потребуется ещё одно нажатие её Home Screen icon; повторная авторизация при этом не выполняется. Приложение и PWA не должны добавлять промежуточные подтверждения, если они не нужны для безопасности или восстановления после ошибки.

## 3. Непреодолимые ограничения iOS

- Web Push доступен только web app, добавленному пользователем на Home Screen.
- Safari не предоставляет `beforeinstallprompt` или другой API для программной установки PWA на поддерживаемой нижней границе iOS 16.4.
- Нажатия `Поделиться`, `На экран «Домой»`, `Добавить` и системного `Разрешить` нельзя выполнить за пользователя.
- Удаление PWA прекращает её Web Push; служебный значок должен оставаться установленным.
- Native GRVMgram не может надёжно читать permission/subscription storage отдельной standalone PWA.
- Custom URL scheme не является доказательством происхождения запроса, поэтому Telegram login token нельзя принимать без явного native confirmation.

Configuration Profile/MDM не используется: для обычного пользователя он требует больше действий, создаёт пугающий trust flow и не даёт общего безопасного consumer-install механизма.

## 4. Архитектура

### 4.1 Native GRVMgram

Native часть отвечает только за:

- запуск мастера для выбранного аккаунта;
- хранение install-wide pairing state;
- строгий разбор `grvmgram://notify-auth` и `grvmgram://notify-open`;
- явное подтверждение и вызов существующего `approveAuthTransferToken`;
- сохранение canonical `RecentAccountSession.hash`;
- точное разрешение public Telegram user ID в локальный `AccountRecordId`;
- открытие account/chat/message;
- exact revoke и переход в штатный экран `Устройства`;
- честные состояния ошибки, orphaned session и неподтверждённого disconnect.

Минимальная новая поверхность:

- `GRVMNotifyDeepLink` — pure parser с unit/contract tests;
- `GRVMNotifyState` — Codable install-wide state в `AccountManager.sharedData`;
- `GRVMNotifyCoordinator` — один single-flight coordinator в `TelegramUI`;
- settings/onboarding UI и RU/EN localization;
- явное расширение cold-start allowlist рядом с `AppDelegate` launch-options routing и единый hook для всех foreground UIKit URL callbacks;
- общий pending-request buffer, который передаёт оба пути в один coordinator;
- регистрация scheme `grvmgram` в Bazel/plist без удаления существующего `tgfork`.

Stock `tg://login` и обычный URL routing не изменяются.

### 4.2 GRVM Notify PWA

Web часть является pinned fork `tweb`, а не новым MTProto-клиентом. Она переиспользует:

- `auth.exportLoginToken` и существующий polling/DC migrate flow;
- Telegram account storage;
- `account.registerDevice` с `token_type = 10`;
- Web Push subscription и Service Worker;
- upstream passcode encryption и live-window decrypt bridge.

В GRVM Notify mode поверх готового bootstrap показывается один setup surface. Обычный multi-account/chat UI не предлагается как часть мастер-сценария.

После подключения setup surface превращается в минимальный management screen: фактический Web Push status, режим preview/privacy, retry, переход в GRVMgram и disconnect. Он также даёт доступ к существующей настройке local passcode, не открывая добавление второго аккаунта.

### 4.3 Hosting

- Канонический целевой origin: `https://grvm-notify.pages.dev`.
- Hosting: Cloudflare Pages, static files only.
- `/setup/*` обязан переписываться на `/index.html`.
- Service Worker выпускается в корне и получает scope `/`.
- После первого production enrollment origin считается неизменяемым: его смена потребует переустановки PWA и новой push subscription.
- Публичный deploy выполняется только вместе с GPL-совместимым доступом к полному modified source и build scripts.

## 5. Install-wide state

Native state хранится вне Postbox отдельного аккаунта и содержит:

- `pairedUserId: Int64?`;
- `sessionHash: Int64?`;
- `pendingAccountUserId: Int64?`;
- `pendingStartedAt: Int32?`;

Инварианты:

- `pairedUserId` и `sessionHash` либо оба заданы, либо оба отсутствуют;
- `sessionHash` не равен нулю;
- live pairing на установку только один;
- pending target задаётся текущим аккаунтом до открытия Safari;
- pending target действует 24 часа либо до явной отмены/успешного pairing; после expiry PWA предлагает заново запустить мастер из GRVMgram;
- штатный auth callback использует pending target и не показывает chooser;
- callback без допустимого pending target не выбирает случайный/current account и требует перезапустить мастер из GRVMgram;
- account switch и logout автоматически не заявляют, что независимая PWA-сессия отозвана.

Public Telegram user ID нельзя преобразовывать в `AccountRecordId(rawValue:)`. Разрешение выполняется перебором active account contexts и требует ровно одного совпадения public peer ID.

Сохранённые `pairedUserId/sessionHash` доказывают наличие принятой Telegram Web-сессии, но не доказывают действующую browser permission или успешную push registration. Native UI называет это состояние `Web-сессия подключена`; authoritative push status показывается внутри PWA. При registration error сессия сохраняется, а management screen предлагает retry либо disconnect.

## 6. Поток подключения

### 6.1 Запуск

1. Пользователь открывает `Настройки GRVMgram → Уведомления` для текущего аккаунта.
2. GRVMgram записывает pending account и открывает fixed HTTPS setup URL в Safari.
3. Страница показывает только короткую пошаговую инструкцию установки для текущей версии iOS.
4. Пользователь выполняет системное Add to Home Screen и запускает PWA.

Работоспособность не зависит от переноса query-параметров или storage между Safari и standalone PWA.

### 6.2 Одна кнопка PWA

Нажатие `Активировать`:

1. проверяет standalone mode и поддерживаемую iOS;
2. вызывает `Notification.requestPermission()` непосредственно из user gesture;
3. при отказе остаётся в понятном состоянии `permission-denied`;
4. запускает существующий tweb QR login-token flow без показа QR как обязательного действия;
5. формирует строгий `grvmgram://notify-auth` и пытается открыть GRVMgram; если iOS блокирует automatic transition после async permission/token flow, показывает одну явную кнопку `Продолжить в GRVMgram` с актуальным вращающимся token;
6. продолжает существующий polling, пока native не примет token;
7. после `auth.loginTokenSuccess` автоматически выполняет push registration;
8. показывает финальное состояние `Готово` либо конкретную восстанавливаемую ошибку; повторная попытка регистрации не требует повторного Telegram login.

### 6.3 Native authorization

Native handler:

1. поглощает все URL со scheme `grvmgram`, включая malformed, не передавая их stock external routing;
2. в cold start явно допускает `grvmgram` в `launchOptions[.url]`, а foreground UIKit callbacks передают тот же URL в общий pending buffer;
3. принимает только allowlisted command, уникальные query fields, bounded base64url token и exact HTTPS return origin;
4. требует существующий pending target account;
5. сохраняет parsed request и ждёт matching `AuthorizedApplicationContext`, готовность root UI и `AppLockContext.isCurrentlyLocked == false`;
6. после readiness/unlock повторно проверяет pending target, наличие аккаунта и отсутствие уже активного pairing;
7. показывает confirmation с именем точного аккаунта и объяснением отдельной Web-сессии;
8. вызывает `approveAuthTransferToken` на найденном `AccountContext`;
9. в первом success callback вызывает `GRVMNotifyStateStore.writeAndVerify`, который записывает `pairedUserId + sessionHash` и читает entry обратно до показа успеха;
10. при отрицательном logical read-back пытается сразу отозвать только что созданную сессию; low-level disk atomicity всё равно не обещается;
11. пытается открыть allowlisted HTTPS return URL. Если iOS не возвращает в установленную standalone PWA, native экран явно просит один раз открыть `GRVM Notify` с Home Screen; сохранённый polling/login state продолжает сценарий без повторного подтверждения.

Coordinator не принимает два token параллельно. Ошибки `.invalid`, `.expired`, `.alreadyAccepted` и `.generic` получают разные пользовательские сообщения и безопасный restart path.

Новый URL, logout, удаление target account или отмена мастера инвалидируют ожидающий request. Account switch сам по себе не переназначает request на другой аккаунт. Automated tests используют fault-injecting state-store double для проверки отрицательного `writeAndVerify` и exact rollback.

Полностью устранить crash gap между server accept и локальным сохранением hash невозможно. Если приложение будет принудительно завершено в этом узком интервале, пользователь получает инструкцию проверить `Настройки Telegram → Устройства`; приложение не заявляет ложный successful pairing.

## 7. Push registration policy

GRVM Notify mode поддерживает только один logged-in Web account. Ограничение применяется до создания/изменения subscription и во всех путях регистрации:

- settings effect;
- явная registration из setup UI;
- `registerAgain`;
- `account_logged_in`;
- retry после reconnect/service-worker refresh.

Все эти пути и GRVM-mode account-login/logout mutation events используют один mutex и один общий policy method. `notifyAllAccounts = false` не считается registration guard.

Single-account preflight выполняется до `settings.push = true`, до запроса/создания `PushSubscription` и до изменения `registeredDevice`. Обычное multi-account поведение upstream tweb вне GRVM Notify mode не меняется.

Каждое изменение logged-in account set увеличивает `accountsGeneration`. Registration захватывает generation и exact account identity, повторно валидирует их непосредственно перед server call и после acknowledgement. Если набор аккаунтов изменился, partial registration отзывается, локальный committed state не меняется, а UI переходит в `multi-account-blocked` или retryable error. Второй account нельзя добавить через скрытый UI, но policy не полагается только на UI.

Обязательные исправления pinned upstream:

- записывать `registeredDevice` только после успешного acknowledgement всех `account.registerDevice`;
- при ошибке оставлять состояние пригодным для повторной попытки;
- аналогично не очищать unregister state до server acknowledgement;
- передавать `other_uids` как массив;
- не логировать subscription endpoint, `p256dh`, `auth`, secret, account IDs, raw/decrypted payload или message body;
- не логировать `auth.exportLoginToken`, полный `grvmgram://notify-auth`, его query fields либо token-bearing error/crash breadcrumbs в web и native;
- исправить cold-worker race: encrypted handler сначала `await`-ит загрузку key metadata и при любой storage/parse/decrypt ошибке всегда показывает generic fallback;
- не переносить `push_key` в незашифрованное Service Worker storage.

## 8. Privacy и содержимое уведомлений

### Local passcode OFF

- `secret` при registration пустой.
- Production gate должен доказать, что Telegram присылает plain payload.
- Закрытая PWA показывает разрешённые Telegram/PWA privacy settings sender/chat/body и IDs.
- Click может открыть точный native account/chat/message.

### Local passcode ON

- Используется случайный per-account `push_key` из шифруемого account storage tweb.
- При живом unlocked PWA client upstream bridge может расшифровать `{p}`.
- При полностью закрытой PWA Service Worker показывает только generic/no-preview notification.
- Generic notification без проверяемых IDs открывает PWA root, а не произвольный native chat.

GRVMgram не обходит lock-screen privacy пользователя и не пытается раскрывать скрытый текст.

## 9. Notification click и native navigation

Для exact click PWA принимает только согласованный набор положительных целых значений:

- public `account_user_id`;
- ровно один peer kind: user/group/channel;
- raw peer ID;
- cloud message ID в диапазоне `Int32`;
- optional thread/topic identifier, если он присутствует в фактическом Telegram payload.

`account_user_id` из payload и mapping `push_accounts[accountNumber]` должны совпадать, если присутствуют оба. Несовпадение или неполный target не открывает произвольный аккаунт.

Service Worker открывает HTTPS landing. Account/chat/message identifiers передаются в URL fragment, а не в server-visible query, чтобы они не попадали в hosting request logs и referrer. Landing пытается вызвать `grvmgram://notify-open`; видимая кнопка `Открыть в GRVMgram` остаётся fallback, пока device QA не докажет надёжный automatic jump.

Native coordinator:

- проверяет ownership по сохранённым `pairedUserId/sessionHash`;
- разрешает public user ID в exact active context;
- строит namespaced `PeerId` и cloud `MessageId`;
- получает от `AppDelegate` отдельную navigation closure: она переключает exact account, ждёт matching `AuthorizedApplicationContext`, его root readiness и снятие app lock, повторно проверяет ownership/account, затем вызывает `openChatWithPeerId(..., alwaysKeepMessageId: true)`; это гарантирует message subject и для старого входящего сообщения;
- для отсутствующего peer подписывается максимум на 5 секунд на локальный peer state, не заявляя, что это инициирует сетевую загрузку; request отменяется при новом URL/logout/account removal;
- если peer за 5 секунд не появился, показывает localized `Чат ещё не синхронизирован` и не открывает другой target;
- v1 не угадывает forum thread ID. Только подтверждённое положительное поле `custom.thread_id` может быть передано navigation closure; без него forum notification открывает parent forum/chat fallback без гарантии точного topic/message.

Foreground и cold-start переходы используют один parser/handler.

## 10. Disconnect, revoke и восстановление

Поддерживаются три пользовательских пути:

- `Отключить` в PWA: staged state machine `ready → unregistering → serverUnregistered → loggingOut → disconnected`;
- `Отключить` в GRVMgram: exact revoke сохранённого `sessionHash` через paired native account;
- ручной revoke через штатный Telegram `Настройки → Устройства`.

PWA не выполняет logout/local cleanup, пока server unregister не подтверждён. При unregister error она сохраняет subscription/account/session material, показывает `unregister-failed` и предлагает retry. Если logout произошёл вне staged flow, UI показывает partial disconnect и направляет к native/Devices revoke вместо заявления об успешном отключении.

После подтверждённого PWA logout native pairing state может временно оставаться до следующего открытия GRVMgram. Settings screen запускает error-preserving reconciliation; успешный server response без сохранённого hash очищает state. PWA может лишь предложить открыть GRVMgram для этой проверки и не отправляет недоверенный callback, который самостоятельно очищает native ownership.

Native state очищается после успешного completion `terminateAnotherSession(id:)`. Для reconciliation после ручного Devices revoke добавляется минимальный error-preserving one-shot TelegramEngine method поверх `account.getAuthorizations`; только успешный server response без exact hash очищает state. Timeout, retrying `ActiveSessionsContext`, `nil` result или offline не считаются доказательством отсутствия сессии.

Если paired native account удалён:

- ownership сохраняется как orphaned;
- другой текущий аккаунт не используется для revoke;
- GRVMgram предлагает повторно добавить тот же account либо отозвать сессию через Devices на другом Telegram-клиенте;
- локальный state не очищается под видом отключения.

HTTPS-страница не обещает очистить storage отдельной standalone PWA. После native revoke пользователь при необходимости один раз открывает Home Screen PWA, чтобы она завершила локальную cleanup.

## 11. Build и deployment hardening

- Clone/build tweb выполняется с LF; Windows CRLF parser defect исправляется через `trim()` и repository line-ending policy.
- Используются Node `^22.18 || >=24.11` и `pnpm@11.16.0`.
- Production build выключает source maps.
- Deploy staging создаётся с нуля по allowlist; старые hashed bundles из upstream `public/` не копируются.
- Release staging включает только `index.html`, manifest, актуальный root `sw-*.js`, текущие build-referenced JS/CSS/runtime assets, GRVM icons, `_headers`, `_redirects`, license/notices и source link. `.map`, tests, raw sources и старые root bundles исключаются.
- `_redirects` содержит SPA rewrites `/setup/* /index.html 200` и `/open/* /index.html 200`.
- `_headers` задаёт минимум `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`, ограниченный `Permissions-Policy` и проверенную build-smoke CSP с `frame-ancestors 'none'`, `base-uri 'self'`, `object-src 'none'`; необходимые Telegram HTTPS/WSS/media/worker origins добавляются только по фактическому runtime inventory.
- Любые public API/VAPID values считаются public configuration, но не публикуются произвольно до проверки разрешённой конфигурации и реального `account.registerDevice`.
- Upstream VAPID public key нельзя заменять без соответствующего sender-side private key.
- GPL handoff включает modified source, build scripts, notices и точную pinned upstream revision.

## 12. Проверка

### Web automated checks

- deep-link builder/parser и duplicate-field rejection;
- standalone/support detection;
- permission только из user gesture;
- single-account policy во всех registration entry points;
- account-generation race до/во время/после server registration;
- registration/unregistration acknowledgement, rollback и retry;
- `other_uids` array shape;
- cold encrypted push generic fallback;
- passcode OFF/ON state labels;
- click target validation и account mapping disagreement;
- log redaction;
- отсутствие login token и полного auth URL в logs/crash breadcrumbs;
- staged disconnect и сохранение retry state при partial failure;
- clean production staging, no source maps, Service Worker scope и `/setup/` rewrite.

### Native automated checks

- foreground/cold-start strict URL parsing;
- killed-app `grvmgram` admission через launch options и общий pending buffer;
- malformed `grvmgram` URL поглощается;
- public user ID никогда не raw-cast в `AccountRecordId`;
- pending-account happy path без chooser;
- multi-account unexpected callback rejection;
- single-flight token acceptance;
- root readiness, locked cold start и logout/account switch во время ожидания;
- `writeAndVerify` state persistence и fault-injected exact rollback path;
- ownership checks для notification click;
- user/group/channel/message/thread parsing;
- exact incoming-message navigation с `alwaysKeepMessageId = true`;
- 5-second local missing-peer wait/error и forum parent fallback без проверенного `custom.thread_id`;
- exact revoke, error-preserving session reconciliation, offline ambiguity и orphaned account state;
- RU/EN localization и settings visibility.

### Единственный итоговый release gate

После web/native реализации выполняется один полный локальный contract gate и независимый whole-diff review. Затем выполняется одна macOS CI-сборка IPA, скачивание artifact и реальная установка через Sideloadly.

Device matrix проверяет:

1. Add to Home Screen и one-flow onboarding без QR/password/copy/paste.
2. Permission denied и повторное включение через iOS Settings.
3. Один Web account; второй блокируется до disconnect.
4. Plain push при полностью закрытой PWA и passcode OFF.
5. Generic/no-preview push при полностью закрытой PWA и passcode ON.
6. Live-client decrypt при passcode ON.
7. Click в foreground, background и cold-start IPA.
8. Exact account/chat/message для локально разрешимого peer; forum topic только при подтверждённом `custom.thread_id`, иначе parent fallback.
9. Missing peer и malformed payload без открытия неправильного чата.
10. Network failure/retry регистрации.
11. Native revoke, PWA disconnect и Telegram Devices revoke.
12. Logout/удаление paired native account.
13. Relaunch, account switch и семидневный Sideloadly re-sign cycle.
14. Automatic return в standalone PWA и fallback через повторное открытие Home Screen icon без повторной авторизации.

Notification device results хранятся в `docs/grvm-notify-device-qa.md`. В `docs/grvmgram-third-build-qa-checklist.md` добавляются только regression-карточки затронутого native URL/account/navigation/settings потока.

## 13. Production go/no-go

Это не throwaway prototype: все проверки выполняются на production code path. Публичный выпуск блокируется, если не подтверждён хотя бы один из пунктов:

- Telegram принимает `token_type = 10` на выбранной production-конфигурации;
- iOS доставляет plain push полностью закрытой Home Screen PWA;
- passcode ON гарантированно показывает generic fallback без утечки;
- single-account invariant выдерживается при login/reconnect/settings churn;
- notification click не открывает неправильный account/chat;
- native auth confirmation и exact revoke работают на реальной IPA;
- static deployment не содержит stale bundles/source maps и сопровождается GPL source handoff.

Если automatic PWA-to-native jump нестабилен, production допускает видимую fallback-кнопку. Остальные go/no-go пункты обязательны.

## 14. Явные non-goals первой версии

- Один физически установленный значок вместо native IPA + Home Screen PWA.
- Программное нажатие системных Add/Allow.
- Native APNs и собственный push provider/backend.
- Несколько Telegram Web accounts в одной установленной PWA.
- Full encrypted preview при полностью закрытой PWA с passcode ON.
- Синхронизация native-only GRVM filters, Shadow Ban и foreground dedupe в PWA.
- Гарантированный exact forum-topic routing без подтверждённого thread identifier в Telegram push payload.
- Автоматический revoke после удаления paired native account.
- Не связанный с уведомлениями рефакторинг Telegram-iOS или tweb.
