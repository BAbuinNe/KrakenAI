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
    assert 'prefers-reduced-motion: reduce' in src
    assert 'pointermove' in src
    assert 'getBoundingClientRect' in src
    assert "addEventListener('click'" in src
    assert 'kraken:state' in src
    assert 'data:video/mp4;base64,' not in src
    assert 'kraken-wave-smooth-alpha.webm' in src
    assert 'kraken-idle-smooth-alpha.webm' in src
    assert 'video.playsInline=true' in src
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

def test_rendered_kraken_animation_assets():
    src=(STATIC/'mascot.js').read_text(encoding='utf-8')
    css=(STATIC/'styles.css').read_text(encoding='utf-8')
    # Preserve render assets as reference while the live implementation uses MP4.
    assert (STATIC/'kraken-idle.webp').read_bytes().startswith(b'RIFF')
    assert (STATIC/'kraken-wave.webp').read_bytes().startswith(b'RIFF')
    assert src.count('data:video/mp4;base64,') == 0
    assert (STATIC/'kraken-idle-smooth-alpha.webm').read_bytes().startswith(b'\x1a\x45\xdf\xa3')
    assert (STATIC/'kraken-wave-smooth-alpha.webm').read_bytes().startswith(b'\x1a\x45\xdf\xa3')
    assert (STATIC/'kraken-idle-poster.webp').read_bytes().startswith(b'RIFF')
    assert "btn.addEventListener('click',()=>playWave(btn))" in src
    assert 'pointermove' in src
    assert 'kr-mascot-video' in css
    assert 'prefers-reduced-motion: reduce' in src


def test_theme_circular_reveal_and_transparent_mascot():
    script=(STATIC/'app.js').read_text(encoding='utf-8')
    css=(STATIC/'styles.css').read_text(encoding='utf-8')
    assert 'document.startViewTransition' in script
    assert "clipPath:" in script and 'circle(0px at' in script
    assert "transitionTheme(event.currentTarget)" in script
    assert "transitionTheme($('themeButton'))" in script
    assert '@media(prefers-reduced-motion:reduce)' in css
    assert '::view-transition-new(root)' in css
    assert ':root[data-theme=dark] .kr-mascot-button{background:transparent!important' in css
    assert 'kr-mascot-video' in css


def test_kraken_first_visit_analysis_questions_and_thinking_animation():
    script=(STATIC/'app.js').read_text(encoding='utf-8')
    styles=(STATIC/'styles.css').read_text(encoding='utf-8')
    mascot=(STATIC/'mascot.js').read_text(encoding='utf-8')
    assert 'function showFirstVisitGuide()' in script
    assert 'kraken_welcome_guide_v2' in script
    assert 'function renderAnalysisQuestions()' in script
    assert 'state.analysisId' in script
    assert 'analysis_id:state.analysisId' in script
    assert 'className=\\'kr-thinking-indicator\\'' in script
    assert "if(!started){placeholder.replaceChildren();started=true;}" in script
    assert 'kr-thinking-mode' in mascot
    assert 'kr-curl' in styles
    assert '@media(prefers-reduced-motion:reduce)' in styles
