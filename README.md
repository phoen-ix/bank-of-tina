# 🏦 Bank of Tina

Eine selbst gehostete Webanwendung zur Verwaltung gemeinsamer Ausgaben und Salden in einem kleinen Büro oder einer Gruppe. Funktionen umfassen Ausgabenerfassung mit Belegen, wöchentliche E-Mail-Berichte pro Benutzer, eine Admin-Zusammenfassungs-E-Mail, Diagramme und Statistiken, automatisierte Backups und eine vollständig konfigurierbare Oberfläche mit Designs und E-Mail-Vorlagen. Komplett zweisprachig (Deutsch und Englisch). Gebaut mit Flask und MariaDB, läuft vollständig in Docker — keine externen Dienste erforderlich.

> **🇬🇧 English version below / 🇩🇪 Deutsche Version zuerst**

---

## ✨ Funktionen

### Benutzer & Salden
- Teammitglieder mit Name und E-Mail hinzufügen
- Echtzeit-Saldoverfolgung für jeden Benutzer
- Benutzer deaktivieren (auf der Übersicht ausgeblendet, in den Einstellungen verwaltbar)
- Übersicht zeigt Name und Saldo; E-Mail-Spalte optional (Einstellungen → Allgemein, standardmäßig aus)
- Benutzerdetailseite zeigt paginierte Transaktionshistorie (20 pro Seite); Klick auf den Namen eines Benutzers auf der Übersicht öffnet sie
- **E-Mail-Einstellungen pro Benutzer** — individuell ein-/ausschalten der wöchentlichen Saldo-E-Mail; Auswahl wie viel Transaktionshistorie einbezogen wird (`Letzte 3`, `Diese Woche`, `Dieser Monat` oder `Keine`)

### Transaktionen
- **Ausgabe** — erfassen wer bezahlt hat und Artikel einzelnen Personen zuordnen
- **Einzahlung** — Geld zum Saldo eines Benutzers hinzufügen
- **Auszahlung** — Geld vom Saldo eines Benutzers abziehen
- **Bearbeiten** jeder gespeicherten Transaktion: Beschreibung, Notizen, Betrag, Datum, Von/An-Benutzer, Ausgabenpositionen und Beleg
- **Notizfeld** — optionale Freitext-Notizen zu jeder Transaktion für längeren Kontext oder Begründung; inline in allen Transaktionslisten angezeigt und in der Suche enthalten
- **Löschen** jeder Transaktion (Salden werden automatisch zurückgesetzt)
- **Monatsansicht** — Transaktionen nach Tag gruppiert mit ◀ ▶ Navigation und einem Monat/Jahr-Schnellwähler; standardmäßig der aktuelle Monat
- **Suche** — Volltextsuche über Beschreibungen und Ausgabenpositionen; erweiterte Filter für Typ, Benutzer, Datumsbereich, Betragsbereich und einen „Hat Anhang/Beleg"-Schalter; paginierte Ergebnisse (25 pro Seite); nur aktive Benutzer erscheinen im Benutzerfilter

### Ausgabenpositionen
- Einzelpositionen pro Ausgabe hinzufügen (Name + Preis)
- Artikel bei gespeicherten Transaktionen bearbeiten, hinzufügen oder entfernen
- Konfigurierbare Anzahl vorausgefüllter leerer Zeilen beim Öffnen des Transaktionsformulars

### Häufige Autovervollständigung
- **Artikelnamen** — häufig verwendete Artikelnamen speichern; Autovervollständigungsvorschläge beim Hinzufügen von Artikeln
- **Beschreibungen** — häufig verwendete Transaktionsbeschreibungen speichern; Autovervollständigung erscheint in allen Beschreibungsfeldern (Ausgabe, Einzahlung, Auszahlung)
- **Preise** — häufig verwendete Preise speichern; Autovervollständigung erscheint in Artikelpreisfeldern
- **Globaler Schalter** — alle Autovervollständigung mit einem einzelnen Schalter ein- oder ausschalten
- **Blacklist** — Pro-Typ-Blacklists verhindern, dass bestimmte Werte jemals automatisch gesammelt werden
- **Auto-Sammlung** — optionaler geplanter Job, der die Transaktionshistorie durchsucht und Werte befördert, die einen konfigurierbaren Schwellenwert erreichen oder überschreiten; separate Ein/Aus-Schalter und Schwellenwerte für Artikelnamen, Beschreibungen und Preise
- **Debug-Log** — wenn der Debug-Modus an ist, wird jede Auto-Sammlungs-Entscheidung (hinzugefügt/übersprungen/Zusammenfassung) in die Datenbank geschrieben und in der Einstellungsoberfläche angezeigt; Log ist auf 500 Einträge begrenzt

### Belege
- JPG-, PNG- oder PDF-Belege beim Erfassen einer Transaktion hochladen
- Beleg bei bestehenden Transaktionen hochladen, ersetzen oder entfernen — die alte Datei wird automatisch von der Festplatte gelöscht
- Dateien werden in einer organisierten Verzeichnisstruktur gespeichert:
  `uploads/JJJJ/MM/TT/KäuferName_dateiname.ext`
- Dateinamen werden vor dem Speichern bereinigt (Sonderzeichen entfernt)

### Backup & Wiederherstellung
- **Backup erstellen** auf Abruf oder nach einem wiederkehrenden Zeitplan (gleicher Tag/Uhrzeit-Wähler wie bei E-Mail und Auto-Sammlung)
- Jedes Backup ist eine einzelne `bot_backup_JJJJ_MM_TT_HH-mm-ss.tar.gz` mit:
  - `dump.sql` — vollständiger MariaDB-Dump mit `DROP TABLE IF EXISTS` (auf Festplatte gestreamt, kein Speicherlimit)
  - `receipts/` — vollständige Kopie aller hochgeladenen Belegbilder
  - `.env` — Zugangsdaten aus den Umgebungsvariablen des Containers rekonstruiert
- **Herunterladen** jedes Backups direkt aus dem Browser
- **Wiederherstellen** aus jedem aufgelisteten Backup mit einem Klick — Belege werden zuerst wiederhergestellt, damit die Datenbank nie berührt wird, wenn das Dateikopieren fehlschlägt
- **Hochladen** eines Backups von einer anderen Instanz — große Dateien werden in 5-MB-Blöcken mit Fortschrittsbalken gesendet, es gibt kein effektives Größenlimit
- **Auto-Bereinigung** — konfigurieren, wie viele Backups behalten werden; ältere werden automatisch nach jedem geplanten Lauf gelöscht
- **Backup-Status-E-Mail** — wenn ein Seiten-Admin konfiguriert ist, wird nach jedem *geplanten* Backup eine optionale E-Mail mit dem Ergebnis (Erfolg oder Fehler), Dateinamen, behaltenen Backups und Anzahl der bereinigten gesendet; manuelle Backups lösen diese E-Mail nie aus
- **Debug-Log** — wenn der Debug-Modus an ist, wird jeder Backup-Schritt in die Datenbank geschrieben und in der Einstellungsoberfläche angezeigt

### 🌐 Mehrsprachigkeit (i18n)
- **Zwei Sprachen** — Deutsch und Englisch, umschaltbar über Einstellungen → Allgemein → Sprache
- **Globale Einstellung** — die Sprache gilt app-weit (gespeichert in der Datenbank wie alle anderen Einstellungen)
- **Vollständige Abdeckung** — alle UI-Elemente, Flash-Nachrichten, E-Mail-Vorlagen, Diagrammbeschriftungen und Transaktionstyp-Badges werden übersetzt
- **Flask-Babel** — Standard-gettext `.po`/`.mo`-Dateien; ~427 übersetzte Zeichenketten
- **Lokalisierte Datumsanzeige** — Monatsnamen und Tagesheader werden in der gewählten Sprache angezeigt
- **Standardsprache** — Deutsch (`de`); kann jederzeit auf Englisch (`en`) umgestellt werden

### PWA — Zum Startbildschirm hinzufügen
- **Web App Manifest** — dynamisch unter `/manifest.json` bereitgestellt; `theme_color` folgt der konfigurierten Navigationsfarbe
- **Service Worker** — Network-First-Strategie; holt immer aktuelle Daten; zeigt eine eigenständige Offline-Seite wenn das Netzwerk nicht erreichbar ist oder der Server einen HTTP-Fehler zurückgibt (z.B. 503); bereitgestellt über `/sw.js` via Flask-Route für volle App-Scope-Kontrolle
- **Icons** — 32×32, 192×192 und 512×512 PNG-Icons; auf dem Host via Bind-Mount (`./icons/`) persistiert, überleben Container-Rebuilds; beim ersten Start automatisch mit der Standard-Designfarbe generiert; `/favicon.ico`-Route liefert das 32px-Icon; verwaltbar über Einstellungen → Vorlagen → App-Icon:
  - **Aus Navigationsfarbe generieren** — Ein-Klick-Neugenerierung mit der aktuellen Designfarbe als Hintergrund (weiße Bank-Silhouette)
  - **Benutzerdefiniertes Icon hochladen** — beliebiges PNG oder JPG hochladen; automatisch auf 32×32, 192×192 und 512×512 skaliert
  - **Auf Standard zurücksetzen** — stellt das originale Bootstrap-Blue-Icon wieder her
  - Cache-Busting stellt sicher, dass Browser und PWA neue Icons sofort übernehmen
- **Android Chrome**: Drei-Punkt-Menü → „Zum Startbildschirm hinzufügen" (oder automatisches Installationsbanner)
- **iOS Safari**: Teilen-Menü → „Zum Home-Bildschirm" → korrektes Icon, Name und Standalone-Start
- Kein App Store erforderlich; keine nativen Build-Tools erforderlich

### Oberfläche
- **Toast-Benachrichtigungen** — Erfolgs-/Fehlermeldungen erscheinen als Bootstrap-5-Toasts in der oberen rechten Ecke, verschwinden automatisch nach 4 Sekunden und stapeln sich bei mehreren gleichzeitigen Nachrichten; enthält einen globalen `showToast(message, type)` JS-Helper für programmatische Nutzung
- **Skeleton-Loading** — die Diagrammseite zeigt pulsierende Skeleton-Platzhalter (horizontale Balken für Salden/Top-Artikel, vollbreite Rechtecke für Verlauf/Volumen) während die Daten geladen werden

### Vorlagen & Design
- **Farbpalette** — Navigationsfarbe, E-Mail-Header-Farbverlauf (Anfang + Ende), positive und negative Saldofarben; jede mit Farbwähler und Hex-Textfeld
- **Vordefinierte Designs** — Auswahl aus Standard, Ozean, Wald, Sonnenuntergang oder Schiefer über ein Dropdown; ein Preset auswählen füllt sofort alle Wähler; manuelles Ändern eines Wählers wechselt zu „Benutzerdefiniert"
- **E-Mail-Betreffs** — bearbeitbare Betreffzeile für jeden der drei E-Mail-Typen
- **E-Mail-Textvorlagen** — Begrüßung, Einleitung, Fußzeile 1 und Fußzeile 2 der wöchentlichen Saldo-E-Mail bearbeiten; Einleitung und Fußzeile der Admin-Zusammenfassungs-E-Mail; Fußzeile der Backup-Status-E-Mail; ein Feld leer lassen um die Zeile auszulassen
- **E-Mail-Adressen-Schalter** — Admin-Zusammenfassungs-E-Mail-Karte hat einen „E-Mail-Adressen in Zusammenfassungstabelle anzeigen"-Schalter (Standard aus); wenn aus, werden nur Namen und Salden angezeigt
- **Platzhalter** — werden beim Senden ersetzt:

  | Platzhalter | Verfügbar in |
  |-------------|-------------|
  | `[Name]` | Wöchentliche E-Mail Betreff & Text |
  | `[Balance]` | Wöchentliche E-Mail Text |
  | `[BalanceStatus]` | Wöchentliche E-Mail Text |
  | `[Date]` | Alle drei E-Mail-Betreffs & -Texte |
  | `[UserCount]` | Admin-Zusammenfassung Betreff & Text |
  | `[BackupStatus]` | Backup-Status-E-Mail Betreff |

- **Live-Vorschau** — jede E-Mail-Vorlagenkarte hat einen **Vorschau**-Button der das gerenderte HTML in einem neuen Tab öffnet, mit echten Daten (oder Beispieldaten wenn keine Benutzer existieren)
- Alle Design- und Vorlageneinstellungen werden in der Datenbank gespeichert und sofort ohne Neustart angewendet

### Einstellungen (Web-UI — kein `.env`-Bearbeiten nötig)
Die Einstellungsseite ist in sechs Tabs aufgeteilt:

| Tab | Was konfiguriert wird |
|-----|----------------------|
| **Allgemein** | Standard-Artikelzeilen im Transaktionsformular; Anzahl letzter Transaktionen auf der Übersicht (0 blendet den Bereich aus); Zeitzone; **Sprache** (Deutsch/Englisch); **Dezimaltrennzeichen** (Punkt `1.99` oder Komma `1,99`); **Währungssymbol** (€, $, £, ¥ und mehr); E-Mail-Spalte auf der Übersicht ein-/ausblenden; Seiten-Admin |
| **E-Mail** | SMTP-Zugangsdaten; E-Mail-Versand aktivieren/deaktivieren; Debug-Modus; Admin-Zusammenfassungs-E-Mail-Schalter; Saldo-E-Mails auf Abruf senden; wiederkehrenden Zeitplan einrichten |
| **Häufige** | Globaler Autovervollständigungsschalter; Artikelnamen, Beschreibungen und Preise manuell verwalten (jeweils mit eigener Blacklist); Auto-Sammlungs-Job konfigurieren und Debug-Log anzeigen |
| **Backup** | Backups erstellen/herunterladen/löschen; aus jedem Backup oder einer hochgeladenen Datei wiederherstellen; automatischen Backup-Zeitplan mit Auto-Bereinigung konfigurieren; Backup-Status-E-Mail an Seiten-Admin; Debug-Log |
| **Vorlagen** | Farbpalette + vordefinierte Designs; bearbeitbare Betreffs und Texte für alle drei E-Mail-Typen; Vorschau-Buttons; **App-Icon**-Karte — Icons aus Navigationsfarbe generieren, benutzerdefiniertes Icon hochladen oder auf Standard zurücksetzen |
| **Benutzer** | Neue Benutzer hinzufügen (inkl. E-Mail-Opt-in und Transaktionsumfang); aktive und deaktivierte Benutzer in getrennten Listen (deaktivierte Liste ist ausgeblendet wenn leer); Benutzer deaktivieren oder reaktivieren |

### E-Mail-Benachrichtigungen
- SMTP-Zugangsdaten werden sicher in der Datenbank gespeichert (konfiguriert über Einstellungen → E-Mail)
- **Jetzt senden**-Button um sofort allen aktiven Benutzern ihren aktuellen Saldo per E-Mail zu senden
- **Automatischer Zeitplan** — Tag und Uhrzeit (24-Stunden-Format) wählen; der Zeitplan überlebt Container-Neustarts
- **Opt-in pro Benutzer** — Benutzer können die wöchentliche E-Mail abbestellen; abgemeldete Benutzer werden bei jedem Versand übersprungen (manuell und geplant)
- **Transaktionsumfang pro Benutzer** — jede Benutzer-E-Mail enthält die gewählte Option: letzte 3 Transaktionen, alle Transaktionen dieser Woche, dieses Monats oder keine Transaktionshistorie
- **Admin-Zusammenfassungs-E-Mail** — wenn ein Seiten-Admin konfiguriert ist (Einstellungen → Allgemein), wird eine optionale zusätzliche E-Mail mit einer farbcodierten Saldenübersicht *aller* aktiven Benutzer gesendet (unabhängig vom individuellen Opt-in-Status)

---

## 🚀 Schnellstart

### Voraussetzungen
- Docker und Docker Compose (Plugin `docker compose` oder eigenständiges `docker-compose`)

### 1. Repository klonen
```bash
git clone https://github.com/phoen-ix/bank-of-tina.git
cd bank-of-tina
```

### 2. Umgebungsdatei erstellen
```bash
cp .env.example .env
```
`.env` öffnen und einen starken `SECRET_KEY` sowie die gewünschten Datenbank-Zugangsdaten setzen:
```bash
# Secret Key generieren mit:
python3 -c "import secrets; print(secrets.token_hex(32))"
```
Die `DB_*`-Standardwerte (`tina`/`tina`) sind für eine private Bereitstellung in Ordnung — für alles was ins Internet zeigt, ändern.

### 3. Anwendung starten
```bash
docker compose up -d
```

### 4. Weboberfläche öffnen
```
http://dein-server-ip:5000
```

Das war's. SMTP-Zugangsdaten und der E-Mail-Zeitplan werden über die **Einstellungen**-Seite in der App konfiguriert — kein Neustart erforderlich.

---

## 📱 Bedienungsanleitung

### Benutzer hinzufügen
1. **Einstellungen** → **Benutzer**-Tab → Name und E-Mail eingeben
2. **Wöchentlicher E-Mail-Bericht** (ein/aus) und **In E-Mail einschließen** (Transaktionsumfang) einstellen
3. **Hinzufügen**

### Ausgabe erfassen
1. **Transaktion hinzufügen** → **Ausgabe**-Tab
2. Auswählen wer bezahlt hat
3. Beschreibung eingeben (optional: Beleg hochladen)
4. Artikelzeilen ausfüllen (vorausgefüllt basierend auf der Allgemein-Einstellung)
5. **Ausgabe erfassen**

### Transaktionen nach Monat durchblättern
1. **Alle Transaktionen** in der Navigation → zeigt standardmäßig den aktuellen Monat
2. Mit ◀ / ▶ einen Monat vor/zurück navigieren (▶ ist im aktuellen Monat deaktiviert)
3. Die **Monat**- und **Jahr**-Dropdowns verwenden um direkt zu einer vergangenen Periode zu springen

### Transaktionen suchen
1. Die Suchleiste in der Navigation (auf jeder Seite) für eine schnelle Stichwortsuche verwenden
2. Oder direkt zu `/search` navigieren für mehr Kontrolle
3. **Erweiterte Filter** klicken um nach Typ, Benutzer, Datumsbereich, Betragsbereich und/oder dem **Hat Anhang/Beleg**-Schalter zu filtern — Filter können kombiniert werden
4. Ergebnisse erstrecken sich über alle Monate und zeigen das vollständige Datum (`JJJJ-MM-TT HH:MM`)

### Transaktion bearbeiten
1. **Alle Transaktionen** (oder Benutzerdetailseite) → Stift-Symbol
2. Beliebiges Feld anpassen — Beschreibung, Betrag, Datum, Von/An-Benutzer
3. Ausgabenpositionen hinzufügen, bearbeiten oder entfernen (die Summe aktualisiert das Betragsfeld automatisch)
4. Neuen Beleg hochladen, bestehenden ersetzen oder **Beleg entfernen** ankreuzen zum Löschen
5. **Änderungen speichern** — Salden werden automatisch neu berechnet

### Transaktion löschen
- Papierkorb-Symbol auf jeder Transaktionszeile — Salden werden automatisch zurückgesetzt

### E-Mail einrichten
1. **Einstellungen** → **E-Mail**-Tab
2. SMTP-Zugangsdaten eingeben und **Einstellungen speichern** klicken
3. **E-Mails jetzt senden** zum Testen verwenden, oder unter **Automatischer Zeitplan** einen wiederkehrenden Zeitplan einrichten
4. Optional **Admin-Zusammenfassungs-E-Mail senden** aktivieren — erfordert dass zuerst ein Seiten-Admin im Allgemein-Tab eingestellt wird

### E-Mail-Vorlagen anpassen
1. **Einstellungen** → **Vorlagen**-Tab
2. Ein Farb-Preset wählen oder einzelne Farbwähler anpassen
3. Betreff und Text für jeden E-Mail-Typ bearbeiten; Platzhalter wie `[Name]`, `[Balance]`, `[Date]` verwenden
4. **Vorschau** klicken um die gerenderte E-Mail in einem neuen Tab vor dem Speichern zu öffnen
5. **Vorlagen speichern** — Änderungen werden beim nächsten Versand wirksam

### Backup erstellen
1. **Einstellungen** → **Backup**-Tab → **Jetzt Backup erstellen**
2. Das Backup erscheint sofort in der Liste — **Herunterladen** klicken um es lokal zu speichern
3. Für automatische Backups **Automatischer Backup-Zeitplan** aktivieren, Tag/Uhrzeit und Anzahl der aufzubewahrenden Backups wählen, dann **Zeitplan speichern**

### Backup wiederherstellen
- **Aus der Liste**: **Wiederherstellen** neben einem bestehenden Backup klicken und bestätigen
- **Aus einer Datei**: den **Backup hochladen**-Bereich verwenden — eine `bot_backup_*.tar.gz`-Datei auswählen und **Hochladen** klicken; die Datei wird in Blöcken hochgeladen (kein Größenlimit) und erscheint nach Fertigstellung in der Liste, bereit zur Wiederherstellung

### Benutzer verwalten
1. **Einstellungen** → **Benutzer**-Tab
2. Aktive Benutzer werden in einer **Aktive Benutzer**-Liste angezeigt; deaktivierte Benutzer erscheinen in einer separaten **Deaktivierte Benutzer**-Liste (ausgeblendet wenn keine deaktivierten Benutzer existieren)
3. **Deaktivieren** klicken um einen Benutzer in die deaktivierte Liste zu verschieben, oder **Reaktivieren** um ihn in die aktive Liste zurückzuholen
4. Auf den Namen eines Benutzers klicken um seine Detailseite zu öffnen, dann **Benutzer bearbeiten** um Name, E-Mail, Mitglied-seit-Datum oder E-Mail-Einstellungen zu ändern

### Sprache wechseln
1. **Einstellungen** → **Allgemein**-Tab → **Sprache**-Dropdown
2. **Deutsch** oder **English** wählen
3. **Speichern** — die gesamte Oberfläche wechselt sofort zur gewählten Sprache

---

## 🗂️ Dateistruktur

```
bank-of-tina/
├── app/
│   ├── app.py                    # Einstiegspunkt: Flask-App erstellen, Extensions initialisieren, Scheduler starten
│   ├── extensions.py             # Gemeinsame Instanzen: db, csrf, migrate, limiter, scheduler, babel
│   ├── config.py                 # Konstanten: THEMES, TEMPLATE_DEFAULTS, TEMPLATE_DEFAULTS_DE, ALLOWED_EXTENSIONS, BACKUP_DIR
│   ├── models.py                 # Alle 11 SQLAlchemy-Modelle (vollständig typ-annotiert)
│   ├── helpers.py                # Hilfsfunktionen: parse_amount, fmt_amount, save_receipt, etc.
│   ├── email_service.py          # E-Mail-Erstellung und -Versand (Saldo, Admin-Zusammenfassung, Backup-Status)
│   ├── backup_service.py         # Backup-Erstellung, Wiederherstellung, Bereinigung, Status-E-Mail
│   ├── scheduler_jobs.py         # APScheduler-Job-Einrichtung und -Wiederherstellung
│   ├── translations/             # Gettext-Übersetzungsdateien (Babel)
│   │   ├── de/LC_MESSAGES/       # Deutsche Übersetzungen (.po + .mo)
│   │   └── en/LC_MESSAGES/       # Englische Übersetzungen (.po + .mo)
│   ├── migrations/               # Alembic-Migrationen (Flask-Migrate)
│   ├── routes/
│   │   ├── __init__.py           # register_blueprints(app)
│   │   ├── main.py               # main_bp: Health, Übersicht, Benutzer, Transaktionen, Suche, Belege, PWA
│   │   ├── settings.py           # settings_bp: alle Einstellungen, häufige Artikel, Backup, Vorlagen, Icons
│   │   └── analytics.py          # analytics_bp: Diagrammseite + Datenendpunkt
│   ├── templates/                # Jinja2-Vorlagen (alle mit {{ _('...') }} internationalisiert)
│   └── static/
│       ├── sw.js                 # Service Worker (Network-First, Offline-Fallback)
│       ├── offline.html          # Eigenständige Offline-Fallback-Seite
│       └── vendor/               # Selbst gehostete Frontend-Abhängigkeiten (kein CDN)
├── tests/
│   ├── conftest.py               # pytest-Fixtures (SQLite in-memory, kein CSRF, make_user-Factory)
│   ├── test_helpers.py           # Tests für parse_amount, fmt_amount, hex_to_rgb, apply_template
│   ├── test_models.py            # Tests für User, Transaction, ExpenseItem, Setting, CommonItem
│   ├── test_routes.py            # Tests für Übersicht, Transaktionen, Suche, Bearbeitung, API
│   ├── test_settings.py          # Tests für Einstellungen-CRUD, häufige Artikel, Vorlagen, Zeitplan
│   ├── test_analytics.py         # Tests für Diagrammseite und Datenendpunkt
│   ├── test_health.py            # Tests für /health-Endpunkt
│   ├── test_email_service.py     # Tests für E-Mail-Erstellung und -Versand
│   └── test_i18n.py              # Tests für Internationalisierung (Sprachumschaltung, Übersetzungen)
├── babel.cfg                     # Babel-Extraktionskonfiguration
├── messages.pot                  # Extrahierte Übersetzungsvorlagen
├── uploads/                      # Belege — als JJJJ/MM/TT/ organisiert (Bind-Mount)
├── backups/                      # Backup-Archive (Bind-Mount)
├── icons/                        # PWA-Icons (Bind-Mount; beim ersten Start automatisch generiert)
├── mariadb-data/                 # MariaDB-Datenverzeichnis (Bind-Mount)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## 🔒 Sicherheitshinweise

- **Content Security Policy** — jede HTML-Antwort enthält einen Nonce-basierten CSP-Header (`script-src 'self' 'nonce-…'`; `style-src 'self' 'unsafe-inline'`; `frame-ancestors 'none'`; `object-src 'none'`). Alle Inline-Event-Handler wurden zu `addEventListener` / Event-Delegation konvertiert, sodass kein `'unsafe-inline'` für Skripte benötigt wird.
- **HTML-Injection-Prävention** — alle benutzergesteuerten Werte (Namen, E-Mails, Beschreibungen, Fehlermeldungen) werden mit `html.escape()` escapt bevor sie in HTML-E-Mail-Vorlagen eingefügt werden
- **XSS-sichere Toast-Benachrichtigungen** — der `showToast()` JS-Helper baut DOM-Knoten programmatisch mit `textContent`, niemals `innerHTML`
- **Sichere Tar-Extraktion** — Backup-Wiederherstellung lehnt Symlinks, Hardlinks, absolute Pfade, `..`-Traversierung und alle Mitglieder ab, deren aufgelöster Pfad das Extraktionsverzeichnis verlässt
- **Sichere Suchabfragen** — SQL-Wildcards (`%`, `_`) in Benutzereingaben werden escapt bevor ILIKE-Muster erstellt werden
- **SMTP-Timeout** — ausgehende E-Mail-Verbindungen verwenden ein 30-Sekunden-Timeout um endloses Hängen zu verhindern
- Einen starken, zufälligen `SECRET_KEY` in der `.env`-Datei setzen
- Niemals die `.env`-Datei committen (sie ist in `.gitignore`)
- Der Docker-Container startet als Root nur um Bind-Mount-Verzeichnisberechtigungen zu korrigieren, wechselt dann sofort zu einem Nicht-Root-Benutzer (`appuser`, UID 1000) via `gosu`
- Pro-Route-Rate-Limiting ist auf schreibintensiven Endpunkten aktiviert
- Für Gmail ein **App-Passwort** verwenden statt des Hauptkonto-Passworts
- Netzwerkzugriff auf Port 5000 einschränken — hinter einem Reverse-Proxy (nginx, Caddy) mit Authentifizierung platzieren wenn die App ins Internet zeigt

---

## 🔧 Wartung

### Health-Check
```bash
curl http://localhost:5000/health
# Gibt strukturiertes JSON mit einzelnen Prüfergebnissen zurück:
# {"status": "ok", "checks": {"database": "ok", "scheduler": "ok", "icons_writable": "ok"}}
# Gibt 503 mit "status": "error" zurück wenn die Datenbank nicht erreichbar ist
```

Das Dockerfile enthält eine `HEALTHCHECK`-Anweisung und der docker-compose Web-Service verwendet `/health` für seinen Healthcheck.

### Logs anzeigen
```bash
docker compose logs -f web    # Strukturierte Log-Ausgabe (Zeitstempel, Level, Modul, Nachricht)
docker compose logs -f db
```

`LOG_LEVEL`-Umgebungsvariable setzen um die Ausführlichkeit zu steuern (`DEBUG`, `INFO`, `WARNING`, `ERROR`). Standard ist `INFO`.

### Backup & Wiederherstellung
Den eingebauten **Einstellungen → Backup**-Tab für das Erstellen, Herunterladen, Hochladen und Wiederherstellen von Backups verwenden.

Für einen manuellen reinen Datenbank-Dump:
```bash
docker compose exec db mysqldump -u "$DB_USER" -p"$DB_PASSWORD" bank_of_tina > backup_$(date +%Y%m%d).sql
```

### Nach Code-Änderungen aktualisieren
```bash
docker compose build && docker compose up -d
```

### Alles zurücksetzen ⚠️ (löscht alle Daten)
```bash
docker compose down
rm -rf mariadb-data/ uploads/*/ icons/
docker compose up -d
```

---

## 🐛 Fehlerbehebung

| Problem | Schritte |
|---------|----------|
| E-Mails werden nicht gesendet | Einstellungen → E-Mail prüfen; SMTP-Zugangsdaten verifizieren; Logs prüfen |
| Beleg-Upload schlägt fehl | `chmod 755 uploads/` prüfen; verifizieren dass die Datei JPG/PNG/PDF ist |
| Port 5000 belegt | Host-Port in `docker-compose.yml` ändern (`"8080:5000"`) |
| Web-Container startet nicht | `docker compose logs web` — die App wiederholt DB-Verbindungen bis zu 5 Mal mit exponentiellem Backoff beim Start; db-Logs prüfen wenn alle Versuche fehlschlagen |
| DB-Verbindung abgelehnt | Sicherstellen dass `mariadb-data/` beschreibbar ist; `docker compose restart db` |

---

### Diagramme & Statistiken
Eine eigene **Diagramme**-Seite (Navigationsleiste → Diagramme) mit einer gemeinsamen Filterleiste und vier Tabs:

| Tab | Diagrammtyp | Was angezeigt wird |
|-----|-------------|-------------------|
| **Salden** | Horizontaler Balken | Aktueller Saldo pro Benutzer; grün/rot je nach Vorzeichen; sortiert von höchstem zu niedrigstem |
| **Verlauf** | Mehrlinien | Laufender Saldo jedes Benutzers über die Zeit, aus dem Transaktionslog rekonstruiert; wöchentliche oder monatliche Datenpunkte je nach ausgewähltem Bereich |
| **Volumen** | Balken + Linie | Transaktionsanzahl (Balken, linke Achse) und Gesamtbetrag (Linie, rechte Achse) gruppiert nach Woche oder Monat |
| **Top-Artikel** | Horizontaler Balken | Top 15 Ausgabenpositionen nach Gesamtbetrag oder Anzahl; zwischen beiden Modi umschalten |

**Filterleiste** — Datumsbereich-Wähler, Schnellvorlagen (30 T / 90 T / 1 J / Alle Zeit), Mehrfachauswahl-Benutzer-Dropdown, Anwenden-Button.

**Drucken / PDF** — druckt nur den aktuell aktiven Tab, formatiert für A4 Querformat; Diagramm-Canvas wird vor der Browser-Erfassung auf Seitengröße skaliert. Browser-Druckdialog öffnen → Als PDF speichern.

---

## 🧪 Tests ausführen

Tests verwenden eine SQLite-In-Memory-Datenbank und benötigen keine laufenden Dienste:

```bash
FLASK_TESTING=1 python -m pytest tests/ -v
```

Die Testsuite umfasst 85 Tests in 8 Testmodulen: Hilfsfunktionen, Modelle, Routen, Einstellungen, Diagramme, Health-Check, E-Mail-Service und Internationalisierung. Alle Tests bestehen ohne Warnungen.

---

## 💡 Zukunftsideen

- [ ] CSV-/Excel-Export von Transaktionen
- [ ] Benutzerauthentifizierung und Login-System
- [ ] Wechselkurs-bewusste Mehrwährungsunterstützung (Währungssymbol ist bereits konfigurierbar)
- [ ] OCR für automatische Belegerfassung
- [ ] Gespeicherte/angeheftete Suchen

---

Entwickelt mit ❤️ um Büro-Mittagessen einfacher zu machen! 🥗

---
---

# 🇬🇧 English

A self-hosted web application for tracking shared expenses and balances within a small office or group. Features include expense recording with receipts, per-user weekly email reports, an admin summary email, charts and statistics, automated backups, and a fully configurable UI with themes and email templates. Fully bilingual (German and English). Built with Flask and MariaDB, runs entirely in Docker — no external services required.

---

## ✨ Features

### Users & Balances
- Add team members with name and email
- Real-time balance tracking for every user
- Deactivate users (hidden from dashboard, manageable from Settings)
- Dashboard shows Name and Balance; email column optional (Settings → General, default off)
- User detail page shows paginated transaction history (20 per page); click a user's name on the dashboard to open it
- **Per-user email preferences** — opt in/out of the weekly balance email individually; choose how much transaction history to include (`Last 3`, `This week`, `This month`, or `None`)

### Transactions
- **Expense** — record who paid and assign items to individuals
- **Deposit** — add money to a user's balance
- **Withdrawal** — deduct money from a user's balance
- **Edit** any saved transaction: description, notes, amount, date, from/to user, expense items, and receipt
- **Notes field** — optional free-text notes on any transaction for longer context or justification; shown inline on all transaction lists and included in search
- **Delete** any transaction (balances are automatically reversed)
- **Month-by-month view** — transactions grouped by day with ◀ ▶ navigation and a month/year jump picker; defaults to the current month
- **Search** — free-text search across descriptions and expense items; advanced filters for type, user, date range, amount range, and a "Has attachment / receipt" toggle; paginated results (25 per page); only active users appear in the user filter

### Expense Items
- Add line items per expense (name + price)
- Edit, add, or remove items on saved transactions
- Configurable number of pre-filled blank rows when opening the Add Transaction form

### Common Autocomplete
- **Item names** — save frequently used expense item names; get autocomplete suggestions when adding items
- **Descriptions** — save frequently used transaction descriptions; autocomplete appears on all description fields (expense, deposit, withdrawal)
- **Prices** — save frequently used prices; autocomplete appears on expense item price fields
- **Global toggle** — enable or disable all autocomplete with a single switch
- **Blacklist** — per-type blacklists prevent specific values from ever being auto-collected
- **Auto-collect** — optional scheduled job that scans the transaction history and promotes values that appear at or above a configurable threshold; separate on/off switches and thresholds for item names, descriptions, and prices
- **Debug log** — when debug mode is on, every auto-collect decision (added / skipped / summary) is written to the database and shown in the Settings UI; log is capped at 500 entries

### Receipts
- Upload JPG, PNG, or PDF receipts when recording a transaction
- Upload, replace, or remove a receipt on any existing transaction — the old file is deleted from disk automatically
- Files are saved in an organised directory tree:
  `uploads/YYYY/MM/DD/BuyerName_filename.ext`
- Filenames are sanitised (special characters removed) before saving

### Backup & Restore
- **Create backup** on demand or on a recurring schedule (same day/time picker as email and auto-collect)
- Each backup is a single `bot_backup_YYYY_MM_DD_HH-mm-ss.tar.gz` containing:
  - `dump.sql` — full MariaDB dump with `DROP TABLE IF EXISTS` (streamed to disk, no memory limit)
  - `receipts/` — complete copy of all uploaded receipt images
  - `.env` — credentials reconstructed from the container's environment variables
- **Download** any backup directly from the browser
- **Restore** from any listed backup with one click — receipts are restored first so the database is never touched if the file copy fails
- **Upload** a backup from another instance — large files are sent in 5 MB chunks with a progress bar, so there is no effective size limit
- **Auto-prune** — configure how many backups to keep; older ones are deleted automatically after each scheduled run
- **Backup status email** — when a site admin is configured, an optional email is sent after each *scheduled* backup with the result (success or failure), filename, backups kept, and number pruned; manual backups never trigger this email
- **Debug log** — when debug mode is on, every backup step is written to the database and shown in the Settings UI

### 🌐 Internationalization (i18n)
- **Two languages** — German and English, switchable via Settings → General → Language
- **Global setting** — language applies app-wide (stored in the database like all other settings)
- **Full coverage** — all UI elements, flash messages, email templates, chart labels, and transaction type badges are translated
- **Flask-Babel** — standard gettext `.po`/`.mo` files; ~427 translated strings
- **Localized date display** — month names and day headers are shown in the selected language
- **Default language** — German (`de`); can be switched to English (`en`) at any time

### PWA — Install to Home Screen
- **Web App Manifest** — served dynamically at `/manifest.json`; `theme_color` tracks the configured navbar color
- **Service worker** — network-first strategy; always fetches fresh data; shows a self-contained offline page when the network is down or the server returns an HTTP error (e.g. 503); served from `/sw.js` via a Flask route so it can control the entire app scope
- **Icons** — 32×32, 192×192, and 512×512 PNG icons; persisted on the host via bind mount (`./icons/`) so they survive container rebuilds; auto-generated with the default theme color on first run; `/favicon.ico` route serves the 32px icon; manageable from Settings → Templates → App Icon:
  - **Regenerate from navbar color** — one-click regeneration using the current theme color as background (white bank silhouette)
  - **Upload custom icon** — upload any PNG or JPG; automatically resized to 32×32, 192×192, and 512×512
  - **Reset to default** — restores the original Bootstrap blue icon
  - Cache-busting ensures browsers and PWA pick up new icons immediately
- **Android Chrome**: three-dot menu → "Add to home screen" (or automatic install banner)
- **iOS Safari**: Share sheet → "Add to Home Screen" → correct icon, name, and standalone launch
- No App Store required; no native build tools required

### UI
- **Toast notifications** — success/error messages appear as Bootstrap 5 toasts in the top-right corner, auto-hide after 4 seconds, and stack when multiple messages fire simultaneously; includes a global `showToast(message, type)` JS helper for programmatic use
- **Skeleton loading** — the Charts page shows pulsing skeleton placeholders (horizontal bars for Balances/Top Items, full-width rectangles for History/Volume) while data loads, replacing the previous spinner

### Templates & Theming
- **Color palette** — navbar color, email header gradient (start + end), positive and negative balance colors; each has a color picker paired with a hex text field
- **Preset themes** — choose from Default, Ocean, Forest, Sunset, or Slate via a dropdown; selecting a preset fills all pickers instantly; manually changing any picker switches to "Custom"
- **Email subjects** — editable subject line for each of the three email types
- **Email body templates** — edit the greeting, intro, footer line 1, and footer line 2 of the weekly balance email; set the intro and footer of the admin summary email; set the footer of the backup status email; leave any field blank to omit that line
- **Include email addresses toggle** — admin summary email card has an "Include email addresses in summary table" switch (default off); when off, only names and balances are shown
- **Placeholders** — substituted at send time:

  | Placeholder | Available in |
  |-------------|--------------|
  | `[Name]` | Weekly email subject & body |
  | `[Balance]` | Weekly email body |
  | `[BalanceStatus]` | Weekly email body |
  | `[Date]` | All three email subjects & bodies |
  | `[UserCount]` | Admin summary subject & body |
  | `[BackupStatus]` | Backup status email subject |

- **Live preview** — each email template card has a **Preview** button that opens the rendered HTML in a new tab using real data (or sample data when no users exist)
- All theme and template settings are stored in the database and applied immediately with no restart

### Settings (web UI — no `.env` editing needed)
The Settings page is split into six tabs:

| Tab | What you configure |
|-----|--------------------|
| **General** | Default number of blank item rows in the Add Transaction form; number of recent transactions shown on the dashboard (0 hides the section); timezone; **language** (German/English); **decimal separator** (period `1.99` or comma `1,99`) applied to all monetary display and input throughout the app; **currency symbol** (€, $, £, ¥, and more) shown before all monetary amounts throughout the UI, charts, and emails; toggle to show/hide the email column on the dashboard; site admin (used for admin summary emails) |
| **Email** | SMTP credentials; enable/disable email sending; debug mode (logs runs to DB, surfaces SMTP errors in the UI); admin summary email toggle; send balance emails on demand; set a recurring auto-schedule |
| **Common** | Global autocomplete toggle; manually manage item names, descriptions, and prices (each with its own blacklist); configure the auto-collect scheduled job and view its debug log |
| **Backup** | Create/download/delete backups; restore from any backup or an uploaded file; configure an automatic backup schedule with auto-prune; backup status email to site admin (scheduled runs only); debug log |
| **Templates** | Color palette + preset themes; editable subjects and body text for all three email types (balance, admin summary, backup status); preview buttons for each email; **App Icon** card — regenerate icons from navbar color, upload a custom icon, or reset to default |
| **Users** | Add new users (including email opt-in and transaction scope preferences); active users and deactivated users are shown in separate lists (the deactivated list is hidden when empty); deactivate or reactivate any user |

### Email Notifications
- SMTP credentials are stored securely in the database (configured via Settings → Email)
- **Send Now** button to immediately email all active users their current balance
- **Auto-schedule** — pick a day and time (24 h clock); the schedule survives container restarts
- **Per-user opt-in** — users can be set to opt out of the weekly email; opted-out users are skipped on every send (manual and scheduled)
- **Per-user transaction scope** — each user's email includes their choice of: last 3 transactions, all transactions this week, all transactions this month, or no transaction history at all
- **Admin summary email** — when a site admin is configured (Settings → General), an optional extra email is sent to them after each run with a colour-coded balance overview of *all* active users (regardless of individual opt-in status)

---

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose (plugin `docker compose` or standalone `docker-compose`)

### 1. Clone the repository
```bash
git clone https://github.com/phoen-ix/bank-of-tina.git
cd bank-of-tina
```

### 2. Create your environment file
```bash
cp .env.example .env
```
Open `.env` and set a strong `SECRET_KEY` and your desired database credentials:
```bash
# Generate a secret key with:
python3 -c "import secrets; print(secrets.token_hex(32))"
```
The `DB_*` defaults (`tina`/`tina`) are fine for a private deployment — change them for anything internet-facing.

### 3. Start the application
```bash
docker compose up -d
```

### 4. Open the web interface
```
http://your-server-ip:5000
```

That's it. SMTP credentials and the email schedule are configured from the **Settings** page inside the app — no restart required.

---

## 📱 Usage Guide

### Adding Users
1. **Settings** → **Users** tab → fill in name and email
2. Set **Weekly email report** (toggle on/off) and **Include in email** (transaction scope)
3. **Add**

### Recording an Expense
1. **Add Transaction** → **Expense** tab
2. Select who paid
3. Enter a description (optional: upload a receipt)
4. Fill in item rows (pre-filled based on your General setting)
5. **Record Expense**

### Browsing Transactions by Month
1. **All Transactions** in the nav → defaults to the current month
2. Use ◀ / ▶ to move one month at a time (▶ is disabled on the current month)
3. Use the **Month** and **Year** dropdowns to jump directly to any past period

### Searching Transactions
1. Use the search bar in the navbar (any page) for a quick keyword search
2. Or navigate to `/search` directly for more control
3. Click **Advanced filters** to filter by type, user, date range, amount range, and/or the **Has attachment / receipt** toggle — filters can be combined
4. Results span all months and show the full date (`YYYY-MM-DD HH:MM`)

### Editing a Transaction
1. **All Transactions** (or a user's detail page) → pencil icon
2. Adjust any field — description, amount, date, from/to user
3. Add, edit, or remove expense items (the total auto-updates the Amount field)
4. Upload a new receipt, replace an existing one, or tick **Remove receipt** to delete it
5. **Save Changes** — balances are recalculated automatically

### Deleting a Transaction
- Trash icon on any transaction row — balances are reversed automatically

### Setting Up Email
1. **Settings** → **Email** tab
2. Fill in SMTP credentials and click **Save Settings**
3. Use **Send Emails Now** to test, or configure a recurring schedule under **Auto-Schedule**
4. Optionally enable **Send admin summary email** — requires a site admin to be set in the General tab first

### Customising Email Templates
1. **Settings** → **Templates** tab
2. Pick a colour preset or adjust individual colour pickers
3. Edit the subject and body text for each email type; use placeholders like `[Name]`, `[Balance]`, `[Date]`
4. Click **Preview** to open the rendered email in a new tab before saving
5. **Save Templates** — changes take effect on the next send

### Creating a Backup
1. **Settings** → **Backup** tab → **Create Backup Now**
2. The backup appears in the list instantly — click **Download** to save it locally
3. To schedule automatic backups, enable **Auto-Backup Schedule**, pick a day/time and how many backups to keep, then **Save Schedule**

### Restoring a Backup
- **From the list**: click **Restore** next to any existing backup and confirm
- **From a file**: use the **Upload Backup** section — select a `bot_backup_*.tar.gz` file and click **Upload**; the file is uploaded in chunks (no size limit) and appears in the list when done, ready to restore

### Managing Users
1. **Settings** → **Users** tab
2. Active users are shown in an **Active Users** list; deactivated users appear in a separate **Deactivated Users** list (hidden when no deactivated users exist)
3. Click **Deactivate** to move a user to the deactivated list, or **Reactivate** to restore them to the active list
4. Click a user's name to open their detail page, then **Edit User** to change their name, email, member-since date, or email preferences

### Switching Language
1. **Settings** → **General** tab → **Language** dropdown
2. Select **Deutsch** or **English**
3. **Save** — the entire UI switches to the selected language immediately

---

## 🔒 Security Notes

- **Content Security Policy** — every HTML response includes a nonce-based CSP header (`script-src 'self' 'nonce-…'`; `style-src 'self' 'unsafe-inline'`; `frame-ancestors 'none'`; `object-src 'none'`). All inline event handlers have been converted to `addEventListener` / event delegation so no `'unsafe-inline'` is needed for scripts.
- **HTML injection prevention** — all user-controlled values (names, emails, descriptions, error messages) are escaped with `html.escape()` before insertion into HTML email templates
- **XSS-safe toast notifications** — the `showToast()` JS helper builds DOM nodes programmatically with `textContent`, never `innerHTML`
- **Safe tar extraction** — backup restore rejects symlinks, hardlinks, absolute paths, `..` traversal, and any member whose resolved path escapes the extraction directory
- **Safe search queries** — SQL wildcards (`%`, `_`) in user search input are escaped before building ILIKE patterns
- **SMTP timeout** — outbound email connections use a 30-second timeout to prevent indefinite hangs
- Set a strong, random `SECRET_KEY` in your `.env` file
- Never commit your `.env` file (it is in `.gitignore`)
- The Docker container starts as root only to fix bind-mount directory ownership, then immediately drops to a non-root user (`appuser`, UID 1000) via `gosu`
- Per-route rate limiting is enabled on write-heavy endpoints (user add, transaction add, send-now, backup create/restore)
- Use an **App Password** for Gmail rather than your main account password
- Restrict network access to port 5000 — place behind a reverse proxy (nginx, Caddy) with authentication if the app is internet-facing
- Back up the `mariadb-data/` directory regularly, or use the built-in **Backup** feature (Settings → Backup tab)

---

## 🔧 Maintenance

### Health check
```bash
curl http://localhost:5000/health
# Returns structured JSON with individual check results:
# {"status": "ok", "checks": {"database": "ok", "scheduler": "ok", "icons_writable": "ok"}}
# Returns 503 with "status": "error" when the database is unreachable
```

The Dockerfile includes a `HEALTHCHECK` instruction and the docker-compose web service uses `/health` for its healthcheck.

### View logs
```bash
docker compose logs -f web    # Structured log output (timestamp, level, module, message)
docker compose logs -f db
```

Set the `LOG_LEVEL` environment variable to control verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`). Default is `INFO`.

### Backup & restore
Use the built-in **Settings → Backup** tab for creating, downloading, uploading, and restoring backups.

For a manual database-only dump:
```bash
docker compose exec db mysqldump -u "$DB_USER" -p"$DB_PASSWORD" bank_of_tina > backup_$(date +%Y%m%d).sql
```

### Update after code changes
```bash
docker compose build && docker compose up -d
```

### Reset everything ⚠️ (deletes all data)
```bash
docker compose down
rm -rf mariadb-data/ uploads/*/ icons/
docker compose up -d
```

---

## 🐛 Troubleshooting

| Problem | Steps |
|---------|-------|
| Emails not sending | Check Settings → Email; verify SMTP credentials; check logs |
| Receipt upload fails | Check `chmod 755 uploads/`; verify file is JPG/PNG/PDF |
| Port 5000 in use | Change the host port in `docker-compose.yml` (`"8080:5000"`) |
| Web container won't start | `docker compose logs web` — the app retries DB connections up to 5 times with exponential backoff on startup; check db logs if all retries fail |
| DB connection refused | Ensure `mariadb-data/` is writable; `docker compose restart db` |

---

### Charts & Statistics
A dedicated **Charts** page (nav bar → Charts) with a shared filter bar and four tabs, each showing a different view of the data:

| Tab | Chart type | What it shows |
|-----|-----------|---------------|
| **Balances** | Horizontal bar | Current balance per user; green/red per sign; sorted highest → lowest |
| **History** | Multi-line | Each user's running balance over time, reconstructed from the transaction log; weekly or monthly sample points depending on the selected range |
| **Volume** | Bar + line combo | Transaction count (bars, left axis) and total amount (line, right axis) grouped by week or month |
| **Top Items** | Horizontal bar | Top 15 expense line items by total amount or count; toggle between the two modes |

**Filter bar** — date range pickers, quick presets (30 d / 90 d / 1 yr / All time), multi-select user dropdown, Apply button.

**Print / PDF** — prints only the currently active tab, formatted for A4 landscape; chart canvas is resized to fill the page before the browser captures it. Open browser print dialog → Save as PDF.

---

## 🧪 Running Tests

Tests use an in-memory SQLite database and require no running services:

```bash
FLASK_TESTING=1 python -m pytest tests/ -v
```

The test suite includes 85 tests across 8 test modules covering helpers, models, routes, settings, analytics, health check, email service, and internationalization. All tests pass with zero warnings.

---

## 💡 Future Ideas

- [ ] CSV / Excel export of transactions
- [ ] User authentication and login system
- [ ] Exchange-rate-aware multi-currency support (currency symbol is already configurable)
- [ ] OCR for automatic receipt parsing
- [ ] Saved/pinned searches

---

Made with ❤️ to make office lunches easier! 🥗
