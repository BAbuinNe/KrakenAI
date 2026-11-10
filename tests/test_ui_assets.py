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
