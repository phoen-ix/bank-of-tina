# Bank of Tina

Eine selbst gehostete Webanwendung zur Verwaltung gemeinsamer Ausgaben und Salden in einem kleinen Büro oder einer Gruppe. Funktionen umfassen Ausgabenerfassung mit Belegen, wöchentliche E-Mail-Berichte pro Benutzer, eine Admin-Zusammenfassungs-E-Mail, Diagramme und Statistiken, automatisierte Backups und eine vollständig konfigurierbare Oberfläche mit Designs und E-Mail-Vorlagen. Komplett zweisprachig (Deutsch und Englisch). Gebaut mit Flask und MariaDB, läuft vollständig in Docker — keine externen Dienste erforderlich.

---

## Funktionen

### Benutzer & Salden
- Teammitglieder mit Name und E-Mail hinzufügen
- Echtzeit-Saldoverfolgung für jeden Benutzer
- Benutzer deaktivieren (auf der Übersicht ausgeblendet, in den Einstellungen verwaltbar)
- Übersicht zeigt Name und Saldo; E-Mail-Spalte optional (Einstellungen -> Allgemein, standardmäßig aus)
- Benutzerdetailseite zeigt paginierte Transaktionshistorie (20 pro Seite); Klick auf den Namen eines Benutzers auf der Übersicht öffnet sie
- **E-Mail-Einstellungen pro Benutzer** — individuell ein-/ausschalten der wöchentlichen Saldo-E-Mail; Auswahl wie viel Transaktionshistorie einbezogen wird (`Letzte 3`, `Diese Woche`, `Dieser Monat` oder `Keine`)

### Transaktionen
- **Ausgabe** — erfassen wer bezahlt hat und Artikel einzelnen Personen zuordnen
- **Einzahlung** — Geld zum Saldo eines Benutzers hinzufügen
- **Auszahlung** — Geld vom Saldo eines Benutzers abziehen
- **Bearbeiten** jeder gespeicherten Transaktion: Beschreibung, Notizen, Betrag, Datum, Von/An-Benutzer, Ausgabenpositionen und Beleg
- **Notizfeld** — optionale Freitext-Notizen zu jeder Transaktion für längeren Kontext oder Begründung; inline in allen Transaktionslisten angezeigt und in der Suche enthalten
- **Löschen** jeder Transaktion (Salden werden automatisch zurückgesetzt)
- **Monatsansicht** — Transaktionen nach Tag gruppiert mit Vor-/Zurück-Navigation und einem Monat/Jahr-Schnellwähler; standardmäßig der aktuelle Monat
- **Suche** — Volltextsuche über Beschreibungen und Ausgabenpositionen; erweiterte Filter für Typ, Benutzer, Datumsbereich, Betragsbereich und einen "Hat Anhang/Beleg"-Schalter; paginierte Ergebnisse (25 pro Seite); nur aktive Benutzer erscheinen im Benutzerfilter

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

### Mehrsprachigkeit (i18n)
- **Zwei Sprachen** — Deutsch und Englisch, umschaltbar über Einstellungen -> Allgemein -> Sprache
- **Globale Einstellung** — die Sprache gilt app-weit (gespeichert in der Datenbank wie alle anderen Einstellungen)
- **Vollständige Abdeckung** — alle UI-Elemente, Flash-Nachrichten, E-Mail-Vorlagen, Diagrammbeschriftungen und Transaktionstyp-Badges werden übersetzt
- **Flask-Babel** — Standard-gettext `.po`/`.mo`-Dateien; ~427 übersetzte Zeichenketten
- **Lokalisierte Datumsanzeige** — Monatsnamen und Tagesheader werden in der gewählten Sprache angezeigt
- **Standardsprache** — Deutsch (`de`); kann jederzeit auf Englisch (`en`) umgestellt werden

### PWA — Zum Startbildschirm hinzufügen
- **Web App Manifest** — dynamisch unter `/manifest.json` bereitgestellt; `theme_color` folgt der konfigurierten Navigationsfarbe
- **Service Worker** — Network-First-Strategie; holt immer aktuelle Daten; zeigt eine eigenständige Offline-Seite wenn das Netzwerk nicht erreichbar ist oder der Server einen HTTP-Fehler zurückgibt (z.B. 503); bereitgestellt über `/sw.js` via Flask-Route für volle App-Scope-Kontrolle
- **Icons** — 32x32, 192x192 und 512x512 PNG-Icons; auf dem Host via Bind-Mount (`./icons/`) persistiert, überleben Container-Rebuilds; beim ersten Start automatisch mit der Standard-Designfarbe generiert; `/favicon.ico`-Route liefert das 32px-Icon; verwaltbar über Einstellungen -> Vorlagen -> App-Icon:
  - **Aus Navigationsfarbe generieren** — Ein-Klick-Neugenerierung mit der aktuellen Designfarbe als Hintergrund (weiße Bank-Silhouette)
  - **Benutzerdefiniertes Icon hochladen** — beliebiges PNG oder JPG hochladen; automatisch auf 32x32, 192x192 und 512x512 skaliert
  - **Auf Standard zurücksetzen** — stellt das originale Bootstrap-Blue-Icon wieder her
  - Cache-Busting stellt sicher, dass Browser und PWA neue Icons sofort übernehmen
- **Android Chrome**: Drei-Punkt-Menü -> "Zum Startbildschirm hinzufügen" (oder automatisches Installationsbanner)
- **iOS Safari**: Teilen-Menü -> "Zum Home-Bildschirm" -> korrektes Icon, Name und Standalone-Start
- Kein App Store erforderlich; keine nativen Build-Tools erforderlich

### Oberfläche
- **Toast-Benachrichtigungen** — Erfolgs-/Fehlermeldungen erscheinen als Bootstrap-5-Toasts in der oberen rechten Ecke, verschwinden automatisch nach 4 Sekunden und stapeln sich bei mehreren gleichzeitigen Nachrichten; enthält einen globalen `showToast(message, type)` JS-Helper für programmatische Nutzung
- **Skeleton-Loading** — die Diagrammseite zeigt pulsierende Skeleton-Platzhalter (horizontale Balken für Salden/Top-Artikel, vollbreite Rechtecke für Verlauf/Volumen) während die Daten geladen werden

### Vorlagen & Design
- **Farbpalette** — Navigationsfarbe, E-Mail-Header-Farbverlauf (Anfang + Ende), positive und negative Saldofarben; jede mit Farbwähler und Hex-Textfeld
- **Vordefinierte Designs** — Auswahl aus Standard, Ozean, Wald, Sonnenuntergang oder Schiefer über ein Dropdown; ein Preset auswählen füllt sofort alle Wähler; manuelles Ändern eines Wählers wechselt zu "Benutzerdefiniert"
- **E-Mail-Betreffs** — bearbeitbare Betreffzeile für jeden der drei E-Mail-Typen
- **E-Mail-Textvorlagen** — Begrüßung, Einleitung, Fußzeile 1 und Fußzeile 2 der wöchentlichen Saldo-E-Mail bearbeiten; Einleitung und Fußzeile der Admin-Zusammenfassungs-E-Mail; Fußzeile der Backup-Status-E-Mail; ein Feld leer lassen um die Zeile auszulassen
- **E-Mail-Adressen-Schalter** — Admin-Zusammenfassungs-E-Mail-Karte hat einen "E-Mail-Adressen in Zusammenfassungstabelle anzeigen"-Schalter (Standard aus); wenn aus, werden nur Namen und Salden angezeigt
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
| **Allgemein** | Standard-Artikelzeilen im Transaktionsformular; Anzahl letzter Transaktionen auf der Übersicht (0 blendet den Bereich aus); Zeitzone; **Sprache** (Deutsch/Englisch); **Dezimaltrennzeichen** (Punkt `1.99` oder Komma `1,99`); **Währungssymbol** (EUR, $, £, ¥ und mehr); E-Mail-Spalte auf der Übersicht ein-/ausblenden; Seiten-Admin |
| **E-Mail** | SMTP-Zugangsdaten; E-Mail-Versand aktivieren/deaktivieren; Debug-Modus; Admin-Zusammenfassungs-E-Mail-Schalter; Saldo-E-Mails auf Abruf senden; wiederkehrenden Zeitplan einrichten |
| **Häufige** | Globaler Autovervollständigungsschalter; Artikelnamen, Beschreibungen und Preise manuell verwalten (jeweils mit eigener Blacklist); Auto-Sammlungs-Job konfigurieren und Debug-Log anzeigen |
| **Backup** | Backups erstellen/herunterladen/löschen; aus jedem Backup oder einer hochgeladenen Datei wiederherstellen; automatischen Backup-Zeitplan mit Auto-Bereinigung konfigurieren; Backup-Status-E-Mail an Seiten-Admin; Debug-Log |
| **Vorlagen** | Farbpalette + vordefinierte Designs; bearbeitbare Betreffs und Texte für alle drei E-Mail-Typen; Vorschau-Buttons; **App-Icon**-Karte — Icons aus Navigationsfarbe generieren, benutzerdefiniertes Icon hochladen oder auf Standard zurücksetzen |
| **Benutzer** | Neue Benutzer hinzufügen (inkl. E-Mail-Opt-in und Transaktionsumfang); aktive und deaktivierte Benutzer in getrennten Listen (deaktivierte Liste ist ausgeblendet wenn leer); Benutzer deaktivieren oder reaktivieren |

### E-Mail-Benachrichtigungen
- SMTP-Zugangsdaten werden sicher in der Datenbank gespeichert (konfiguriert über Einstellungen -> E-Mail)
- **Jetzt senden**-Button um sofort allen aktiven Benutzern ihren aktuellen Saldo per E-Mail zu senden
- **Automatischer Zeitplan** — Tag und Uhrzeit (24-Stunden-Format) wählen; der Zeitplan überlebt Container-Neustarts
- **Opt-in pro Benutzer** — Benutzer können die wöchentliche E-Mail abbestellen; abgemeldete Benutzer werden bei jedem Versand übersprungen (manuell und geplant)
- **Transaktionsumfang pro Benutzer** — jede Benutzer-E-Mail enthält die gewählte Option: letzte 3 Transaktionen, alle Transaktionen dieser Woche, dieses Monats oder keine Transaktionshistorie
- **Admin-Zusammenfassungs-E-Mail** — wenn ein Seiten-Admin konfiguriert ist (Einstellungen -> Allgemein), wird eine optionale zusätzliche E-Mail mit einer farbcodierten Saldenübersicht *aller* aktiven Benutzer gesendet (unabhängig vom individuellen Opt-in-Status)

---

## Schnellstart

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

## Bedienungsanleitung

### Benutzer hinzufügen
1. **Einstellungen** -> **Benutzer**-Tab -> Name und E-Mail eingeben
2. **Wöchentlicher E-Mail-Bericht** (ein/aus) und **In E-Mail einschließen** (Transaktionsumfang) einstellen
3. **Hinzufügen**

### Ausgabe erfassen
1. **Transaktion hinzufügen** -> **Ausgabe**-Tab
2. Auswählen wer bezahlt hat
3. Beschreibung eingeben (optional: Beleg hochladen)
4. Artikelzeilen ausfüllen (vorausgefüllt basierend auf der Allgemein-Einstellung)
5. **Ausgabe erfassen**

### Transaktionen nach Monat durchblättern
1. **Alle Transaktionen** in der Navigation -> zeigt standardmäßig den aktuellen Monat
2. Mit den Pfeiltasten einen Monat vor/zurück navigieren (Vorwärts ist im aktuellen Monat deaktiviert)
3. Die **Monat**- und **Jahr**-Dropdowns verwenden um direkt zu einer vergangenen Periode zu springen

### Transaktionen suchen
1. Die Suchleiste in der Navigation (auf jeder Seite) für eine schnelle Stichwortsuche verwenden
2. Oder direkt zu `/search` navigieren für mehr Kontrolle
3. **Erweiterte Filter** klicken um nach Typ, Benutzer, Datumsbereich, Betragsbereich und/oder dem **Hat Anhang/Beleg**-Schalter zu filtern — Filter können kombiniert werden
4. Ergebnisse erstrecken sich über alle Monate und zeigen das vollständige Datum (`JJJJ-MM-TT HH:MM`)

### Transaktion bearbeiten
1. **Alle Transaktionen** (oder Benutzerdetailseite) -> Stift-Symbol
2. Beliebiges Feld anpassen — Beschreibung, Betrag, Datum, Von/An-Benutzer
3. Ausgabenpositionen hinzufügen, bearbeiten oder entfernen (die Summe aktualisiert das Betragsfeld automatisch)
4. Neuen Beleg hochladen, bestehenden ersetzen oder **Beleg entfernen** ankreuzen zum Löschen
5. **Änderungen speichern** — Salden werden automatisch neu berechnet

### Transaktion löschen
- Papierkorb-Symbol auf jeder Transaktionszeile — Salden werden automatisch zurückgesetzt

### E-Mail einrichten
1. **Einstellungen** -> **E-Mail**-Tab
2. SMTP-Zugangsdaten eingeben und **Einstellungen speichern** klicken
3. **E-Mails jetzt senden** zum Testen verwenden, oder unter **Automatischer Zeitplan** einen wiederkehrenden Zeitplan einrichten
4. Optional **Admin-Zusammenfassungs-E-Mail senden** aktivieren — erfordert dass zuerst ein Seiten-Admin im Allgemein-Tab eingestellt wird

### E-Mail-Vorlagen anpassen
1. **Einstellungen** -> **Vorlagen**-Tab
2. Ein Farb-Preset wählen oder einzelne Farbwähler anpassen
3. Betreff und Text für jeden E-Mail-Typ bearbeiten; Platzhalter wie `[Name]`, `[Balance]`, `[Date]` verwenden
4. **Vorschau** klicken um die gerenderte E-Mail in einem neuen Tab vor dem Speichern zu öffnen
5. **Vorlagen speichern** — Änderungen werden beim nächsten Versand wirksam

### Backup erstellen
1. **Einstellungen** -> **Backup**-Tab -> **Jetzt Backup erstellen**
2. Das Backup erscheint sofort in der Liste — **Herunterladen** klicken um es lokal zu speichern
3. Für automatische Backups **Automatischer Backup-Zeitplan** aktivieren, Tag/Uhrzeit und Anzahl der aufzubewahrenden Backups wählen, dann **Zeitplan speichern**

### Backup wiederherstellen
- **Aus der Liste**: **Wiederherstellen** neben einem bestehenden Backup klicken und bestätigen
- **Aus einer Datei**: den **Backup hochladen**-Bereich verwenden — eine `bot_backup_*.tar.gz`-Datei auswählen und **Hochladen** klicken; die Datei wird in Blöcken hochgeladen (kein Größenlimit) und erscheint nach Fertigstellung in der Liste, bereit zur Wiederherstellung

### Benutzer verwalten
1. **Einstellungen** -> **Benutzer**-Tab
2. Aktive Benutzer werden in einer **Aktive Benutzer**-Liste angezeigt; deaktivierte Benutzer erscheinen in einer separaten **Deaktivierte Benutzer**-Liste (ausgeblendet wenn keine deaktivierten Benutzer existieren)
3. **Deaktivieren** klicken um einen Benutzer in die deaktivierte Liste zu verschieben, oder **Reaktivieren** um ihn in die aktive Liste zurückzuholen
4. Auf den Namen eines Benutzers klicken um seine Detailseite zu öffnen, dann **Benutzer bearbeiten** um Name, E-Mail, Mitglied-seit-Datum oder E-Mail-Einstellungen zu ändern

### Sprache wechseln
1. **Einstellungen** -> **Allgemein**-Tab -> **Sprache**-Dropdown
2. **Deutsch** oder **English** wählen
3. **Speichern** — die gesamte Oberfläche wechselt sofort zur gewählten Sprache

---

## Dateistruktur

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

## Sicherheitshinweise

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

## Wartung

### Health-Check
```bash
curl http://localhost:5000/health
# Gibt strukturiertes JSON mit einzelnen Prüfergebnissen zurück:
# {"status": "ok", "checks": {"database": "ok", "scheduler": "ok", "icons_writable": "ok"}}
# Gibt 503 mit "status": "error" zurück wenn die Datenbank nicht erreichbar ist
```

### Logs anzeigen
```bash
docker compose logs -f web    # Strukturierte Log-Ausgabe (Zeitstempel, Level, Modul, Nachricht)
docker compose logs -f db
```

`LOG_LEVEL`-Umgebungsvariable setzen um die Ausführlichkeit zu steuern (`DEBUG`, `INFO`, `WARNING`, `ERROR`). Standard ist `INFO`.

### Backup & Wiederherstellung
Den eingebauten **Einstellungen -> Backup**-Tab für das Erstellen, Herunterladen, Hochladen und Wiederherstellen von Backups verwenden.

Für einen manuellen reinen Datenbank-Dump:
```bash
docker compose exec db mysqldump -u "$DB_USER" -p"$DB_PASSWORD" bank_of_tina > backup_$(date +%Y%m%d).sql
```

### Nach Code-Änderungen aktualisieren
```bash
docker compose build && docker compose up -d
```

### Alles zurücksetzen (löscht alle Daten)
```bash
docker compose down
rm -rf mariadb-data/ uploads/*/ icons/
docker compose up -d
```

---

## Fehlerbehebung

| Problem | Schritte |
|---------|----------|
| E-Mails werden nicht gesendet | Einstellungen -> E-Mail prüfen; SMTP-Zugangsdaten verifizieren; Logs prüfen |
| Beleg-Upload schlägt fehl | `chmod 755 uploads/` prüfen; verifizieren dass die Datei JPG/PNG/PDF ist |
| Port 5000 belegt | Host-Port in `docker-compose.yml` ändern (`"8080:5000"`) |
| Web-Container startet nicht | `docker compose logs web` — die App wiederholt DB-Verbindungen bis zu 5 Mal mit exponentiellem Backoff beim Start |
| DB-Verbindung abgelehnt | Sicherstellen dass `mariadb-data/` beschreibbar ist; `docker compose restart db` |

---

### Diagramme & Statistiken
Eine eigene **Diagramme**-Seite (Navigationsleiste -> Diagramme) mit einer gemeinsamen Filterleiste und vier Tabs:

| Tab | Diagrammtyp | Was angezeigt wird |
|-----|-------------|-------------------|
| **Salden** | Horizontaler Balken | Aktueller Saldo pro Benutzer; grün/rot je nach Vorzeichen; sortiert von höchstem zu niedrigstem |
| **Verlauf** | Mehrlinien | Laufender Saldo jedes Benutzers über die Zeit, aus dem Transaktionslog rekonstruiert; wöchentliche oder monatliche Datenpunkte je nach ausgewähltem Bereich |
| **Volumen** | Balken + Linie | Transaktionsanzahl (Balken, linke Achse) und Gesamtbetrag (Linie, rechte Achse) gruppiert nach Woche oder Monat |
| **Top-Artikel** | Horizontaler Balken | Top 15 Ausgabenpositionen nach Gesamtbetrag oder Anzahl; zwischen beiden Modi umschalten |

**Filterleiste** — Datumsbereich-Wähler, Schnellvorlagen (30 T / 90 T / 1 J / Alle Zeit), Mehrfachauswahl-Benutzer-Dropdown, Anwenden-Button.

**Drucken / PDF** — druckt nur den aktuell aktiven Tab, formatiert für A4 Querformat; Diagramm-Canvas wird vor der Browser-Erfassung auf Seitengröße skaliert. Browser-Druckdialog öffnen -> Als PDF speichern.

---

## Tests ausführen

Tests verwenden eine SQLite-In-Memory-Datenbank und benötigen keine laufenden Dienste:

```bash
FLASK_TESTING=1 python -m pytest tests/ -v
```

Die Testsuite umfasst 85 Tests in 8 Testmodulen: Hilfsfunktionen, Modelle, Routen, Einstellungen, Diagramme, Health-Check, E-Mail-Service und Internationalisierung. Alle Tests bestehen ohne Warnungen.

---

## Zukunftsideen

- [ ] CSV-/Excel-Export von Transaktionen
- [ ] Benutzerauthentifizierung und Login-System
- [ ] Wechselkurs-bewusste Mehrwährungsunterstützung (Währungssymbol ist bereits konfigurierbar)
- [ ] OCR für automatische Belegerfassung
- [ ] Gespeicherte/angeheftete Suchen

---

Entwickelt um Büro-Mittagessen einfacher zu machen!
