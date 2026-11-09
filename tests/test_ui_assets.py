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
