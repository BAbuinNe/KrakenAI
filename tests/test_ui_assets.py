from pathlib import Path

STATIC=Path(__file__).resolve().parents[1]/'app'/'static'

def test_tentacles_code_is_local_and_accessible():
    html=(STATIC/'index.html').read_text(encoding='utf-8')
    script=(STATIC/'tentacles.js').read_text(encoding='utf-8')
    assert 'id="tentacleCanvas"' in html
    assert 'id="chatPanel"' in html
    assert '/static/tentacles.js' in html
    assert 'prefers-reduced-motion: reduce' in script
    assert 'visibilitychange' in script
    assert 'pointer-events' in (STATIC/'styles.css').read_text(encoding='utf-8')
    assert 'fetch(' not in script
    assert "getContext('webgl')" not in script


def test_first_party_svg_icons():
    from pathlib import Path
    static=Path(__file__).resolve().parents[1]/'app'/'static'
    iconpack=(static/'icons.svg').read_text(encoding='utf-8')
    markup=(static/'index.html').read_text(encoding='utf-8')
    for symbol in ('chat','compare','upload','file-check'):
        assert f'<symbol id="{symbol}"' in iconpack
        assert '/static/icons.svg#'+symbol in markup
    for char in ('▤','◈','↥','≋','＋','↗','ⓘ','◎','♢','🐙','📄'):
        assert char not in markup

def test_weighted_ranking_controls_present():
    app=(STATIC/'app.js').read_text(encoding='utf-8')
    css=(STATIC/'styles.css').read_text(encoding='utf-8')
    assert 'function rankingMarkup' in app
    assert 'function bindRankingControls' in app
    assert "data-ranking-weight" in app
    assert "data-ranking-reliability" in app
    assert "locationLabel(c.requirement_locator)" in app
    assert "encodeURIComponent(rid) + '/ranking'" in app
    assert ".ranking-weights" in css

def test_conversation_ui_has_accessible_streaming_controls():
    markup=(STATIC/'index.html').read_text(encoding='utf-8')
    js=(STATIC/'app.js').read_text(encoding='utf-8')
    icons=(STATIC/'icons.svg').read_text(encoding='utf-8')
    for key in ('conversations','retryButton','stopButton'):
        assert 'id="'+key+'"' in markup
    for fn in ('loadConversations','openConversation','streamConversation','stopGenerating','retryMessage'):
        assert 'function '+fn in js
    assert 'new AbortController()' in js
    assert "'/stream'" in js
    assert 'event:' in js
    for ico in ('edit','refresh','close'):
        assert '<symbol id="'+ico+'"' in icons

def test_safe_markdown_chat_search():
    html=(STATIC/'index.html').read_text(encoding='utf-8')
    app=(STATIC/'app.js').read_text(encoding='utf-8')
    md=(STATIC/'markdown.js').read_text(encoding='utf-8')
    assert 'id="conversationSearch"' in html
    assert '/static/markdown.js' in html
    assert 'filterConversations()' in app
    assert 'KrakenMarkdown?.render' in app
    assert 'innerHTML' not in md
    assert 'createTextNode' in md
    assert 'noopener noreferrer' in md

def test_live_mascot_respects_accessibility():
    src=(STATIC/'mascot.js').read_text(encoding='utf-8')
    assert "prefers-reduced-motion: reduce" in src
    assert 'data-kr-arm' in src
    assert "addEventListener('pointermove'" in src
    assert 'getBoundingClientRect' in src
    assert "addEventListener('click',wave)" in src
    assert 'requestAnimationFrame' in src
    assert 'kr-mascot-button' in src
    assert "kraken:state" in src
    assert "fetch(" not in src

def test_interactive_mascot_integrated_in_chat_and_new_chat():
    html=(STATIC/'index.html').read_text(encoding='utf-8')
    app=(STATIC/'app.js').read_text(encoding='utf-8')
    css=(STATIC/'styles.css').read_text(encoding='utf-8')
    src=(STATIC/'mascot.js').read_text(encoding='utf-8')
    for page in (html,app):
        assert '<div class="mascot-wrap"><svg class="mascot"' in page
    assert "aria-label','Помахать кракену" in src
    assert ".kr-mascot-button:focus-visible" in css
    assert "prefers-reduced-motion: reduce" in src

def test_refined_workspace_controls_are_wired():
    html=(STATIC/'index.html').read_text(encoding='utf-8')
    app=(STATIC/'app.js').read_text(encoding='utf-8')
    for control in ('railUpload','railCompare','railCheck','railReports','profileButton','profileTheme','profileSignout'):
        assert 'id="'+control+'"' in html
        assert "'"+control+"'" in app
    assert 'analysis-rail' in html
    assert "Демо-режим" not in (STATIC/'boot.js').read_text(encoding='utf-8')

def test_tentacle_pointer_attraction_not_blocking_content():
    js=(STATIC/'tentacles.js').read_text(encoding='utf-8')
    css=(STATIC/'styles.css').read_text(encoding='utf-8')
    assert "addEventListener('pointermove'" in js
    assert "cursorSmooth.active" in js
    assert "pointer-events:none" in css
