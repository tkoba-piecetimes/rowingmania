import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'pipeline'))
import generate_site as g
import json

FIX=ROOT/'tests'/'fixtures'
TERMS=json.loads((FIX/'glossary.json').read_text(encoding='utf8'))['terms']

def md(text,rel='../../',article='t'):
    with patch.object(g,'DIAGRAMS',FIX/'diagrams'):
        return g.md_to_html(text,rel,article)

def gl(html):
    with patch.object(g,'DIAGRAMS',FIX/'diagrams'):
        return g.apply_glossary(html,TERMS,'../../',article='t')

class Diagram(unittest.TestCase):
    def test_figure(self):
        h=md('![スクラムの並び](diagram:test-fig)')
        self.assertIn('<figure class="diagram"><img src="../../assets/diagrams/test-fig.svg" alt="スクラムの並び" loading="lazy" width="640" height="400"><figcaption>スクラムの並び</figcaption></figure>',h)
    def test_missing_slug_fails(self):
        with self.assertRaises(ValueError) as cm:
            md('![x](diagram:nothing-here)',article='my-article')
        self.assertIn('nothing-here',str(cm.exception)); self.assertIn('my-article',str(cm.exception))
    def test_other_image_not_converted(self):
        self.assertNotIn('<figure',md('![x](https://example.com/a.png)'))

class Glossary(unittest.TestCase):
    def test_first_occurrence_only(self):
        h=gl('<p>バインドが大切。バインドを確認。</p>')
        self.assertEqual(h.count('class="term"'),1)
        self.assertIn('data-term="bind"',h); self.assertIn('role="tooltip"',h)
        self.assertIn('src="../../assets/diagrams/test-fig.svg"',h)
    def test_alias_shares_first_use(self):
        h=gl('<p>バインディングとバインド</p>')
        self.assertEqual(h.count('class="term"'),1)
    def test_not_in_svg(self):
        self.assertNotIn('class="term"',gl('<figure><svg><text>バインド</text></svg></figure>'))
    def test_not_in_heading_link_th_or_attr(self):
        h=gl('<h2>バインド</h2><h3>バインド</h3><p><a href="/バインド">バインド</a></p><table><tr><th>バインド</th></tr></table>')
        self.assertNotIn('class="term"',h)
        h=gl('<h2>バインド</h2><p>バインドです</p><li>バインド</li>')
        self.assertEqual(h.count('class="term"'),1)
        self.assertIn('<h2>バインド</h2>',h)
    def test_katakana_boundary(self):
        self.assertNotIn('class="term"',gl('<p>ブロックを崩す。ロックンロール</p>'))
        self.assertIn('data-term="lock"',gl('<p>ロックは2列目。</p>'))
        self.assertIn('data-term="lock"',gl('<p>の、ロックが</p>'))
    def test_nakaguro_is_boundary(self):
        self.assertIn('data-term="lock"',gl('<p>プロップ・ロックの順</p>'))
    def test_longest_form_wins_and_no_nesting(self):
        h=gl('<p>バインディングのスクラム</p>')
        self.assertEqual(h.count('class="term"'),2)
    def test_max_terms(self):
        with patch.object(g,'DIAGRAMS',FIX/'diagrams'):
            h=g.apply_glossary('<p>バインド ロック スクラム</p>',TERMS,'',max_terms=2)
        self.assertEqual(h.count('class="term"'),2)
    def test_no_terms_noop(self):
        self.assertEqual(g.apply_glossary('<p>バインド</p>',None),'<p>バインド</p>')

class BuildArticle(unittest.TestCase):
    def _build(self,article,terms=TERMS):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            site=Path(d)
            captured={}
            def fake_write(path,html):captured[path]=html
            from contextlib import ExitStack
            with ExitStack() as st:
                st.enter_context(patch.object(g,'DIAGRAMS',FIX/'diagrams'))
                st.enter_context(patch.object(g,'SITE',site))
                st.enter_context(patch.object(g,'write_page',fake_write))
                st.enter_context(patch.object(g,'load_glossary_terms',lambda:terms))
                st.enter_context(patch.object(g,'page',lambda rel,title,body,meta,**k:body))
                for name in ('cta_band','article_cta_band','build_article_cta_band','intern_cta_band'):
                    if hasattr(g,name): st.enter_context(patch.object(g,name,lambda *a,**k:''))
                if hasattr(g,'sticky_bar'): st.enter_context(patch.object(g,'sticky_bar',lambda:''))
                g.build_articles([article],{})
            return captured['articles/'+article['slug']]
    base=dict(slug='a1',title='T',description='d',category='技術',date='2026-10-01',body='バインドの話。')
    def test_level_badge(self):
        self.assertIn('はじめての方向け',self._build({**self.base,'level':'入門'}))
        self.assertNotIn('はじめての方向け',self._build({**self.base,'level':'経験者'}))
        self.assertNotIn('はじめての方向け',self._build(self.base))
    def test_more_link_only_if_glossary_page(self):
        h=self._build(self.base)
        if hasattr(g,'build_glossary'): self.assertIn('href="../../glossary/#term-bind"',h)
        else: self.assertNotIn('glossary/#',h)
    @unittest.skipUnless(hasattr(g,'TERM_TIP_SCRIPT'),'JSは共通assetsで読み込む媒体')
    def test_script_only_with_terms(self):
        self.assertIn('<script>',self._build(self.base))
        self.assertNotIn('<script>',self._build(self.base,terms=None))
    def test_glossary_off_and_missing(self):
        self.assertIn('class="term"',self._build(self.base))
        self.assertNotIn('class="term"',self._build({**self.base,'glossary':'off'}))
        self.assertNotIn('class="term"',self._build(self.base,terms=None))

@unittest.skipUnless(hasattr(g,'build_glossary'),'この媒体に用語辞典ページは無い')
class GlossaryPage(unittest.TestCase):
    def _page(self,terms,old=None):
        import tempfile
        cap={}
        with patch.object(g,'DIAGRAMS',FIX/'diagrams'), patch.object(g,'load_glossary_terms',lambda:terms),              patch.object(g,'ROOT',Path(old) if old else ROOT/'nonexistent'),              patch.object(g,'write_page',lambda p,h:cap.__setitem__(p,h)), patch.object(g,'page',lambda rel,title,body,meta,**k:body):
            g.build_glossary({})
        return cap.get('glossary')
    def test_new_format_anchor_category_diagram(self):
        t=[{**TERMS[0],'category':'技術'},TERMS[1]]
        h=self._page(t)
        self.assertIn('id="term-bind"',h); self.assertIn('<h2>技術</h2>',h); self.assertIn('<h2>用語</h2>',h)
        self.assertIn('assets/diagrams/test-fig.svg',h); self.assertIn('2語',h)
    def test_old_format_fallback(self):
        import tempfile,json as j
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'content').mkdir(); (Path(d)/'content'/'glossary.json').write_text(j.dumps([{'term':'A','category':'C','def':'D'}]),encoding='utf8')
            h=self._page(None,d)
        self.assertIn('<h2>C</h2>',h); self.assertIn('<td>D</td>',h)
    def test_none_no_page(self):
        self.assertIsNone(self._page(None))
    def test_more_link(self):
        h=gl('<p>バインド</p>')
        self.assertNotIn('glossary/#',h)
        with patch.object(g,'DIAGRAMS',FIX/'diagrams'):
            h=g.apply_glossary('<p>バインド</p>',TERMS,'../../',glossary_link=True)
        self.assertIn('href="../../glossary/#term-bind"',h)

if __name__=='__main__':unittest.main()
