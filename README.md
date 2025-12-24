# CalibreWEB Advanced

*(Založeno na originálním projektu [Calibre-Web](https://github.com/janeczku/calibre-web) od Janeczka)*

[Česky](#česky) | [English](#english)

---

# Česky

Vítejte v **CalibreWEB Advanced**. Pokud hledáte jen obyčejné úložiště souborů, jste na špatném místě.
Tento projekt vznikl z jednoduché frustrace: *"Mám tisíce e-knih, ale trávím více času jejich organizací než samotným čtením."*

Proto jsme vzali původní Calibre-Web, rozebrali ho na šroubky a přepsali jej na **Aktivního Čtenářského Asistenta**.

## 📚 Dokumentace

- 🔐 **[Registrace a První kroky](user_registration_guide.md)**
- 📖 **[Příručka pro Čtenáře](secondary_user_guide.md)**
- 👑 **[Příručka pro Administrátora](admin_full_access_guide.md)**
- 🚧 **[Roadmapa Vývoje](ROADMAP.md)**
- ⚙️ **[Technická Dokumentace](DOCUMENTATION.md)**

## 🚀 Příběh změn: Proč "Advanced"?

Toto není jen seznam funkcí. Toto jsou problémy, které jsme měli, a řešení, která jsme vyvinuli.

### 1. Konec chaosu v sériích: "Series Tracker" & "Gap Detection"
* **Problém**: Čtete detektivku. Dočtete díl 4. Chcete díl 5. Máte ho? Jak se jmenuje? Původní Calibre-Web vám ukázal jen abecední seznam souborů. Museli jste jít na Wikipedii nebo Databazeknih, hledat seznam dílů, a pak ručně prohledávat disk.
* **Naše Řešení**: Vytvořili jsme **Series Tracker**.
    * **Vizuální Progress**: Náš systém ví, že série "Harry Potter" má 7 dílů. Vidíte grafický bar: *"Máš 71% série."*
    * **Gap Detection (Detekce Mezer)**: Toto je "killer feature". Algoritmus projede vaše knihy. Pokud najde díly 1, 2, 4 a 5, automaticky označí sérii **červeným vykřičníkem**. Po rozkliknutí vám napíše: *"POZOR: Chybí ti díl 3 (Vězeň z Azkabanu)"*.
    * **New Release Radar**: Systém umí (ve spolupráci s metadaty) upozornit, že autor vydal nový díl, který ještě nemáte.

### 2. Zdraví knihovny: "Library Auditor 2.0"
* **Problém**: S knihovnou o velikosti 50 000+ knih se stávají chyby. Soubor se při kopírování poškodí. Záznam v databázi zůstane po smazaném souboru. Obálka chybí. V původním systému to zjistíte až v momentě, kdy si chcete knihu stáhnout – kliknete a dostanete chybu 500. To je pro uživatele frustrující.
* **Naše Řešení**: Na pozadí běží tichý strážce **Auditor**.
    * **Forenzní kontrola**: Každou noc (nebo na vyžádání) Auditor projde každý jeden záznam v databázi a fyzicky sáhne na soubor na disku.
    * **Metadata Police**: Hledá knihy bez autorů, bez jazyka, bez obálky nebo se špatným formátem jména.
    * **Reporting**: Administrátor má dedikovaný dashboard, kde vidí zdraví knihovny v procentech a seznam konkrétních problémů k vyřešení. Vaše knihovna je tak vždy "Download Ready".

### 3. Komunita a Bezpečí: "phpBB Auth" & "Approval Queue"
* **Problém**: Chtěli jsme knihovnu zpřístupnit komunitě, ale nechtěli jsme spravovat další databázi hesel a riskovat úniky. Chtěli jsme, aby přístup měli jen lidé, které známe.
* **Naše Řešení**:
    * **Single Sign-On**: Zahodili jsme původní přihlašování a napojili jádro přímo na databázi fóra **phpBB**. Uživatelé se přihlašují svým známým jménem a heslem.
    * **Waiting Room (Čekárna)**: Když se někdo přihlásí poprvé, nevidí nic. Systém ho zachytí a umístí do "Čekací listiny" (Role 0). Administrátor dostane notifikaci: *"Uživatel XY (známý z fóra) chce přístup."* Teprve po ručním schválení se brány knihovny otevřou. To nám umožňuje udržovat 100% důvěryhodnou komunitu.
    * **Limited Admin**: Vytvořili jsme novou roli, která může opravovat názvy knih a obálky, ale nemůže smazat server nebo změnit nastavení. Díky tomu nám s údržbou pomáhají dobrovolníci bez rizika.

### 4. Svoboda čtení: Pryč s kabely
* **Problém**: *"Musím najít kabel, připojit čtečku k PC, otevřít Calibre, poslat..."* V roce 2025 je to otravné.
* **Naše Řešení**:
    * **PocketBook & Moon+ Reader**: Plná implementace **OPDS serveru**. Ve čtečce zadáte URL jen jednou. Pak už jen procházíte "obchod" s knihami zdarma přímo na displeji čtečky a stahujete přes Wi-Fi.
    * **Kobo Sync**: Pro majitele Kobo čteček jsme integrovali `kepubify` a protokol pro synchronizaci. Nejenže se knihy stahují vzduchem, ale **synchronizuje se stav přečtení**. Dočtete kapitolu v tramvaji na čtečce, a doma na webu vidíte, že máte splněno.
    * **Kindle**: Funkční "Send-to-Kindle" tlačítko, které pošle e-mail s knihou přímo Amazonu, pokud preferujete tento ekosystém.

### 5. Vizuální Revoluce: "CA Black" & Hierarchie
* **Problém**: Původní vzhled byl... funkční, ale zastaralý. Bílé pozadí vypalovalo oči v noci a seznamy knih byly nepřehledné "nudle".
* **Naše Řešení**:
    * **CA Black Theme**: Vytvořili jsme vlastní CSS motiv od nuly. Používá hlubokou černou (pro OLED displeje) a jemné šedé tóny. Není to jen "invertování barev", je to kompletní redesign pro noční čtení.
    * **Hierarchické Stromy**: Zapomeňte na tabulky. V našem zobrazení vidíte Autora -> Pod ním jeho Série -> A v nich seřazené Knihy. Data jsou strukturovaná tak, jak o nich přemýšlíte.
    * **Minimalismus**: Odstranili jsme zbytečná tlačítka. Na mobilu vidíte jen obálku, název a tlačítko "Číst".

### 6. Kurátorství: Vy rozhodujete
* **Problém**: Knihovna je plná žánrů, které vás nezajímají. Proč musíte neustále scrollovat přes "Červenou knihovnu", když chcete "Sci-Fi"?
* **Naše Řešení**: **Smart Preferences**.
    * U každého autora a série máte dvě nová tlačítka: **Srdíčko (Preferovat)** a **Křížek (Ignorovat)**.
    * Pokud dáte křížek, autor zmizí z vaší domovské stránky. Už ho neuvidíte.
    * Pokud dáte srdíčko, jeho nové knihy se objeví jako první. Vy si tvoříte vlastní knihovnu uvnitř té veřejné.

---

# English

Welcome to **CalibreWEB Advanced**. If you are looking for simple file storage, look elsewhere.
This project was born from a frustration: *"I have thousands of ebooks, but I spend more time organizing them than reading them."*

So we took the original Calibre-Web, stripped it down, and rebuilt it into an **Active Reading Assistant**.

## 📚 Documentation

- 🔐 **[Registration & First Steps](user_registration_guide.md)**
- 📖 **[Reader Guide](secondary_user_guide.md)**
- 👑 **[Admin Guide](admin_full_access_guide.md)**
- 🚧 **[Roadmap](ROADMAP.md)**
- ⚙️ **[Technical Documentation](DOCUMENTATION.md)**

## 🚀 The Story of Changes: Why "Advanced"?

This is not just a feature list. These are the problems we faced and the solutions we engineered.

### 1. Ending Series Chaos: "Series Tracker" & "Gap Detection"
* **Problem**: You finish Book 4 of a mystery saga. You want Book 5. Do you own it? What is it called? The original app just showed an alphabetical list of files. You had to browse Wikipedia to find the order and then manually search your drive.
* **Our Solution**: **The Series Tracker**.
    * **Visual Progress**: The system knows "Harry Potter" has 7 books. A graphic bar tells you: *"You own 71% of this saga."*
    * **Gap Detection**: This is the killer feature. The algorithm scans your metadata. If it finds Books 1, 2, 4, and 5, it flags the series with a **Red Alert**. It explicitly reports: *"MISSING: Vol 3 (Prisoner of Azkaban)"*. No more manual checking.
    * **New Release Radar**: It highlights when an author you follow releases a new book into the library.

### 2. Library Health: "Library Auditor 2.0"
* **Problem**: In a library of 50,000+ books, rot happens. Files get corrupted, records get orphaned, covers vanish. In the original system, you only found out when a download failed with a 500 Error. Frustrating.
* **Our Solution**: The **Auditor**.
    * **Forensic Scan**: Every night, the Auditor crawls the database and touches every physical file.
    * **Metadata Police**: It hunts for books with missing authors, languages, or covers.
    * **Reporting**: Admins get a dedicated health dashboard showing the library's status score and a todo-list of fixes. Your library stays "Download Ready".

### 3. Community & Safety: "phpBB Auth" & "Approval Queue"
* **Problem**: We wanted to share books with our community but didn't want to manage a second password database or risk leaks. We needed a trusted-only environment.
* **Our Solution**:
    * **Single Sign-On**: We completely replaced the auth system. It connects directly to our **phpBB Forum** database. Users login with their familiar credentials.
    * **Waiting Room**: Login doesn't mean access. New users land in a "Pending" state (Role 0). The Admin gets an alert: *"User XY (from the forum) requests entry."* Only after manual approval does the library open up. This keeps the ecosystem 100% trusted.
    * **Limited Admin**: A new role that lets volunteers fix tyops and covers without giving them the keys to delete the server or change configs.

### 4. Freedom form Cables
* **Problem**: *"Find cable, connect reader, open Calibre, send..."* In 2025, this is archaic.
* **Our Solution**:
    * **PocketBook & Moon+ Reader**: Full **OPDS Server** implementation. Enter the URL once, and browse a "Bookstore-like" interface on your e-ink screen. Download via Wi-Fi instantly.
    * **Kobo Sync**: Deep integration with `kepubify`. Not only do books sync wirelessly, but **reading status syncs too**. Finish a chapter on the train, and the web dashboard marks it as read.
    * **Kindle**: A functional "Send-to-Kindle" button if you prefer the Amazon ecosystem.

### 5. Visual Revolution: "CA Black" & Hierarchy
* **Problem**: The original look was functional but dated. The white background hurt eyes at night, and lists were cluttered.
* **Our Solution**:
    * **CA Black Theme**: A custom CSS engine built from scratch. It uses Deep Blacks (for OLED battery saving) and soft grays. It's not just inverted colors; it's a redesign.
    * **Hierarchical Trees**: Tables are gone. Now you see Author -> Series -> Books in a tree structure. Data is organized how you think.
    * **Minimalism**: We hid the clutter. On mobile, you see just the cover, title, and "Read" button.

### 6. Curation: You Decide
* **Problem**: The library is huge. Why scroll through "Romance" if you only read "Sci-Fi"?
* **Our Solution**: **Smart Preferences**.
    * Every author/series has **Heart (Prefer)** and **Cross (Ignore)** buttons.
    * Click "Ignore", and they vanish from your home feed.
    * Click "Prefer", and their new uploads appear at the top. You curate your own personal library within the public one.

---
*Created and maintained by the CalibreWEB Advanced community, December 2025.*
