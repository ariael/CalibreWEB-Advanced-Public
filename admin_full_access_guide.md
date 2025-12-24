# Příručka Administrátora / Admin Guide

[Česky](#česky) | [English](#english)

---

# Česky

## Přehled
Jako Administrátor (nebo Omezený admin) v edici "CalibreWEB Advanced" máte k dispozici pokročilé nástroje pro údržbu knihovny a komunity.

## 1. Správa Uživatelů
### Fronta Schvalování (Approval Queue)
- **Noví Uživatelé**: Nezískají přístup ihned. Jsou automaticky zařazeni do stavu "Čekající" (Role 0).
- **Akce**: Jděte do `Admin` > `Uživatelé`. Uvidíte seznam čekajících žádostí.
- **Schválit**: Přiřaďte jim roli (např. "User" nebo vlastní roli).
- **Zamítnout**: Smažte uživatele nebo jej ponechte ve stavu čekající.

### Role Omezený Administrátor
- Může spravovat uživatele a knihy.
- **Nemůže** přistupovat ke kritickým nastavením systému (konfigurace serveru, umístění databáze, email server).

## 2. Library Auditor
**Auditor** je motor pro kontrolu zdraví knihovny.
- **Přístup**: `Admin` > `Auditor`.
- **Funkce**:
    - **Integrita Databáze**: Kontroluje poškozené vazby v databázi.
    - **Kontrola Souborů**: Ověřuje, zda ke každé knize existuje fyzický soubor na disku.
    - **Metadata**: Označuje knihy s chybějícími autory, jazyky nebo obálkami.
- **Reálný čas**: Můžete sledovat průběh skenování (progress bar) v reálném čase.

## 3. Hromadná Úprava Metadat
- **Série**: Můžete vybrat celou sérii a aplikovat změny (např. přidat štítek "Fantasy") na všechny knihy v ní najednou.
- **Kde**: V pohledu **Series Tracker** hledejte tlačítko "Hromadná úprava" (Bulk Edit) – pouze pro Adminy.

---

# English

## Overview
As an Administrator (or Limited Admin) in the "CalibreWEB Advanced" edition, you have advanced tools to maintain the library health and community.

## 1. User Management
### Approval Queue
- **New Users**: Do not get access immediately. They are placed in a "Pending" state (Role 0).
- **Action**: Go to `Admin` > `Users`. You will see pending requests.
- **Approve**: Assign them a role (e.g., "User" or customized role).
- **Reject**: Delete the user or leave them in pending.

### Limited Admin Role
- Can manage users and books.
- **Cannot** access critical system settings (server config, database location, email server).

## 2. Library Auditor
The **Auditor** is your health-check engine.
- **Access**: `Admin` > `Auditor`.
- **Functions**:
    - **Database Integrity**: Checks for broken foreign keys.
    - **File Check**: Verifies that every book record has an actual file on disk.
    - **Metadata**: Flag books with missing authors, languages, or covers.
- **Real-time**: You can see the progress bar as it scans thousands of books.

## 3. Bulk Metadata Editing
- **Series**: You can select a whole series and apply changes (e.g., add "Fantasy" tag) to all books in it at once.
- **Where**: In the **Series Tracker** view, look for the "Bulk Edit" button (Admins only).
