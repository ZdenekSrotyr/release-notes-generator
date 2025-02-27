# Release Notes Generator

Jednoduchý nástroj pro automatické generování release notes do samostatných souborů pro komponenty a repozitáře.

## Funkce

- Automatické vyhledávání repozitářů obsahujících "component" v názvu
- Extrakce názvu komponenty z `.github/workflows/push.yml` (KBC_DEVELOPERPORTAL_APP)
- Získávání změn mezi tagy a informací z pull requestů
- Chronologické řazení releasů podle data tagu
- Integrace se Slack pro sdílení nových release notes
- GitHub Actions podpora pro automatické generování
- Samostatné soubory release notes pro každý release komponenty v adresáři `release_notes`
- Automatická detekce posledního vygenerovaného release

## Instalace

```bash
# Naklonování repozitáře
git clone https://github.com/your-org/release-notes-generator.git
cd release-notes-generator

# Instalace závislostí
pip install -r requirements.txt
```

## Použití

### Parametry příkazové řádky

```bash
# Nastavení GitHub tokenu (povinné)
export GITHUB_TOKEN="ghp_your_token_here"

# Základní použití - generuje release notes od minulého dne
python main.py

# Generování od posledního spuštění
python main.py --since-last-run

# Povolení Slack notifikací (vyžaduje webhook URL)
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/xxx/yyy/zzz"
python main.py --slack

# Kompletní příklad
python main.py --since-last-run --slack
```

### Všechny parametry příkazové řádky

```
--since-last-run    Generuje od data posledního souboru v adresáři release_notes
--slack             Povolí odesílání notifikací na Slack
```

### Proměnné prostředí

Používají se následující proměnné prostředí:

- `GITHUB_TOKEN` - GitHub API token (povinný)
- `SLACK_WEBHOOK_URL` - Slack webhook URL (pro Slack notifikace)

### GitHub Actions

Součástí je GitHub Actions workflow, který umožňuje:

1. Generovat release notes automaticky podle rozvrhu
2. Spouštět generování ručně s vlastními parametry
3. Commity nových release notes přímo do repozitáře
4. Volitelně odesílat notifikace na Slack

Nastavení:

1. Přidejte tajemství (secrets) do vašeho GitHub repozitáře:
   - `GITHUB_TOKEN` (poskytováno automaticky)
   - `SLACK_WEBHOOK_URL` (pro Slack notifikace)

2. Workflow lze spustit:
   - Ručně z karty Actions
   - Automaticky podle nastaveného rozvrhu

## Slack integrace

Sdílejte release notes se svým týmem přes Slack:

1. Nastavte parametr `--slack` při spuštění nástroje
2. Poskytněte webhook URL přes proměnnou prostředí `SLACK_WEBHOOK_URL`

Slack zpráva obsahuje:
- Seznam komponent, které byly aktualizovány
- Názvy tagů a data vydání
- Až 3 změny pro každý tag s odkazem na GitHub
- Informaci o celkovém počtu změn

## Funkce detekce od posledního spuštění

Parametr `--since-last-run` automaticky detekuje datum posledního souboru v adresáři `release_notes` a generuje nové položky od tohoto data. To je užitečné pro:

1. Inkrementální aktualizace bez ručního zadávání dat
2. Zajištění, že nebudou vynechány žádné release mezi spuštěními
3. Automatizované pravidelné aktualizace pomocí GitHub Actions

## Přizpůsobení výstupu

Přizpůsobte výstup úpravou šablony v adresáři `templates`. Šablona pro release poznámky komponenty je `component-release.md.j2`, která používá formát Jinja2.

## Release Notes souborů

Nástroj generuje samostatné soubory release notes pro každý release komponenty:

1. Každý release komponenty je uložen jako samostatný soubor v adresáři `release_notes`
2. Soubory jsou pojmenovány ve formátu `YYYY-MM-DD-HH-MM-SS_tag_component-name.md`
3. To umožňuje lepší organizaci a sledování releasů podle komponent

Tato funkce pomáhá s:
- Sledováním, které release již byly zpracovány
- Vytvářením strukturovaného archivu všech releasů komponent
- Zjednodušením procesu informování o nových releasech 