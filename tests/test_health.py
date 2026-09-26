def test_health_returns_ok(client, app):
    response = client.get('/health')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'ok'
    assert 'checks' in data
    assert data['checks']['database'] == 'ok'
    assert 'scheduler' in data['checks']
    assert 'icons_writable' in data['checks']


def test_health_json_format(client, app):
    response = client.get('/health')
    assert response.content_type.startswith('application/json')
    data = response.get_json()
    assert 'status' in data
    assert 'checks' in data


def test_csp_header(client, app):
    """CSP header is present on HTML responses with a valid nonce."""
    response = client.get('/')
    assert response.status_code == 200
    csp = response.headers.get('Content-Security-Policy')
    assert csp is not None
    assert "script-src 'self' 'nonce-" in csp
    assert "default-src 'self'" in csp
    assert "style-src 'self' 'unsafe-inline'" in csp
    assert "frame-ancestors 'none'" in csp


def test_csp_not_on_json(client, app):
    """CSP header should not appear on JSON responses."""
    response = client.get('/health')
    csp = response.headers.get('Content-Security-Policy')
    assert csp is None


def test_security_headers_everywhere(client, app):
    for path in ('/', '/health'):
        response = client.get(path)
        assert response.headers.get('X-Content-Type-Options') == 'nosniff'
        assert response.headers.get('Referrer-Policy') == 'same-origin'


def test_redirect_back_ignores_foreign_referrer(client, app, make_user):
    with app.app_context():
        user = make_user()
        response = client.post(f'/user/{user.id}/toggle-active',
                               headers={'Referer': 'https://evil.example/phish'})
        assert response.status_code == 302
        assert 'evil.example' not in response.headers['Location']
        response = client.post(f'/user/{user.id}/toggle-active',
                               headers={'Referer': 'http://localhost/user/1'})
        assert response.headers['Location'] == 'http://localhost/user/1'
