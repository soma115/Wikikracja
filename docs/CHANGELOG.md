# CHANGELOG


## v1.6.0 (2026-08-10)

### Features

- **polls**: Add poll/survey module with live countdown, stopwatch icon and voting results view.
- **site parameters**: Move system parameters from `settings.py` to the database with a referendum-based management interface.
- **notifications**: Reintroduce Firebase Cloud Messaging (FCM) push notifications with debounce, delivery acknowledgements and mobile (Android/iOS) event reminders.
- **assets**: Add asset/resource view with filtering, searching and configurable columns.
- **onboarding**: Replace onboarding with Quick Links dashboard supporting drag-and-drop and localStorage.
- **chat**: Auto-save message drafts, Enter / Ctrl+Enter to send, persistent unread filter, per-row read/unread toggle and chat tile on dashboard.
- **voting**: Rich-text character counter, better handling of cached votes, `Status.IntegerChoices` for decision status, restart referendum on lost cached votes and delayed vote saving.
- **board**: Add post slug field with SEO-friendly URLs and featured image size handling.
- **email**: Queue individual emails, order email sections, catch/deliver errors and improve test coverage.
- **search**: Add global search.
- **users**: Auto-verify emails for invited users, add Voivodeship/Country fields and clean up profile form.
- **decisions**: Add version history with diff visualization.

### Bug Fixes

- Fix missing `verified=True` on `account_emailaddress` records.
- Fix "account not found" signup issue.
- Fix demo environment issue.
- Suppress `asyncio.CancelledError` logs from ASGI disconnects.
- Fix 301 redirect for email login links.
- Fix chat room sorting case-insensitivity.
- Fix lost newline formatting in voting descriptions.

### Refactor

- Consolidate CSS variables and utility classes, remove inline styles and unused themes.
- Refactor dashboard tiles and top navigation.
- Remove custom login template, redirect to allauth default.
- Remove unused admin sections.
- Update docs and changelog.


## v1.5.0 (2026-06-10)

### Bug Fixes

- **bookkeeping**: Key pivot rows by cat_id, not category name
  ([`90eccf3`](https://github.com/soma115/Wikikracja/commit/90eccf3500707650795fe8bd73aab4b8e77b2c49))

Deleted categories all resolved to cat_name='—', causing rows_by_cat.setdefault('—', …) to merge
  them into a single row and sum their amounts incorrectly.

Key the dict by cat_id (integer) instead; the display label 'category_name' stays '—' for
  missing/null categories but each original category ID gets its own row.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **bookkeeping**: Make Asset.save() default-switch atomic
  ([`fdf110a`](https://github.com/soma115/Wikikracja/commit/fdf110af9d4f5c76625ae3a8e5e23078aec1f5a3))

Setting is_default=True unsets the previous default before saving the new one. Without a
  transaction, if super().save() raised after the unset, the DB was left with zero defaults and no
  rollback. Wrapped both steps in transaction.atomic().

Also flags validate_constraints() with a TODO: it excludes is_default globally, so any future
  constraint on that field would be silently skipped at form validation and only surface as an
  IntegrityError on save — future constraints should narrow exclude to the constraint name.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **bookkeeping**: Require asset on transactions at DB level
  ([`71b0406`](https://github.com/soma115/Wikikracja/commit/71b04060186aea8ac138cf243ccaa69134fdf41f))

Transaction.asset was null=True (a legacy artifact of adding the field to existing rows in
  0026/0027), while the form already required it (blank=False). NULL-asset transactions would
  silently vanish from asset_balances and category_breakdown, which skipped asset_id=None.

Migration 0030 defensively backfills any NULL asset with the default asset (a no-op in practice —
  0027 already backfilled all to PLN), then alters the field to NOT NULL. Creating a transaction
  without an asset now raises IntegrityError instead of disappearing from the books.

Removes the now-dead `asset is None` guards in services.py. Keeps the `asset_obj is None` guard (a
  distinct referential check, not nullability).

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **chat**: Case-insensitive room name check with Unicode support
  ([`f39a237`](https://github.com/soma115/Wikikracja/commit/f39a2378abbbecd104b2cdde10003ea37e732dda))

Replaced DB-level iexact with Python casefold() scan. SQLite's LIKE only case-folds ASCII A-Z, so
  Polish letters like Ś/ś, Ż/ż, Ó/ó slipped through — 'Środa' and 'środa' could coexist as separate
  rooms.

Python's casefold() handles full Unicode case-folding correctly and is DB-agnostic. Full table scan
  is acceptable for the rooms table; a denormalized title_cf column with an index would be the next
  step at large scale.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **chat**: Data-raw in EJS template stops "pokaż więcej" leaking into edited content
  ([`9a5988a`](https://github.com/soma115/Wikikracja/commit/9a5988a857df775a9529f65055cb2887ed3457f1))

Edycja wiadomości załadowanej z historii (po reload) wstrzykiwała literalny tekst "… pokaż więcej"
  do treści. Przyczyna: dataset.raw był ustawiany tylko w addMessage (nowe wiadomości w sesji), więc
  batch insert / replace / embed renderowały .msg-text bez raw_text. setEditing fallback'ował do
  innerHTML — czyli ciągnął całą strukturę .expandable razem z hint'em. User edytował, wysyłał z
  powrotem, backend zapisywał HTML expandable jako część treści.

Fix: data-raw="<%=raw_message%>" w template'cie EJS — single source of truth dla wszystkich 4
  ścieżek renderu. EJS <%= escape'uje wartość bezpiecznie do atrybutu. Po edycji (editMessageText /
  updateMessage) dataset.raw jest synchronizowane tuż przed innerHTML.

Test: e2e/chat-edit-message.spec.js pokrywa oba scenariusze (sesja + reload).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

- **chat**: Handle race condition in _post_send_processing
  ([`af6259c`](https://github.com/soma115/Wikikracja/commit/af6259c46cf80d46aea4ff25d813c559e251862c))

When online_registry reports a member as online but get_consumer() returns None (race between
  registry check and disconnect), the code fell through to consumer.repo.unsee_room() with
  consumer=None, raising AttributeError on every message sent to the room.

Consolidate the no-consumer branch: skip further processing with continue regardless of mute status;
  only schedule a push notification beforehand when not muted.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **chat**: Label system messages as "System" instead of "—"
  ([`b7c3a94`](https://github.com/soma115/Wikikracja/commit/b7c3a94ded366d209b44ddf300c069f08f5ad7b3))

System messages (sender=None, non-anonymous — e.g. room rename) were rendered with no author: the
  sidebar preview and message bubble showed "—:" because build_chat_message_payload returned
  username=None and the room_link template fell into its else branch.

- serializers.py: username falls back to "System" for sender-less, non-anonymous messages
  (consistent with the notification title path, which already used "System"). - room_link.html: else
  branch renders {% trans 'System' %} instead of "—".

The .po diff is otherwise pure churn — line-number updates and a reorder of the already-translated
  "Change language" string; the only new entry is "System" / "System".

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **chat**: Unread filter respects manual toggle over URL intent
  ([`b824245`](https://github.com/soma115/Wikikracja/commit/b8242454e5d711d1f769d9a77745bbb65f105e7c))

decideUnreadFilterOverride + flaga userToggledFilter: reczny klik usera bije asynchroniczne
  wsOnConnect, ktore czytajac wciaz obecne ?view=unread w URL wlaczaloby filtr z powrotem (bug
  "filtr wraca po odkliknieciu").

Empty-state "brak nieprzeczytanych": gola ikona -> realny <button> delegujacy do #unread-filter-btn
  (bez duplikacji logiki), aria-label opisuje akcje (zdejmuje filtr). Guard after='' gdy tlumaczenie
  zgubi placeholder {icon}.

Testy: decideUnreadFilterOverride (8) + showUnreadEmptyState (6, jsdom).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>

- **chat**: Update sidebar preview on last message edit
  ([`e62dc9e`](https://github.com/soma115/Wikikracja/commit/e62dc9e8fa182e35a6780aa7daef1c5ba80b6e7b))

Editing the last message in a room now refreshes the sidebar snippet for all connected clients in
  real time, and persists the updated text to Room.last_message_text in the DB.

Backend: - signals.py: on Message edit, update last_message_text only when the edited message is the
  room's last (checked by pk, immune to auto_now changing Message.time on every save). Guard skips
  the exists() query for saves that don't touch the text field. - services.py:
  is_last_message_in_room() repo method (pk__gt). - consumers.py: edit_message payload gains
  room_id, username, anonymous, is_last_message so the frontend can update the sidebar correctly.

Frontend: - domapi.js: updateSidebarForMessage() gains {reorder, bumpActivity} options. bumpActivity
  defaults to reorder, so new messages bump date and dataset.lastActivity as before; edits pass
  reorder:false and get bumpActivity:false automatically — snippet and sender update but the sort
  key and displayed date stay untouched. - chat.js: onReceiveEdit calls
  updateSidebarForMessage({reorder:false}) when is_last_message is true.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **chat**: Update unread badge in real-time for online users who had seen the room
  ([`8285e1b`](https://github.com/soma115/Wikikracja/commit/8285e1b1638f788e5d6bfa309b722e174ff32a3e))

consumer.unsee_room(room) does not exist on ChatConsumer — only on ChatRepository. This caused
  AttributeError swallowed by the try/except, so online receivers never got a push_unread_count()
  call and their nav badge stayed stale until next page load or tab refocus.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **ci**: Downgrade GitHub Actions to stable versions
  ([`0ca48ac`](https://github.com/soma115/Wikikracja/commit/0ca48ac16fa92c0c85ad80e9c4430e6dd127f9e0))

actions/checkout v6, docker/* v4-v7 don't exist — caused workflow failure on every push.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **expandable**: Block toggle when selection intersects body
  ([`a098aa3`](https://github.com/soma115/Wikikracja/commit/a098aa3a62c3dc0340ca2d7b483048b45258cf3f))

Add intersectsNode guard and Jest tests for cross-boundary selection. Bump app version to 1.4.3.
  Stop tracking CLAUDE.md; ignore local AI rules files in .gitignore.

Co-authored-by: Cursor <cursoragent@cursor.com>

- **i18n**: Restore 3 Polish translations dropped during main merge
  ([`db3d7cd`](https://github.com/soma115/Wikikracja/commit/db3d7cd3bde66927468713294e8dddad387fa7c1))

makemessages after the merge picked up new msgids from main's side but left their msgstr empty
  because main's .po wasn't merged. Restore the missing translations (with typo fixes vs main's
  original):

- "This information will allow us to contact you and activate your account." — fix main's typo
  "skonaktować" -> "skontaktować" - "We will contact you soon." - "We have sent an email with a
  confirmation link to your inbox."

PLN -> zł was dropped from main but is no longer used in our code after the bookkeeping refactor
  (asset_balances returns symbol dynamically), so makemessages no longer extracts it.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

- **i18n**: Unstick PL email confirmation msgstr (merge artifact)
  ([`a0b63d4`](https://github.com/soma115/Wikikracja/commit/a0b63d4edbd912932db375d15fda48a7f25f4008))

msgstr for "Your email has been confirmed... onboarding form: %(link)s" had a duplicated tail glued
  after %(link)s — second copy of the same sentence with slightly different phrasing. Likely
  artifact of an earlier merge or paste-during-translation. User saw the duplicate text in the
  confirmation email.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

- **richtext**: Eliminate ghost empty lines from paste and legacy DB content
  ([`fca609e`](https://github.com/soma115/Wikikracja/commit/fca609eeccf8e8151bec4cc88bb8e090f906be36))

Root cause was 2-layered: 1. Frontend paste used execCommand('insertText') → browser wrapped in
  <div> blocks with filler <br>, then getInputHtml serialized those blocks to "<br><br>" producing
  extra empty lines. 2. Backend sanitize() did NOT normalize \n → <br>; only the |richtext template
  tag did. Chat consumers and RichTextWidget stored raw \n in DB, and edit-flow re-emitted raw \n
  via TEXT_NODE in getInputHtml, perpetuating the bug for any legacy or non-template-tag render
  path.

Changes: - richtext-core.js: new insertPlainTextAtCaret() inserts text+<br> via DOM API;
  getInputHtml normalizes block fillers, strips trailing <br>, and converts \n in TEXT_NODE (legacy
  content) to <br>. - All 3 paste handlers (chat normal, embedded, RichTextWidget) use
  insertPlainTextAtCaret — single source of truth. - sanitize() (zzz/richtext.py): central
  CRLF/CR/LF → <br> normalization before bleach.clean. Template tag drops its duplicate. - 28 jest
  tests + 13 Django tests + 2 Playwright E2E covering paste, legacy TEXT_NODE, CRLF, edit-flow.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

- **richtext**: Handle &amp; entity as unit in URL linkification regex
  ([`6203a79`](https://github.com/soma115/Wikikracja/commit/6203a79154d6fb1ed72a29e66f71e6cce95236c5))

URL_REGEX alternation ((?:&amp;|char_class)*) tries the 5-char entity sequence first, preventing the
  regex from stopping at ';' mid-entity. Added tests covering &amp; in query strings and regression
  for pre-linked <a> tags that must not be double-wrapped.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **tasks**: Clip get_chat_room_title to 90 chars correctly
  ([`83235e6`](https://github.com/soma115/Wikikracja/commit/83235e68fe8e2c8d824e521369ee2a9c6531ba91))

f"Task #{id}: {title[:90]}" clips the title first, then prepends the prefix — a 100-char title would
  yield a 107-char result. Moved the slice to the end of the full string instead.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **test**: Ignore collectstatic dir in jest
  ([`1f2502b`](https://github.com/soma115/Wikikracja/commit/1f2502b76304c9049dc8f44a4675a8e8b37106be))

jest.config nie mial testPathIgnorePatterns, wiec Jest kolekcjonowal stale kopie testow z root-owego
  static/ (collectstatic, gitignorowany) obok zrodel <app>/static/... — kazdy test chatu/home lecial
  2x (11 suit / 140 testow zamiast 6 / 73). Stara kopia po edycji testu bez ponownego collectstatic
  dawalaby falszywy PASS maskujacy regresje.

Kotwica <rootDir>/static/ trafia tylko w root static/, nie w zrodla pod <app>/static/ (gole /static/
  wycieloby wszystkie testy -> 0 zebranych).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>

- **tests**: Use TransactionTestCase for SendEmailToAll thread visibility
  ([`fd8d0ba`](https://github.com/soma115/Wikikracja/commit/fd8d0baf9e62148bb42bd7f3f4106cdb8ca4c61e))

`SendEmailToAll` spawns a background thread that queries the DB for active users. Under `TestCase`
  the test runs inside a transaction invisible to the background thread — its read hits an
  `OperationalError: database table is locked: obywatele_uzytkownik`, the exception is swallowed by
  the broad except

in `_send_with_delay`, and the email never reaches `mail.outbox`. Result: 2 tests asserting outbox
  counts (1 and 2 emails) always saw 0.

`TransactionTestCase` commits between operations, so the worker thread sees the test fixtures.
  Production race-condition protection in `SendEmailToAll._get_recipients` (run inside the thread,
  just before send) is preserved.

`ChatMessagesEmailTest` left on `TestCase` — its worker thread does not hit the DB (recipients
  computed in the main thread before spawn).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

- **ui**: Anchor referendum toast over card without layout jump
  ([`337dd9f`](https://github.com/soma115/Wikikracja/commit/337dd9f112f93dcd07e74c2b8c5b98358c7e4283))

The signature/referendum confirmation toast was centered at a fixed 33% viewport offset, ignoring
  screen width. Anchor it horizontally to the content card and place it near the card title instead.

Two follow-up issues addressed: - The notification permission banner expands via a 300ms max-height
  transition that pushes the card down. Measuring the card at DOMContentLoaded gave a stale
  position, so the toast appeared too high. Hide the toast until placed and reveal it only after the
  banner's transitionend (or immediately when no banner animates), eliminating the visible jump. -
  The banner's frozen max-height could clip wrapped text after a resize/orientation change;
  recompute shown banners on resize.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>

### Chores

- **deps**: Bump @babel transitives via npm install drift
  ([`1e4e3fb`](https://github.com/soma115/Wikikracja/commit/1e4e3fb605516205bb97776c5cad9fd5136457e3))

Lockfile resolved newer @babel/* (7.28.x/7.29.0-3 → 7.29.7) during local npm install for jest/jsdom
  devDeps. No package.json changes.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

- **deps**: Bump pytest 8.3.4->9.0.3 (CVE-2025-71176)
  ([`3a40ecc`](https://github.com/soma115/Wikikracja/commit/3a40eccabe2c98d13721303e891c9b03db8befe4))

Fixes Dependabot alert #72 (GHSA-6w46-j5rx-g56g): pytest <9.0.3 used an insecure
  /tmp/pytest-of-{user} tmpdir pattern on UNIX (local DoS / privesc).

Bump test plugins for pytest 9 compatibility: - pytest-django 4.9.0 -> 4.12.0 - pytest-asyncio
  0.25.0 -> 1.4.0 (major 0.x->1.x; existing asyncio_mode=auto +
  asyncio_default_fixture_loop_scope=function already satisfy 1.x requirements, so no config change
  needed)

Full suite green: 373 passed under Python 3.14.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>

### Features

- **board**: Allow deleting document categories in use
  ([`c2a7ef5`](https://github.com/soma115/Wikikracja/commit/c2a7ef5f4b15af1fa5c97c9376824e2f3832afd4))

Deleting a document category that documents reference is now allowed: the FK Post.category is
  SET_NULL, so those documents simply become uncategorized instead of returning a 409 "reassign
  first" error.

Before deletion the manage-categories modal fetches and lists the affected document titles in the
  confirm dialog (native confirm with up to 10 titles + "…and N more"), so the user sees exactly
  what will be orphaned. Protected categories stay blocked (403).

- categories: add generic CategoryItemsAPI (titles + true count, ordered and capped) reusable across
  apps - board: PostCategoryDeleteAPI block_if_in_use=False; PostCategoryItemsAPI endpoint (limit
  10); wire url + template urls.items/and_more - category-manager.js: optional items branch gated on
  urls.items, so tasks (no items url) keeps the old count-only confirm - tests: delete-in-use
  unassigns, protected→403, items+limit ordering, login required

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>

- **bookkeeping**: Asset.is_default with auto-unset save + DB constraint
  ([`627ba7f`](https://github.com/soma115/Wikikracja/commit/627ba7fa4afc6028129fb151fd6e9d954efd3477))

Add is_default boolean field to Asset, auto-unset previous default in save(), backstop via partial
  UniqueConstraint. Override validate_constraints() to exclude is_default from form-level checks so
  ModelForm doesn't block before save can satisfy the constraint. Includes classmethod get_default()
  with fallback to oldest asset. Polish translations bundled together (.po cannot be staged
  partially).

10 model tests covering field default, persist, auto-unset (create/update/self), form promote
  regression, bypass-via-update integrity, get_default branches.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

- **bookkeeping**: Services layer + pivot report + per-asset bar on transactions
  ([`118c935`](https://github.com/soma115/Wikikracja/commit/118c93594fed3d2ca78c083647dbf14b5f0e9b72))

asset_balances(year, category, partner, asset) and category_breakdown(year) as single source of
  truth for "how much per asset". ReportView migrated from inline _flat_rows to category_breakdown;
  template rewritten as pivot (categories × assets, default-first) with mobile cards and fallback to
  per-currency sections above 5 assets. Transaction list shows balance-per-asset chips above the
  table with tooltip (income/expenses/txn_count).

28 service tests including regression for the main bug (1 PLN + 1 BTC must never equal 2 of
  anything).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

- **chat**: Denormalize Room.last_message_* via post_save signal
  ([`69dc499`](https://github.com/soma115/Wikikracja/commit/69dc499b50301cc15246007f2344b94960068b73))

- Replace ad-hoc update in services with single signal handler as SSoT. - Add data migration to
  backfill existing rooms. - Use Greatest() to prevent last_activity from moving backwards. - Fix
  sidebar updating for historical messages (only update when message.new).

Removes duplicate backfill_last_message management command (covered by migration 0020).

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **home**: Dashboard finances card shows default asset all-time balance
  ([`c65d580`](https://github.com/soma115/Wikikracja/commit/c65d580f5dbb64607aeccd3cf6b7e15351e26fc1))

Dashboard badge + finances card now read default asset symbol and all-time balance from
  asset_balances() instead of hardcoded PLN/current-year sum. Empty-state onboarding CTA when no
  assets exist. Bootstrap tooltips initialized globally in app.js so future pages don't need
  per-page setup.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

- **i18n**: Language switcher for anonymous users across signup flow
  ([`4d1a030`](https://github.com/soma115/Wikikracja/commit/4d1a030824eadd39b568eb67b302d445e68970d3))

Anonymous visitors had no way to change the interface language — the only switcher lived in profile
  settings behind @login_required. The whole signup flow (landing, signup, onboarding, waiting)
  renders for an unauthenticated request, so it shares the anonymous topbar.

- set_user_language: drop @login_required; persist to profile only when authenticated, always set
  the django_language cookie. Add open-redirect guard on `next` since the endpoint is now public. -
  New _language_switcher.html (globe dropdown, PL/EN), included in the anon topbar; active language
  highlighted via {% get_current_language %} so it works without a profile. Choice persists via
  cookie through the flow and after login (UserLanguageMiddleware won't override an empty
  profile.language). - Tests: anon cookie set, invalid code ignored, open-redirect rejected,
  authenticated profile persistence + Auto reset, and switcher presence on home / signup /
  onboarding. - pl translation for "Change language"; en catalog intentionally not tracked.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>

- **site-settings**: Custom branding (logo, name, favicon, PWA icons)
  ([`6563dec`](https://github.com/soma115/Wikikracja/commit/6563decc5c83d4685f5d0755691bb9ab854cd519))

- Add brand_mark, brand_mark_dark, branding_text fields to SiteSettings - Pillow auto-generates
  favicon.ico + apple-touch-icon + PWA icon-192/512 from brand_mark - Auto-letterbox non-square
  uploads to square (transparent background) - Validators: max 1 MB, longest side 512-1024 px,
  PNG-only - Theme-aware rendering (brand_mark for light, brand_mark_dark for dark with fallback) -
  Cache-bust ?v=<timestamp> on branded asset URLs via updated_at - New Branding card in
  /site-settings/ with custom file picker (thumbnail + button + clear) - Manifest view +
  favicon/apple-touch-icon links use derivatives when brand_mark set - <title> uses branding_text
  with fallback to Django Sites name - Sidebar shows "Wikikracja v.X.Y.Z" powered-by line - 63 tests
  across 9 test classes

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

- **site_settings**: Wrap brand mark thumbnail in clickable link to full image
  ([`bb5898a`](https://github.com/soma115/Wikikracja/commit/bb5898ad0af8f90cd3c6a5d50800081cbc49bc12))

Thumbnail was rendered as bare <img> — clicking it did nothing. Now wrapped in <a target="_blank"
  rel="noopener"> so admins can open the full-size image. - href attribute omitted (not empty) when
  no image is set — avoids same-page link - file picker updates link href to data URL so preview is
  clickable before Save - AJAX remove handler hides link and removes href via removeAttribute

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **tasks**: Ajax take/resign coordinator + design unification on detail page
  ([`4401edf`](https://github.com/soma115/Wikikracja/commit/4401edf3331d49e58096be3da20d59e425db813e))

Why: - "Become coordinator" / "Resign" buttons forced full page reload, slow and inconsistent with
  the just-introduced AJAX voting flow. - On detail page, take/resign mixed task-*-btn (small) with
  action-btn-* (larger) styling — buttons visibly differed in height and "Become coordinator"
  appeared on third position before take, then moved off when assigned, breaking visual continuity.

Changes: - take_task / resign_task return JSON on X-Requested-With (assigned_to user dict or null);
  resign returns 403 JSON if not coordinator. - both card meta strip and detail action area
  pre-render BOTH states (data-coord-state="empty" and "me") with `hidden` attribute toggled by JS
  after AJAX success. Cards where someone ELSE is coordinator render only the static link (no
  transition possible from this user). - detail page action order: Resign → Edit → Close → Delete
  (Resign now in the same position where Take used to be, preserving visual continuity on
  take/resign toggle). - take / resign use action-btn variants (new .action-btn-take for blue
  primary, .action-btn-withdraw for red); all icons get fa-fw so they have identical widths; vote
  buttons on detail page get scoped padding/font/min-height to match action-btn dimensions. - detail
  page coordinator label wrapped in `<span data-coord-label>` and updated in place; falls back to
  translated "None" via TASK_COORD_I18N. - CSS [data-coord-state][hidden] { display: none !important
  } overrides Bootstrap's .d-inline { display: inline !important } when JS sets hidden=true on
  `<form class="d-inline">`.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

- **tasks**: Sort by helpers count + "People against" popover + live voter lists
  ([`4d21c47`](https://github.com/soma115/Wikikracja/commit/4d21c4745c615d117e5a98c924d40f83e4935636))

Reasons: - Sort "Poparcie" was using votes_score (net) while card showed votes_up (helpers count) —
  sorting did not match the visible number. - Tasks had no public visibility of opposing votes —
  sprzeciwy invisible outside rejection threshold. - Voting required full page reload to refresh
  helper/opponent lists.

Changes: - sort 'score' now ranks by votes_up (helpers); rejection threshold (votes_score <= -2)
  unchanged. - new endpoint tasks:against_json + fa-ban popover button on each task card (analogous
  to helpers). - detail page shows "Willing to help" and "Against this task" as flex lists with
  avatars (reuses helpers-popover-list / helpers-popover-item / helpers-popover-avatar styles). -
  vote AJAX now returns votes_down too; JS updates both helpers and against counters + voter lists
  live (no reload). - chat/_embedded_chat: removed per-request ?v={now} cache-buster that forced
  full re-fetch of ~110KB JS + 40KB CSS on every page reload.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

- **ui**: Brand mark UX — live preview, AJAX remove, toast system, scroll restore
  ([`6b8510b`](https://github.com/soma115/Wikikracja/commit/6b8510bda08de03f26d17d28daa4cd8111f08626))

- Brand mark upload: live preview on file select, client-side validation (PNG only, max 1 MB,
  512–1024 px), error messages before save - AJAX remove brand mark without page reload (two new
  endpoints) - Toast system replaces {% bootstrap_messages %} — fixed at 1/3 from top, centered,
  auto-hides after 4s; uses message.level_tag for correct CSS class - Global scroll-restore.js
  (data-preserve-scroll on forms) replaces per-page duplicates in profile.js and site_admin inline
  script - FieldFile.delete(save=True) for storage-backend-agnostic file removal

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **ui**: Restore version label in sidebar and site-settings header
  ([`dbabed4`](https://github.com/soma115/Wikikracja/commit/dbabed44f95d5492c9f453e0153d546279f61923))

Adds "Wikikracja v.1.4.2" under the sidebar logo (links to /site-settings/) and version badge in the
  site-settings heading. Reuses existing .logo-sub style. Adds --font-mono CSS variable. Version is
  hardcoded in two templates — update both on each release.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

### Refactoring

- **auth**: Conditionally show registration based on GROUP_IS_PUBLIC setting
  ([`4fb2334`](https://github.com/soma115/Wikikracja/commit/4fb23345ff2b2eff2c43a7517d4099ad7decdeab))

Add GROUP_IS_PUBLIC setting to control user registration availability. Hide registration links in
  base.html, home.html, and login.html templates when group is not public. Update
  CustomAccountAdapter to check GROUP_IS_PUBLIC in is_open_for_signup(). Add group_is_public context
  processor to make setting available in templates.

- **chat**: Add room rename functionality with validation and UI
  ([`7ff5cc4`](https://github.com/soma115/Wikikracja/commit/7ff5cc402356f30a2c6b8802da21ea2ea74502cd))

Add rename_room view and API endpoint to allow renaming public, non-protected rooms. Update RoomForm
  validation to check for exact case duplicates while excluding current instance during edit. Add
  rename modal UI with JavaScript handlers, include rename button in room dropdown menu for eligible
  rooms, send system message to room on successful rename, and add comprehensive tests for rename
  functionality including permission checks and validation.

- **glosowania**: Add wymaga_kary checkbox to conditionally show penalty field
  ([`c986591`](https://github.com/soma115/Wikikracja/commit/c986591d098bb96c770085048aa49b420091ceda))

Add wymaga_kary boolean field to Decyzja model to indicate when a penalty is required. Update forms
  and templates to include the new checkbox, add JavaScript to toggle kara field visibility based on
  checkbox state, improve checkbox styling for dark mode, and set initial wymaga_kary value based on
  existing kara content when editing.

- **obywatele**: Replace boolean form_completed with percentage-based form_completion_percent
  ([`ea7a980`](https://github.com/soma115/Wikikracja/commit/ea7a98035567cced80dd7810ab2b5889890ed5f4))

Add form_completion_percent property to Uzytkownik model that calculates completion percentage based
  on ONBOARDING_FORM_FIELDS and user's first/last name. Replace form_completed boolean checks in
  poczekalnia and szczegoly views/templates with progress bars showing completion percentage. Use
  color-coded progress bars (green for 100%, yellow for ≥50%, red for <50%).

- **tasks**: Add statistics page and update chat room title format
  ([`eca4401`](https://github.com/soma115/Wikikracja/commit/eca4401ab99ae4ed3459c693d2aa64d841d9f347))

Add TaskStatsView to display task completion metrics including total completed, success/failure
  counts, mixed evaluations, tasks without evaluations, and weekly completion stats. Update task
  chat room title format to include task ID prefix. Remove automatic chat room title updates on task
  edits. Add statistics link to tasks menu and update Polish translations for new statistics page
  strings.

- **tasks**: Replace display-4 with fs-1 and round success rate to integer
  ([`1fb4efe`](https://github.com/soma115/Wikikracja/commit/1fb4efe323a385819175ead76dcb763eddc8311c))

Replace Bootstrap display-4 class with fs-1 for consistent font sizing in task statistics cards.
  Change success_rate rounding from 1 decimal place to integer for cleaner display.

- **version**: Single-source app version (pyproject <-> zzz.__version__)
  ([`e9b5e7d`](https://github.com/soma115/Wikikracja/commit/e9b5e7dfebb1830f4ef968b28ded14ee4e2b2c55))

App version is now read from zzz.__version__ via the site_description context processor and rendered
  as {{ app_version }} in the sidebar and site-settings header, replacing the value hardcoded in two
  templates.

- zzz/__init__.py: __version__ as the runtime source of truth - pyproject.toml: semantic-release
  version_variables keeps __version__ in lockstep with project.version on every release (no manual
  edits) - reconcile drift: pyproject 1.4.3 (phantom manual bumps on ui) reset to 1.4.1 to match the
  last release tag v1.4.1; semantic-release owns it now

Tests (TDD, red->green): tests/test_version.py covers drift guard (__version__ == pyproject),
  context processor exposure, and dynamic sidebar render. 79 passed across test_version + home +
  site_settings.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>

### Testing

- **site_settings**: Ajax remove brand mark endpoints (Test 13)
  ([`b4d5c01`](https://github.com/soma115/Wikikracja/commit/b4d5c0102404c98ff19e10cbb4411d6c8b7b15a7))

7 cases: clears field, deletes file from disk, dark does not affect light, empty field returns ok,
  requires POST, requires login.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>


## v1.4.1 (2026-05-23)

### Bug Fixes

- **vote**: Wrap decision processing in atomic transaction with row-level locking
  ([`02427c6`](https://github.com/soma115/Wikikracja/commit/02427c694bfebbc983f0db5dbdc855178ef69663))

Adds transaction.atomic() block around main loop and select_for_update() on Decyzja queryset to
  prevent race conditions when multiple vote command instances run concurrently. Moves decyzje query
  inside transaction and filters status__in=[proposition, discussion, referendum] at DB level
  instead of if-check per iteration. Also locks abolished decisions (znosi) with
  select_for_update().get() to avoid concurrent status

### Refactoring

- **chat**: Optimize one2one room deletion using queryset filtering
  ([`7cb32e5`](https://github.com/soma115/Wikikracja/commit/7cb32e580680f4c854b170b573552a31f88bbc51))

Replaces username-in-title check with allowed=user filter on Room queryset, removes TODO comment
  about false positives with public rooms, and uses bulk delete() instead of iterating. Moves
  log.info() before deletion (rooms_to_delete queryset evaluates during iteration, then bulk
  deletes).

- **count_citizens**: Add clarifying comments for reputation threshold logic
  ([`8248255`](https://github.com/soma115/Wikikracja/commit/82482558ae51fc374bdc8b2ca5894b8c482f9742))

- **details**: `votecode.objects.create()` in transaction.
  ([`cd89a10`](https://github.com/soma115/Wikikracja/commit/cd89a1055be2b3d5da9968ec018e4aec26fad9d0))

- **models**: Remove unused post_save signal handler for Uzytkownik
  ([`dd82c7a`](https://github.com/soma115/Wikikracja/commit/dd82c7a45e3f98cb731d0dd106ff4f07fe3ded2e))

- **settings**: Comment out redundant X_FRAME_OPTIONS SAMEORIGIN line
  ([`11fceb5`](https://github.com/soma115/Wikikracja/commit/11fceb56d3912daa9c0204b3b93d49aa215f529f))

- **version**: Remove app_version from templates and context
  ([`51a6ab9`](https://github.com/soma115/Wikikracja/commit/51a6ab9511ea35d64440058007909efcffa032ce))

Usuwa APP_VERSION z settings (tomllib parse pyproject.toml), context_processors.site_description,
  oraz z dwóch miejsc w UI (sidebar logo-sub, site_admin heading i card). Logo-sub teraz pokazuje
  request.site.name zamiast v.{{ app_version }}.

- **views**: Add @login_required decorator to mark_as_read view
  ([`206ba8f`](https://github.com/soma115/Wikikracja/commit/206ba8fc432c60cd0a4b2261d6f5c650228afa78))

- **views**: Add status check to prevent editing non-proposition decisions
  ([`2900fc5`](https://github.com/soma115/Wikikracja/commit/2900fc5f374641f8575b938ea4e6c60abe63bc81))

- **vote**: Add clarifying comment for proposition-to-rejected block logic
  ([`5ba93f2`](https://github.com/soma115/Wikikracja/commit/5ba93f2743ecbf059b486d9ea760870f09650ad1))

Adds NOTE comment explaining control flow for the proposition→rejected block (indent 24): it's a
  sibling of the if/elif above, inside the outer "if i.status == proposition". Reached when (a)
  author hasn't signed, OR (b) author signed but insufficient signatures gathered. The elif branch's
  continue skips this block when proposal moves to discussion.

- **vote**: Clean up command structure and remove redundant setup code
  ([`430d4a0`](https://github.com/soma115/Wikikracja/commit/430d4a0df0a2a4e149c7d3cebf5dbe8a33997be7))

Removes obsolete django.setup() call and imports (django, os.environ), deletes placeholder handle()
  method with Polish comment, and moves translation.activate + main logic from __init__ to handle().
  Django management commands auto-setup before handle() runs, making manual setup unnecessary. Line
  numbers in locale/pl/LC_MESSAGES/django.po shift down by 8 due to removed lines.


## v1.4.0 (2026-05-23)

### Bug Fixes

- Dropdown z-index i wyciszanie pokoju
  ([`c402d00`](https://github.com/soma115/Wikikracja/commit/c402d0097bc0e54b3f1687c3ac432f27327e01cc))

- dropdown-menu nie byl zaslaniany przez pokoje ponizej (overflow: clip na kontenerach, position:
  relative na .room-link) - .room-list-controls z-index 10->20 + position: relative (kebab menu
  wychodzi ponad liste) - globalny styl .dropdown-menu/.dropdown-item z CSS variables design systemu
  - ikona wyciszenia (fa-bell-slash) pojawia sie/znika natychmiast po kliknieciu bez odswiezenia
  strony - etykieta przycisku: "Toggle notifications" -> "Wycisz pokoj" / "Cofnij wyciszenie" - i18n
  PL: Wycisz pokoj / Cofnij wyciszenie

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Embedded chat - wiadomosci sklejone i za duze marginesy
  ([`5d6655b`](https://github.com/soma115/Wikikracja/commit/5d6655bf2daffa9303e01af98e0aa31f284ca240))

Selektory .message scopowane do #room nie dzialaly w embedded chacie (#ec-messages zamiast #room).
  Rozwiazanie:

- bazowe reguly .messages .message bez #room: display:flex, margin-bottom, margin-right/left 2%
  (odpowiednie dla waskego embedded) - #room .messages .message override: marginesy 6% i max-width
  80/90% tylko dla glownego czatu (desktop i mobile media query) - embedded chat automatycznie
  dostaje pelna szerokosc bez ograniczen

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Invalidate unread cache for offline recipients on message send
  ([`75689ff`](https://github.com/soma115/Wikikracja/commit/75689ff9195d1d65c90505a835e8ad553c749a97))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Merge
  ([`9f73487`](https://github.com/soma115/Wikikracja/commit/9f73487d11fb1f75a2584af91eb38b582ed63cff))

- Message_max_length 1500zn, przekaż do embedded chata (glosowania, tasks)
  ([`e5851c7`](https://github.com/soma115/Wikikracja/commit/e5851c78e0597ac55fc1ff84ceb1cfc1ce47cae4))

Widoki głosowania i zadań nie przekazywały MESSAGE_MAX_LENGTH do kontekstu, przez co embedded chat
  używał fallbacku 500 zamiast globalnego ustawienia.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Napraw link do profilu kandydata na stronie /poczekalnia/
  ([`321c13d`](https://github.com/soma115/Wikikracja/commit/321c13d1d5241f94b0a3326370a6f4b4ac4a9880))

citizens_list.js crashował na /poczekalnia/ bo brakowało elementów #citizens-list-view,
  #citizens-grid-view i #citizens-search. Dodano null guardy — skrypt działa teraz na obu stronach.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Ogranicz szerokość dropdownu kategorii na mobile
  ([`12f6ca0`](https://github.com/soma115/Wikikracja/commit/12f6ca0923865f318d0ac391155608c168b14b83))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Paste image appendowal pliki zamiast je podmieniac
  ([`30a8a02`](https://github.com/soma115/Wikikracja/commit/30a8a02f8a3d6be2e4afb0eed080062f0849cced))

initGlobalPasteImageHandler tworzyl nowy DataTransfer z tylko wklejonym plikiem i przypisywal go do
  fileInput.files, niszczac wczesniej wklejone/ wybrane obrazki. Po fixie istniejace pliki sa
  przepisywane do nowego DataTransfer przed dodaniem nowego pliku.

Po fixie kolejne CTRL+V dodaja nowe obrazki zamiast zastepowac poprzednie.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

- Replace blocking alert() with toast for WS errors
  ([`4622723`](https://github.com/soma115/Wikikracja/commit/4622723a7d50190c592e5f410eb0322121e7e4cf))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Restored translations used in JS
  ([`82931c9`](https://github.com/soma115/Wikikracja/commit/82931c9abe31b3f2448bdbb1678f7e89d85ca9dc))

- Ukryj prywatne DM-y na profilu obywatela
  ([`4ed4cf3`](https://github.com/soma115/Wikikracja/commit/4ed4cf34e9d051900947e808089c5db5fabf03a9))

Zakładki "Czaty" i "Założono" pokazywały wiadomości i pokoje z prywatnych rozmów 1-na-1, co
  ujawniało treści prywatnych DM-ów osobom trzecim.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Zsynchronizuj last_activity z last_message_at
  ([`8a88e8b`](https://github.com/soma115/Wikikracja/commit/8a88e8b83c5025ec57a1eea008842b0f6829f378))

Commit denormalizujacy last_message wprowadzil regresje: Room.objects.filter ().update(...) omija
  auto_now, wiec last_activity przestal byc aktualizowany przy nowych wiadomosciach. Sort sidebara
  po dacie pokazywal pokoje wedlug zatluczonego last_activity (np. tralla z ostatnia wiadomoscia
  dzis ladowala ponizej pokoju z wiadomoscia sprzed 2 tygodni).

Sidebar template uzywa teraz last_message_at jako primary sort key z default_if_none na
  last_activity dla pustych pokojow.

consumers przez services.update_room_last_message ustawia last_activity explicit na message.time —
  fix dotyczy tez obywatele/citizen_czaty (sortowanie pokojow w profilu uzytkownika).

Backfill management command zaktualizowany — uzywa last_activity = max(current, message.time) zeby
  nie cofnac dat dla pokojow modyfikowanych po ostatniej wiadomosci. Re-uruchomiony na bazie: 19
  pokojow zaktualizowanych.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

- **activity**: Chat messages nie pokazywaly sie w aktywnosc/
  ([`6a60b13`](https://github.com/soma115/Wikikracja/commit/6a60b138fece28c801a04547001b1a79f22d58c1))

_generate_feed_raw() budowal elementy pokojow bez _allowed_user_ids, przez co generate_feed_items()
  zawsze pomijal wiadomosci z chatu.

Dodano _is_public i _allowed_user_ids do cache, poprawiono filtr aby uwzgledniał publiczne pokoje,
  dodano sygnal m2m_changed dla Room.allowed (inwalidacja cache po zmianie dostepu) oraz testy TDD.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **chat**: Draft nie kasuje sie po wyslaniu wiadomosci
  ([`388cda0`](https://github.com/soma115/Wikikracja/commit/388cda0f78a7264bf4d79b2352a70c50364d35ac))

clearDraft() byl wolany przed innerHTML='', przez co natywny input event przegladarki (ze stara
  trescia) nadpisywal draft z powrotem. Przesunieto clearDraft po wyczyszczeniu inputa.

Dodatkowo: new Event('input') zamieniony na InputEvent z bubbles:true we wszystkich 3 miejscach
  (restoreDraft, onSubmitMessage, stopEditing) — event nie docieral do document-level listenerow
  (counter, saveDraft).

Dodano setup Jest + testy regresyjne (draft.test.js).

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **chat**: Mobile — tap aktywnego pokoju zwija rozwiniętą listę
  ([`a307616`](https://github.com/soma115/Wikikracja/commit/a307616e1b1e9c315a667e485c089d8bdb4fbb41))

Bez tego klik w już-joined room z rozwiniętej listy (mobile) nie robił nic (early-return po klasie
  .joined), więc nie było jak wrócić do pokoju inaczej niż przez `>>` w nagłówku listy.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

- **chat**: Nie pokazuj "... pokaz wiecej" dla krotkich wiadomosci
  ([`0fb015d`](https://github.com/soma115/Wikikracja/commit/0fb015de6f359de7c18d5306b9af8ce7c79473ff))

Odwroc logike expandable z fail-open na fail-closed: hint i klikalnosc wlaczane dopiero gdy JS
  potwierdzi overflow (.has-overflow), zamiast domyslnie wlaczonych z opcjonalnym wylaczeniem
  (.no-overflow). Wczesniej kazde niepowodzenie detekcji (timing fontow, edit-flow) zostawialo "...
  pokaz wiecej" przy krotkich wiadomosciach.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

- **chat**: Pokaz przycisk zwijania listy pokoi na mobile
  ([`0b28430`](https://github.com/soma115/Wikikracja/commit/0b28430733e205193c6886d344a936d1ab209a32))

Ukryj tekstowe etykiety (Date/Likes/Popular) w pasku sortowania ponizej 768px, zeby przycisk >> mial
  miejsce na ekranie.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

- **i18n**: Napraw ekstrakcje tlumaczen chat/views.py + dropdown chevron sidebar
  ([`0b013cd`](https://github.com/soma115/Wikikracja/commit/0b013cd799dbba2920ac68a3abd06317ec3f830b))

Problemy: 1. Wzor `{x: _(x) for x in strings}` w get_translations() nie byl widoczny dla
  makemessages - wszystkie te stringi byly tracone z .po przy kazdym `start_dev.py --full`, co
  powodowalo regresje w UI czatu (placeholder, hint skrotow, reactions). 2. Dropdown chevron przy
  pokojach w sidebarze byl obcinany przez overflow:hidden na .nav-cat-content (uzywany do animacji
  collapse).

Zmiany: - chat/views.py: get_translations() zwraca dict literal z jawnym _("...") na kazdym kluczu -
  kazdy string jest teraz widoczny dla xgettext - locale/pl: dodane/poprawione polskie tlumaczenia
  dla wszystkich stringow w get_translations() (Reply, Shift hint, Upvote/Downvote, miesiace
  Jan-Dec, Tomorrow, Link copied, edit/edited, Popular, Sorting and filter, Likes, Could not copy
  link, Copy message link) - handlers.js: bootstrap.Dropdown dla .room-link__chevron z
  popperConfig.strategy='fixed' - dropdown pozycjonowany wzgledem viewportu, omija overflow rodzica

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

- **obywatele**: Last_login pokazuje rzeczywista aktywnosc usera
  ([`4ac98fe`](https://github.com/soma115/Wikikracja/commit/4ac98fedd5f5b9df0bfbd5a6c1af335d8b11d491))

Middleware UpdateLastSeenMiddleware aktualizuje last_login przy kazdym requescie zalogowanego usera
  (throttling 5 min przez Redis). Bez tego /obywatele/?sort=-last_login pokazywal stare daty -
  Django aktualizuje last_login tylko przy formalnym logowaniu, a sesje trwaja 90 dni.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

- **tasks**: Filtrowanie po kategorii nie pokazywalo zadan
  ([`3f39e85`](https://github.com/soma115/Wikikracja/commit/3f39e85fcaeb0a9d30911cd2bd9b4bb0c0c7e847))

Karta zadania miala data-category=\"{{ task.category }}\" co przez __str__ AbstractCategory
  renderowalo NAZWE kategorii. Filter dropdown przekazuje SLUGI (data-key={{ cat.slug }}). JS
  porownywal slug z nazwa, nigdy nie matchowalo, wszystkie karty znikaly.

Zmiana: data-category={{ task.category.slug }}. Spojne z backendowym _filter_by_category ktory tez
  uzywa slugow.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

- **ui**: Pola tekstowe widoczne na tle strony — nowe tokeny --input-bg / --input-border
  ([`264002d`](https://github.com/soma115/Wikikracja/commit/264002d499def92d367cbfb6bde49718e390974c))

Inputy i textarea używały --bg-base (tło strony), przez co zlewały się z tłem. Dodano tokeny
  --input-bg i --input-border per-temat; objęte: .form-control, .compose-box, .richtext-wrapper,
  .arg-inline-form textarea, .cat-mgr-input, .topbar .search-box. Focus state naprawiony z hardcoded
  dark-accent na var(--accent) / var(--accent-muted).

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

### Chores

- Ignoruj uploady w media/elibrary
  ([`872f23d`](https://github.com/soma115/Wikikracja/commit/872f23dc4d064f263fe3a56c75489dde86bb9976))

Pliki w media/elibrary/ to dynamiczne uploady — nie powinny trafiac do repozytorium (analogicznie do
  media/board/attachments i media/avatars).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

- Usun nieuzywany import cache z chat/views
  ([`c4c4e5e`](https://github.com/soma115/Wikikracja/commit/c4c4e5e449d313ef552d93ea995d3d12cc0db0e8))

Pozostalosc po wczesniejszym refactor cleanupie.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

- **i18n**: Odswiez referencje linii w pl/django.po
  ([`1f3a9a5`](https://github.com/soma115/Wikikracja/commit/1f3a9a5241e3fe5deacda8ea8b3426bc9c9b2210))

Auto-generated przez makemessages po zmianach kodu - same numery linii i POT-Creation-Date, brak
  zmian w tlumaczeniach.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

- **test**: Add pytest infrastructure
  ([`77e0c1f`](https://github.com/soma115/Wikikracja/commit/77e0c1fd08c1e3cc8564709af327b4e07dabd118))

- Add pytest, pytest-django, pytest-asyncio, factory-boy to requirements - Configure pytest in
  pyproject.toml with zzz.test_settings - Set asyncio_mode=auto for native async def test support -
  Create tests/ package for cross-cutting test suite

Existing Django TestCase suites (chat, events, home, obywatele, tasks) work natively under pytest —
  no migration needed.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **vscode**: Recommend Playwright extension
  ([`1933805`](https://github.com/soma115/Wikikracja/commit/1933805001bb1efa272689103f2aaab98c316013))

Po dodaniu @playwright/test devom przy klonie projektu VSCode zasugeruje instalację oficjalnego
  rozszerzenia (test runner UI, codegen, debug).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

### Documentation

- Add test migration plan with discovered signal behaviors
  ([`10d3b8c`](https://github.com/soma115/Wikikracja/commit/10d3b8c5bd6708946790730f06d00c40ee807b60))

Documents the cherry-pick approach used to migrate tests from the `tests` branch (jordan
  exploration): hybrid co-located + /tests/ structure, pytest adoption, 24 tests kept out of ~200
  from source branch (rest rejected as placebo or duplicates).

Records two non-obvious signal behaviors discovered during migration: -
  obywatele.models.create_user_profile: auto-creates Uzytkownik per User -
  glosowania.signals.create_or_update_chat_room_for_referendum: auto-creates chat_room with specific
  properties (public, protected, founder, welcome message, allowed.set(active_users)) on
  Decyzja(status=1)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

### Features

- Add pending/failed message states to DOM API and CSS
  ([`811c8d2`](https://github.com/soma115/Wikikracja/commit/811c8d27ccbe7f2b90bfdc54d330569f6a7f0b7a))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Avatar/ikona pokoju w liscie
  ([`e43a9e3`](https://github.com/soma115/Wikikracja/commit/e43a9e3af82ebf0f0f3a3205b1fc76d831aa8210))

Kazdy pokoj dostaje kolko po lewej z ikona zalezna od typu — publiczna grupa (users), zadanie
  (tasks), referendum (vote-yea), DM (avatar drugiej osoby z Uzytkownik.avatar, fallback fa-user).
  Klasa modifier --public/--task/--vote/ --private zachowana w DOM dla pozniejszej kolorystyki
  per-typ.

Rozdzielony prefetch listy pokojow w views.py: publiczne dostaja lean only('id','username') (moga
  miec setki czlonkow), prywatne select_related ('uzytkownik') zeby zaladowac avatar jednym
  zapytaniem.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

- Denormalizacja last_message na Room
  ([`02410db`](https://github.com/soma115/Wikikracja/commit/02410db2640f3dc01ba0b3eb5f5bb94d503532ec))

Dodaje 4 pola (text/sender/at/anonymous) aktualizowane w consumers po zapisie wiadomosci. Eliminuje
  join na Message przy renderze listy pokojow w sidebarze, gdy bedziemy pokazywac preview ostatniej
  wiadomosci. Backfill istniejacych pokojow management commandem.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

- Dwuliniowy uklad pokoju z podgladem ostatniej wiadomosci
  ([`c2afbf1`](https://github.com/soma115/Wikikracja/commit/c2afbf12d0e0f78bf188da3a6704e4ae4498b969))

Sidebar wyswietla 2 linie per pokoj: nazwa + data po prawej nad linia "nadawca: podglad". Pokoje
  nieprzeczytane maja pogrubiona nazwe i date w akcencie, wyciszone pokazuja dzwoneczek
  przekreslony. Pusta tresc (tylko zalacznik) renderuje "zalacznik" jako fallback. Pokoje bez
  wiadomosci pokazuja tylko 1 linie.

Dodaje filter relative_chat_date (HH:MM/Wczoraj/dzien/dzien miesiac/+rok) i
  select_related('last_message_sender') na queryset listy pokojow.

Naprawia 3 bugi w handleRoomLinkClick (dawniej handleRoomNameClick): - parentElement dawniej zwracal
  .room-link, po zmianie nestingu juz nie; - click na 2. linii (preview) nie joinowal pokoju —
  rozszerzony target na cale .room-link z wykluczeniem .room-controls; - pre-existing:
  classList.contains("joined") sprawdzane na .room-name (zawsze false bo klasa jest na .room-link).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

- Hover-reveal kontrolek pokoju (chevron + dropdown)
  ([`b9591cd`](https://github.com/soma115/Wikikracja/commit/b9591cdfe91d78414432336a6d47a9fc60bd6a0d))

Cztery przyciski (track/seen/notif/copy) chowaja sie pod chevronem ktory pojawia sie tylko przy
  hover na pokoj (desktop) lub jest permanentnie widoczny na touch (@media (hover: hover)
  detection). Klik chevronu otwiera Bootstrap dropdown z labelkami tekstowymi przy opcjach.

Istniejace klasy .track-switch/.seen-switch/.notif-switch/.copy-room-url zachowane na
  dropdown-itemach, wiec wszystkie handlery dzialaja bez zmian.

Naprawia copy-link feedback: button w dropdownie znika razem z menu po klikniecu, wiec inline badge
  nie zdazyl sie pokazac — teraz uzywa window.show Toast. Message copy zostaje na inline feedback.

Usuwa martwy CSS po .copy-link-btn (klasa juz nie istnieje w templatce).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

- Live update sidebara po nowej wiadomosci
  ([`b3fba3d`](https://github.com/soma115/Wikikracja/commit/b3fba3db211e40d7c448d69d0a52b3562ebed386))

Po wyslaniu/odebraniu wiadomosci pokoj natychmiast wskakuje na gore swojej kategorii z aktualna
  godzina i podgladem tekstu — bez odswiezania strony.

- DomApi.updateSidebarForMessage() aktualizuje date, nadawce, snippet i przesuwa .room-link na
  poczatek kontenera - _relativeChatDate() replikuje logike Django relative_chat_date w JS (korzysta
  z TRANSLATIONS: Yesterday, dni tygodnia, skroty miesiecy) - wywolanie przy optimistic UI
  (confirmMessage) i normalnej sciezce - 'attachment', 'Mute room', 'Unmute room' dodane do
  get_translations()

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Merge UI branch (without tests)
  ([`ee1710b`](https://github.com/soma115/Wikikracja/commit/ee1710bfe0f615d72f9d71211194c1e7256f8573))

- Nawiguj do konkretnej wiadomości z profilu obywatela
  ([`280ffdc`](https://github.com/soma115/Wikikracja/commit/280ffdcb31a7d060ec506e8ce9f1e41fa9662f56))

Link z zakładki "Czaty" teraz przekazuje message_id, dzięki czemu chat przewija do wybranej
  wiadomości i podświetla ją przez 5 sekund.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Przycisk 'wg kategorii' w toolbarze pokoi
  ([`cb53a71`](https://github.com/soma115/Wikikracja/commit/cb53a71871941ccc1eff162b4abc58169ccf9001))

sort-reset-btn wyciagniety z dropdown do toolbaru jako ikona fa-layer-group. Kolejnosc: szukaj |
  nieprzeczytane | czas | wg kategorii | ... | >> Padding sort-btn w toolbarze zmniejszony (.45rem)
  i gap (.25rem) zeby wszystko zmieszcilo sie na mobile.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Redesign listy obywateli — awatar, zebra stripes, spójność z design system
  ([`df16da5`](https://github.com/soma115/Wikikracja/commit/df16da5d7ff0adfb06239cfed4b67c8600e70aff))

- Awatar w widoku listy (28px) z kropką statusu nałożoną w rogu, jak w gridzie - Nick pogrubiony
  (font-weight 600) w kolumnie listy - Zebra stripes przez color-mix(bg-card 93%, blue 7%) — solidny
  kolor bez problemu z przezroczystością na Darkly theme - Reset szarego tła Bootstrap na bg-card
  dla wszystkich wierszy tabeli - Grid: minmax 140px→180px, awatar 40px→48px, hover tło accent-muted
  - proposal-chat-link: hardkodowane rgba zastąpione przez --accent-muted i --accent-glow -
  citizens_list.css: usunięto redundantny hover cursor i hardkodowany kolor hover

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Redesign strony logowania — global design, theme toggle, podgląd hasła
  ([`7c1b395`](https://github.com/soma115/Wikikracja/commit/7c1b3950c267b23edae49bb93aab664c36fd65a1))

- login.html: CSS variables zamiast text-info, show/hide password - app.css: #login-box card styles
  oparte wyłącznie na design tokenach - base.html: theme toggle button w anon-nav (ta sama logika co
  po zalogowaniu) - app.js: poprawiony komentarz (handler był błędnie przypisany do base.html)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Redesign toolbara listy pokojow (szukajka + kebab)
  ([`792c7c8`](https://github.com/soma115/Wikikracja/commit/792c7c88d0428fe8fd00635fd882be2a23290cbb))

Nowy uklad: szukajka po nazwie pokoju + sort-time + unread-filter + kebab (z opcjami Dodaj/Bez
  sortowania/Zwin wszystko/Pokaz archiwum/Info) + hide-list. Globalny archive toggle zastapil 4
  per-category buttony przy naglowkach kategorii.

Pre-existing tlumaczenia PL nie zostaly zaktualizowane (makemessages bedzie zrobione zbiorczo po
  reszcie commitow z serii UI).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

- Sortowanie pokoi po ostatniej aktywności (↓/↑) z resetem do kategorii
  ([`e99dbb4`](https://github.com/soma115/Wikikracja/commit/e99dbb4441a8b1371a3dcfb13e9e583b79d03a71))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Toolbar obywateli — grid/list toggle, live search, filtr aktywności, status dot
  ([`5cc416e`](https://github.com/soma115/Wikikracja/commit/5cc416ee3249ebe317b0656aa44995b1f233aa7d))

- Toolbar: wyszukiwarka live (debounce 150ms, filtruje nick/imię/nazwisko), dropdown filtra
  aktywności (online/7d/30d/nieaktywni), toggle widoku grid/list (PagePrefs, global design system) -
  Widok grid: avatar z fallbackiem na inicjał, status dot, nick, imię+nazwisko, miasto, przycisk DM
  - Status dot: 4 stany (online <5min, aktywny ≤7d, uśpiony ≤30d, nieaktywny) — tokeny w :root -
  Kafelek '% zalogowanych' w pulpicie wspólnoty → link do ?aktywnosc=30d - Fix: sync filtrów z
  PagePrefs przed nawigacją (zapobiega przywracaniu przez head-script) - Design system: CSS
  variables we wszystkich nowych stylach, .view-toggle-btn/.toolbar-view zgodne z global design,
  usunięty martwy CSS .filter-chip

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Whatsapp-style input + tlumaczenia embedded czatu
  ([`7d64501`](https://github.com/soma115/Wikikracja/commit/7d645016b412a584cc84bac8a4e1a3ea4e8fae1c))

- Enter wysyla, Shift+Enter nowa linia (zamiast Ctrl+Enter) - '-' lub '*' + spacja zamienia sie na
  punkt listy '•' - Placeholder hints: skroty klawiaturowe w pustym polu - richtext-core.js jako
  single source of truth dla embedded i main chat - ec_translations przekazywane z widokow tasks i
  glosowania zeby embedded chat mial polskie tlumaczenia

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Widok obywateli — filtr aktywności, grid/list toggle, live search
  ([`574c210`](https://github.com/soma115/Wikikracja/commit/574c210987bfe70fa2199b2a4c93f244e6670975))

Dodano filtrowanie po aktywności (online/7d/30d/nieaktywni), przełącznik widoku lista↔grid z
  pamięcią w localStorage, live search po nazwie użytkownika oraz wskaźniki statusu aktywności
  (status-dot). Widok wspolnota linkuje do filtra 30d. Usunięto zduplikowany przycisk Dodaj w widoku
  propozycji Agory.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Wklejanie obrazków ze schowka (Ctrl+V) w czacie głównym i embedded
  ([`07e82ad`](https://github.com/soma115/Wikikracja/commit/07e82ada86bf8e8d3fa298dfaebdffdb964db99b))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Wymagaj logowania dla widoku wspolnota
  ([`0dacdb6`](https://github.com/soma115/Wikikracja/commit/0dacdb69e5455635b0e6136bcfb44421e7840dcf))

Dodano @login_required decorator do wspolnota view - dostep tylko dla zalogowanych uzytkownikow.

- Zunifikuj widok poczekalni z listą obywateli (grid/list + szukajka)
  ([`76e10d1`](https://github.com/soma115/Wikikracja/commit/76e10d175adb200d9023c2ce09527d893008960b))

- poczekalnia.html: toolbar z szukajką i przełącznikiem widoku list/grid, awatar, ikona głosu inline
  w wierszu, ikony statusów email/formularza, scope preferencji 'poczekalnia' - start.html:
  data-href na wierszach i kartach (poprawka semantyczna URL) - citizens_list.js: kliknięcia używają
  data-href zamiast hardcoded URL - app.css: klasa .candidate-vote-badge dla ikony głosu w gridzie

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **calendar**: Klikalne puste dni + klikalny kafelek kalendarza
  ([`36a191f`](https://github.com/soma115/Wikikracja/commit/36a191f9e971d88081fff6dc6bd0b99482932da2))

- Tytuł sekcji "Calendar" na /obywatele/wspolnota/ jest teraz linkiem do /events/; styl
  text-decoration przeniesiony do a.wspol-section-title w components.css (single source of truth) -
  Puste dni w _calendar_partial.html mają data-day + href do events:list; istniejący JS
  (jumpToDay/setFromDate) automatycznie filtruje agendę do następnego eventu po klikniętym dniu

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **chat**: Klikalne nicki + awatary autorow wiadomosci
  ([`8f66075`](https://github.com/soma115/Wikikracja/commit/8f660759b9f7e3b22fd7573838b3ee718b6c43e4))

Nick autora w naglowku wiadomosci staje sie linkiem do /obywatele/<id>/ (zarowno w normalnym czacie
  jak i w embedded). Przed nickiem pokazujemy awatar uzytkownika: - uploaded avatar -> obrazek z
  media/avatars/ - brak avatara -> kolko z inicjalami (2 pierwsze litery username, accent bg)
  spojnie z stroną profilu obywatele/szczegoly.html - anonimowa wiadomosc -> ikona "?" w neutralnym
  kole (nie zdradza autora)

Rozmiar awatara dopasowany do wysokosci linii naglowka (= height ikony reply, 1.875rem). Awatar +
  nick razem w jednym <a>, zeby caly element "autor" byl klikalny.

Implementacja: - chat/serializers.py (NEW): wyciagnieto build_chat_message_payload jako czysta
  funkcja, testowalna w izolacji. Dla anon: user_id=None, avatar_url wymuszone na
  /static/home/images/anonymous.svg. - chat/consumers.py: oba paths (single + batch) uzywaja
  serializera, user_id przestaje byc kasowane z payloadu. - chat/services.py: get_avatar_url
  naprawione - uzywa user.uzytkownik zamiast user.profile (poprzednia wersja zawsze rzucala
  AttributeError zjadany przez except, kazdy user dostawal placeholder). select_related
  ('uzytkownik') w get_user_by_id i get_recent_messages_batch wycinaja N+1. Funkcja przemianowana z
  _get_avatar_url na get_avatar_url (uzywana miedzymodulowo). -
  chat/static/chat/js/{templates,domapi,chat,chat-embedded}.js: pipeline user_id + avatar_url
  przepuszczony przez addMessage/buildMessageHtml. - chat/static/chat/css/chat.css: .username-link,
  .msg-author-avatar, .msg-author-initials uzywaja CSS variables (--color-text-muted,
  --color-accent, --accent-hover, --border). - home/static/home/images/anonymous.svg (NEW): "?" w
  szarym kole. - chat/tests/test_serializers.py (NEW): 16 testow pokrywajacych user_id, avatar_url,
  vote, reactions, own, new dla scenariuszy anon/non-anon. - chat/tests/test_services.py (NEW): 4
  testy get_avatar_url (no upload, None user, AttributeError, happy path z SimpleUploadedFile).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

- **chat**: Rework nawigacji — ?view=rooms / ?view=unread + empty states
  ([`6bfc4dc`](https://github.com/soma115/Wikikracja/commit/6bfc4dc6cfd58746269ab61bef7d64726bb3c1c1))

Sidebar i dashboard badge prowadza teraz do dedykowanych widokow czata: - ?view=rooms (sidebar) —
  lista pokoi, filtr unread OFF, placeholder w obszarze wiadomosci - ?view=unread (badge) — lista z
  filtrem unread ON, empty state w prawej kolumnie gdy 0 wynikow - ?unread=1 — legacy alias dla
  starych bookmark'ow/push'y

Empty state "brak nieprzeczytanych" przeniesiony do applyUnreadFilter — dziala tez w runtime, gdy
  user przeczyta ostatni unread przy aktywnym filtrze. Komunikat zawiera inline ikone (eye-slash)
  wskazujaca konkretny przycisk do klikniecia.

CSS :has() chowa drzewo kategorii gdy empty state widoczny — bez tykania inline style .row, zeby nie
  kolidowac z sort'em wg czasu.

Dodatkowo: TDD strict dla decideStartupAction (testy JS), testy Django dla badge'a + sidebar linka,
  anti-flash dla restore filtra z localStorage, placeholder "Wybierz pokoj" gdy brak aktywnego
  pokoju, tlumaczenia PL.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

- **glosowania**: Badge z licznikiem zamiast numeru etapu w stepperze
  ([`d392f7f`](https://github.com/soma115/Wikikracja/commit/d392f7f994d3cb6a115017e63e1f05c22fe3e04c))

- helper get_stepper_counts() (1 aggregate query z Exists na ZebranePodpisy) - template tag {%
  glosowania_counts %} + 9 testow - badge .stepper-step-count ukryty przy 0; light/official override

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

### Performance Improvements

- Compress images client-side before upload (canvas → WebP 0.75, max 1280px)
  ([`a8b6a16`](https://github.com/soma115/Wikikracja/commit/a8b6a160ae5425e5aaa70207ac8e2ff803e40676))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Optimistic UI for sending messages
  ([`cb73027`](https://github.com/soma115/Wikikracja/commit/cb730272f0d1ca74f4af3c0a150bdc22e6dbbb59))

Renders the user's own message immediately on send with a pending state, then swaps to confirmed
  when the server echoes it back. Matched via client-generated temp_id passed through the WS payload
  and broadcast. Failed state shown after 10s timeout if no broadcast arrives.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

- **chat**: Apply LIMIT and ORDER BY in SQL for message batch fetch
  ([`05b056f`](https://github.com/soma115/Wikikracja/commit/05b056f260c31c179474decaaeec67a3c5d270c6))

For the common case (sort by date, no popularity filter) the query now uses the existing (room,
  time) DB index and lets the DB do ORDER BY + LIMIT instead of loading the full room history into
  Python.

The Python path is kept for sort_by='likes' and popular_only=True because upvotes live in a
  JSONField and cannot be ordered/filtered at the DB level.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **chat**: Broadcast message before running per-recipient bookkeeping
  ([`ce4799a`](https://github.com/soma115/Wikikracja/commit/ce4799a834385b35b165dbb7bbde7c997067b398))

Previously the broadcast was queued on the proxy and only dispatched after the whole send handler
  returned — meaning every subscriber waited for the sender's
  tracked_by/seen_by/membership/push-notification work to finish.

Now the broadcast goes directly through channel_layer.group_send right after save_message +
  save_attachments. The remaining work (participated_only tracking, unread state for offline
  members, browser/push notifications) moves to _post_send_processing, run via asyncio.create_task
  so the handler returns immediately.

A small _dispatch_proxy helper flushes proxy-built helper messages outside of receive_json.
  Exceptions in the background task are logged and contained to avoid silent task-never-awaited
  warnings.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

- **chat**: Eliminate redundant DB queries in send_message handler
  ([`599028f`](https://github.com/soma115/Wikikracja/commit/599028fc7f41b67fe9c12462473cd09e2e0046e1))

Removed a duplicate get_room() call and a get_user_by_name() lookup that re-fetched the
  already-available self.scope['user']. Saves 2 DB queries on every message send.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

### Refactoring

- Usun email_notifications_chat_participated z ustawien
  ([`6007736`](https://github.com/soma115/Wikikracja/commit/6007736c6397153c368137ac301772ce3aac9c0c))

- Pole email_notifications_chat_participated usuniete z modelu Uzytkownik (migracja 0020) -
  obywatele/views.py: 4. wiersz notifications usuniety, 'chat_participated' usuniete z
  NOTIFICATION_FIELDS w toggle_notification - profile.js: usunieto MUTUALLY_EXCLUSIVE +
  disableToggle (frontendowy hack ktory pilnowal ze 2 toggle czatu nie sa rownoczesnie ON) -
  django.po: usunieto nieuzywane tlumaczenia (Track room, Untrack room, Chat — my active
  discussions, etc.)

Ustawienia czatu maja teraz 1 prosty toggle ON/OFF. Per-room mute pozostaje jako precyzyjna
  kontrola.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

- Usun track button + auto-mute z UI czatu
  ([`b6c5247`](https://github.com/soma115/Wikikracja/commit/b6c524721feb5c33b54eadc10795b111882bd857))

- room_link.html: usunieto {% with %} z is_tracked/is_not_participated, usunieto blok {% if
  participated_only %} z track button, usunieto klase room-auto-muted - chat.css: usunieto style
  .room-link.room-auto-muted - handlers.js: usunieto handler kliku na .track-switch (fetch
  toggle-track endpoint juz nie istnieje) - chat.js: usunieto onRoomTracked websocket handler

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

- Usun tracked_by + participated_only z backendu czatu
  ([`493241f`](https://github.com/soma115/Wikikracja/commit/493241f955d9a8606ca51abf0417a2c0e86ee2b4))

- Room.tracked_by usuniete (migracja 0019) - Endpoint toggle_track + url + view usuniete -
  consumers.py: usunieto participated_only filtr w push notifications i auto-track w
  _post_send_processing (oszczednosc na queries) - chat/views.py: usunieto participated_only /
  participated_room_ids z kontekstu chat view (eliminacja query Message.filter na kazdym wejsciu) -
  filters.py: usunieto not_participated, is_tracked_by, is_auto_muted

Per-room mute pozostaje jedynym mechanizmem precyzyjnej kontroli.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

- Usuń inline style i zduplikowane skrypty z zakładek profilu
  ([`28835b2`](https://github.com/soma115/Wikikracja/commit/28835b21fb6d0be39414ac4d7b6051869fb4b1aa))

Inline font-size i max-width przeniesione do klas CSS (.table-hover-rows, .citizen-tab-empty,
  .td-truncate). Cztery identyczne script bloki zastąpione jednym event delegation listenerem w
  szczegoly.html.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

### Testing

- Add bulk_create performance tests with CaptureQueriesContext
  ([`13f63a1`](https://github.com/soma115/Wikikracja/commit/13f63a18d8f9abb631404845308027ef3eaa10b8))

Asserts on query count (≤ 5) instead of wall time. Time-based thresholds in SQLite test DB are too
  noisy and would never detect N+1 in a meaningful window — but query count flips from ~1-2 (correct
  bulk_create) to 100+ at the moment of regression.

Covers bulk_create for board.Post (100 records) and bookkeeping.Transaction (150 records).

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Add per-app tests (bookkeeping Transaction, obywatele Rate)
  ([`82514d5`](https://github.com/soma115/Wikikracja/commit/82514d5c07a82b6fc066ae99031ce3d7a849b260))

- bookkeeping/tests/test_models.py: new tests/ package for previously untested app; covers
  Transaction relations + type choices - obywatele/tests/test_reputation.py: covers Rate model with
  unique_together constraint and reputation sum flow

Both use Django TestCase (per-app convention on ui), not pytest factories. obywatele test documents
  the post_save(User) signal that auto-creates Uzytkownik — must use .get(uid=user), not
  .create(uid=user).

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Add shared conftest and factories (allauth-compatible)
  ([`3856942`](https://github.com/soma115/Wikikracja/commit/38569425a26def07ce975ab8316376a6de2b5a66))

- tests/conftest.py: 6 fixtures (authenticated_client, chat_room, board_category, bookkeeping_*,
  sample_users); uses force_login to bypass allauth email-only backend - tests/factories.py: 5
  factories (UserFactory, PostCategoryFactory, PostFactory, RoomFactory, DecyzjaFactory);
  UserFactory.password hashed via post_generation with update_fields=['password'] to isolate from
  post_save(User) signals - tests/test_smoke.py: 6 smoke tests verifying factories + fixtures work

DecyzjaFactory deliberately does NOT set chat_room — glosowania.signals auto-creates chat_room on
  Decyzja(status=1) save; setting it would create an orphan room.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Add WebSocket integration suite for ChatConsumer (8 tests)
  ([`5f1020b`](https://github.com/soma115/Wikikracja/commit/5f1020b51b408e1d7d4855916669caaa015de2b2))

Covers ChatConsumer protocol surface with concrete error code assertions: - Anonymous user rejection
  (close on connect) - Authenticated connect returns unread_count - Join public room returns
  metadata (id, title, public, notifications) - Join private room as non-member returns
  ACCESS_DENIED - Send to unjoined room returns ROOM_ACCESS_DENIED - message-react with invalid
  reaction returns INVALID_REACTION - get-notifications-data returns 'rooms' field - Multi-user
  broadcast via InMemoryChannelLayer reaches second user

InMemoryChannelLayer from zzz/test_settings.py — no Redis required for tests.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Add workflow smoke tests (chat lifecycle + glosowania signal)
  ([`f42fe62`](https://github.com/soma115/Wikikracja/commit/f42fe620bd924747309266d1d88b1709e6e06010))

- tests/test_workflow_chat.py: full Message lifecycle (create → edit with MessageHistory →
  MessageReadBy → MessageAttachment → reactions JSONField) - tests/test_workflow_glosowania.py:
  complete Decyzja flow (Argument FOR/AGAINST, ZebranePodpisy, KtoJuzGlosowal, VoteCode, status
  transition) + dedicated test_signal_auto_creates_chat_room_for_new_decyzja that explicitly asserts
  glosowania.signals.create_or_update_chat_room_for_referendum behavior (public, protected, founder,
  welcome message, allowed.set(active_users))

These are smoke tests verifying schema/relations stay intact across releases — not business logic
  tests for quorum/timing rules.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Configure pytest testpaths to discover per-app tests
  ([`716f69c`](https://github.com/soma115/Wikikracja/commit/716f69c630a917acbaa41e7239cfb1e1a40510d7))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Fix flaky email tests with synchronous threading stub
  ([`1f9d716`](https://github.com/soma115/Wikikracja/commit/1f9d71625e2a23cb29b8bcd1361c790f299821f9))

Patch threading.Thread to a synchronous _SyncThread in setUp so the TestCase transaction is visible
  to recipient queries inside the email worker. Production code unchanged — keeps the
  race-protection commit that fetches recipients inside the worker just before sending.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **e2e**: Add Playwright setup with mobile chat regression test
  ([`a9d4678`](https://github.com/soma115/Wikikracja/commit/a9d4678535fbeb24e747521d2023649c12e860da))

Setup z storageState reuse (login raz w auth.setup.js), dwa projekty (mobile-chromium Pixel 5,
  desktop-chromium 1280x800), inline loader .env.local bez zewnętrznego dotenv. Test pokrywa zarówno
  pozytywny flow mobile (lista się zwija przy tapie aktywnego pokoju) jak i desktop guard
  (window.innerWidth < 768 — klasa room-list-showing nie jest zdejmowana).

.gitignore dorzucony też dla .coverage (untracked pytest-cov artifact).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

- **e2e**: Wait for #sidebar after login to confirm session persistence
  ([`92c53b9`](https://github.com/soma115/Wikikracja/commit/92c53b95c87d5c633c6e4c6e4959a0314d311970))

Dodany waitForSelector('#sidebar') po Promise.all z waitForURL — sidebar renderuje się tylko dla
  zalogowanych ({% if user.is_authenticated %}), więc jego obecność potwierdza że sesja z
  _auth_user_id jest zapisana i serwer ją rozpoznał. networkidle odpada bo WebSockety nigdy nie
  milkną.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>


## v1.3.2 (2026-05-19)

### Bug Fixes

- **scheduler**: Konwertuj czas spotkania na lokalna strefe czasowa w powiadomieniach
  ([`9e21fdf`](https://github.com/soma115/Wikikracja/commit/9e21fdf6064ffaee97f069ef389fefdb2fd0b41c))


## v1.3.1 (2026-05-09)

### Bug Fixes

- **settings**: Read version from pyproject.toml instead of installed package metadata
  ([`475afca`](https://github.com/soma115/Wikikracja/commit/475afcae3e925f7c1c82b26ea502128b3e1ae10e))


## v1.3.0 (2026-05-09)

### Bug Fixes

- Build/merge duplicate translations
  ([`cead3ed`](https://github.com/soma115/Wikikracja/commit/cead3ed05f4b0db1f722966b1adcde3e54082275))

- **chat**: Declare glosowania dependency in 0017_room_founder migration
  ([`33af2af`](https://github.com/soma115/Wikikracja/commit/33af2af2d688b6c4d96ced85cf6b43b37f0fb95e))

What was broken --------------- The data migration chat/0017_room_founder.py calls Decyzja =
  apps.get_model('glosowania', 'Decyzja') to backfill the `founder` field for referendum chat rooms
  — but its `dependencies` list only mentioned chat/0016 and the User model. It never declared the
  glosowania app.

Why that's a bug ---------------- Django decides migration ordering ONLY from the explicit
  `dependencies` list — it does not infer dependencies from code inside RunPython functions. Without
  the declaration, Django was free to plan chat/0017 before any glosowania migration had run. On a
  fresh database (tests, CI, fresh clone) the Decyzja model didn't exist yet at that point, so
  apps.get_model('glosowania', 'Decyzja') raised: LookupError: No installed app with label
  'glosowania'.

This never surfaced on existing databases because chat/0017 was already recorded in
  django_migrations there — Django skips it on subsequent runs and the buggy code path simply never
  executes again.

Fix --- Add ('glosowania', '0013_auto_20260408_1446') to the dependencies. That's the migration that
  introduces Decyzja.chat_room, which is the exact field the data migration queries. Now Django
  guarantees the glosowania schema exists before chat/0017 runs.

Safety ------ Zero risk for already-migrated databases: Django respects dependencies only when
  planning what to run next, not when re-checking what is already applied. Production and dev DBs
  continue as-is; only fresh test/CI builds change behavior — they now succeed instead of crashing.

- **chat**: Eliminate duplicate sends and unblock broadcast on push notifications
  ([`165f4c4`](https://github.com/soma115/Wikikracja/commit/165f4c4fd0b2898c058c5ba4af3be629046ebf8c))

- asyncio.create_task() for push notifications in consumers.py so they no longer block the
  group_send broadcast (was causing 1-3s delay) - Disable send button immediately on submit,
  re-enable when own message returns via broadcast; 5s timeout as safety net (chat.js) - Same lock
  pattern in embedded chat (chat-embedded.js)

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

- **chat**: Expandable hint — inline bottom-right, horizontal gradient
  ([`78f1bfe`](https://github.com/soma115/Wikikracja/commit/78f1bfe6ab7399bfacc032822ab22c3110afc081))

Replace full-width vertical overlay with bottom-right inline hint that sits on the last visible line
  (Facebook-style). Layered horizontal gradients ensure solid background even when --expandable-bg
  is semi-transparent (own messages use rgba accent-muted).

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **chat**: Open_dm creates DM room on demand
  ([`406ab96`](https://github.com/soma115/Wikikracja/commit/406ab962037f3b6f50ebb8d85d98cea20933d9a6))

Clicking the chat icon for a citizen on /obywatele/ used to silently redirect to the chat list when
  no 1:1 room existed yet — relying solely on the user_accepted signal to materialize all pairs.
  open_dm now creates the missing room on the fly, reactivates archived ones, and always redirects
  with #room_id so the chat page opens the conversation.

- **events**: Calendar dots respect start_date; prevent chunk overlap in grid
  ([`9caf588`](https://github.com/soma115/Wikikracja/commit/9caf588d9e19455b37d67d1f700d470baf1944f6))

- build_calendar_grid: daily/weekly events now respect start_date — calendar no longer shows dots on
  days before the event begins - jumpToDay: check loadedMonths before fetching a chunk to avoid
  re-loading months already in the initial 90-day window (prevented doubled cards in grid view) -
  Remove scrollToFirstVisible — display:none hides past content so no scroll is needed; native
  anchor scroll caused off-by-one in viewport

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **home**: Show 5 upcoming events instead of 3 on dashboard
  ([`0c859c9`](https://github.com/soma115/Wikikracja/commit/0c859c97106dd2e744122457dd7fe42a04f63b4e))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **tasks**: Capture-phase click listener prevents card collapse on vote
  ([`0d147fd`](https://github.com/soma115/Wikikracja/commit/0d147fdaf60a66dbbf834e412327d142f06d144f))

Replace submit-event delegation with capture-phase click listener
  (document.addEventListener('click', handler, true)) so the handler fires before card-body onclick
  (navigate to detail) and card-header onclick (toggleCard) can execute. Also remove form.submit()
  fallback in catch to avoid page reloads on AJAX errors.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

### Chores

- **i18n**: Sync django.po z upstream (POT-Creation-Date + numery linii)
  ([`fd16753`](https://github.com/soma115/Wikikracja/commit/fd167530c253d8d887a98bd02cd19c0f255ce8aa))

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

### Features

- **categories**: Shared category system for board, tasks & elibrary
  ([`2fe94cd`](https://github.com/soma115/Wikikracja/commit/2fe94cd2404caf19828615c0ef289b2a09ca624c))

- New `categories` app: AbstractCategory base model + generic API views (CategoryAPIBase,
  CategoryEditAPI, CategoryDeleteAPI, CategoryReorderAPI) - board: PostCategory inherits
  AbstractCategory, category filter dropdown, manage modal with drag-and-drop reorder, cache
  invalidation for elibrary - tasks: Category refactored onto shared base, reorder API added -
  elibrary: category filter + manage modal reusing board categories - SortableJS (local, v1.15.6)
  for DnD reorder; shared JS modules (category-manager.js, sortable-list.js) loaded globally from
  base.html - Global design: inline styles extracted to CSS utility classes (.post-row-link,
  .post-card-link, .cat-group-icon, .text-*-clamp, .avatar-*, .book-*, .text-meta, .text-author);
  board/elibrary templates unified to card/card-header/card-body structure - Removed stale
  postcategory_list/form/confirm_delete templates - Polish translations updated for all new UI
  strings

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>

- **chat**: Expandable long messages, raise message limit to 1000, project docs
  ([`ec28ec0`](https://github.com/soma115/Wikikracja/commit/ec28ec0f24552f284693dd49aea935443f4f17ab))

- Long chat messages are clipped at ~9 lines with "… pokaż więcej" hint; click anywhere to toggle
  expand/collapse. markOverflow() detects when content actually overflows so short messages don't
  show the hint. Note: hint overlay still has stacking issue — needs refinement (see TODO). - Raise
  MESSAGE_MAX_LENGTH default from 500 to 1000 and surface it on /site-settings/. - Expose redis port
  in docker-compose for local Django access. - Add CLAUDE.md with project working rules and design
  system guide.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **chat**: Live unread counter — Redis cache + WebSocket push + routing do pierwszej
  nieprzeczytanej
  ([`de7be32`](https://github.com/soma115/Wikikracja/commit/de7be32f3942e3840f50c14c8ca69c719d17340b))

## Co zostało zmienione

### Backend - **chat/services.py**: Redis cache dla licznika nieprzeczytanych pokoi per-user (klucz
  `chat_unread:{user_id}`, TTL 5 min). Invalidacja przy `see_room` / `unsee_room`. Nowa metoda
  `ChatRepository.get_unread_count()`. - **chat/consumers.py**: Każdy user dołącza do grupy
  `user_{id}` przy WS connect. Po `room-seen` / `room-unseen` serwer pushuje zaktualizowany licznik
  przez `{type: "chat.unread_count", count: N}` do tej grupy. Nowe metody: `push_unread_count()` i
  handler `chat_unread_count(event)`. Przy WS connect serwer od razu wysyła bieżący licznik do
  klienta. - **home/views.py**: `chat_unread_count` czytany z cache Redis, obliczany z DB tylko przy
  cache miss. - **chat/views.py**: Nowy endpoint `GET /chat/api/unread-count/` → `{"count": N}` (z
  cache, bez uderzania w DB przy każdym żądaniu). - **chat/urls.py**: Rejestracja nowego URL
  `api/unread-count/`.

### Frontend - **home/templates/home/home.html**: Badge czatu ma `id="chat-unread-badge"`. Link
  prowadzi do `/chat/?unread=1` gdy są nieprzeczytane pokoje. Dodany JS: (a) `visibilitychange` —
  odświeża licznik gdy użytkownik wraca do zakładki (fix bfcache / back-navigation), (b) lekkie
  połączenie WS `/chat/stream/` — gdy serwer pushnie `unread_count`, badge aktualizuje się
  natychmiast bez przeładowania strony. - **chat/static/chat/js/chat.js**: Przy starcie czatu z
  `?unread=1` aktywowany jest filtr "Nieprzeczytane" i otwierany pierwszy nieprzeczytany pokój. URL
  param czyszczony przez `history.replaceState`.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

- **chat/mobile**: Sticky toolbar, brak autofocusu, lista pokoi przy ?unread=1
  ([`1b3d610`](https://github.com/soma115/Wikikracja/commit/1b3d610b130d195a4f4c69a0b8be99d4f0616483))

- CSS: .room-list-controls sticky top:0 na mobile — toolbar z przyciskami (+ Pokój, Nieprzeczytane,
  itp.) zostaje przyklejony u góry panelu listy pokoi nawet gdy użytkownik scrolluje w dół przez
  długą listę - JS: messageInput.focus() przy wejściu do pokoju tylko na desktop (>= 768px) — na
  mobile klawiatura nie otwiera się automatycznie, dopiero po kliknięciu w pole wpisywania - JS:
  ?unread=1 z pulpitu — na desktop otwiera pierwszy nieprzeczytany pokój, na mobile zostaje na
  liście pokoi z aktywnym filtrem "Nieprzeczytane" żeby użytkownik sam wybrał pokój

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

- **events**: Agenda/grid views with mini-calendar drawer and lazy chunk loading
  ([`f68314c`](https://github.com/soma115/Wikikracja/commit/f68314c1ab1e46e4614f3e96ccd08d722f2c9f95))

- New agenda list view: month/day grouping, event chips, past days hidden by default - Grid view:
  expandable cards (pk+date IDs to avoid collisions across chunks) - Single toolbar drawer trigger
  for mini-calendar; closes on outside click or day double-click - Day click filters both agenda and
  grid from selected date; stays in current view - Lazy 3-month chunk loading when clicking a
  far-future day not yet in DOM - New views: events_agenda_chunk (AJAX partial), events_calendar
  reused for drawer - build_calendar_grid extracted to events/calendar.py, shared with obywatele -
  Polish month names via Django i18n date filter (cal_first_day|date:"F Y") - Grid defaults to
  hiding past cards on initial load (consistent with agenda)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **glosowania**: Increase law text max length from 1000 to 2000 chars
  ([`003a900`](https://github.com/soma115/Wikikracja/commit/003a90028197173e1926f54904f486ab2d6ac219))

- **home**: Make New Citizens card fully clickable
  ([`863d895`](https://github.com/soma115/Wikikracja/commit/863d895db1b251f247eb84f11c5222377d521366))

Whole card links to citizen list via Bootstrap stretched-link. Individual citizen avatars and
  waiting-badge link keep their own targets via position:relative (above the stretched-link in
  stacking context).

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **tasks**: Ajax voting, global design buttons, tooltips
  ([`d487a52`](https://github.com/soma115/Wikikracja/commit/d487a5285390035a670fecd7b271194f8fd822e8))

- vote_task view returns JSON for AJAX requests (X-Requested-With header) tracking new_vote value
  and votes_up count - new tasks/static/tasks/js/tasks.js: single shared handleVoteSubmit function
  used by both list and detail views — no code duplication; updates button state (active-vote, icon,
  text) and vote counters in-place without page reload or closing expanded card - task_detail.html +
  _task_card.html: replaced generic Bootstrap btn-* classes with project design-system classes
  (task-vote-btn, action-btn, task-take-btn, task-resign-btn) that use CSS variables and adapt to
  all themes; added data-text/icon/tooltip-active/inactive attributes - Bootstrap tooltips on all
  action buttons with context-sensitive text - i18n: 8 new Polish translations for button states and
  tooltips

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **tasks**: Coordinator role + helpers popover on task cards
  ([`a523258`](https://github.com/soma115/Wikikracja/commit/a523258ac5ba6b725cbc3a32786c2957bec8d4f9))

- meta strip: Autor → Koordynator · Data · ❤ N · Detale with role icons (fa-user-pen, fa-user-gear,
  fa-clock-rotate-left) - per-element tooltips (author, coordinator, date, helpers count, details) -
  lazy-loaded helpers popover (hover on desktop, click on touch devices) via new
  tasks/<pk>/helpers.json endpoint, up to 10 avatars + "and N more" - DOMPurify sanitization for
  popover html; cache invalidated on vote change - rename UI: "Take task"/"Resign" →
  "Zostań/Zrezygnuj z koordynacji", "Owner"/"Assigned to" → "Koordynator" across card and detail
  views - refactor inline styles in body to .task-assignee-link/.task-assignee-empty - new pl
  translations for all introduced strings

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

- **tasks**: Dynamic categories — DB model, CRUD API, manage modal
  ([`186e3be`](https://github.com/soma115/Wikikracja/commit/186e3be58c0006003814c5dfb5dd481990f93f06))

Replaces hardcoded Task.Category TextChoices with a proper Category model (slug, name, description,
  order, is_protected). Users can now add, edit and delete categories from the task list UI via a
  modal opened from the category filter panel.

- Migration 0008: creates tasks_category table, seeds 7 existing categories, migrates Task.category
  varchar→FK (SET_NULL on delete) - API endpoints: GET/POST /api/categories/, POST
  /api/categories/<pk>/edit|delete/ - Modal: inline edit, add new, delete with affected-task count
  warning - Category filter reads slugs from DB instead of TextChoices - CSS via design tokens (no
  hardcoded colours); theme-aware

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **ui**: Persistent filters and view settings via PagePrefs
  ([`4ac97b0`](https://github.com/soma115/Wikikracja/commit/4ac97b04cd3381ec04151209bee4c508c9488c8a))

Replaces 5 separate localStorage wrappers (setTaskView, setProposalsView, setElibraryView,
  setBoardView, setActivityView) with a single global PagePrefs module. Filters (URL params),
  grid/list toggle and Bootstrap tab selection are now stored per-scope in one JSON key
  (wikikracja:prefs:{scope}) and restored on return visit without flashing.

- Anti-FOUC head-script restores URL filters before body renders - Patches history.pushState to
  capture JS-driven URL changes (category filter) - HTML uses data-view / data-view-container
  conventions — zero onclick bindings - Elibrary category filter gains URL sync (was DOM-only, now
  shareable) - One-shot migration of legacy localStorage keys on first load

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

### Testing

- **tasks**: Add test_settings.py to run tests without Redis
  ([`395cea4`](https://github.com/soma115/Wikikracja/commit/395cea4cd820bc2444314bf3b21e011d24af00c2))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>


## v1.2.0 (2026-05-01)

### Bug Fixes

- **chat**: Fix image upload button, size limit, and lightbox in embedded chat
  ([`7f45ced`](https://github.com/soma115/Wikikracja/commit/7f45ceda1126593678d73a50e11315247979e56f))

- Fix image upload button not opening file dialog: fmt-btn click handler was calling
  e.preventDefault() unconditionally, blocking the label's default action — now only fires for
  buttons with data-cmd - Fix upload field name in chat-core.js: was 'files', server expects
  'images' - Fix upload size limit: remove accidental *2 multiplier in views.py, align JS client
  (wsapi.js, chat-core.js) to match UPLOAD_IMAGE_MAX_SIZE_MB=5 - Unify lightbox: extract
  openBigImage + createImageClickHandler into chat-core.js as shared exports; domapi.js delegates,
  chat-embedded.js now uses the same lightbox as main chat

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **chat**: Unify formatting toolbar — fix active state and focus-theft bug
  ([`bc662a6`](https://github.com/soma115/Wikikracja/commit/bc662a60efe945256f622a054c3469578b98ed8c))

- Anonymous button now uses same active style as B/I/U (removed custom .anonymous-toggle.active CSS
  override) - Extracted initFormattingToolbar() to chat-core.js — single definition used by both
  main chat and embedded chat - mousedown preventDefault prevents focus-theft, so text selection is
  preserved when clicking toolbar buttons; fixes "deselect one resets all" - Fixed
  updateToolbarState in embedded chat scoping to [data-cmd] only, so anonymous button active state
  is no longer reset on selectionchange - Removed dead const-reassignment block in handlers.js
  (would crash in strict/module mode when SITE_SETTINGS.messageMaxLength is set) - Fixed
  content.classList.remove('open') accidentally inside comment

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

### Features

- **chat**: Compress uploads to WebP and lazy-load attached images
  ([`87c177a`](https://github.com/soma115/Wikikracja/commit/87c177a4d9f83a99598a856f84a1acc75292b823))

- On upload: resize to max 1920px long side (LANCZOS), convert to WebP @85% quality — typically
  3-10x smaller than original PNG/JPEG - Use image.size for size check instead of reading full bytes
  to memory - Add loading="lazy" to attached-image elements so browser defers off-screen images
  instead of loading entire chat history at once

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

### Refactoring

- **chat**: Unify upload size limit into single UPLOAD_MAX_BYTES constant
  ([`b343c12`](https://github.com/soma115/Wikikracja/commit/b343c1295d2d03ad9fc6022d1faed0f3a39ebe01))

Move hardcoded 5MB limit from wsapi.js and chat-core.js into one exported constant in chat-core.js,
  imported by wsapi.js — single source of truth.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>


## v1.1.0 (2026-04-29)

### Bug Fixes

- Add reaction counts for messages in chat
  ([`3486f63`](https://github.com/soma115/Wikikracja/commit/3486f63aebd084c80b7026d087b9beeea98a69cb))

- Badly merged user chats view
  ([`a1f8144`](https://github.com/soma115/Wikikracja/commit/a1f8144ba79d1af4c3a67da6724f6409e15ae34e))

- Bug: chat activity does not list the real messages of the person selected
  ([`c1022dc`](https://github.com/soma115/Wikikracja/commit/c1022dcae03721baa1487d1b9160a47b172c8b48))

- Chat reactions does not work on first click on them
  ([`e107843`](https://github.com/soma115/Wikikracja/commit/e107843fd5c137d86f2324e48462fbe891c8cb53))

- Migrations and settings
  ([`3b448e8`](https://github.com/soma115/Wikikracja/commit/3b448e8f8de6cf594dbbe3cffbbcf49e671f5ea3))

- Semantic build, unneded json
  ([`711a20b`](https://github.com/soma115/Wikikracja/commit/711a20b449116aa3250da0c2719a35081697ff7f))

- Set created_at on in-memory task objects in test helpers
  ([`f41d8cf`](https://github.com/soma115/Wikikracja/commit/f41d8cf2fa8c32dbf2f95ce2bfe1cf594816b4e4))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **chat**: Fix compose bar overflow on narrow mobile screens
  ([`20f3a54`](https://github.com/soma115/Wikikracja/commit/20f3a54506eee79ddaf23d82f84789d260937a85))

- Reduce padding in embedded chat on mobile (ec-messages, ec-input-area, compose-bar) to gain ~30px
  horizontal space - Add flex-wrap to compose-bar on mobile so send button wraps to a second line
  instead of overflowing — applies to both main and embedded chat - Remove dead CSS: unused
  .chat-controls-row and redundant .send-message display override

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **chat**: Fix reply-to button not working — missing import of setReplyTarget
  ([`ef3837f`](https://github.com/soma115/Wikikracja/commit/ef3837f24b236fa6f07d0c57124bb084cd304da2))

Clicking the reply button caused a ReferenceError because setReplyTarget was used in handlers.js but
  never imported from chat.js. As a result, currentReplyId was never set and messages were sent
  without reply_to_id, so quoted/reply messages were silently broken.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **chat**: Make quote-jump return button work in embedded chat
  ([`dca7b16`](https://github.com/soma115/Wikikracja/commit/dca7b166b249a7676f26b0bbf369adb92fee6c49))

Move showReturnBtn logic into createQuoteJumpHandler in chat-core.js so it is shared by both main
  and embedded chat views. Remove ~60 lines of duplicate handler code from handlers.js.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **chat**: Scroll listy pokojów, batch rendering, reconnect fix
  ([`09c3726`](https://github.com/soma115/Wikikracja/commit/09c3726875ad139aa21d2df276c7875e81c47d02))

- CSS: 100dvh, layout-wrapper/main-area height chain, room-list height:0 flex:1 1 0 - CSS:
  room-list-controls flex-shrink:0 (zamiast sticky), mobile safe-area-inset - JS: batch rendering
  wiadomości przy join (jeden insertAdjacentHTML zamiast N) - JS: reconnect guard — reset
  CurrentRoomId przed rejoinem po reconnect WebSocket - JS: parseInt(room_id) i strict === w
  onRoomTryJoin i onReceiveMessages - domapi.js: buildMessageHtml jako osobna metoda dla batch
  renderingu

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **chat**: Strip HTML tags from email notifications
  ([`b747b1b`](https://github.com/soma115/Wikikracja/commit/b747b1b191e60c6e5f37f6098b2d35647064720a))

<br> tags converted to newlines, other HTML tags removed before inserting message text into
  plain-text email body.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **editor**: Improve TinyMCE layout and usability globally
  ([`2750c7e`](https://github.com/soma115/Wikikracja/commit/2750c7e250d97b8f6f84e81aea93fc6140ec1b9a))

- elibrary book_form: widen editor column (col-md-6 → col-md-8), narrow uploads sidebar (col-md-4) -
  uploader.js: sliding toolbar mode, fixed height 500px, manual resize handle, remove autoresize
  plugin - app.css: ensure .tox-tinymce fills container width on all screen sizes

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **richtext**: Zastosuj |richtext również w podglądach kart i potwierdzeniu usunięcia
  ([`b1542c2`](https://github.com/soma115/Wikikracja/commit/b1542c2cc157ac5cf2b0c9bfa45b6231fb13bec3))

W poprzednim commicie objąłem widok szczegółów (rozwinięty kafelek), ale przegapiłem kilka miejsc
  gdzie pola opisu są renderowane raw:

- tasks/_task_card.html:53 (Agora-style preview na liście /tasks/) — widoczny był surowy <b>...</b>
  w tekście podglądu pod tytułem zadania. - glosowania/_proposal_card.html:60 (preview na liście
  propozycji, /glosowania/proposition/) — analogiczny problem dla pola tresc. -
  events/event_confirm_delete.html:18 (potwierdzenie usunięcia wydarzenia) — |truncatewords:30
  zostawiało raw HTML. - home/search.html:141 (wyniki wyszukiwania, mieszane typy contentu) — raw {{
  item.description }} jednolinijkowo z white-space:nowrap. Tu użyty |striptags zamiast |richtext, bo
  description w wynikach pochodzi z różnych modeli (task/post/book/event/...) i niektóre mają
  TinyMCE HTML — strip do plain tekstu daje spójny preview niezależnie od źródła.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

### Chores

- Merge remote ui branch, resolve locale conflicts
  ([`67ab606`](https://github.com/soma115/Wikikracja/commit/67ab6067edee4f341e6a5f23ff67ef22199a71d1))

Accept remote line-number references in django.po (11 upstream commits updated obywatele/views.py
  line numbers); accept deletion of en locale.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

### Features

- **chat**: Add Room.founder field with backfill migration; fix citizen activity tabs
  ([`72c1dc1`](https://github.com/soma115/Wikikracja/commit/72c1dc1eac2406ccf0ccb5393d6c340d5916201a))

- Add `founder` ForeignKey to Room model (null=True for legacy rooms) - Migration 0017 backfills
  founder: referendum rooms via Decyzja.author, task rooms and manual rooms via first message sender
  - Set founder on Room creation in glosowania and tasks signals - citizen_czaty: show messages sent
  by the user instead of rooms they belong to - citizen_zalozono: include rooms founded by the user

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **chat**: Mobile room-list toggle, unified sort-btn styles, layout fixes
  ([`d349361`](https://github.com/soma115/Wikikracja/commit/d3493610ff00351e14e1e4ef5620b979f18d82a2))

Mobile: - Replace folded-room-header/drawer with room-active + room-list-showing CSS classes - Sort
  toolbar << shows room list without leaving room; >> next to Unread returns to chat - Send button
  always visible on mobile

Desktop: - Sort toolbar toggle btn hidden when list visible; shown as << when list collapsed -
  room-list-controls buttons unified to global sort-btn class (consistent with /glosowania/ toolbar)

Layout: - Extract room-list-controls outside scrollable #room-list into separate .room-list-col
  wrapper so scrollbar never affects controls alignment - Unify padding between chat-breadcrumb-row
  and room-list-controls (.25rem .75rem) - Remove floating mobile-back-to-room button

Cleanup: - Remove dead code: onBackToRoomList, setFoldedRoomTitle, chat-show-rooms-bar viewport
  handler - Remove unused CSS: col-scrollable, list-of-rooms, list-of-pms - Remove stale ZMIANA
  labels from comments

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **chat**: Persist unsent message drafts in localStorage
  ([`36d86c2`](https://github.com/soma115/Wikikracja/commit/36d86c21e86589c78ecfd37ef8e3a3ad3b6b6810))

Drafts are saved per room on every keystroke and restored when re-entering the room. Cleared
  automatically on successful send.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **dashboard**: Reorganize tiles into 3 columns per row and fix onboarding step_voted backfill
  ([`c7e87b3`](https://github.com/soma115/Wikikracja/commit/c7e87b3bb0d17c98cd34919fed1f4853ffa53258))

Row 1: First steps | Activity | Upcoming events Row 2: Voting proposals | Discussed votings (new) |
  Active referendum Row 3: unchanged

Added discussed_proposals queryset (status=2), renamed "New proposals" to "Voting proposals" with
  Polish translations, and backfilled step_voted for users who voted before the onboarding signal
  existed.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **glosowania**: Redesign details and edit pages, clean up
  ([`de758e4`](https://github.com/soma115/Wikikracja/commit/de758e4af283c1ffec8d7207725f58ee9975d72c))

- szczegoly.html: unified single card (title + meta + action), full-width args grid, dynamic
  support/vote labels, cleaned unused imports and wrappers - edit.html: match global
  card+card-header style - components.css: detail-status-badge sizing, action-btn fit-content,
  detail-layout single column, new arg-card/form/toggle styles - django.po: add PL translations for
  new UI strings

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **nav**: Add Chat link to navigation menu
  ([`c06d19a`](https://github.com/soma115/Wikikracja/commit/c06d19ac3439d7be3830d494086e791a0f854ddb))

- **richtext**: Unify rich-text editing/rendering across tasks, glosowania, events
  ([`4d39d0d`](https://github.com/soma115/Wikikracja/commit/4d39d0df508758a9877fc0cf4b7202f92cc61e28))

Wprowadza wspólny pipeline dla pól tekstowych z minimalnym formatowaniem (B/I/U + auto-linkifikacja
  URL), współdzielony między czatem a formularzami zadań, głosowań i wydarzeń. Zastępuje ~7
  wariantów filtrów (|linebreaks, |linebreaksbr, |urlize, |safe + ad-hoc bleach.clean) jednym
  filtrem oraz jednym widgetem Django.

NOWE PLIKI - zzz/richtext.py — centralny sanityzator (bleach.clean + bleach.linkify), jedyne źródło
  prawdy: ALLOWED_TAGS = ['b','i','u','br','a'] + ALLOWED_ATTRS = {'a': ['href','rel','target']}.
  Zewnętrzne linki automatycznie dostają target="_blank" rel="noopener" przez callback. -
  home/templatetags/richtext.py — filtr {{ x|richtext }}: sanitize → \n na <br> → linkify →
  mark_safe. - home/widgets.py — RichTextWidget(forms.Textarea): contenteditable + toolbar B/I/U +
  hidden input + counter (opcjonalny). value_from_datadict() sanityzuje POST-a (defense in depth gdy
  JS wyłączony). - home/static/common/js/richtext-core.js — pure functions: getInputHtml,
  formatMessage, updateCounter, handleEnterKey, getVisibleTextLength. ALLOWED_TAGS/ATTR
  zsynchronizowane z backendem. - home/static/common/js/richtext-input.js — auto-init dla
  [data-richtext]: toolbar, skróty Ctrl+B/I/U, plain-text paste, sync hidden input przy submit.

REFAKTOR CZATU (zero zmian zachowania) - chat/consumers.py: usunięta lokalna stała
  ALLOWED_HTML_TAGS, dwa wywołania bleach.clean(...) zamienione na sanitize(..., linkify=False). -
  chat/services.py: usunięte 3 martwe importy (bleach, settings, format_chat_message), dwa
  re.sub(r'<[^>]+>', ...) zamienione na strip_tags(). - chat/static/chat/js/chat-core.js: pure
  functions (getInputHtml, formatMessage, updateCounter, handleEnterKey, getVisibleTextLength)
  przeniesione do /static/common/js/richtext-core.js. chat-core.js teraz je re-eksportuje, więc
  chat.js / chat-embedded.js / handlers.js / domapi.js działają bez zmian.

ZASTOSOWANIE W FORMULARZACH - tasks: TaskForm.description → RichTextWidget. Szablony task_form.html
  (+ {{form.media}}), task_detail.html, _task_card.html, _task_cards.html używają |richtext zamiast
  |linebreaks(br)|safe. - glosowania: DecyzjaForm.tresc/kara/uzasadnienie + ArgumentForm.content →
  RichTextWidget z max_length. Szablony szczegoly.html (5 wystąpień), _proposal_card.html (3),
  delete_argument.html (1) → |richtext. dodaj.html / edit.html / edit_argument.html ładują
  {{form.media}}. Inline formularze argumentów FOR/AGAINST w szczegoly.html zostawione na plain
  <textarea> (sanityzacja na POST przez ArgumentForm.value_from_datadict). - events:
  EventForm.description → RichTextWidget. event_detail.html / event_list.html → |richtext.
  event_form.html ładuje {{form.media}}.

POLA Z TINYMCE — CELOWO NIETKNIĘTE (zaufana treść admina/długie teksty) - board.post.text — TinyMCE
  + |safe (bez zmian). - elibrary.book.abstract — używa TinyMCE poprzez static/js/uploader.js
  (tinymce.init({selector:'textarea'})) ładowane w book_form.html. KOREKTA: book_list.html i
  book_detail.html teraz renderują {{...|safe}} zamiast escape'owanego tekstu (wcześniej tagi
  <p>/<strong> wyświetlały się jako tekst). UpdateBookForm pozostaje na forms.Textarea — TinyMCE
  zamienia ją client-side. - home.start.text, home.footer.text, activity.description — bez zmian
  (treść redagowana w panelu admina, dozwolony pełen HTML).

GLOBALNIE - home/templates/home/base.html: DOMPurify ładowany raz globalnie (używany i przez chat
  input, i przez RichTextWidget). Usunięte duplikaty <script> z chat.html, _embedded_chat.html oraz
  z RichTextWidget.Media.

LOKALIZACJA - locale/pl/LC_MESSAGES/django.po: zaktualizowane numery linii po nowych blokach {%
  block extra_css %} w szablonach formularzy + dodane polskie tłumaczenie nowego placeholdera w
  opisie zadania.

DOZWOLONE TAGI (backend ↔ frontend, jedno źródło prawdy) b, i, u, br, a (z atrybutami
  href/rel/target) Reszta (np. <p>, <strong>, <script>) wycinana przez bleach.clean (backend) i
  DOMPurify (frontend).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

- **tasks**: Add category field with multi-select JS filter and tooltips
  ([`52c2348`](https://github.com/soma115/Wikikracja/commit/52c2348efebabc04e457b40cc555fe65d7cee09c))

- Task.Category with 7 choices + CATEGORY_DESCRIPTIONS dict (gettext_lazy) - Migration
  0007_add_task_category - Category field in task create/edit form with [i] popover listing all
  categories - Multi-select dropdown filter in toolbar: JS DOM filtering + pushState URL sync, no
  reload - Fix cache invalidation: version-key pattern replaces broken delete_pattern - Fix dropdown
  panel closing on click via stopPropagation - Popover and dropdown styled with project design
  tokens (--bg-card, --accent) - PL and EN translations for all category labels and descriptions

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

### Refactoring

- Modularize chat functionality by extracting core features into chat-core.js
  ([`5b8c2c5`](https://github.com/soma115/Wikikracja/commit/5b8c2c5a9b355f713b2d6d9c4cc79ffcc44f08b7))

- **chat**: Apply compose-box layout to embedded chat view
  ([`c28ea24`](https://github.com/soma115/Wikikracja/commit/c28ea24a4ed67deaeced8ec669171a6f3199a7a2))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **chat**: Introduce ChatRepository and simplify consumer logic
  ([`20b7ec1`](https://github.com/soma115/Wikikracja/commit/20b7ec1399449ccaa9f4267e0ca11cd8819c0da0))

Refactor chat consumers to use a repository pattern via ChatRepository, removing direct model
  imports and cleaning up unused code and comments for better maintainability and readability.

- **chat**: Modularize event handlers by utilizing shared functions from chat-core.js
  ([`b7e8eaf`](https://github.com/soma115/Wikikracja/commit/b7e8eaf617fb3774b728cefc5957bb467db16b73))

- **chat**: Redesign compose bar into unified input box
  ([`22c6ea8`](https://github.com/soma115/Wikikracja/commit/22c6ea84f4e17ddec24c8b891001ca24cc7c811b))

Move send button and formatting toolbar into a single rounded compose-box container below the
  textarea, matching new UI design.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **push-notifications**: Migrate VAPID public key handling to dynamic settings
  ([`379a2a7`](https://github.com/soma115/Wikikracja/commit/379a2a74259061e474fce3ecb72b664320100167))


## v1.0.0 (2026-04-25)

### Bug Fixes

- 1 ASGI thred in debug mode
  ([`e19f579`](https://github.com/soma115/Wikikracja/commit/e19f579c5ef9e8de4f86f7d83b1d61cbd68ca96a))

- Add allowed users to room on creation to prevent race condition in create_one2one_rooms
  ([`025a6c8`](https://github.com/soma115/Wikikracja/commit/025a6c807eba2ec24e700907ae7fd821638ae2fd))

- Add database transaction with select_for_update lock to prevent race conditions in user activation
  ([`a70494b`](https://github.com/soma115/Wikikracja/commit/a70494b8536e21f9228f185dbb9cc3eb5a50ad28))

- Add detailed logging for room access checks and improve fix_room_permissions command output
  ([`7fc33f6`](https://github.com/soma115/Wikikracja/commit/7fc33f63619e799931d49db82ab3eb3c68cfa04f))

- Add DoesNotExist exception handling with logging to chat consumers, glosowania views, and
  obywatele views
  ([`b8ed394`](https://github.com/soma115/Wikikracja/commit/b8ed39402b1dc587a9c2e27be88063cc1e5a7662))

- Add None reputation check and logging to activate_eligible_users, return 0 on population error
  ([`d3a223b`](https://github.com/soma115/Wikikracja/commit/d3a223b818966b1f893ecc2e1f5cbc7d84a5bb38))

- Add orphaned Uzytkownik cleanup and logging to duplicate email migration
  ([`82168d7`](https://github.com/soma115/Wikikracja/commit/82168d7cc43a6127327dbf53db1e82b0156a60ef))

- Add Room ManyToMany cleanup for orphaned users in duplicate email migration
  ([`d039fbd`](https://github.com/soma115/Wikikracja/commit/d039fbd2e0f2f75f7341bfe01e245e3f42f6c9ab))

- Added explicit id declaration in models for coe quality
  ([`fb898da`](https://github.com/soma115/Wikikracja/commit/fb898da1df94ba9da16d55afbd4288e9aed2b75f))

- Adjust scheduler intervals - chat_messages to 12,18h, chat_rooms and count_citizens to every 5
  minutes, update_site to minute 2
  ([`74720e0`](https://github.com/soma115/Wikikracja/commit/74720e069aca58268fe0d85cd7e091f97b7228de))

- All translations
  ([`42c90ae`](https://github.com/soma115/Wikikracja/commit/42c90aebba404a86ad9a9267a8b30d8fd8e5251d))

- Chat js circular dependency resolved
  ([`6f04b8e`](https://github.com/soma115/Wikikracja/commit/6f04b8e38d96c6fc5076bb9b5a640b5097224328))

- Chat optimization, no WebSock if not subscribed
  ([`47e9f94`](https://github.com/soma115/Wikikracja/commit/47e9f94c7cf9eb4998cc0866e9a7a2e8bc00049f))

- Cron day of week
  ([`c343412`](https://github.com/soma115/Wikikracja/commit/c34341217cac57beaea72cb1bd7a7054b4707db0))

- Cssy poprawnie zmergowane
  ([`39fdbda`](https://github.com/soma115/Wikikracja/commit/39fdbdaaa5e9b2c43a9ecd2490767ea274c0825a))

- Deleted unused files
  ([`bee21a0`](https://github.com/soma115/Wikikracja/commit/bee21a059fad558ae0800d726d6dcec5e9684dae))

- Dont show (and force) unseen archived rooms, Default: collapsed
  ([`6d492b1`](https://github.com/soma115/Wikikracja/commit/6d492b19e89568c8524b7258ce5a87fcabcbde6a))

- Escape regex pattern and remove duplicate email migrations
  ([`aaeef90`](https://github.com/soma115/Wikikracja/commit/aaeef901af50a842035b4b662a50ce9880adad2a))

- Exclude archived rooms from new message notifications and remove unused imports
  ([`6715e6e`](https://github.com/soma115/Wikikracja/commit/6715e6efa491aeccce6b934118c3246c43496381))

- Get_messages optimizations
  ([`719396f`](https://github.com/soma115/Wikikracja/commit/719396fe7519b46bc64c6928145e837b240201c5))

- Hide scheduler.lock
  ([`6b58ad6`](https://github.com/soma115/Wikikracja/commit/6b58ad66c74425c8262d71196efa0bdeb31ddb6c))

- Implement activity feed read marking functionality and update unread item handling
  ([`aba76a3`](https://github.com/soma115/Wikikracja/commit/aba76a3c641d85dd822eac33cffff166f611ef4b))

- Improve user activation logging and prevent duplicate activations in count_citizens command
  ([`55829d2`](https://github.com/soma115/Wikikracja/commit/55829d21f464969ec670e86d016cd7bc68d7c456))

- Improve user handling with case-insensitive email check, safer signal handlers, and optimized
  query
  ([`3295844`](https://github.com/soma115/Wikikracja/commit/3295844a7e0f40e28e5ed863c73a8990c393fd52))

- In docker scheduler runs twice, file lock added
  ([`b6c2814`](https://github.com/soma115/Wikikracja/commit/b6c28147f4819b28653fb5bcc292fb6d32c275e5))

- Just formatted chat.css
  ([`6037c04`](https://github.com/soma115/Wikikracja/commit/6037c049a57c7f477336ab76ab490e37d0305dc4))

- Less logging
  ([`32c45f3`](https://github.com/soma115/Wikikracja/commit/32c45f3fb6e986d01351ea4e69a3a6d282eb7168))

- Minor html fixes
  ([`15e1ecc`](https://github.com/soma115/Wikikracja/commit/15e1eccbaae4d9cfecac598d0cd5fa72e0020ecf))

- Move scheduler singleton check from apps.py to scheduler.py and return existing instance
  ([`64f55b5`](https://github.com/soma115/Wikikracja/commit/64f55b568da965105ad86adb2e7160d80e56af45))

- No negative req reputation
  ([`4d05e6c`](https://github.com/soma115/Wikikracja/commit/4d05e6cb8a52b88b0fdb39778cae9260985a3c31))

- One websocket connection for notif and chat
  ([`f69197e`](https://github.com/soma115/Wikikracja/commit/f69197ef391e45243fe831f1a82df31b7295b753))

- Optimized get-notifications-data
  ([`1b46166`](https://github.com/soma115/Wikikracja/commit/1b461664a05f70774d34a4837034b494914b160f))

- Python 3.14 migration fix, dead library
  ([`ca41b24`](https://github.com/soma115/Wikikracja/commit/ca41b245ab6a96512e1d589d9e6d7fc6c49fbe99))

- Remove outdated security documentation files after fixes have been applied to codebase
  ([`4879c01`](https://github.com/soma115/Wikikracja/commit/4879c018446b3e2dc5724011172b43340226b40c))

- Removed redudant index
  ([`0f1a16e`](https://github.com/soma115/Wikikracja/commit/0f1a16e2a8283981d315f17f4234468c7044e259))

- Room list not showing
  ([`1064efd`](https://github.com/soma115/Wikikracja/commit/1064efddfe1aeeb043d0fc789937a73a32ba5c40))

- Set reputation to 0 for users without ratings and move save outside conditional
  ([`91f44c0`](https://github.com/soma115/Wikikracja/commit/91f44c0963471006ad04c5d1f84aa317ef83233c))

- Update translation files with new line numbers after DoesNotExist exception handling changes
  ([`da59ff9`](https://github.com/soma115/Wikikracja/commit/da59ff95d806cd4e8900ca479b6e40dc5aa7271c))

- Update translation files with new line numbers after settings.py changes
  ([`32100a8`](https://github.com/soma115/Wikikracja/commit/32100a899af87b89a6f5d976a8f6b2e097b648df))

- Updated github workflow actions versions
  ([`60c8419`](https://github.com/soma115/Wikikracja/commit/60c84199907c7c150fbbd6954342f3e1ec24e173))

- Wider Zasoby screen
  ([`13dc811`](https://github.com/soma115/Wikikracja/commit/13dc81147d1b3053e89968b93ce56c962e665066))

### Chores

- Js and css cleanings
  ([`f180822`](https://github.com/soma115/Wikikracja/commit/f180822a5a27884d00a4309b16374118dae0554b))

- Updated requerements
  ([`99aad8c`](https://github.com/soma115/Wikikracja/commit/99aad8cd7e2e540452809e14bd868b52fffab0e8))

### Features

- Add 'why' field to profile display and form handling.
  ([`3f44a34`](https://github.com/soma115/Wikikracja/commit/3f44a3437c9cfe1c64ad40684bf64be99149b62a))

- Add 'why' field to profile display and form handling. Part 2.
  ([`6607d12`](https://github.com/soma115/Wikikracja/commit/6607d12176eb1124efd1b0d02ccbdfa3507ab834))

- Add duplicate email validation and handling in signup form
  ([`2e808cd`](https://github.com/soma115/Wikikracja/commit/2e808cd2f112cf3619f9d86beb2e499ea33d83dc))

- Android Firebase notifications
  ([`84e093e`](https://github.com/soma115/Wikikracja/commit/84e093efc2bad930c5e80bde15dc2ddd13b27174))

- Android firebase notifications almost work
  ([`be2907c`](https://github.com/soma115/Wikikracja/commit/be2907c3dc157eb4ed6ff264ae2fce55b5989eac))

- Chat mobile view like discord/messenger, not yet perfect
  ([`086ad46`](https://github.com/soma115/Wikikracja/commit/086ad46d38451e2fc7397f9ee94e715dbd99b4b5))

- Efficient browser hot reload
  ([`d1390d7`](https://github.com/soma115/Wikikracja/commit/d1390d78eeaa9146ecfac85bea695b35e35409a1))

- Fix starting daphne
  ([`0ba826e`](https://github.com/soma115/Wikikracja/commit/0ba826e2d125ecb960c44eb61c5c035c60fa6467))

- Minor translation fix
  ([`81bffad`](https://github.com/soma115/Wikikracja/commit/81bffad6d80f46ba66b8fd362e1faac3f3b34bcf))

- More chat performance impovements
  ([`110d813`](https://github.com/soma115/Wikikracja/commit/110d8131ab943ea7a614a4bc4fd72de2ec7c9e73))

- Moved chat rooms management into scheduler, added debug toolbar, count_citizens every 10 mins
  ([`70fcc55`](https://github.com/soma115/Wikikracja/commit/70fcc55f976c49a3485be3ac73a10787c0f81051))

- New icon unSee in rooms
  ([`0e08fbe`](https://github.com/soma115/Wikikracja/commit/0e08fbe5fa234a97cb02703174e016fbba86ec33))

- Packages removed and updated, DEBUG settings adjusted
  ([`92c1496`](https://github.com/soma115/Wikikracja/commit/92c1496f5fc9310761509b60e4161440a36d8a3e))

- Push notif, PWA, logs
  ([`28da10b`](https://github.com/soma115/Wikikracja/commit/28da10b86bc40dc85f1463c849d757bcf124d244))

- Show votes count for user
  ([`fe7b4c3`](https://github.com/soma115/Wikikracja/commit/fe7b4c36233078e933fb81d79bbeb456c9a25bba))

- Standarize logging
  ([`d7a6745`](https://github.com/soma115/Wikikracja/commit/d7a6745a6309545845cedd196574d2ffcfb21dbd))

- Support hashed/versioned static files
  ([`9776760`](https://github.com/soma115/Wikikracja/commit/9776760d4abb96b675ff4f2a8c9cc6d22c4ac4df))

- Update bootstrap to 5, jquery to 4, chat ui, base
  ([`16ce09a`](https://github.com/soma115/Wikikracja/commit/16ce09a82db87eefed538275b695b77fb8f92f95))

- Warn: DB CHANGE! Implement voting system using JSONField in Message model and migrate existing
  votes
  ([`31ec94d`](https://github.com/soma115/Wikikracja/commit/31ec94d77daec26afaabb2c8fdcdaa553765fe63))

- Warn: DB CHANGE! Implement voting system using JSONField in Message model and migrate existing
  votes
  ([`2a1b018`](https://github.com/soma115/Wikikracja/commit/2a1b018e69f4e479c0e019a485f256552f795cf9))

- Yapf formatter, ruff linter and import sorter
  ([`ea9e90a`](https://github.com/soma115/Wikikracja/commit/ea9e90acfeda9b998d3f1ef859b80f65c18d5123))
