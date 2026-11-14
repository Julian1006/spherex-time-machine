"""Which sentences the page can show, so that a translation can be checked against them.

The page is written in English and app/lang/es.json maps each English sentence to Spanish.
Nothing ties the two together except the text itself, so a sentence reworded in the template
would silently fall back to English. keys() reads the template the way the page does and lists
every sentence it can show; check() says which ones the translation lacks and which entries no
longer match anything.

    python build/lang.py            what is missing from, or left over in, app/lang/es.json
    python build/lang.py --keys     every sentence, one per line
"""
import json, re
from html.parser import HTMLParser

ES_PATH = 'app/lang/es.json'


class _Markup(HTMLParser):
    """The text and the spoken labels of the page's own markup, in the order they appear."""
    def __init__(self):
        super().__init__()
        self.found, self.stack = [], []

    def handle_starttag(self, tag, attrs):
        self.stack.append(tag)
        for k, v in attrs:
            if k in ('aria-label', 'title', 'placeholder') and v:
                self.found.append(v)

    def handle_endtag(self, tag):
        if tag in self.stack:
            while self.stack and self.stack.pop() != tag:
                pass

    def handle_data(self, data):
        text = re.sub(r'\s+', ' ', data).strip()
        if text and not (self.stack and self.stack[-1] in ('script', 'style')):
            self.found.append(text)


def keys(template, index):
    """Every sentence the page can show, once each, in a stable order."""
    out = []
    markup = _Markup()
    markup.feed(template[template.index('</style>'):template.index('<script>\n/*__LIVE__*/')])
    out += markup.found
    script = template[template.index('const IDX = '):]
    out += re.findall(r'\bT\(\s*"((?:[^"\\]|\\.)*)"', script)                 # T("…") with the sentence written out
    guide = re.search(r'^const GUIDE = (\[\[.*\]\]);$', script, re.M)        # the ? help: [where, id, sentence]
    out += [g[2] for g in json.loads(guide.group(1))] if guide else []
    for word, label in re.findall(r'\{ word: "([^"]+)",\s+label: "([^"]+)"', script):      # the kinds of pixel flag
        out += [word, label]
    out += re.findall(r'\{name: "([^"]+)", ra:', script)                      # the five test objects
    for t in index['targets']:
        out += [t['name'], t.get('blurb') or '', t.get('moving') or '']
    seen, unique = set(), []
    for k in out:
        if k and re.search(r'[A-Za-z]', k) and k not in seen:                 # "+", "1×", "—" need no translating
            seen.add(k)
            unique.append(k)
    return unique


def check(translation, needed):
    """(sentences with no translation, translations that match no sentence)."""
    have = set(needed)
    return [k for k in needed if k not in translation], [k for k in translation if k not in have]


if __name__ == '__main__':
    import sys
    tpl = open('app/template.html', encoding='utf-8').read()
    idx = json.load(open('data/out/index.json'))
    needed = keys(tpl, idx)
    if '--keys' in sys.argv:
        print('\n'.join(needed))
        raise SystemExit
    try:
        es = json.load(open(ES_PATH, encoding='utf-8'))
    except FileNotFoundError:
        es = {}
    missing, stale = check(es, needed)
    for k in missing:
        print('MISSING  ' + k)
    for k in stale:
        print('STALE    ' + k)
    print('%d sentences, %d translated, %d missing, %d stale' % (len(needed), len(needed) - len(missing), len(missing), len(stale)))
