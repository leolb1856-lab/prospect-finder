import argparse
import csv
import logging
import time
from datetime import date
from urllib.parse import urlparse

import requests

# ──────────────────────────────────────────────
# Paramètres par défaut (modifiables ici ou via CLI)
# ──────────────────────────────────────────────
NAF_CODES = [
    '41.10A',  # Promotion immobilière
    '41.20A',  # Construction maisons individuelles
    '41.20B',  # Construction autres bâtiments
    '42.11Z',  # Routes et autoroutes
    '43.11Z',  # Travaux démolition
    '43.12A',  # Travaux terrassement
    '43.21A',  # Travaux électricité
    '43.22A',  # Travaux plomberie
    '43.31Z',  # Plâtrerie
    '43.32A',  # Menuiserie bois
    '43.33Z',  # Revêtements sols et murs
    '43.34Z',  # Peinture et vitrerie
    '43.91A',  # Travaux charpente
    '43.91B',  # Travaux couverture
    '43.99A',  # Travaux étanchéité
    '43.99C',  # Maçonnerie générale
]

TRANCHES_EFFECTIF = ['02', '03', '11', '12']
# 02=3-5 salariés, 03=6-9, 11=10-19, 12=20-49

DEPARTEMENTS = []  # vide = toute la France, ex: ['75', '69', '13']

MAX_RESULTS = 500

ONLY_WITH_WEBSITE = False

SEARCH_WEBSITES = True  # Chercher les sites web via DuckDuckGo (plus lent)

# ──────────────────────────────────────────────
# Constantes
# ──────────────────────────────────────────────
API_BASE = 'https://recherche-entreprises.api.gouv.fr/search'
PER_PAGE = 25
SLEEP_BETWEEN_REQUESTS = 0.4
SLEEP_BETWEEN_SEARCHES = 1.2  # entre chaque recherche DDG
MAX_RETRIES = 3

EFFECTIF_MAP = {
    'NN': '0 salarié',
    '00': '0 salarié',
    '01': '1-2 salariés',
    '02': '3-5 salariés',
    '03': '6-9 salariés',
    '11': '10-19 salariés',
    '12': '20-49 salariés',
    '21': '50-99 salariés',
}

# Domaines d'annuaires à exclure des résultats de recherche
DIRECTORY_DOMAINS = {
    'societe.com', 'pappers.fr', 'infogreffe.fr', 'verif.com',
    'kompass.com', 'manageo.fr', 'companywall.fr', 'sirene.fr',
    'bodacc.fr', 'annuaire-entreprises.data.gouv.fr', 'data.gouv.fr',
    'linkedin.com', 'facebook.com', 'instagram.com', 'twitter.com',
    'pagesjaunes.fr', 'google.com', 'bing.com', 'duckduckgo.com',
    'youtube.com', 'lafourchette.com', 'tripadvisor.fr',
    'entreprises.gouv.fr', 'cci.fr', 'bpifrance.fr',
    'indeed.com', 'glassdoor.com', 'leboncoin.fr',
}

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(message)s',
    datefmt='%H:%M:%S',
)
log = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description='Extraction prospects BTP')
    parser.add_argument('--max-results', type=int, default=MAX_RESULTS)
    parser.add_argument('--departements', type=str, default='',
                        help='Codes département séparés par virgule, ex: 75,69,13')
    parser.add_argument('--only-with-website', type=str, default=str(ONLY_WITH_WEBSITE),
                        help='true ou false')
    parser.add_argument('--search-websites', type=str, default=str(SEARCH_WEBSITES),
                        help='Chercher les sites web via DuckDuckGo (true/false)')
    return parser.parse_args()


def api_get(params: dict) -> dict | None:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(API_BASE, params=params, timeout=15)
            if r.status_code == 200:
                return r.json()
            log.warning('API %s — tentative %d/%d', r.status_code, attempt, MAX_RETRIES)
        except requests.RequestException as exc:
            log.warning('Erreur réseau : %s — tentative %d/%d', exc, attempt, MAX_RETRIES)
        time.sleep(attempt * 1.5)
    return None


def is_directory_url(url: str) -> bool:
    try:
        domain = urlparse(url).netloc.lower().replace('www.', '')
        return any(d in domain for d in DIRECTORY_DOMAINS)
    except Exception:
        return True


def search_website_ddg(company_name: str, city: str) -> str:
    try:
        from duckduckgo_search import DDGS
        query = f'"{company_name}" {city}'
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
        for r in results:
            url = r.get('href', '')
            if url and not is_directory_url(url):
                return url
    except Exception as e:
        log.debug('Recherche DDG échouée pour %s : %s', company_name, e)
    return ''


def find_website_in_api(result: dict) -> str:
    siege = result.get('siege') or {}
    candidates = [
        result.get('site_internet'),
        result.get('url'),
        siege.get('site_internet'),
        siege.get('url'),
    ]
    for c in candidates:
        if isinstance(c, str) and c.strip():
            return c.strip()
    return ''


def build_address(siege: dict) -> str:
    parts = [
        siege.get('numero_voie', ''),
        siege.get('type_voie', ''),
        siege.get('libelle_voie', ''),
        siege.get('code_postal', ''),
        siege.get('libelle_commune', ''),
    ]
    return ' '.join(p for p in parts if p).strip()


def get_dirigeant(result: dict) -> str:
    dirigeants = result.get('dirigeants') or []
    if not dirigeants:
        return ''
    # Chercher un dirigeant personne physique en priorité
    for d in dirigeants:
        if d.get('type_dirigeant') == 'personne physique':
            prenom = d.get('prenoms', '') or d.get('prenom', '') or ''
            nom = d.get('nom', '') or ''
            full = f'{prenom} {nom}'.strip()
            if full:
                return full
    return ''


def extract_prospect(result: dict) -> dict:
    siege = result.get('siege') or {}
    tranche = siege.get('tranche_effectif_salarie') or result.get('tranche_effectif_salarie') or ''
    return {
        'Nom entreprise': result.get('nom_complet') or result.get('nom_raison_sociale') or '',
        'SIRET': siege.get('siret', ''),
        'Code NAF': siege.get('activite_principale', ''),
        'Dirigeant': get_dirigeant(result),
        'Adresse': build_address(siege),
        'Ville': siege.get('libelle_commune', ''),
        'Département': siege.get('departement', ''),
        'Effectif': EFFECTIF_MAP.get(tranche, tranche),
        'Site web': find_website_in_api(result),
        '_raw': result,  # temporaire pour la recherche DDG
    }


def fetch_naf(naf: str, departements: list[str], tranches: list[str],
              max_results: int, only_website: bool) -> list[dict]:
    prospects = []
    page = 1

    while len(prospects) < max_results:
        params = {
            'activite_principale': naf,
            'per_page': PER_PAGE,
            'page': page,
            'etat_administratif': 'A',
        }
        if departements:
            params['departement'] = ','.join(departements)

        data = api_get(params)
        time.sleep(SLEEP_BETWEEN_REQUESTS)

        if data is None:
            log.error('[NAF %s] Échec API à la page %d — abandon', naf, page)
            break

        results = data.get('results') or []
        if not results:
            break

        for r in results:
            siege = r.get('siege') or {}
            tranche = siege.get('tranche_effectif_salarie') or r.get('tranche_effectif_salarie') or ''
            if tranches and tranche not in tranches:
                continue

            prospect = extract_prospect(r)

            if only_website and not prospect['Site web']:
                continue

            prospects.append(prospect)
            if len(prospects) >= max_results:
                break

        total_pages = data.get('total_pages') or 1
        log.info('[NAF %s] Page %d/%d — %d prospects trouvés jusqu\'ici',
                 naf, page, total_pages, len(prospects))

        if page >= total_pages:
            break
        page += 1

    return prospects


def enrich_websites(prospects: list[dict]) -> list[dict]:
    total = len(prospects)
    log.info('=== Recherche des sites web pour %d entreprises ===', total)
    for i, p in enumerate(prospects, 1):
        if p['Site web']:
            log.info('[Web %d/%d] %s — déjà présent', i, total, p['Nom entreprise'])
            continue
        log.info('[Web %d/%d] Recherche : %s (%s)', i, total, p['Nom entreprise'], p['Ville'])
        website = search_website_ddg(p['Nom entreprise'], p['Ville'])
        p['Site web'] = website
        if website:
            log.info('[Web %d/%d] Trouvé : %s', i, total, website)
        time.sleep(SLEEP_BETWEEN_SEARCHES)
    return prospects


def main():
    args = parse_args()

    only_website = args.only_with_website.lower() not in ('false', '0', 'no')
    search_websites = args.search_websites.lower() not in ('false', '0', 'no')
    departements = [d.strip() for d in args.departements.split(',') if d.strip()] or DEPARTEMENTS
    max_results = args.max_results

    log.info('=== Extraction BTP démarrée ===')
    log.info('NAF : %s', NAF_CODES)
    log.info('Départements : %s', departements or 'France entière')
    log.info('Max résultats : %d', max_results)
    log.info('Effectifs ciblés : %s', TRANCHES_EFFECTIF)
    log.info('Recherche sites web : %s', search_websites)

    all_prospects: list[dict] = []
    seen_sirets: set[str] = set()

    for naf in NAF_CODES:
        if len(all_prospects) >= max_results:
            break
        remaining = max_results - len(all_prospects)
        naf_prospects = fetch_naf(naf, departements, TRANCHES_EFFECTIF, remaining, only_website)

        for p in naf_prospects:
            siret = p['SIRET']
            if siret and siret in seen_sirets:
                continue
            if siret:
                seen_sirets.add(siret)
            all_prospects.append(p)
            if len(all_prospects) >= max_results:
                break

        log.info('[NAF %s] Terminé — total cumulé : %d', naf, len(all_prospects))

    if search_websites and all_prospects:
        all_prospects = enrich_websites(all_prospects)

    # Retirer le champ temporaire _raw
    for p in all_prospects:
        p.pop('_raw', None)

    filename = f'prospects_btp_{date.today().isoformat()}.csv'
    fieldnames = ['Nom entreprise', 'SIRET', 'Code NAF', 'Dirigeant',
                  'Adresse', 'Ville', 'Département', 'Effectif', 'Site web']

    with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_prospects)

    with_website = sum(1 for p in all_prospects if p.get('Site web'))
    log.info('=== Extraction terminée : %d prospects (%d avec site web) → %s ===',
             len(all_prospects), with_website, filename)


if __name__ == '__main__':
    main()
